"""
Python adapter for the C++ Kalman tracker.

Replaces the original ObjectTracker in initial.py while preserving
all metadata fields (measurements, grade_history, last_crop, contour,
command_sent, etc.) that the ZoneProcessor needs.

Key improvements over the original ObjectTracker:
  - C++ Kalman prediction for rotation-robust tracking
  - Dynamic gating instead of fixed max_distance=4000
  - det_index from C++ eliminates fragile post-hoc nearest-distance matching
  - get_robust_size() uses trimmed median instead of max()
  - get_consensus_grade() for majority-vote defect classification
"""

import time
import statistics
import cv2
from collections import Counter

try:
    import cashew_tracker_core
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False


class CppObjectTracker:
    """
    Drop-in replacement for ObjectTracker that delegates position tracking
    and ID association to the C++ CashewTracker, while maintaining the
    Python-side metadata dictionary that ZoneProcessor relies on.
    """

    def __init__(
        self,
        zone_name,
        max_distance=320,
        max_disappeared=8,
        pixel_to_mm_ratio=1.0,
    ):
        if not CPP_AVAILABLE:
            raise ImportError(
                "cashew_tracker_core is not built. Run: "
                "cd cpp_tracker && build.bat"
            )

        self.zone_name = zone_name
        self.pixel_to_mm_ratio = pixel_to_mm_ratio
        self.max_disappeared = max_disappeared
        self.core = cashew_tracker_core.CashewTracker(
            180.0,                  # base_gate_px — minimum position gate
            4000.0,                 # gate_per_sec_px — extra gate allowance per second
            max(float(max_distance), 420.0),  # max_gate_px — hard ceiling
            int(max_disappeared),   # max_missed
            60.0,                   # process_noise
            12.0,                   # measurement_noise
        )
        self.objects = {}
        self.next_id = 1  # kept for compatibility, but C++ manages real IDs
        self.last_timestamp = None

    def update(self, contours, is_good_flags, grades, crops, frame_timestamp=None):
        """
        Update tracked objects with new detections.

        Parameters
        ----------
        contours : list[np.ndarray]
            OpenCV contours for detected cashews.
        is_good_flags : list[bool]
            Whether each detection is considered good quality.
        grades : list[str|None]
            Grade label for each detection (None = good).
        crops : list[np.ndarray]
            Cropped images of each detection.
        frame_timestamp : float, optional
            Timestamp from time.perf_counter(). Auto-generated if missing.

        Returns
        -------
        list[int]
            IDs of objects that have disappeared (exceeded max_missed).
        """
        if frame_timestamp is None:
            frame_timestamp = time.perf_counter()

        # --- Build C++ detection list ---
        detections = []
        valid_indices = []  # Maps detection index → original contour index

        for i, c in enumerate(contours):
            if c is None or len(c) < 3:
                continue

            M = cv2.moments(c)
            if M["m00"] == 0:
                continue

            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

            # Use fitEllipse for rotation-stable size measurement
            if len(c) >= 15:
                ellipse = cv2.fitEllipse(c)
                w, h = ellipse[1]  # (major_axis, minor_axis)
            else:
                rect = cv2.minAreaRect(c)
                w, h = rect[1]
            mm_size = max(w, h) * self.pixel_to_mm_ratio

            d = cashew_tracker_core.Detection()
            d.x = float(cx)
            d.y = float(cy)
            d.size_mm = float(mm_size)

            detections.append(d)
            valid_indices.append(i)

        # --- Run C++ tracker update ---
        tracks = self.core.update(detections, frame_timestamp)

        current_ids = set()

        for tr in tracks:
            obj_id = int(tr.id)
            current_ids.add(obj_id)

            # Use det_index from C++ for reliable detection-to-track mapping
            det_local = int(tr.det_index)

            if det_local >= 0 and det_local < len(valid_indices) and tr.matched:
                # This track was matched to a detection in this frame
                original_i = valid_indices[det_local]

                centroid = (
                    int(round(detections[det_local].x)),
                    int(round(detections[det_local].y)),
                )
                size_mm = float(detections[det_local].size_mm)

                if obj_id not in self.objects:
                    # --- New object ---
                    self.objects[obj_id] = {
                        "centroid": centroid,
                        "prev_centroid": centroid,
                        "curr_time": frame_timestamp,
                        "prev_time": frame_timestamp,
                        "velocity_x": float(tr.vx),
                        "velocity_y": float(tr.vy),
                        "speed_px_s": float(tr.speed_px_s),
                        "predicted_centroid": (
                            float(tr.predicted_x),
                            float(tr.predicted_y),
                        ),
                        "measurements": [size_mm],
                        "max_mm": size_mm,
                        "grade_history": [grades[original_i]],
                        "last_crop": crops[original_i].copy(),
                        "latest_contour": contours[original_i],
                        "is_good": is_good_flags[original_i],
                        "current_grade": grades[original_i],
                        "disappeared_count": 0,
                        "start_time": frame_timestamp,
                        "start_y": centroid[1],
                        "command_sent": False,
                    }
                else:
                    # --- Existing object update ---
                    obj = self.objects[obj_id]

                    old_max = obj["max_mm"]

                    obj["prev_centroid"] = obj["centroid"]
                    obj["prev_time"] = obj["curr_time"]
                    obj["curr_time"] = frame_timestamp
                    obj["centroid"] = centroid

                    obj["velocity_x"] = float(tr.vx)
                    obj["velocity_y"] = float(tr.vy)
                    obj["speed_px_s"] = float(tr.speed_px_s)
                    obj["predicted_centroid"] = (
                        float(tr.predicted_x),
                        float(tr.predicted_y),
                    )

                    obj["measurements"].append(size_mm)

                    # Keep history bounded to avoid unbounded RAM growth
                    if len(obj["measurements"]) > 60:
                        obj["measurements"] = obj["measurements"][-60:]

                    obj["max_mm"] = max(old_max, size_mm)

                    grade = grades[original_i]
                    obj["grade_history"].append(grade)
                    if len(obj["grade_history"]) > 60:
                        obj["grade_history"] = obj["grade_history"][-60:]

                    # Fix: compare against old max BEFORE updating max_mm
                    if size_mm > old_max:
                        obj["last_crop"] = crops[original_i].copy()

                    obj["latest_contour"] = contours[original_i]
                    obj["is_good"] = is_good_flags[original_i]
                    obj["current_grade"] = grade
                    obj["disappeared_count"] = 0

            else:
                # Track exists in C++ but was NOT matched to a detection this frame.
                # Update velocity/prediction from C++ to maintain Kalman state.
                if obj_id in self.objects:
                    obj = self.objects[obj_id]
                    obj["disappeared_count"] = int(tr.missed)
                    obj["velocity_x"] = float(tr.vx)
                    obj["velocity_y"] = float(tr.vy)
                    obj["speed_px_s"] = float(tr.speed_px_s)
                    obj["predicted_centroid"] = (
                        float(tr.predicted_x),
                        float(tr.predicted_y),
                    )

        # --- Collect disappeared IDs ---
        disappeared = []
        for obj_id in list(self.objects.keys()):
            if obj_id not in current_ids:
                # C++ has already deleted this track
                self.objects[obj_id]["disappeared_count"] = max(
                    self.objects[obj_id].get("disappeared_count", 0),
                    self.max_disappeared + 1,
                )
                disappeared.append(obj_id)

        self.last_timestamp = frame_timestamp
        return disappeared

    def get_object_info(self, obj_id):
        """Get the metadata dict for a tracked object."""
        return self.objects.get(obj_id)

    def remove_object(self, obj_id):
        """Remove object from both Python metadata and C++ tracker."""
        self.objects.pop(obj_id, None)
        self.core.remove_track(int(obj_id))

    def reset(self):
        """Clear all tracking state."""
        self.objects.clear()
        self.core.reset()

    # ----------------------------------------------------------------
    # New methods for robust measurement and grade consensus
    # ----------------------------------------------------------------

    def get_robust_size(self, obj_id):
        """
        Return a robust size estimate using trimmed median of last 30 measurements.

        Uses last 30 measurements (most recent/relevant) instead of all history,
        and trims top/bottom 10% before computing median to reject outliers
        from partial contours or rotation spikes.
        """
        obj = self.objects.get(obj_id)
        if obj is None:
            return 0.0

        measurements = obj["measurements"]
        n = len(measurements)

        if n < 3:
            # Too few for statistics — use max as fallback
            return max(measurements) if measurements else 0.0

        # Use last 30 measurements — most recent and relevant
        recent = measurements[-30:] if n > 30 else measurements
        sorted_m = sorted(recent)
        n_recent = len(sorted_m)

        # Trim top and bottom 10%
        trim = max(1, n_recent // 10)
        if trim < n_recent // 2:
            trimmed = sorted_m[trim:-trim]
        else:
            trimmed = sorted_m

        return statistics.median(trimmed)

    def get_consensus_grade(self, obj_id):
        """
        Return the consensus defect grade based on grade history.

        Only returns a defect grade if >40% of frames agree on it AND
        at least 2 frames saw a defect. Otherwise returns None (= good).
        """
        obj = self.objects.get(obj_id)
        if obj is None:
            return None

        history = obj.get("grade_history", [])
        defects = [g for g in history if g is not None]
        total = max(1, len(history))

        if len(defects) / total > 0.40 and len(defects) >= 2:
            return Counter(defects).most_common(1)[0][0]

        return None
