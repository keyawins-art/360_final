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

void CashewTracker::correct(Track& t, double mx, double my, double size_mm) {
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

    // Update running exponential average of size
    if (size_mm > 0.0) {
        if (t.avg_size_mm <= 0.0) {
            t.avg_size_mm = size_mm;
        } else {
            t.avg_size_mm = 0.85 * t.avg_size_mm + 0.15 * size_mm;
        }
    }

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
    // Predict all tracks to current time and store predicted position.
    for (auto& kv : tracks_) {
        Track& t = kv.second;
        const double dt = std::max(0.0, timestamp - t.last_t);
        predict(t, dt);
        t.last_t = timestamp;
        t.matched = false;
        t.det_index = -1;

        // Store pre-correction predicted position for debug/visualization
        t.pred_x = t.x;
        t.pred_y = t.y;
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

            // Size-based association cost:
            // Use relative size difference when track has a size history.
            // This prevents swapping IDs between a large and small cashew.
            double size_penalty = 0.0;
            if (det.size_mm > 0.0 && t.avg_size_mm > 0.0) {
                double size_ratio = det.size_mm / t.avg_size_mm;
                // Penalize if detection is very different in size from track history
                // e.g., ratio=0.5 or ratio=2.0 → large penalty
                double log_ratio = std::log(std::max(size_ratio, 0.01));
                size_penalty = std::min(60.0, std::abs(log_ratio) * 40.0);
            } else if (det.size_mm > 0.0) {
                // No history yet — mild size term
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

        correct(t, det.x, det.y, det.size_mm);

        t.last_meas_t = timestamp;
        t.last_t = timestamp;
        t.det_index = c.det;

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
        t.pred_x = det.x;
        t.pred_y = det.y;
        t.det_index = d;
        t.avg_size_mm = det.size_mm;

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
        o.predicted_x = t.pred_x;
        o.predicted_y = t.pred_y;
        o.speed_px_s = std::sqrt(t.vx * t.vx + t.vy * t.vy);
        o.missed = t.missed;
        o.matched = t.matched;
        o.is_new = (t.hits <= 1);
        o.det_index = t.det_index;
        o.track_size_mm = t.avg_size_mm;

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
