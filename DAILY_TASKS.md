# Daily Tasks Log

## 2026-08-19
- **Segmentation Improvement:** Replaced Otsu thresholding with `CLAHE` (Contrast Limited Adaptive Histogram Equalization) and `Adaptive Thresholding` to make the vision pipeline robust against shadows, LED flickering, and dust on the conveyor.
- **Size Measurement Improvement:** Switched from `minAreaRect` to `fitEllipse` (for contours with 15+ points) to prevent size exaggeration when cashews rotate on the belt.
- **Robust Size Logic:** Modified `get_robust_size` in the trackers to use a trimmed median of the **last 30 measurements** instead of all history, preventing partial exiting contours from dragging down the final size.
- **Documentation:** Created `PROJECT_DOCS.md` and `DAILY_TASKS.md` for better project tracking.
- **GPU Assessment:** Investigated moving the OpenCV pipeline to GPU. Identified that the currently installed OpenCV is CPU-only, and the RTX 5050 (Blackwell) has PyTorch compatibility warnings requiring specific builds.

## 2026-08-21
- **Air Valve Testing Architecture:**
  - Designed and integrated `BELT_PORTS_MAP` in frontend (`frontend/src/App.jsx`) allowing granular, independent port configurations across all 15 belts.
  - Enabled custom port assignment per belt (e.g. Belt 2 using ports `22, 23, 24, 25, 26, 27, 28`).
  - Fixed Air Valve pagination tab controls (Page 1: Belts 1-5, Page 2: Belts 6-10, Page 3: Belts 11-15).
- **Backend Serial & Multi-Controller Routing:**
  - Enhanced `/api/fire-valve` in `backend/server.py` to route commands to appropriate Arduino controller COM files dynamically based on belt groups (Page 1 -> `com_port(a).txt`, Page 2 -> `com_port(b).txt`, Page 3 -> `com_port(c).txt`).
  - Resolved COM port lookup and multi-device connection handling on Windows serial subsystem.
- **Frontend Build & Deployment:**
## 2026-08-22
- **Granular Multi-Grade Ejection Routing (`GRADE_PORT_MAP`):**
  - Replaced flat zone-level command mapping with granular, grade-specific ejection mappings across all 5 zones (`GRADE_PORT_MAP`).
  - Zone 1 configured with: `400` -> `11|`, `320` -> `12|`, `240` -> `13|`, `210` -> `14|`, `180` -> `15|`, `default/defect` -> `16|`.
  - Configured corresponding unique command groups for Zones 2 through 5 (`21-26|`, `31-36|`, `41-46|`, `51-56|`).
  - Enhanced `load_ranges()` to support both colon-separated (`16-29:400`) and comma-separated (`400,16.30,29`) formats with automatic fallback to `wate/value.txt`.
- **Independent Non-Blocking Multi-Zone Delay Timing:**
  - Integrated `ZONE_DELAY_MAP` in `initial.py` and upgraded `EjectionQueue` and `EjectionEvent` to support per-zone independent delay configurations (`delay_seconds`).
  - Guaranteed zero cross-zone timing interference: each zone schedules its ejection event into a thread-safe min-heap priority queue without blocking the camera frame grab loop.
- **NVIDIA RTX 5050 GPU Acceleration for YOLO Defect Detection:**
  - Resolved PyTorch Blackwell architecture (`sm_120`) incompatibility with older `.pt` CUDA kernels by building a high-performance **ONNX Runtime GPU Engine (`CUDAExecutionProvider`)** in `CashewQualityFilter`.
  - Achieved ultra-fast **~9.9ms - 13ms** inference per cashew on the NVIDIA GeForce RTX 5050 GPU (100+ FPS).
  - Integrated real-time defect classification for all 7 classes: `Bad`, `Blackdot`, `Brown`, `Good`, `Multi`, `Oilly`, `Unpill`, routing defects to reject commands and good cashews to grade commands.

## 2026-09-19
- **Model Upgrade to `D:\yolo_cls\360models\19-09-26`:**
  - Upgraded model path in `grading/initial.py` to target new model weights: `D:\yolo_cls\360models\19-09-26\product_detection\weights\best.pt`.
  - Exported optimized high-speed ONNX GPU model (`best.onnx`) with dynamic shapes for NVIDIA RTX 5050 Blackwell CUDA Execution Provider.
  - Synchronized `best.onnx` and `best.pt` to project root directory.
  - Successfully verified ONNX `CUDAExecutionProvider` load and warmup with classes: `{0: 'Bad', 1: 'Blackdot', 2: 'Good'}`.


