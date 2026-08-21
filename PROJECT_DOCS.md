# 360 Cashew Grading System - Project Documentation

## 1. Overview
The **360 Cashew Grading System** is a high-speed, multi-zone machine vision system designed to detect, track, grade, and eject cashews on a moving conveyor belt. It utilizes industrial cameras, OpenCV for image processing, a highly optimized C++ Kalman Filter for tracking, and YOLO (optional) for AI-based defect detection.

## 2. Core Architecture
The system processes a continuous video feed and splits it into **5 independent processing zones**. Each zone acts like its own virtual camera and tracking system.

### 2.1 Hardware Integration
- **Camera:** Hikvision industrial camera (`MvCameraControl`). Connected via GigE or USB3. Frames are grabbed continuously in a background thread to prevent buffer overflow and latency.
- **Ejection System (PLC/Arduino):** A serial connection sends ejection commands (e.g., `11|`, `16|`) based on the grade of the cashew. Timing is handled asynchronously via `EjectionQueue`.

### 2.2 Software Modules
- **`initial.py`**: The main entry point. Handles camera connection, zone definitions, multi-threading (ThreadPoolExecutor) for processing zones, and the main UI loop.
- **`tracker_adapter.py`**: Python bridge to the C++ Kalman tracker. Manages metadata (measurements, crops, grades) while delegating math-heavy tracking to C++.
- **`fallback_tracker.py`**: A pure-Python implementation of the Kalman tracker, used as a fallback if the C++ module is unavailable.
- **`ejection_queue.py`**: Manages delayed ejection commands to the Arduino/PLC, ensuring precise timing for air valves based on belt speed.

## 3. Image Processing Pipeline (Per Zone)
1. **ROI Extraction:** Frame is cropped to the specific zone.
2. **Enhancement:** `CLAHE` (Contrast Limited Adaptive Histogram Equalization) is applied to handle uneven lighting, shadows, or dust on the belt.
3. **Segmentation:** `Adaptive Threshold` and morphological operations (`MORPH_CLOSE`, `MORPH_OPEN`) isolate cashew contours.
4. **Size Measurement:** `cv2.fitEllipse` calculates the major and minor axes for rotation-stable size estimation (in mm).
5. **Tracking Update:** Contours are passed to the Tracker.

## 4. Tracking Algorithm (Kalman Filter)
The system uses a **Constant-Velocity Kalman Filter**:
- Predicts where the cashew will be in the next frame based on velocity.
- Uses dynamic gating (search radius expands based on speed).
- Highly robust against cashew rotation (which changes centroid slightly) and brief occlusions.
- Calculates a "robust size" using a trimmed median of the last 30 measurements.

## 5. Decision & Ejection
1. **Line Crossing:** When a tracked cashew crosses the 95% Y-coordinate of the zone, its final size and grade are evaluated.
2. **Disappearance:** If a cashew is lost near the exit line, it is assumed to have exited and is also evaluated.
3. **Command Queuing:** The final grade maps to a serial command, scheduled for execution after a configurable delay (e.g., 5.5 seconds).

## 6. Air Valve Testing & Multi-Controller Mapping
The UI provides manual testing interfaces for up to 15 belts across 3 distinct pages/controllers:
- **Controller A (`com_port(a).txt`)**: Controls Page 1 (Belts 1 to 5)
- **Controller B (`com_port(b).txt`)**: Controls Page 2 (Belts 6 to 10)
- **Controller C (`com_port(c).txt`)**: Controls Page 3 (Belts 11 to 15)

Each belt has 7 independently configurable air valve ports mapped via `BELT_PORTS_MAP` in the frontend and routed to the corresponding serial COM port via `/api/fire-valve` on the backend.
