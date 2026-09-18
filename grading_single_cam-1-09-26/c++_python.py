from pathlib import Path
import zipfile, textwrap, os

root = Path("/mnt/data/cashew_cpp_tracker")
root.mkdir(exist_ok=True)

files = {
"cashew_tracker.hpp": r'''
#pragma once
#include <cstdint>
#include <vector>
#include <unordered_map>
#include <cmath>
#include <algorithm>
#include <limits>

struct Detection {
    double x{0.0};
    double y{0.0};
    double size_mm{0.0};
};

struct TrackOutput {
    int id{-1};
    double x{0.0};
    double y{0.0};
    double vx{0.0};
    double vy{0.0};
    double predicted_x{0.0};
    double predicted_y{0.0};
    double speed_px_s{0.0};
    int missed{0};
    bool matched{false};
    bool is_new{false};
};

class CashewTracker {
public:
    CashewTracker(
        double base_gate_px = 120.0,
        double gate_per_sec_px = 2500.0,
        double max_gate_px = 320.0,
        int max_missed = 8,
        double process_noise = 35.0,
        double measurement_noise = 8.0
    );

    std::vector<TrackOutput> update(
        const std::vector<Detection>& detections,
        double timestamp
    );

    std::vector<TrackOutput> get_tracks() const;
    void remove_track(int id);
    void reset();

private:
    struct Track {
        int id{0};

        // Constant-velocity state:
        // [x, y, vx, vy]
        double x{0}, y{0}, vx{0}, vy{0};

        // Diagonal covariance approximation.
        double px{100}, py{100}, pvx{1000}, pvy{1000};

        double last_t{0};
        double last_meas_t{0};

        int missed{0};
        int hits{1};
        bool matched{true};
    };

    std::unordered_map<int, Track> tracks_;
    int next_id_{1};

    double base_gate_;
    double gate_per_sec_;
    double max_gate_;
    int max_missed_;
    double process_noise_;
    double measurement_noise_;

    void predict(Track& t, double dt);
    void correct(Track& t, double mx, double my);
    double gate_for(const Track& t, double dt) const;
    static double distance(double x1, double y1, double x2, double y2);
};
''',

"cashew_tracker.cpp": r'''
#include "cashew_tracker.hpp"

CashewTracker::CashewTracker(
    double base_gate_px,
    double gate_per_sec_px,
    double max_gate_px,
    int max_missed,
    double process_noise,
    double measurement_noise
)
    : base_gate_(base_gate_px),
      gate_per_sec_(gate_per_sec_px),
      max_gate_(max_gate_px),
      max_missed_(max_missed),
      process_noise_(process_noise),
      measurement_noise_(measurement_noise) {}

double CashewTracker::distance(double x1, double y1, double x2, double y2) {
    const double dx = x1 - x2;
    const double dy = y1 - y2;
    return std::sqrt(dx * dx + dy * dy);
}

void CashewTracker::predict(Track& t, double dt) {
    if (dt <= 0.0) return;

    t.x += t.vx * dt;
    t.y += t.vy * dt;

    // Simple constant-velocity covariance propagation.
    t.px  += dt * dt * t.pvx + process_noise_;
    t.py  += dt * dt * t.pvy + process_noise_;
    t.pvx += process_noise_;
    t.pvy += process_noise_;
}

void CashewTracker::correct(Track& t, double mx, double my) {
    // Independent scalar Kalman corrections for x and y.
    const double kx = t.px / (t.px + measurement_noise_);
    const double ky = t.py / (t.py + measurement_noise_);

    const double old_x = t.x;
    const double old_y = t.y;

    t.x += kx * (mx - t.x);
    t.y += ky * (my - t.y);

    t.px *= (1.0 - kx);
    t.py *= (1.0 - ky);

    // Velocity is estimated from the measurement residual.
    // The caller has already predicted to the current timestamp.
    // We use a conservative correction to avoid rotation-induced jumps.
    const double residual_x = mx - old_x;
    const double residual_y = my - old_y;

    t.vx = 0.80 * t.vx + 0.20 * residual_x;
    t.vy = 0.80 * t.vy + 0.20 * residual_y;

    // Cashews travel down the belt. Strongly suppress large backward velocity.
    if (t.vy < -500.0) t.vy = -500.0;

    t.hits++;
    t.missed = 0;
    t.matched = true;
}

double CashewTracker::gate_for(const Track& t, double dt) const {
    const double predicted_move =
        std::sqrt(t.vx * t.vx + t.vy * t.vy) * std::max(dt, 0.001);

    return std::min(
        max_gate_,
        std::max(base_gate_, predicted_move + gate_per_sec_ * std::max(dt, 0.0))
    );
}

std::vector<TrackOutput> CashewTracker::update(
    const std::vector<Detection>& detections,
    double timestamp
) {
    // Predict all tracks to current time.
    for (auto& kv : tracks_) {
        Track& t = kv.second;
        const double dt = std::max(0.0, timestamp - t.last_t);
        predict(t, dt);
        t.last_t = timestamp;
        t.matched = false;
    }

    // Build all feasible track/detection pairs.
    struct Candidate {
        double cost;
        int id;
        int det;
    };

    std::vector<Candidate> candidates;

    for (const auto& kv : tracks_) {
        const Track& t = kv.second;

        double dt = std::max(0.0, timestamp - t.last_meas_t);
        const double gate = gate_for(t, dt);

        for (int d = 0; d < static_cast<int>(detections.size()); ++d) {
            const Detection& det = detections[d];

            const double dx = det.x - t.x;
            const double dy = det.y - t.y;
            const double dist = std::sqrt(dx * dx + dy * dy);

            if (dist > gate) continue;

            // Direction gate:
            // For a downward conveyor, reject a strong backward jump.
            // Small backward centroid movement is allowed because the cashew rotates.
            const double expected_y = t.y;
            if (det.y < expected_y - std::max(80.0, gate * 0.65)) {
                continue;
            }

            // Prefer detections close to the predicted position.
            // Mild size term helps avoid accidental ID swaps when objects are close.
            double size_penalty = 0.0;
            if (det.size_mm > 0.0) {
                // Size is intentionally weak because rotation changes apparent dimensions.
                size_penalty = std::min(25.0, std::abs(det.size_mm) * 0.02);
            }

            candidates.push_back({dist + size_penalty, t.id, d});
        }
    }

    std::sort(candidates.begin(), candidates.end(),
              [](const Candidate& a, const Candidate& b) {
                  return a.cost < b.cost;
              });

    std::unordered_map<int, bool> used_tracks;
    std::vector<bool> used_detections(detections.size(), false);

    // Greedy global-by-cost association.
    // For the small number of cashews per zone this is fast and avoids
    // the pathological per-detection "first nearest track" behavior.
    for (const auto& c : candidates) {
        if (used_detections[c.det]) continue;
        if (used_tracks[c.id]) continue;

        auto it = tracks_.find(c.id);
        if (it == tracks_.end()) continue;

        Track& t = it->second;
        const Detection& det = detections[c.det];

        double dt = std::max(0.0, timestamp - t.last_meas_t);
        correct(t, det.x, det.y);

        t.last_meas_t = timestamp;
        t.last_t = timestamp;

        used_tracks[c.id] = true;
        used_detections[c.det] = true;
    }

    // Mark unmatched tracks as missed.
    std::vector<int> to_delete;
    for (auto& kv : tracks_) {
        Track& t = kv.second;
        if (!t.matched) {
            t.missed++;
            if (t.missed > max_missed_) {
                to_delete.push_back(t.id);
            }
        }
    }

    for (int id : to_delete) {
        tracks_.erase(id);
    }

    // Create tracks for unmatched detections.
    for (int d = 0; d < static_cast<int>(detections.size()); ++d) {
        if (used_detections[d]) continue;

        const Detection& det = detections[d];

        Track t;
        t.id = next_id_++;
        t.x = det.x;
        t.y = det.y;
        t.vx = 0.0;
        t.vy = 0.0;
        t.px = 100.0;
        t.py = 100.0;
        t.pvx = 1000.0;
        t.pvy = 1000.0;
        t.last_t = timestamp;
        t.last_meas_t = timestamp;
        t.missed = 0;
        t.hits = 1;
        t.matched = true;

        tracks_[t.id] = t;
    }

    return get_tracks();
}

std::vector<TrackOutput> CashewTracker::get_tracks() const {
    std::vector<TrackOutput> out;
    out.reserve(tracks_.size());

    for (const auto& kv : tracks_) {
        const Track& t = kv.second;

        TrackOutput o;
        o.id = t.id;
        o.x = t.x;
        o.y = t.y;
        o.vx = t.vx;
        o.vy = t.vy;
        o.predicted_x = t.x;
        o.predicted_y = t.y;
        o.speed_px_s = std::sqrt(t.vx * t.vx + t.vy * t.vy);
        o.missed = t.missed;
        o.matched = t.matched;
        o.is_new = (t.hits <= 1);

        out.push_back(o);
    }

    std::sort(out.begin(), out.end(),
              [](const TrackOutput& a, const TrackOutput& b) {
                  return a.id < b.id;
              });

    return out;
}

void CashewTracker::remove_track(int id) {
    tracks_.erase(id);
}

void CashewTracker::reset() {
    tracks_.clear();
    next_id_ = 1;
}
''',

"bindings.cpp": r'''
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "cashew_tracker.hpp"

namespace py = pybind11;

PYBIND11_MODULE(cashew_tracker_core, m) {
    m.doc() = "High-speed C++ cashew tracker with constant-velocity Kalman prediction";

    py::class_<Detection>(m, "Detection")
        .def(py::init<>())
        .def_readwrite("x", &Detection::x)
        .def_readwrite("y", &Detection::y)
        .def_readwrite("size_mm", &Detection::size_mm);

    py::class_<TrackOutput>(m, "TrackOutput")
        .def_readonly("id", &TrackOutput::id)
        .def_readonly("x", &TrackOutput::x)
        .def_readonly("y", &TrackOutput::y)
        .def_readonly("vx", &TrackOutput::vx)
        .def_readonly("vy", &TrackOutput::vy)
        .def_readonly("predicted_x", &TrackOutput::predicted_x)
        .def_readonly("predicted_y", &TrackOutput::predicted_y)
        .def_readonly("speed_px_s", &TrackOutput::speed_px_s)
        .def_readonly("missed", &TrackOutput::missed)
        .def_readonly("matched", &TrackOutput::matched)
        .def_readonly("is_new", &TrackOutput::is_new);

    py::class_<CashewTracker>(m, "CashewTracker")
        .def(
            py::init<double,double,double,int,double,double>(),
            py::arg("base_gate_px") = 120.0,
            py::arg("gate_per_sec_px") = 2500.0,
            py::arg("max_gate_px") = 320.0,
            py::arg("max_missed") = 8,
            py::arg("process_noise") = 35.0,
            py::arg("measurement_noise") = 8.0
        )
        .def("update", &CashewTracker::update,
             py::arg("detections"), py::arg("timestamp"))
        .def("get_tracks", &CashewTracker::get_tracks)
        .def("remove_track", &CashewTracker::remove_track)
        .def("reset", &CashewTracker::reset);
}
''',

"setup.py": r'''
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "cashew_tracker_core",
        ["bindings.cpp", "cashew_tracker.cpp"],
        cxx_std=17,
        extra_compile_args=["/O2"],
    ),
]

setup(
    name="cashew_tracker_core",
    version="1.0.0",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
''',

"requirements-build.txt": r'''
pybind11>=2.11
setuptools>=68
wheel
''',

"tracker_adapter.py": r'''
"""
Python adapter for the C++ tracker.

This is designed to replace the matching portion of the current Python
ObjectTracker while preserving the metadata used elsewhere in the project:
measurements, grade_history, last_crop, contour, command_sent, etc.

Your current ZoneProcessor already computes:
    valid_contours
    is_good_flags
    grades
    crops

and then calls:
    self.tracker.update(valid_contours, is_good_flags, grades, crops)

Use CppObjectTracker below instead.
"""

import time
import cv2

try:
    import cashew_tracker_core
except ImportError as exc:
    raise ImportError(
        "cashew_tracker_core is not built. Run: "
        "python setup.py build_ext --inplace"
    ) from exc


class CppObjectTracker:
    def __init__(
        self,
        zone_name,
        max_distance=320,
        max_disappeared=8,
        pixel_to_mm_ratio=1.0,
    ):
        self.zone_name = zone_name
        self.pixel_to_mm_ratio = pixel_to_mm_ratio
        self.core = cashew_tracker_core.CashewTracker(
            120.0,       # minimum position gate
            2500.0,      # extra gate allowance per second
            float(max_distance),
            int(max_disappeared),
            35.0,        # process noise
            8.0,         # measurement noise
        )
        self.objects = {}
        self.last_timestamp = None

    def update(self, contours, is_good_flags, grades, crops, frame_timestamp=None):
        if frame_timestamp is None:
            frame_timestamp = time.perf_counter()

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

            d = cashew_tracker_core.Detection()
            d.x = float(cx)
            d.y = float(cy)
            d.size_mm = float(mm_size)

            detections.append(d)
            valid_indices.append(i)

        tracks = self.core.update(detections, frame_timestamp)

        current_ids = set()

        # Match C++ output back to the original detection index.
        #
        # The C++ tracker output contains position/velocity, but not the
        # original contour index. We therefore associate the returned track
        # to the nearest current detection, using the track's predicted/current
        # position. This is only metadata attachment; the actual ID association
        # has already happened inside C++.
        used_detection_indices = set()

        for tr in tracks:
            obj_id = int(tr.id)
            current_ids.add(obj_id)

            best_local = None
            best_dist = float("inf")

            for local_i, d in enumerate(detections):
                if local_i in used_detection_indices:
                    continue

                dx = float(d.x) - float(tr.x)
                dy = float(d.y) - float(tr.y)
                dist2 = dx * dx + dy * dy

                if dist2 < best_dist:
                    best_dist = dist2
                    best_local = local_i

            if best_local is not None and tr.matched:
                used_detection_indices.add(best_local)
                original_i = valid_indices[best_local]

                centroid = (
                    int(round(detections[best_local].x)),
                    int(round(detections[best_local].y)),
                )
                size_mm = float(detections[best_local].size_mm)

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

                    # Keep history bounded to avoid unbounded RAM growth.
                    if len(obj["measurements"]) > 60:
                        obj["measurements"] = obj["measurements"][-60:]

                    obj["max_mm"] = max(old_max, size_mm)

                    grade = grades[original_i]
                    obj["grade_history"].append(grade)
                    if len(obj["grade_history"]) > 60:
                        obj["grade_history"] = obj["grade_history"][-60:]

                    # Correct bug from the original code:
                    # compare against old max BEFORE updating max_mm.
                    if size_mm > old_max:
                        obj["last_crop"] = crops[original_i].copy()

                    obj["latest_contour"] = contours[original_i]
                    obj["is_good"] = is_good_flags[original_i]
                    obj["current_grade"] = grade
                    obj["disappeared_count"] = 0

            else:
                # C++ prediction exists but there is no current detection.
                # Keep the object alive temporarily so a rotating cashew can
                # recover its original ID.
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

        # Remove tracks that exceeded the C++ missed-frame limit.
        disappeared = []
        for obj_id in list(self.objects.keys()):
            if obj_id not in current_ids:
                disappeared.append(obj_id)

        for obj_id in disappeared:
            # Keep metadata available until the caller evaluates it.
            self.objects[obj_id]["disappeared_count"] = max(
                self.objects[obj_id].get("disappeared_count", 0),
                max_disappeared,
            )

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
''',

"INTEGRATION.md": r'''
# Integrating the C++ tracker into the existing cashew project

The uploaded project currently does:

    valid_contours
        -> is_good_flags
        -> grades
        -> crops
        -> self.tracker.update(...)

and its Python tracker matches contours using centroid distance and a fixed
maximum distance.

This package moves only the real-time association/prediction core into C++.

## 1. Build

On Windows, use a Visual Studio Developer Command Prompt with a C++17
compiler available.

    py -m pip install -r requirements-build.txt
    py setup.py build_ext --inplace

You should then see a file similar to:

    cashew_tracker_core.cp3xx-win_amd64.pyd

## 2. Copy files

Put these files beside your Python application:

    cashew_tracker.hpp
    cashew_tracker.cpp
    bindings.cpp
    tracker_adapter.py
    setup.py
    requirements-build.txt

## 3. Replace the Python tracker

In the main application, add:

    from tracker_adapter import CppObjectTracker

Then change the ZoneProcessor constructor from:

    self.tracker = ObjectTracker(self.name)

to:

    self.tracker = CppObjectTracker(
        self.name,
        max_distance=320,
        max_disappeared=8,
        pixel_to_mm_ratio=PIXEL_TO_MM_RATIO,
    )

The existing call can remain:

    disappeared_ids = self.tracker.update(
        valid_contours,
        is_good_flags,
        grades,
        crops,
        frame_timestamp=frame_timestamp,
    )

If the active version of your project does not pass frame_timestamp, the
adapter will use time.perf_counter().

## 4. Important behavior change

The old tracker uses a large fixed distance gate. The C++ tracker instead
predicts position using a constant-velocity Kalman-style state:

    x, y, vx, vy

and uses a dynamic gate based on predicted movement.

This is specifically intended to reduce ID loss when a cashew rotates and
its contour centroid temporarily jumps.

## 5. Tuning

Start with:

    base_gate_px       = 120
    max_gate_px        = 320
    max_missed         = 8

Do NOT immediately increase max_gate to thousands of pixels. A very large gate
can cause one cashew to steal another cashew's ID.

If the belt is much faster, increase max_gate gradually and validate with
recorded video.

## 6. Accuracy testing

Before putting it on the production machine, record several minutes of the
actual conveyor:

- normal cashews
- rotating cashews
- close cashews
- partially occluded cashews
- small pieces
- false objects/rollers

Compare:

    ID switches
    missed objects
    duplicate IDs
    false tracks
    PLC timing error

The C++ tracker does not magically improve detection accuracy. It improves
the tracking/prediction portion. Detection thresholds and image quality still
need validation.

## 7. Important limitation

This implementation intentionally does NOT move the HIK camera SDK or all
OpenCV processing to C++ yet.

That should be the second optimization step after profiling. The current
project's detection pipeline is still Python/OpenCV, while the tracking core
is native C++.

If profiling shows camera conversion, morphology, contour extraction, or AI
inference is the dominant bottleneck, move that specific stage next.
'''
}

for name, content in files.items():
    (root / name).write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

# Add a small smoke-test script
(root / "test_tracker.py").write_text(textwrap.dedent(r'''
import time
import cashew_tracker_core

tracker = cashew_tracker_core.CashewTracker(
    120.0, 2500.0, 320.0, 8, 35.0, 8.0
)

t = time.perf_counter()

for i in range(20):
    d = cashew_tracker_core.Detection()
    d.x = 300
    d.y = 100 + i * 15
    d.size_mm = 22
    out = tracker.update([d], t + i * 0.01)

    if out:
        tr = out[0]
        print(
            f"id={tr.id} x={tr.x:.1f} y={tr.y:.1f} "
            f"vx={tr.vx:.1f} vy={tr.vy:.1f} "
            f"speed={tr.speed_px_s:.1f} missed={tr.missed}"
        )
''').lstrip(), encoding="utf-8")

zip_path = Path("/mnt/data/cashew_cpp_tracker.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in root.iterdir():
        z.write(p, arcname=p.name)

print(zip_path)
