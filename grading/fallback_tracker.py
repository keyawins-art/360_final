"""
Pure-Python fallback tracker with Kalman prediction.

Drop-in replacement for CppObjectTracker when the C++ module is not
available (e.g., no compiler on the production machine).

Implements the same architecture:
  - Constant-velocity Kalman filter per track
  - Dynamic gating based on predicted velocity
  - Global cost-sorted greedy association
  - Direction gate (cashews move downward)
  - Size-based association cost
  - det_index for reliable metadata attachment
  - get_robust_size() and get_consensus_grade()
"""

import time
import math
import statistics
import cv2
from collections import Counter


class _KalmanTrack:
    """Internal per-object Kalman track state."""

    __slots__ = (
        "id", "x", "y", "vx", "vy",
        "px", "py", "pvx", "pvy",
        "last_t", "last_meas_t",
        "missed", "hits", "matched",
        "pred_x", "pred_y", "det_index",
        "avg_size_mm",
    )

    def __init__(self, track_id, x, y, timestamp, size_mm=0.0):
        self.id = track_id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.px = 100.0
        self.py = 100.0
        self.pvx = 1000.0
        self.pvy = 1000.0
        self.last_t = timestamp
        self.last_meas_t = timestamp
        self.missed = 0
        self.hits = 1
        self.matched = True
        self.pred_x = x
        self.pred_y = y
        self.det_index = -1
        self.avg_size_mm = size_mm


class _TrackOutput:
    """Mimics the C++ TrackOutput struct."""

    __slots__ = (
        "id", "x", "y", "vx", "vy",
        "predicted_x", "predicted_y",
        "speed_px_s", "missed", "matched",
        "is_new", "det_index", "track_size_mm",
    )

    def __init__(self):
        self.id = -1
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.predicted_x = 0.0
        self.predicted_y = 0.0
        self.speed_px_s = 0.0
        self.missed = 0
        self.matched = False
        self.is_new = False
        self.det_index = -1
        self.track_size_mm = 0.0


class _PythonKalmanTracker:
    """
    Pure-Python equivalent of the C++ CashewTracker.
    Same algorithm, same parameters, same API.
    """

    def __init__(
        self,
        base_gate_px=120.0,
        gate_per_sec_px=2500.0,
        max_gate_px=320.0,
        max_missed=8,
        process_noise=35.0,
        measurement_noise=8.0,
    ):
        self._base_gate = base_gate_px
        self._gate_per_sec = gate_per_sec_px
        self._max_gate = max_gate_px
        self._max_missed = max_missed
        self._process_noise = process_noise
        self._measurement_noise = measurement_noise
        self._tracks = {}  # id -> _KalmanTrack
        self._next_id = 1

    def _predict(self, t, dt):
        if dt <= 0.0:
            return
        t.x += t.vx * dt
        t.y += t.vy * dt
        t.px += dt * dt * t.pvx + self._process_noise
        t.py += dt * dt * t.pvy + self._process_noise
        t.pvx += self._process_noise
        t.pvy += self._process_noise

    def _correct(self, t, mx, my, size_mm):
        kx = t.px / (t.px + self._measurement_noise)
        ky = t.py / (t.py + self._measurement_noise)

        old_x = t.x
        old_y = t.y

        t.x += kx * (mx - t.x)
        t.y += ky * (my - t.y)

        t.px *= (1.0 - kx)
        t.py *= (1.0 - ky)

        residual_x = mx - old_x
        residual_y = my - old_y

        t.vx = 0.80 * t.vx + 0.20 * residual_x
        t.vy = 0.80 * t.vy + 0.20 * residual_y

        if t.vy < -500.0:
            t.vy = -500.0

        # Update running size average
        if size_mm > 0.0:
            if t.avg_size_mm <= 0.0:
                t.avg_size_mm = size_mm
            else:
                t.avg_size_mm = 0.85 * t.avg_size_mm + 0.15 * size_mm

        t.hits += 1
        t.missed = 0
        t.matched = True

    def _gate_for(self, t, dt):
        speed = math.sqrt(t.vx * t.vx + t.vy * t.vy)
        predicted_move = speed * max(dt, 0.001)
        return min(
            self._max_gate,
            max(self._base_gate, predicted_move + self._gate_per_sec * max(dt, 0.0)),
        )

    def update(self, detections, timestamp):
        """
        Parameters
        ----------
        detections : list of dicts with keys 'x', 'y', 'size_mm'
        timestamp : float

        Returns
        -------
        list[_TrackOutput]
        """
        # Predict all tracks
        for t in self._tracks.values():
            dt = max(0.0, timestamp - t.last_t)
            self._predict(t, dt)
            t.last_t = timestamp
            t.matched = False
            t.det_index = -1
            t.pred_x = t.x
            t.pred_y = t.y

        # Build candidates
        candidates = []
        for t in self._tracks.values():
            dt = max(0.0, timestamp - t.last_meas_t)
            gate = self._gate_for(t, dt)

            for d_idx, det in enumerate(detections):
                dx = det["x"] - t.x
                dy = det["y"] - t.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist > gate:
                    continue

                # Direction gate
                if det["y"] < t.y - max(80.0, gate * 0.65):
                    continue

                # Size penalty
                size_penalty = 0.0
                if det["size_mm"] > 0.0 and t.avg_size_mm > 0.0:
                    ratio = det["size_mm"] / t.avg_size_mm
                    log_ratio = math.log(max(ratio, 0.01))
                    size_penalty = min(60.0, abs(log_ratio) * 40.0)
                elif det["size_mm"] > 0.0:
                    size_penalty = min(25.0, abs(det["size_mm"]) * 0.02)

                candidates.append((dist + size_penalty, t.id, d_idx))

        # Sort by cost
        candidates.sort(key=lambda c: c[0])

        used_tracks = set()
        used_dets = set()

        # Greedy assignment
        for cost, tid, d_idx in candidates:
            if d_idx in used_dets or tid in used_tracks:
                continue
            t = self._tracks.get(tid)
            if t is None:
                continue

            det = detections[d_idx]
            self._correct(t, det["x"], det["y"], det["size_mm"])
            t.last_meas_t = timestamp
            t.last_t = timestamp
            t.det_index = d_idx

            used_tracks.add(tid)
            used_dets.add(d_idx)

        # Handle missed tracks
        to_delete = []
        for t in self._tracks.values():
            if not t.matched:
                t.missed += 1
                if t.missed > self._max_missed:
                    to_delete.append(t.id)

        for tid in to_delete:
            del self._tracks[tid]

        # Create new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx in used_dets:
                continue
            t = _KalmanTrack(self._next_id, det["x"], det["y"], timestamp, det["size_mm"])
            t.det_index = d_idx
            self._tracks[t.id] = t
            self._next_id += 1

        return self._get_outputs()

    def _get_outputs(self):
        outputs = []
        for t in self._tracks.values():
            o = _TrackOutput()
            o.id = t.id
            o.x = t.x
            o.y = t.y
            o.vx = t.vx
            o.vy = t.vy
            o.predicted_x = t.pred_x
            o.predicted_y = t.pred_y
            o.speed_px_s = math.sqrt(t.vx * t.vx + t.vy * t.vy)
            o.missed = t.missed
            o.matched = t.matched
            o.is_new = t.hits <= 1
            o.det_index = t.det_index
            o.track_size_mm = t.avg_size_mm
            outputs.append(o)
        outputs.sort(key=lambda o: o.id)
        return outputs

    def get_tracks(self):
        return self._get_outputs()

    def remove_track(self, track_id):
        self._tracks.pop(track_id, None)

    def reset(self):
        self._tracks.clear()
        self._next_id = 1


class FallbackObjectTracker:
    """
    Drop-in replacement for CppObjectTracker using pure-Python Kalman tracker.
    Same API, same metadata dictionary structure.
    """

    def __init__(
        self,
        zone_name,
        max_distance=320,
        max_disappeared=8,
        pixel_to_mm_ratio=1.0,
    ):
        self.zone_name = zone_name
        self.pixel_to_mm_ratio = pixel_to_mm_ratio
        self.max_disappeared = max_disappeared
        self.core = _PythonKalmanTracker(
            base_gate_px=120.0,
            gate_per_sec_px=2500.0,
            max_gate_px=float(max_distance),
            max_missed=int(max_disappeared),
            process_noise=35.0,
            measurement_noise=8.0,
        )
        self.objects = {}
        self.next_id = 1
        self.last_timestamp = None

    def update(self, contours, is_good_flags, grades, crops, frame_timestamp=None):
        if frame_timestamp is None:
            frame_timestamp = time.perf_counter()

        # Build detection list
        detections = []
        valid_indices = []

        for i, c in enumerate(contours):
            if c is None or len(c) < 3:
                continue

            M = cv2.moments(c)
            if M["m00"] == 0:
                continue

            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

            rect = cv2.minAreaRect(c)
            w, h = rect[1]
            mm_size = max(w, h) * self.pixel_to_mm_ratio

            detections.append({"x": float(cx), "y": float(cy), "size_mm": float(mm_size)})
            valid_indices.append(i)

        # Run tracker
        tracks = self.core.update(detections, frame_timestamp)

        current_ids = set()

        for tr in tracks:
            obj_id = int(tr.id)
            current_ids.add(obj_id)

            det_local = int(tr.det_index)

            if det_local >= 0 and det_local < len(valid_indices) and tr.matched:
                original_i = valid_indices[det_local]

                centroid = (
                    int(round(detections[det_local]["x"])),
                    int(round(detections[det_local]["y"])),
                )
                size_mm = float(detections[det_local]["size_mm"])

                if obj_id not in self.objects:
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
                    if len(obj["measurements"]) > 60:
                        obj["measurements"] = obj["measurements"][-60:]

                    obj["max_mm"] = max(old_max, size_mm)

                    grade = grades[original_i]
                    obj["grade_history"].append(grade)
                    if len(obj["grade_history"]) > 60:
                        obj["grade_history"] = obj["grade_history"][-60:]

                    if size_mm > old_max:
                        obj["last_crop"] = crops[original_i].copy()

                    obj["latest_contour"] = contours[original_i]
                    obj["is_good"] = is_good_flags[original_i]
                    obj["current_grade"] = grade
                    obj["disappeared_count"] = 0

            else:
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

        disappeared = []
        for obj_id in list(self.objects.keys()):
            if obj_id not in current_ids:
                self.objects[obj_id]["disappeared_count"] = max(
                    self.objects[obj_id].get("disappeared_count", 0),
                    self.max_disappeared + 1,
                )
                disappeared.append(obj_id)

        self.last_timestamp = frame_timestamp
        return disappeared

    def get_object_info(self, obj_id):
        return self.objects.get(obj_id)

    def remove_object(self, obj_id):
        self.objects.pop(obj_id, None)
        self.core.remove_track(int(obj_id))

    def reset(self):
        self.objects.clear()
        self.core.reset()

    def get_robust_size(self, obj_id):
        """Trimmed median size estimate, resistant to rotation outliers."""
        obj = self.objects.get(obj_id)
        if obj is None:
            return 0.0

        measurements = obj["measurements"]
        n = len(measurements)
        if n < 3:
            return max(measurements) if measurements else 0.0

        sorted_m = sorted(measurements)
        trim = max(1, n // 10)
        if trim < n // 2:
            trimmed = sorted_m[trim:-trim]
        else:
            trimmed = sorted_m

        return statistics.median(trimmed)

    def get_consensus_grade(self, obj_id):
        """Majority-vote defect grade — returns None if cashew is good."""
        obj = self.objects.get(obj_id)
        if obj is None:
            return None

        history = obj.get("grade_history", [])
        defects = [g for g in history if g is not None]
        total = max(1, len(history))

        if len(defects) / total > 0.40 and len(defects) >= 2:
            return Counter(defects).most_common(1)[0][0]

        return None
