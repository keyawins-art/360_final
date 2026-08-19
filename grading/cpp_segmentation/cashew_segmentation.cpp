#include "cashew_segmentation.hpp"

CashewSegmentation::CashewSegmentation(
    int min_area, double min_density,
    int h_min, int h_max,
    int s_min, int s_max,
    int v_min, int v_max
)
    : min_area_(min_area),
      min_density_(min_density),
      hsv_lower_(h_min, s_min, v_min),
      hsv_upper_(h_max, s_max, v_max)
{
    kernel_e_5_ = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(5, 5));
    kernel_close_9_ = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(9, 9));
}

std::vector<std::vector<cv::Point>> CashewSegmentation::segment_zone(
    const cv::Mat& zone_bgr,
    int zone_x_offset,
    int zone_y_offset
) {
    std::vector<std::vector<cv::Point>> result_contours;
    if (zone_bgr.empty()) return result_contours;

    // 1. Convert to Grayscale FIRST (3x faster than BGR blur)
    cv::Mat gray;
    cv::cvtColor(zone_bgr, gray, cv::COLOR_BGR2GRAY);

    // 2. Single-channel Gaussian Blur
    cv::Mat smooth;
    cv::GaussianBlur(gray, smooth, cv::Size(7, 7), 0);

    // 3. Clean Otsu Thresholding
    cv::Mat mask_raw;
    cv::threshold(smooth, mask_raw, 0, 255, cv::THRESH_BINARY | cv::THRESH_OTSU);

    // 4. Morphological Refinement using pre-allocated kernels
    cv::Mat mask_clean;
    cv::morphologyEx(mask_raw, mask_clean, cv::MORPH_OPEN, kernel_e_5_);
    cv::morphologyEx(mask_clean, mask_clean, cv::MORPH_CLOSE, kernel_close_9_);

    // 5. Edge Smoothing Blur + Threshold
    cv::Mat mask_smooth, mask_final;
    cv::GaussianBlur(mask_clean, mask_smooth, cv::Size(9, 9), 0);
    cv::threshold(mask_smooth, mask_final, 127, 255, cv::THRESH_BINARY);

    // 6. HSV Mask for Density Check
    cv::Mat hsv, hsv_mask;
    cv::cvtColor(zone_bgr, hsv, cv::COLOR_BGR2HSV);
    cv::inRange(hsv, hsv_lower_, hsv_upper_, hsv_mask);

    // 7. Find Contours
    std::vector<std::vector<cv::Point>> cnts;
    cv::findContours(mask_final, cnts, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    // 8. Filter by Area & Density, then apply zone offsets
    for (const auto& c : cnts) {
        double area = cv::contourArea(c);
        if (area < min_area_) continue;

        // Density Check
        cv::Mat c_mask = cv::Mat::zeros(zone_bgr.size(), CV_8UC1);
        std::vector<std::vector<cv::Point>> single_cnt = {c};
        cv::drawContours(c_mask, single_cnt, -1, 255, -1);

        cv::Mat overlap;
        cv::bitwise_and(c_mask, hsv_mask, overlap);
        int cashew_px = cv::countNonZero(overlap);
        int total_px = cv::countNonZero(c_mask);
        double density = static_cast<double>(cashew_px) / std::max(1, total_px);
        if (density < min_density_) continue;

        // Apply zone offsets directly in C++
        std::vector<cv::Point> c_adjusted = c;
        for (auto& pt : c_adjusted) {
            pt.x += zone_x_offset;
            pt.y += zone_y_offset;
        }
        result_contours.push_back(c_adjusted);
    }

    return result_contours;
}
