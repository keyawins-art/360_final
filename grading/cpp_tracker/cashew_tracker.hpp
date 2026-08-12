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
    int det_index{-1};          // Index into the detections vector, or -1 if unmatched
    double track_size_mm{0.0};  // Running average size for this track
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

        // Pre-correction predicted position (for visualization / debug)
        double pred_x{0}, pred_y{0};

        // Matched detection index in the current frame (-1 if unmatched)
        int det_index{-1};

        // Running exponential average of size_mm for size-based matching
        double avg_size_mm{0.0};
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
    void correct(Track& t, double mx, double my, double size_mm);
    double gate_for(const Track& t, double dt) const;
    static double distance(double x1, double y1, double x2, double y2);
};
