#pragma once
#include <vector>
#include <opencv2/opencv.hpp>

struct DetectionResult {
    int x;
    int y;
    int width;
    int height;
    double area;
    double density;
    std::vector<cv::Point> contour;
};

class CashewSegmentation {
public:
    CashewSegmentation(
        int min_area = 3500,
        double min_density = 0.15,
        int h_min = 0, int h_max = 40,
        int s_min = 30, int s_max = 255,
        int v_min = 15, int v_max = 255
    );

    // Fast C++ processing of a zone ROI
    std::vector<std::vector<cv::Point>> segment_zone(
        const cv::Mat& zone_bgr,
        int zone_x_offset,
        int zone_y_offset
    );

private:
    int min_area_;
    double min_density_;
    cv::Scalar hsv_lower_;
    cv::Scalar hsv_upper_;
    cv::Mat kernel_e_5_;
    cv::Mat kernel_close_9_;
};
