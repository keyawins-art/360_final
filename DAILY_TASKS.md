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
  - Compiled and verified production bundle in `frontend/dist` to sync with FastAPI static assets.

