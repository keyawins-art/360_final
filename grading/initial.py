import sys, os, platform
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ctypes import *
import numpy as np
import cv2
import serial
import time
import re
import json
import ast

# Setup CUDA DLL paths for ONNX GPU (NVIDIA RTX 5050 Blackwell sm_120)
try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(_torch_lib):
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(_torch_lib)
        os.environ['PATH'] = _torch_lib + os.pathsep + os.environ['PATH']
except Exception:
    pass

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

import concurrent.futures
import threading
from collections import Counter
import gc
import math
import datetime
import queue

# =========================================================
# TRACKER SELECTION (C++ Kalman → Python Kalman fallback)
# =========================================================
try:
    from tracker_adapter import CppObjectTracker as _TrackerClass, CPP_AVAILABLE
    if not CPP_AVAILABLE:
        raise ImportError("cashew_tracker_core extension not compiled")
    _TRACKER_TYPE = "C++ Kalman"
except ImportError:
    try:
        from fallback_tracker import FallbackObjectTracker as _TrackerClass
        _TRACKER_TYPE = "Python Kalman (fallback)"
    except ImportError:
        _TrackerClass = None
        _TRACKER_TYPE = "Legacy (built-in)"

from ejection_queue import EjectionQueue

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BUNDLE_DIR = BASE_DIR

# Helper to find first existing path from candidates, or fallback to default
def get_existing_path(candidates, default_path):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return default_path

# =========================================================
# CONFIGURATION & FILE PATHS (CAMERA A & CAMERA B)
# =========================================================

# Camera Serial Files
SERIAL_FILE_A = get_existing_path([
    os.path.join(BASE_DIR, "wate", "camera_ref.txt"),
    os.path.join(BASE_DIR, "camera_serial(a).txt"),
    os.path.join(os.path.expanduser("~"), "Desktop", "camera_serial(a).txt"),
    r"C:\Users\i7\Desktop\camera_serial(a).txt",
    r"D:\Keya Work\360\camera_ref.json"
], os.path.join(BASE_DIR, "wate", "camera_ref.txt"))

SERIAL_FILE_B = get_existing_path([
    os.path.join(BASE_DIR, "wate", "camera_ref.txt"),
    os.path.join(BASE_DIR, "camera_serial(b).txt"),
    os.path.join(os.path.expanduser("~"), "Desktop", "camera_serial(b).txt"),
    r"C:\Users\i7\Desktop\camera_serial(b).txt",
    r"D:\Keya Work\360\camera_ref.json"
], os.path.join(BASE_DIR, "wate", "camera_ref.txt"))

# Arduino / PLC Controller COM Port Files
MAIN_COM_FILE_A = get_existing_path([
    os.path.join(BASE_DIR, "wate", "com_port(a).txt"),
    os.path.join(BASE_DIR, "wate", "comport_ref.txt"),
    r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt",
    r"D:\Keya Work\360\wate\com_port(a).txt"
], os.path.join(BASE_DIR, "wate", "com_port(a).txt"))

MAIN_COM_FILE_B = get_existing_path([
    os.path.join(BASE_DIR, "wate", "com_port(b).txt"),
    os.path.join(BASE_DIR, "wate", "comport_ref.txt"),
    r"D:\4_belt_main\4_belt\Test_checkup\com_port(b).txt",
    r"D:\Keya Work\360\wate\com_port(b).txt"
], os.path.join(BASE_DIR, "wate", "com_port(b).txt"))

RANGES_FILE = get_existing_path([
    os.path.join(BASE_DIR, "wate", "value.txt"),
    r"D:\4_belt_main\4_belt\range\value.txt",
    r"D:\Keya Work\360\wate\value.txt"
], os.path.join(BASE_DIR, "wate", "value.txt"))  # Grading ranges file

ZONES_CONFIG_FILE = get_existing_path([
    os.path.join(BASE_DIR, "zones_config.json"),
    os.path.join(BUNDLE_DIR, "zones_config.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zones_config.json")
], os.path.join(BASE_DIR, "zones_config.json"))

DETECTIONS_FOLDER = get_existing_path([
    os.path.join(BASE_DIR, "detections"),
    r"f:\server\360\detections"
], os.path.join(BASE_DIR, "detections"))

# Ensure detections folder exists
if not os.path.exists(DETECTIONS_FOLDER):
    try:
        os.makedirs(DETECTIONS_FOLDER, exist_ok=True)
        print(f"Created detections folder: {DETECTIONS_FOLDER}")
    except Exception:
        pass

# ================= 10 CUSTOM PROCESS ZONES =================
# Camera A: Zone-1 to Zone-5
# Camera B: Zone-6 to Zone-10
DEFAULT_ZONE_CONFIGS = [
    {'zone': (0, 100, 447, 1920), 'name': 'Zone-1'},
    {'zone': (460, 100, 350, 1910), 'name': 'Zone-2'},
    {'zone': (870, 100, 360, 1910), 'name': 'Zone-3'},
    {'zone': (1310, 100, 340, 1910), 'name': 'Zone-4'},
    {'zone': (0, 0, 0, 0), 'name': 'Zone-5'},
    {'zone': (0, 100, 447, 1920), 'name': 'Zone-6'},
    {'zone': (460, 100, 350, 1910), 'name': 'Zone-7'},
    {'zone': (870, 100, 360, 1910), 'name': 'Zone-8'},
    {'zone': (1310, 100, 340, 1910), 'name': 'Zone-9'},
    {'zone': (0, 0, 0, 0), 'name': 'Zone-10'}
]

class AsyncImageSaver:
    """
    Non-blocking background thread for saving detection images to disk.
    Prevents cv2.imwrite disk I/O latency from stalling vision processing threads.
    """
    def __init__(self, max_queue_size=200):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.worker = threading.Thread(target=self._worker_loop, daemon=True, name="AsyncImageSaver")
        self.worker.start()

    def submit(self, crop, obj_id, final_grade, max_mm, tracked_cnt):
        if crop is None or crop.size == 0:
            return
        try:
            cnt_copy = tracked_cnt.copy() if tracked_cnt is not None else None
            self.queue.put_nowait((crop.copy(), obj_id, final_grade, max_mm, cnt_copy))
        except queue.Full:
            pass  # Drop save if queue is full to preserve real-time vision performance

    def _worker_loop(self):
        while True:
            try:
                item = self.queue.get()
                if item is None:
                    break
                crop, obj_id, final_grade, max_mm, tracked_cnt = item
                self._save(crop, obj_id, final_grade, max_mm, tracked_cnt)
                self.queue.task_done()
            except Exception:
                pass

    def _save(self, last_crop, obj_id, final_grade, max_mm, tracked_cnt):
        try:
            save_img = last_crop.copy()
            h_s, w_s = save_img.shape[:2]
            is_defect = final_grade and not any(size in str(final_grade) for size in ['400', '320', '240', '210', '180'])
            color_border = (0, 0, 255) if is_defect else (0, 255, 0)

            x_b, y_b, w_b, h_b = cv2.boundingRect(tracked_cnt) if tracked_cnt is not None else (0, 0, w_s, h_s)
            side = max(w_b, h_b) + 40
            cx_b, cy_b = x_b + w_b // 2, y_b + h_b // 2
            crop_ox = max(0, cx_b - side // 2)
            crop_oy = max(0, cy_b - side // 2)

            contour_drawn = False
            if tracked_cnt is not None and len(tracked_cnt) >= 3:
                local_cnt = tracked_cnt.copy()
                local_cnt[:, 0, 0] -= crop_ox
                local_cnt[:, 0, 1] -= crop_oy
                smooth_cnt = smooth_contour(local_cnt, window=11)
                if len(smooth_cnt) >= 3:
                    cv2.drawContours(save_img, [smooth_cnt], -1, color_border, 2)
                    contour_drawn = True

            if not contour_drawn:
                smooth_s = cv2.GaussianBlur(save_img, (7, 7), 0)
                gray_s = cv2.cvtColor(smooth_s, cv2.COLOR_BGR2GRAY)
                _, mask_s = cv2.threshold(gray_s, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                kernel_e_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                mask_s = cv2.morphologyEx(mask_s, cv2.MORPH_CLOSE, kernel_e_s, iterations=2)
                mask_s = cv2.GaussianBlur(mask_s, (15, 15), 0)
                _, mask_s = cv2.threshold(mask_s, 127, 255, cv2.THRESH_BINARY)
                cnts_s, _ = cv2.findContours(mask_s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts_s:
                    best_cnt = max(cnts_s, key=cv2.contourArea)
                    smooth_cnt_s = smooth_contour(best_cnt, window=11)
                    cv2.drawContours(save_img, [smooth_cnt_s], -1, color_border, 2)
                else:
                    cv2.rectangle(save_img, (0, 0), (w_s - 1, h_s - 1), color_border, 2)

            label_grade = f"{final_grade or 'None'}"
            label_size = f"{max_mm:.1f}mm"
            cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            filename = f"ID{obj_id}_{final_grade}_{int(max_mm)}mm_{int(time.time())}.jpg"
            filepath = os.path.join(DETECTIONS_FOLDER, filename)
            cv2.imwrite(filepath, save_img)
        except Exception:
            pass

ASYNC_IMAGE_SAVER = AsyncImageSaver()

def load_zones_config():
    """Loads zone configuration and ensures all 10 zones (Zone-1 to Zone-10) are present."""
    loaded_configs = []
    if os.path.exists(ZONES_CONFIG_FILE):
        try:
            with open(ZONES_CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                for c in configs:
                    if 'zone' in c and isinstance(c['zone'], list):
                        c['zone'] = tuple(c['zone'])
                    loaded_configs.append(c)
                print(f"Loaded {len(loaded_configs)} zone configurations from {ZONES_CONFIG_FILE}")
        except Exception as e:
            print(f"Error loading zones config: {e}. Using default.")
            loaded_configs = []

    # Merge/Pad with default configs to ensure 10 zones always exist
    final_configs = []
    for i in range(10):
        if i < len(loaded_configs):
            final_configs.append(loaded_configs[i])
        else:
            final_configs.append(DEFAULT_ZONE_CONFIGS[i].copy())
    return final_configs

def save_zones_config(configs):
    try:
        with open(ZONES_CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=4)
        print(f"\n[SAVE] 10-Zone configuration saved to {ZONES_CONFIG_FILE}")
    except Exception as e:
        print(f"\n[SAVE] Error saving zones config: {e}")

ZONE_CONFIGS = load_zones_config()

# === DETECTION SENSITIVITY CONTROL PANEL (LOW & HIGH LIGHT COMPATIBLE) ===
MIN_CASHEW_AREA = 750        # Catches all small, broken, dark/shadowed, and curved cashews while ignoring noise
MIN_MM_SIZE = 6.0            # Minimum measurement to log/act on cashew (catches small broken pieces)
MAX_CASHEW_MM = 70.0         # Allows single cashews and multi-cashew clusters to be tracked
MAX_ASPECT_RATIO = 3.5       # Rejects thin horizontal roller reflections

HSV_LOWER = np.array([0, 5, 5])          # Ultra-wide threshold: catches cashews in deep shadow or dim light
HSV_UPPER = np.array([180, 255, 255])    # Full spectrum upper bound for bright light/highlights

# === AI CLASSIFICATION THRESHOLDS (SEPARATE PER CLASS) ===
THRESH_BLACKDOT = 0.25      # Sensitive threshold for small & large black spots/dots
THRESH_BAD = 0.10           # Threshold for damaged/broken/spotted bad cashews
THRESH_GOOD = 0.75          # Confidence for clean good cashews
YOLO_CONF_THRESHOLD = 0.15  # Global fallback minimum confidence
YOLO_STRICT_BYPASS = 0.80   # Strict good confidence bypass

PIXEL_TO_MM_RATIO = 0.145   # Calibrated mm per pixel ratio
MAX_TRACKING_DISTANCE = 350 # Tracking association distance ceiling
DELAY_SECONDS = 5.50        # Default PLC ejection delay

# =========================================================
# PER-ZONE INDEPENDENT DELAY CONFIGURATION (ZONE 1 TO 10)
# =========================================================
ZONE_DELAY_MAP = {
    'Zone-1': 5.50,
    'Zone-2': 5.50,
    'Zone-3': 5.50,
    'Zone-4': 5.50,
    'Zone-5': 5.50,
    'Zone-6': 5.50,
    'Zone-7': 5.50,
    'Zone-8': 5.50,
    'Zone-9': 5.50,
    'Zone-10': 5.50
}

SELECTED_ZONE_INDEX = None  # Currently selected zone for adjustment (0-9)
SHOW_DISPLAY = True         # Toggle display window
ZONE_ADJUST_STEP = 10       # Step size in pixels

# =========================================================
# YOLO CONFIGURATION (STRICTLY 19-09-26 MODEL ONLY)
# =========================================================
YOLO_MODEL_PATH = get_existing_path([
    os.path.join(BASE_DIR, "best.onnx"),
    os.path.join(BUNDLE_DIR, "best.onnx"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "best.onnx"),
    os.path.join(BASE_DIR, "best.pt"),
    os.path.join(BUNDLE_DIR, "best.pt"),
    r"D:\yolo_cls\360models\19-09-26\product_detection\weights\best.onnx",
    r"D:\yolo_cls\360models\19-09-26\product_detection\weights\best.pt",
    r"D:\yolo_cls\360models\19-09-26\product_detection\best.onnx",
    r"D:\yolo_cls\360models\19-09-26\product_detection\best.pt",
    r"D:\yolo_cls\360models\19-09-26",
], os.path.join(BASE_DIR, "best.onnx"))

GOOD_CLASS_NAMES = ['good']

# =========================================================
# GRADING CONFIGURATION (ZONES 1 TO 10)
# =========================================================
GRADE_PORT_MAP = {
    # Camera A (Belts 1 to 5) -> Controller A
    'Zone-1': { '400': '11|', '320': '12|', '240': '13|', '210': '14|', '180': '15|', 'bad': '16|', 'blackdot': '16|', 'default': '11|' },
    'Zone-2': { '400': '22|', '320': '23|', '240': '24|', '210': '25|', '180': '26|', 'bad': '21|', 'blackdot': '21|', 'default': '22|' },
    'Zone-3': { '400': '33|', '320': '34|', '240': '35|', '210': '36|', '180': '41|', 'bad': '31|', 'blackdot': '32|', 'default': '33|' },
    'Zone-4': { '400': '44|', '320': '45|', '240': '46|', '210': '51|', '180': '52|', 'bad': '41|', 'blackdot': '42|', 'default': '44|' },
    'Zone-5': { '400': '55|', '320': '56|', '240': '61|', '210': '62|', '180': '63|', 'bad': '51|', 'blackdot': '52|', 'default': '55|' },

    # Camera B (Belts 6 to 10) -> Controller B
    'Zone-6': { '400': '11|', '320': '12|', '240': '13|', '210': '14|', '180': '15|', 'bad': '16|', 'blackdot': '16|', 'default': '11|' },
    'Zone-7': { '400': '22|', '320': '23|', '240': '24|', '210': '25|', '180': '26|', 'bad': '21|', 'blackdot': '21|', 'default': '22|' },
    'Zone-8': { '400': '33|', '320': '34|', '240': '35|', '210': '36|', '180': '41|', 'bad': '31|', 'blackdot': '32|', 'default': '33|' },
    'Zone-9': { '400': '44|', '320': '45|', '240': '46|', '210': '51|', '180': '52|', 'bad': '41|', 'blackdot': '42|', 'default': '44|' },
    'Zone-10': { '400': '55|', '320': '56|', '240': '61|', '210': '62|', '180': '63|', 'bad': '51|', 'blackdot': '52|', 'default': '55|' }
}

ZONE_COMMAND_MAP = {zone: cmds['default'] for zone, cmds in GRADE_PORT_MAP.items()}

# =========================================================
# LOAD SDK
# =========================================================
if platform.system() == "Windows":
    for p in [
        os.path.join(BASE_DIR, "Python", "MvImport"),
        os.path.join(BUNDLE_DIR, "Python", "MvImport"),
        os.path.join(BUNDLE_DIR, "MvImport"),
        r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
    ]:
        if os.path.exists(p) and p not in sys.path:
            sys.path.append(p)

    DLL_PATH = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
    if os.path.exists(DLL_PATH):
        os.environ['PATH'] = DLL_PATH + os.pathsep + os.environ['PATH']
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(DLL_PATH)

try:
    from MvCameraControl_class import *  # type: ignore
    SDK_IMPORTED = True
except Exception as e:
    print(f"SDK not loaded: {e}")
    SDK_IMPORTED = False

# =========================================================
# READ SERIAL & COM PORT HELPERS
# =========================================================

def read_target_serial(cam_id='a'):
    """
    Reads the target serial number for Camera 'a' (index 0) or 'b' (index 1).
    Checks wate/camera_ref.txt, camera_serial(a/b).txt, camera_ref.json.
    """
    idx = 0 if str(cam_id).lower() in ['a', '1'] else 1
    user_desktop = os.path.join(os.path.expanduser("~"), "Desktop", f"camera_serial({cam_id.lower()}).txt")
    candidates = [
        os.path.join(BASE_DIR, "wate", "camera_ref.txt"),
        SERIAL_FILE_A if idx == 0 else SERIAL_FILE_B,
        user_desktop,
        os.path.join(BASE_DIR, f"camera_serial({cam_id.lower()}).txt"),
        rf"C:\Users\i7\Desktop\camera_serial({cam_id.lower()}).txt",
        r"D:\Keya Work\360\camera_ref.json"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c, "r") as f:
                    content = f.read().strip()
                if content.startswith("[") or content.startswith("{"):
                    data = json.loads(content)
                    if isinstance(data, dict):
                        refs = data.get("references", ["", ""])
                        if len(refs) > idx and refs[idx]:
                            return str(refs[idx]).strip()
                    elif isinstance(data, list):
                        if len(data) > idx and data[idx]:
                            return str(data[idx]).strip()
                elif content:
                    lines = [line.strip() for line in content.splitlines() if line.strip()]
                    if lines:
                        if 'camera_ref' in c and len(lines) > idx:
                            return lines[idx]
                        return lines[0]
            except Exception:
                pass
    return None

def read_com_port_from_file(file_path):
    """
    Read COM port string from file and normalize to 'COMX'.
    """
    candidates = [
        os.path.join(BASE_DIR, "wate", "comport_ref.txt"),
        file_path,
        os.path.join(BASE_DIR, "wate", os.path.basename(file_path)) if file_path else None,
    ]
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c, 'r') as f:
                    content = f.read().strip()
                if content.startswith("[") or content.startswith("{"):
                    data = json.loads(content)
                    if isinstance(data, dict):
                        refs = data.get("references", [""])
                        idx = 0
                        if file_path and '(b)' in file_path.lower(): idx = 1
                        elif file_path and '(c)' in file_path.lower(): idx = 2
                        if len(refs) > idx and refs[idx]: content = str(refs[idx]).strip()
                        elif refs and refs[0]: content = str(refs[0]).strip()
                m = re.search(r'(\d+)', content)
                if m:
                    return f"COM{m.group(1)}"
                if content.upper().startswith('COM'):
                    return content
            except Exception:
                pass
    return None

# =========================================================
# GRADING SYSTEM
# =========================================================

def load_ranges(file_path):
    """Load grading ranges from file"""
    ranges = []
    try:
        if not os.path.exists(file_path):
            local_path = os.path.join(BASE_DIR, "wate", "value.txt")
            if os.path.exists(local_path):
                file_path = local_path
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    part = line.strip()
                    if not part:
                        continue
                    if ':' in part:
                        range_part, grade = part.split(':')
                        start, end = map(float, range_part.split('-'))
                        ranges.append((start, end, grade.strip()))
                    elif ',' in part:
                        parts = [p.strip() for p in part.split(',')]
                        if len(parts) >= 3 and parts[1] and parts[2]:
                            grade = parts[0]
                            start = float(parts[1])
                            end = float(parts[2])
                            ranges.append((start, end, grade))
            print(f"Loaded {len(ranges)} grading ranges from {file_path}")
        else:
            print(f"Ranges file not found: {file_path}")
        return ranges
    except Exception as e:
        print(f"Error loading ranges: {e}")
        return []

def get_grade(mm_value, ranges):
    """Get grade based on mm value"""
    if not ranges:
        return None
    for start, end, grade in ranges:
        if start <= mm_value <= end:
            return grade
    return None

# =========================================================
# GPU ACCELERATED YOLO / ONNX QUALITY FILTER CLASS
# =========================================================

class CashewQualityFilter:
    """
    GPU-accelerated Defect Detection and Quality Filter (RTX 5050 ONNX Runtime / YOLO).
    Shared safely between Camera A and Camera B processing threads.
    """
    CLASS_MAP = {0: 'bad', 1: 'blackdot', 2: 'good'}

    def __init__(self, model_path=None):
        self.session = None
        self.model = None
        self.provider = None
        self.input_name = None
        self.input_shape = (640, 640)
        self.lock = threading.Lock()
        self.clahe_crop = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        
        # Build ONNX candidates
        onnx_candidates = [
            os.path.join(BASE_DIR, "best.onnx"),
            os.path.join(BUNDLE_DIR, "best.onnx"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "best.onnx"),
            r"D:\yolo_cls\360models\19-09-26\product_detection\weights\best.onnx",
            r"D:\yolo_cls\360models\19-09-26\product_detection\best.onnx",
            r"D:\yolo_cls\360models\19-09-26\best.onnx",
        ]
        
        onnx_path = next((p for p in onnx_candidates if p and os.path.exists(p)), None)
        
        if ONNX_AVAILABLE and onnx_path:
            try:
                available = ort.get_available_providers()
                providers = []
                if 'CUDAExecutionProvider' in available:
                    cuda_opts = {
                        'device_id': 0,
                        'arena_extend_strategy': 'kNextPowerOfTwo',
                        'cudnn_conv_algo_search': 'DEFAULT',
                        'do_copy_in_default_stream': True,
                    }
                    providers.append(('CUDAExecutionProvider', cuda_opts))
                if 'DmlExecutionProvider' in available:
                    providers.append('DmlExecutionProvider')
                providers.append('CPUExecutionProvider')

                sess_options = ort.SessionOptions()
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                sess_options.intra_op_num_threads = min(8, os.cpu_count() or 4)
                sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

                self.session = ort.InferenceSession(onnx_path, sess_options=sess_options, providers=providers)
                self.provider = self.session.get_providers()[0]
                self.input_name = self.session.get_inputs()[0].name
                inp_shape = self.session.get_inputs()[0].shape
                h = inp_shape[2] if len(inp_shape) > 2 and isinstance(inp_shape[2], int) else 640
                w = inp_shape[3] if len(inp_shape) > 3 and isinstance(inp_shape[3], int) else 640
                self.input_shape = (w, h)
                print(f"\n[AI CORE] Ultra-Fast ONNX Engine loaded from: {onnx_path}")
                print(f"[AI CORE] Active Provider: {self.provider} (Optimized for 60+ FPS)")
                
                # Dynamic class names from ONNX model metadata
                try:
                    custom_meta = self.session.get_modelmeta().custom_metadata_map
                    if 'names' in custom_meta:
                        names_raw = custom_meta['names']
                        try:
                            parsed_names = ast.literal_eval(names_raw)
                            if isinstance(parsed_names, dict):
                                self.CLASS_MAP = {int(k): str(v).lower() for k, v in parsed_names.items()}
                            elif isinstance(parsed_names, list):
                                self.CLASS_MAP = {i: str(v).lower() for i, v in enumerate(parsed_names)}
                            print(f"[AI CORE] ONNX Classes: {self.CLASS_MAP}")
                        except Exception:
                            pass
                except Exception:
                    pass

                # Warmup
                dummy = np.zeros((1, 3, h, w), dtype=np.float32)
                for _ in range(3):
                    self.session.run(None, {self.input_name: dummy})
                print(f"[AI CORE] High-Throughput Warmup Complete (AI Ready)\n")
                return
            except Exception as e:
                print(f"[AI CORE] Error initializing ONNX: {e}")
                self.session = None
                
        pt_candidates = [
            os.path.join(BASE_DIR, "best.pt"),
            os.path.join(BUNDLE_DIR, "best.pt"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "best.pt"),
            r"D:\yolo_cls\360models\19-09-26\product_detection\weights\best.pt",
            r"D:\yolo_cls\360models\19-09-26\product_detection\best.pt",
            r"D:\yolo_cls\360models\19-09-26\best.pt",
        ]
        pt_path = next((p for p in pt_candidates if p and os.path.exists(p)), None)
        
        if YOLO_AVAILABLE and pt_path:
            try:
                self.model = YOLO(pt_path)
                print(f"[AI CORE] YOLO Model loaded from: {pt_path}")
                if hasattr(self.model, 'names') and isinstance(self.model.names, dict):
                    self.CLASS_MAP = {int(k): str(v).lower() for k, v in self.model.names.items()}
                print(f"[AI CORE] YOLO Model Classes: {self.CLASS_MAP}")
            except Exception as e:
                print(f"[AI CORE] Error loading PyTorch YOLO: {e}")

    def detect_frame(self, frame, conf_thresh=0.20, nms_thresh=0.45):
        """
        Ultra-fast SIMD/GPU accelerated YOLO Object Detection on camera frame (60+ FPS optimized).
        """
        if frame is None or frame.size == 0:
            return []
            
        h_orig, w_orig = frame.shape[:2]
        
        if self.session is not None:
            try:
                w_in, h_in = self.input_shape
                # High-speed SIMD C++ preprocessing
                blob = cv2.dnn.blobFromImage(frame, 1.0 / 255.0, (w_in, h_in), swapRB=True, crop=False)
                
                with self.lock:
                    out = self.session.run(None, {self.input_name: blob})[0]
                    
                preds = out[0].T # (8400, 7) [cx, cy, w, h, score_bad, score_blackdot, score_good]
                boxes = preds[:, :4]
                scores = preds[:, 4:]
                
                class_ids = np.argmax(scores, axis=1)
                confidences = np.max(scores, axis=1)
                
                mask = confidences >= conf_thresh
                valid_boxes = boxes[mask]
                valid_cids = class_ids[mask]
                valid_confs = confidences[mask]
                
                if len(valid_boxes) == 0:
                    return []
                    
                scale_x = w_orig / float(w_in)
                scale_y = h_orig / float(h_in)
                
                bx = valid_boxes[:, 0] * scale_x
                by = valid_boxes[:, 1] * scale_y
                bw = valid_boxes[:, 2] * scale_x
                bh = valid_boxes[:, 3] * scale_y
                
                x1 = (bx - bw * 0.5).astype(np.int32)
                y1 = (by - bh * 0.5).astype(np.int32)
                bw_int = bw.astype(np.int32)
                bh_int = bh.astype(np.int32)
                
                orig_boxes = np.stack([x1, y1, bw_int, bh_int], axis=1).tolist()
                scores_list = valid_confs.tolist()
                
                indices = cv2.dnn.NMSBoxes(
                    bboxes=orig_boxes,
                    scores=scores_list,
                    score_threshold=conf_thresh,
                    nms_threshold=nms_thresh
                )
                
                detections = []
                if len(indices) > 0:
                    for idx in (indices.flatten() if hasattr(indices, 'flatten') else indices):
                        cid = valid_cids[idx]
                        cname = self.CLASS_MAP.get(cid, 'good')
                        conf = float(valid_confs[idx])
                        ox, oy, ow, oh = orig_boxes[idx]
                        detections.append({
                            'box': (ox, oy, ox + ow, oy + oh),
                            'center': (ox + ow // 2, oy + oh // 2),
                            'class': cname,
                            'conf': conf
                        })
                return detections
            except Exception as e:
                print(f"[AI GPU DETECT ERROR] {e}")
                
        if self.model is not None:
            try:
                with self.lock:
                    results = self.model(frame, verbose=False, conf=conf_thresh, device='cpu', imgsz=640)
                    detections = []
                    for r in results:
                        for box in r.boxes:
                            cid = int(box.cls[0])
                            cname = self.model.names.get(cid, 'good').lower()
                            conf = float(box.conf[0])
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            detections.append({
                                'box': (x1, y1, x2, y2),
                                'center': ((x1 + x2) // 2, (y1 + y2) // 2),
                                'class': cname,
                                'conf': conf
                            })
                    return detections
            except Exception as e:
                print(f"[AI PYTORCH DETECT ERROR] {e}")
                
        return []

    def get_cashew_categories_batch(self, crops):
        if not crops:
            return []
        if self.session is not None:
            try:
                w_in, h_in = self.input_shape
                valid_indices = []
                valid_crops = []
                for idx, c in enumerate(crops):
                    if c is not None and c.size > 0:
                        valid_indices.append(idx)
                        valid_crops.append(c)

                batch_results = [(None, 0.0)] * len(crops)
                if not valid_crops:
                    return batch_results

                # Process all crops in a single C++ SIMD GPU batch
                batch_tensor = cv2.dnn.blobFromImages(valid_crops, 1.0 / 255.0, (w_in, h_in), swapRB=True, crop=False)
                with self.lock:
                    output = self.session.run(None, {self.input_name: batch_tensor})[0]

                if output.ndim == 3:
                    if output.shape[1] < output.shape[2]:
                        output = output.transpose(0, 2, 1)
                    
                    for i, orig_idx in enumerate(valid_indices):
                        scores = output[i, :, 4:]
                        score_bad = float(np.max(scores[:, 0])) if scores.shape[1] > 0 else 0.0
                        score_blackdot = float(np.max(scores[:, 1])) if scores.shape[1] > 1 else 0.0
                        score_good = float(np.max(scores[:, 2])) if scores.shape[1] > 2 else 0.0

                        if score_blackdot >= THRESH_BLACKDOT and score_blackdot >= score_bad:
                            batch_results[orig_idx] = ('blackdot', score_blackdot)
                        elif score_bad >= THRESH_BAD:
                            batch_results[orig_idx] = ('bad', score_bad)
                        else:
                            batch_results[orig_idx] = ('good', score_good)

                return batch_results
            except Exception as e:
                print(f"[AI GPU BATCH ERROR] {e}")

        if self.model is not None:
            try:
                device_target = 'cpu'
                w_in = self.input_shape[0] if hasattr(self, 'input_shape') else 640
                with self.lock:
                    results = self.model(crops, verbose=False, conf=YOLO_CONF_THRESHOLD, device=device_target, imgsz=w_in)
                    for result in results:
                        if len(result.boxes) > 0:
                            defect_box = None
                            for box in result.boxes:
                                cls_name = self.model.names[int(box.cls[0])].lower()
                                if cls_name in ['bad', 'blackdot']:
                                    defect_box = (cls_name, float(box.conf[0]))
                                    break
                            if defect_box:
                                batch_results.append(defect_box)
                            else:
                                best_box = result.boxes[0]
                                batch_results.append((self.model.names[int(best_box.cls[0])].lower(), float(best_box.conf[0])))
                        else:
                            batch_results.append(('good', 0.0))
                return batch_results
            except Exception as e:
                print(f"[AI PYTORCH ERROR] {e}")

        return [(None, 0.0)] * len(crops)

# =========================================================
# CAMERA CLASS (HIKROBOT DUAL CAMERA COMPATIBLE)
# =========================================================

class HIKCashewCamera:
    """
    Handles a single Hikvision Industrial Camera connection, continuous frame grabbing,
    and dynamic parameter updates independently.
    """
    def __init__(self, cam_name="Cam-A", cam_idx="1", serial_id="a"):
        self.cam_name = cam_name
        self.cam_idx = str(cam_idx)
        self.serial_id = str(serial_id).lower()
        self.cam = None
        self.is_grabbing = False
        self.nPayloadSize = 0
        self.frame_lock = threading.Lock()
        self.latest_raw = None
        self.latest_info = None
        self.grab_thread = None
        self.target_serial = None
        self.current_width = -1
        self.current_height = -1
        self.current_offset_x = -1
        self.current_offset_y = -1
        self.last_params_mtime = 0

    def connect(self):
        if not SDK_IMPORTED:
            print(f"[{self.cam_name}] Hikvision SDK not imported.")
            return False

        self.target_serial = read_target_serial(self.serial_id)
        if not self.target_serial:
            print(f"[{self.cam_name}] No target serial found for Camera {self.cam_idx} ({self.serial_id.upper()})")
            return False

        print(f"\n[{self.cam_name}] Connecting to Serial: {self.target_serial}...")

        try:
            MvCamera.MV_CC_Initialize()
        except Exception:
            pass

        self.cam = MvCamera()
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE

        if MvCamera.MV_CC_EnumDevices(tlayerType, deviceList) != 0:
            print(f"[{self.cam_name}] EnumDevices failed.")
            return False

        selected = None
        for i in range(deviceList.nDeviceNum):
            info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            try:
                if info.nTLayerType == MV_GIGE_DEVICE:
                    serial_str = bytes(info.SpecialInfo.stGigEInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
                elif info.nTLayerType == MV_USB_DEVICE:
                    serial_str = bytes(info.SpecialInfo.stUsb3VInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
                else:
                    continue

                if serial_str.strip() == self.target_serial.strip():
                    selected = info
                    print(f"[{self.cam_name}] Matched Device {i} -> Serial: {serial_str}")
                    break
            except Exception:
                pass

        if selected is None:
            print(f"[{self.cam_name}] Target serial '{self.target_serial}' not found among connected devices.")
            return False

        if self.cam.MV_CC_CreateHandle(selected) != 0:
            print(f"[{self.cam_name}] CreateHandle failed.")
            return False

        if self.cam.MV_CC_OpenDevice(MV_ACCESS_Control, 0) != 0:
            print(f"[{self.cam_name}] OpenDevice failed. (Ensure no other application is using this camera)")
            return False

        # Load parameters from camera_params.json
        params = {}
        try:
            params_path = os.path.join(os.path.dirname(__file__), "camera_params.json")
            if not os.path.exists(params_path):
                params_path = os.path.join(BASE_DIR, "camera_params.json")
            if os.path.exists(params_path):
                self.last_params_mtime = os.path.getmtime(params_path)
                with open(params_path, "r") as f:
                    params = json.load(f).get(self.cam_idx, {})
        except Exception:
            pass

        try:
            self.cam.MV_CC_SetIntValue("OffsetX", 0)
            self.cam.MV_CC_SetIntValue("OffsetY", 0)

            stWidthParam = MVCC_INTVALUE()
            memset(byref(stWidthParam), 0, sizeof(stWidthParam))
            self.cam.MV_CC_GetIntValue("Width", stWidthParam)
            w_max = stWidthParam.nMax if stWidthParam.nMax > 0 else 2448

            stHeightParam = MVCC_INTVALUE()
            memset(byref(stHeightParam), 0, sizeof(stHeightParam))
            self.cam.MV_CC_GetIntValue("Height", stHeightParam)
            h_max = stHeightParam.nMax if stHeightParam.nMax > 0 else 2048

            w_val = int(params.get("width", w_max))
            w_val = (max(32, min(w_max, w_val)) // 8) * 8
            self.cam.MV_CC_SetIntValue("Width", w_val)
            self.current_width = w_val

            h_val = int(params.get("height", h_max))
            h_val = (max(8, min(h_max, h_val)) // 4) * 4
            self.cam.MV_CC_SetIntValue("Height", h_val)
            self.current_height = h_val

            off_x_val = (int(params.get("offsetX", 0)) // 8) * 8
            self.cam.MV_CC_SetIntValue("OffsetX", off_x_val)
            self.current_offset_x = off_x_val

            off_y_val = (int(params.get("offsetY", 0)) // 2) * 2
            self.cam.MV_CC_SetIntValue("OffsetY", off_y_val)
            self.current_offset_y = off_y_val

            # Motion blur prevention: ExposureMode Timed, Auto-Exposure / Gain Off
            try:
                self.cam.MV_CC_SetEnumValue("ExposureMode", 0)  # 0 = Timed
            except Exception:
                pass
            self.cam.MV_CC_SetEnumValue("ExposureAuto", 0)
            self.cam.MV_CC_SetEnumValue("GainAuto", 0)

            if "exposure" in params and params["exposure"]:
                self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
            else:
                self.cam.MV_CC_SetFloatValue("ExposureTime", 6000.0)

            if "gain" in params and params["gain"]:
                self.cam.MV_CC_SetFloatValue("Gain", float(params["gain"]))

            print(f"[{self.cam_name}] Parameters set: {w_val}x{h_val} (Offsets: {off_x_val},{off_y_val})")
        except Exception as e:
            print(f"[{self.cam_name}] Param error: {e}")

        self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)

        stParam = MVCC_INTVALUE()
        memset(byref(stParam), 0, sizeof(stParam))
        self.cam.MV_CC_GetIntValue("PayloadSize", stParam)
        self.nPayloadSize = stParam.nCurValue

        if self.cam.MV_CC_StartGrabbing() != 0:
            print(f"[{self.cam_name}] StartGrabbing failed.")
            return False

        self.is_grabbing = True
        print(f"[{self.cam_name}] Camera successfully connected and grabbing!")

        # High-speed background grab thread to prevent buffer lag
        self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True, name=f"GrabThread-{self.cam_name}")
        self.grab_thread.start()
        return True

    def _grab_loop(self):
        current_data_size = max(1, getattr(self, 'nPayloadSize', 1))
        data = (c_ubyte * current_data_size)()
        frame_info = MV_FRAME_OUT_INFO_EX()

        while self.is_grabbing:
            try:
                target_size = getattr(self, 'nPayloadSize', current_data_size)
                if target_size > 0 and target_size != current_data_size:
                    current_data_size = target_size
                    data = (c_ubyte * current_data_size)()

                if current_data_size <= 0 or not self.cam:
                    time.sleep(0.01)
                    continue

                memset(byref(frame_info), 0, sizeof(frame_info))
                ret = self.cam.MV_CC_GetOneFrameTimeout(byref(data), current_data_size, frame_info, 1000)

                if not self.is_grabbing:
                    break

                if ret == 0 and frame_info.nFrameLen > 0:
                    raw_bytes = string_at(byref(data), frame_info.nFrameLen)
                    with self.frame_lock:
                        self.latest_raw = raw_bytes
                        self.latest_info = (frame_info.nWidth, frame_info.nHeight, frame_info.enPixelType)
                else:
                    time.sleep(0.005)
            except Exception as e:
                time.sleep(0.05)

    def check_and_update_parameters(self):
        params_path = os.path.join(os.path.dirname(__file__), "camera_params.json")
        if not os.path.exists(params_path):
            params_path = os.path.join(BASE_DIR, "camera_params.json")
        if not os.path.exists(params_path):
            return

        try:
            mtime = os.path.getmtime(params_path)
            if not hasattr(self, 'last_params_mtime') or self.last_params_mtime == 0:
                self.last_params_mtime = mtime
                return
            if mtime > self.last_params_mtime:
                self.last_params_mtime = mtime
                print(f"\n[{self.cam_name}] camera_params.json changed! Reloading...")
                with open(params_path, "r") as f:
                    params = json.load(f).get(self.cam_idx, {})

                if "exposure" in params and params["exposure"] is not None:
                    try:
                        self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
                    except Exception:
                        pass
                if "gain" in params and params["gain"] is not None:
                    try:
                        self.cam.MV_CC_SetFloatValue("Gain", float(params["gain"]))
                    except Exception:
                        pass

                stWidthParam = MVCC_INTVALUE()
                memset(byref(stWidthParam), 0, sizeof(stWidthParam))
                self.cam.MV_CC_GetIntValue("Width", stWidthParam)
                w_max = stWidthParam.nMax if stWidthParam.nMax > 0 else 2448

                stHeightParam = MVCC_INTVALUE()
                memset(byref(stHeightParam), 0, sizeof(stHeightParam))
                self.cam.MV_CC_GetIntValue("Height", stHeightParam)
                h_max = stHeightParam.nMax if stHeightParam.nMax > 0 else 2048

                target_w = (max(32, min(w_max, int(params.get("width", self.current_width if self.current_width > 0 else w_max)))) // 8) * 8
                target_h = (max(8, min(h_max, int(params.get("height", self.current_height if self.current_height > 0 else h_max)))) // 4) * 4
                target_ox = (int(params.get("offsetX", self.current_offset_x if self.current_offset_x >= 0 else 0)) // 8) * 8
                target_oy = (int(params.get("offsetY", self.current_offset_y if self.current_offset_y >= 0 else 0)) // 2) * 2

                res_changed = (
                    target_w != getattr(self, 'current_width', -1) or
                    target_h != getattr(self, 'current_height', -1) or
                    target_ox != getattr(self, 'current_offset_x', -1) or
                    target_oy != getattr(self, 'current_offset_y', -1)
                )

                if res_changed:
                    print(f"[{self.cam_name}] Resolution/Offset changed, restarting grab safely...")
                    self.is_grabbing = False
                    if self.grab_thread and self.grab_thread.is_alive():
                        self.grab_thread.join(timeout=1.0)

                    self.cam.MV_CC_StopGrabbing()
                    self.cam.MV_CC_SetIntValue("OffsetX", 0)
                    self.cam.MV_CC_SetIntValue("OffsetY", 0)

                    self.cam.MV_CC_SetIntValue("Width", target_w)
                    self.current_width = target_w

                    self.cam.MV_CC_SetIntValue("Height", target_h)
                    self.current_height = target_h

                    self.cam.MV_CC_SetIntValue("OffsetX", target_ox)
                    self.current_offset_x = target_ox

                    self.cam.MV_CC_SetIntValue("OffsetY", target_oy)
                    self.current_offset_y = target_oy

                    stParam = MVCC_INTVALUE()
                    memset(byref(stParam), 0, sizeof(stParam))
                    self.cam.MV_CC_GetIntValue("PayloadSize", stParam)
                    new_payload = stParam.nCurValue
                    if new_payload > 0:
                        self.nPayloadSize = new_payload

                    if self.cam.MV_CC_StartGrabbing() == 0:
                        self.is_grabbing = True
                        self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True, name=f"GrabThread-{self.cam_name}")
                        self.grab_thread.start()
                        print(f"[{self.cam_name}] Camera successfully re-grabbed at {target_w}x{target_h} ({target_ox},{target_oy})")
                    else:
                        print(f"[{self.cam_name}] Restart grab failed.")
        except Exception as e:
            print(f"[{self.cam_name}] Error updating params: {e}")

    def get_frame(self):
        if not getattr(self, 'is_grabbing', False):
            return None

        with self.frame_lock:
            if self.latest_raw is None:
                return None
            raw_bytes = self.latest_raw
            w, h, pf = self.latest_info

        img = np.frombuffer(raw_bytes, dtype=np.uint8)

        try:
            if pf == PixelType_Gvsp_BGR8_Packed:
                return img.reshape((h, w, 3))
            elif pf == PixelType_Gvsp_RGB8_Packed:
                rgb = img.reshape((h, w, 3))
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            elif pf == PixelType_Gvsp_Mono8:
                mono = img.reshape((h, w))
                return cv2.cvtColor(mono, cv2.COLOR_GRAY2BGR)
            elif pf == PixelType_Gvsp_BayerRG8:
                return cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_RG2BGR)
            elif pf == PixelType_Gvsp_BayerGB8:
                return cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_GB2BGR)
            elif pf == PixelType_Gvsp_BayerBG8:
                return cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_BG2BGR)
            elif pf == PixelType_Gvsp_BayerGR8:
                return cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_GR2BGR)
            else:
                mono = img.reshape((h, w))
                return cv2.cvtColor(mono, cv2.COLOR_GRAY2BGR)
        except Exception:
            return None

    def close(self):
        if self.is_grabbing:
            self.is_grabbing = False
            try:
                self.cam.MV_CC_StopGrabbing()
                self.cam.MV_CC_CloseDevice()
                self.cam.MV_CC_DestroyHandle()
            except Exception:
                pass
            print(f"[{self.cam_name}] Camera closed.")

# =========================================================
# CONTOUR SMOOTHING HELPER
# =========================================================

def smooth_contour(contour, window=9):
    if contour is None or len(contour) < window * 2:
        return contour
    pts = contour.reshape(-1, 2).astype(np.float64)
    n = len(pts)
    if n < 5:
        return contour
    pad = window // 2
    padded_x = np.concatenate([pts[-pad:, 0], pts[:, 0], pts[:pad, 0]])
    padded_y = np.concatenate([pts[-pad:, 1], pts[:, 1], pts[:pad, 1]])
    kernel = np.ones(window) / window
    smooth_x = np.convolve(padded_x, kernel, mode='valid')
    smooth_y = np.convolve(padded_y, kernel, mode='valid')
    smoothed = np.stack([smooth_x, smooth_y], axis=1).astype(np.int32)
    return smoothed.reshape(-1, 1, 2)

KERNEL_E_5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
KERNEL_CLOSE_9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
CLAHE_OBJ = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

# =========================================================
# ZONE PROCESSOR CLASS
# =========================================================

class ZoneProcessor:
    """
    Processes a single zone independently (Zone-1 to Zone-10).
    Routes ejection commands to its designated EjectionQueue without blocking.
    """
    def __init__(self, zone_config, ranges, ejection_queue=None):
        self.zone = zone_config['zone']
        self.name = zone_config.get('name', 'Zone-1')
        self.ranges = ranges
        self.tracker = _TrackerClass(
            self.name,
            max_distance=350,
            max_disappeared=10,
            pixel_to_mm_ratio=PIXEL_TO_MM_RATIO,
        )
        self.ejection_queue = ejection_queue
    
    def update_zone(self, new_zone):
        self.zone = new_zone
    
    def process_frame(self, frame, quality_filter=None, frame_detections=None):
        if frame is None or frame.size == 0:
            return []

        try:
            x, y, w, h = self.zone
            if w <= 0 or h <= 0:
                return []

            img_h, img_w = frame.shape[:2]
            x1 = max(0, min(x, img_w - 1))
            y1 = max(0, min(y, img_h - 1))
            x2 = max(0, min(x + w, img_w))
            y2 = max(0, min(y + h, img_h))
            
            if x2 <= x1 or y2 <= y1:
                return []

            zone_frame = frame[y1:y2, x1:x2]
            if zone_frame.size == 0 or zone_frame.shape[0] < 8 or zone_frame.shape[1] < 8:
                return []
            
            # Chromaticity contrast: Cashew (organic warm: R, G > B) vs Roller/Metal/Belt (cool: B >= R, G)
            b_ch, g_ch, r_ch = cv2.split(zone_frame)
            rg_avg = cv2.addWeighted(r_ch, 0.5, g_ch, 0.5, 0)
            chroma_diff = cv2.subtract(rg_avg, b_ch)
            
            # CLAHE on Chroma to enhance dimly lit cashews without boosting metal glares
            clahe_chroma = CLAHE_OBJ.apply(chroma_diff)
            smooth_chroma = cv2.GaussianBlur(clahe_chroma, (5, 5), 0)
            
            # Otsu threshold on enhanced chromaticity (adapts to bright & dark illumination)
            _, mask_otsu = cv2.threshold(smooth_chroma, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Sensitive Chroma Gate: catches cashews in low light/shadows while rejecting cool blue rollers
            _, min_chroma_gate = cv2.threshold(chroma_diff, 10, 255, cv2.THRESH_BINARY)
            mask_raw = cv2.bitwise_and(mask_otsu, min_chroma_gate)
            
            # Clean morphological cleanup (5x5 kernel preserves cashew edge, prevents line bridging)
            mask_clean = cv2.morphologyEx(mask_raw, cv2.MORPH_OPEN, KERNEL_E_5, iterations=1)
            mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, KERNEL_E_5, iterations=1)
            mask_smooth = cv2.GaussianBlur(mask_clean, (5, 5), 0)
            _, mask_final = cv2.threshold(mask_smooth, 127, 255, cv2.THRESH_BINARY)
            
            hsv = cv2.cvtColor(zone_frame, cv2.COLOR_BGR2HSV)
            hsv_mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
            
            cnts, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            adjusted_contours = []
            for c in cnts:
                if c is None or len(c) < 3:
                    continue
                c_adjusted = c.copy()
                c_adjusted[:, 0, 0] += x1
                c_adjusted[:, 0, 1] += y1
                c_adjusted = smooth_contour(c_adjusted, window=5)
                adjusted_contours.append(c_adjusted)
            
            valid_contours = []
            is_good_flags = []
            grades = []
            crops = []
            
            for i, c in enumerate(adjusted_contours):
                if c is None or len(c) < 3:
                    continue
                area = cv2.contourArea(c)
                if area < MIN_CASHEW_AREA:
                    continue
                    
                if i < len(cnts) and cnts[i] is not None and len(cnts[i]) >= 3:
                    c_mask = np.zeros(zone_frame.shape[:2], dtype=np.uint8)
                    cv2.drawContours(c_mask, [cnts[i]], -1, 255, -1)
                    cashew_pixels = cv2.countNonZero(cv2.bitwise_and(c_mask, hsv_mask))
                    total_pixels = cv2.countNonZero(c_mask)
                    density = cashew_pixels / max(1, total_pixels)
                    if density < 0.08:
                        continue
                    
                if len(c) >= 15:
                    ellipse = cv2.fitEllipse(c)
                    (w_p, h_p) = ellipse[1]
                else:
                    rect = cv2.minAreaRect(c)
                    (w_p, h_p) = rect[1]
                if max(1, w_p * h_p) == 1: continue
                mm_size = max(w_p, h_p) * PIXEL_TO_MM_RATIO
                
                if mm_size > MAX_CASHEW_MM:
                    continue
                
                x_b, y_b, w_b, h_b = cv2.boundingRect(c)
                if w_b > (self.zone[2] * 0.98):
                    continue
                
                # Exclude bottom metal plate / top camera frame borders
                if (y_b + h_b) >= (img_h - 15) or y_b <= 5:
                    continue
                    
                min_dim = min(w_p, h_p)
                max_dim = max(w_p, h_p)
                aspect_ratio = max_dim / max(1.0, min_dim)
                
                # Reject thin horizontal roller lines/glares (cashews have thickness >= 18px, aspect <= 3.0)
                if min_dim < 18:
                    continue
                if aspect_ratio > 3.0:
                    continue
                    
                solidity = area / max(1, w_p * h_p)
                if solidity < 0.15:
                    continue
                    
                side = max(w_b, h_b) + 40
                cx_b, cy_b = x_b + w_b // 2, y_b + h_b // 2
                px = max(0, min(img_w - 1, cx_b - side // 2))
                py = max(0, min(img_h - 1, cy_b - side // 2))
                pw = max(0, min(img_w - px, side))
                ph = max(0, min(img_h - py, side))
                if pw < 8 or ph < 8:
                    continue
                crop = frame[py:py+ph, px:px+pw]
                if crop.size == 0:
                    continue
                
                # Spatial matching against full-frame YOLO detections
                matched_defect = None
                if frame_detections:
                    best_dist = 999999
                    for det in frame_detections:
                        dx, dy = det['center']
                        dist = math.hypot(cx_b - dx, cy_b - dy)
                        max_allow_dist = max(w_b, h_b) * 0.85 + 35
                        if dist <= max_allow_dist:
                            det_x1, det_y1, det_x2, det_y2 = det['box']
                            inter_x1 = max(x_b, det_x1)
                            inter_y1 = max(y_b, det_y1)
                            inter_x2 = min(x_b + w_b, det_x2)
                            inter_y2 = min(y_b + h_b, det_y2)
                            inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
                            cashew_area = max(1, w_b * h_b)
                            overlap = inter_area / cashew_area
                            
                            if dist < best_dist or overlap > 0.15:
                                if det['class'] in ['blackdot', 'bad']:
                                    matched_defect = det['class']
                                    best_dist = dist
                                elif matched_defect is None and det['class'] not in GOOD_CLASS_NAMES:
                                    matched_defect = det['class']
                                    best_dist = dist

                is_defect = (matched_defect in ['bad', 'blackdot'])
                valid_contours.append(c)
                is_good_flags.append(not is_defect)
                grades.append(matched_defect if is_defect else None)
                crops.append(crop)
            
            frame_ts = time.perf_counter()
            disappeared_ids = self.tracker.update(valid_contours, is_good_flags, grades, crops, frame_timestamp=frame_ts)
            
            disappeared_crops = []
            disappeared_objs = []
            already_handled_ids = set()
            already_scheduled_ids = set()
            
            x, y, _, zone_h = self.zone
            min_start_line = y + (zone_h * 0.85)
            trigger_line = y + (zone_h * 0.95)
            disappear_trigger_line = y + (zone_h * 0.20)
        
            # 1. Line Crossing Evaluation
            for obj_id, obj_info in list(self.tracker.objects.items()):
                if obj_info.get('command_sent', False) or obj_id in already_scheduled_ids:
                    continue

                cy = obj_info['centroid'][1]
                start_y = obj_info.get('start_y', cy)
                prev_cy = obj_info.get('prev_centroid', (0, cy))[1]

                if cy >= trigger_line and (start_y < min_start_line or prev_cy < trigger_line):
                    confirm_count = obj_info.setdefault('line_cross_confirm', 0)
                    if cy >= prev_cy or prev_cy <= trigger_line:
                        confirm_count += 1
                    else:
                        confirm_count = max(0, confirm_count - 1)
                    obj_info['line_cross_confirm'] = confirm_count

                    if confirm_count < 2:
                        continue

                    max_mm = obj_info['max_mm']
                    frames_tracked = len(obj_info.get('measurements', []))
                    if max_mm >= MIN_MM_SIZE and frames_tracked >= 3:
                        prev_time = obj_info.get('prev_time', time.perf_counter())
                        curr_time = obj_info.get('curr_time', time.perf_counter())
                        true_exit_time = time.perf_counter()
                        time_overshoot = 0
                        dy = cy - prev_cy
                        dt = curr_time - prev_time

                        if dt > 0 and dy > 0:
                            velocity = dy / dt
                            overshoot_px = cy - trigger_line
                            if overshoot_px > 0:
                                time_overshoot = overshoot_px / velocity
                                true_exit_time -= time_overshoot

                        last_crop = obj_info.get('last_crop')
                        if last_crop is not None:
                            disappeared_crops.append(last_crop)
                            disappeared_objs.append((obj_id, obj_info, true_exit_time, time_overshoot))
                            obj_info['command_sent'] = True
                            obj_info['crossed_trigger_line'] = True
                            already_handled_ids.add(obj_id)
                            already_scheduled_ids.add(obj_id)
                            self.tracker.remove_object(obj_id)
                    else:
                        obj_info['command_sent'] = True
                        obj_info['line_cross_confirm'] = 0
                        already_handled_ids.add(obj_id)
                        self.tracker.remove_object(obj_id)
                else:
                    obj_info['line_cross_confirm'] = 0

            # 2. Disappearance Evaluation
            for obj_id in disappeared_ids:
                if obj_id in already_handled_ids:
                    continue
                obj_info = self.tracker.get_object_info(obj_id)
                if obj_info:
                    if not obj_info.get('command_sent', False):
                        if obj_id in already_scheduled_ids:
                            self.tracker.remove_object(obj_id)
                            continue

                        cy = obj_info['centroid'][1]
                        start_y = obj_info.get('start_y', cy)
                        prev_cy = obj_info.get('prev_centroid', (0, cy))[1]

                        if cy >= disappear_trigger_line and (start_y < min_start_line or prev_cy < disappear_trigger_line):
                            max_mm = obj_info['max_mm']
                            frames_tracked = len(obj_info.get('measurements', []))
                            if max_mm >= MIN_MM_SIZE and frames_tracked >= 3:
                                last_crop = obj_info.get('last_crop')
                                if last_crop is not None:
                                    disappeared_crops.append(last_crop)
                                    disappeared_objs.append((obj_id, obj_info, time.perf_counter(), 0))
                                    obj_info['command_sent'] = True
                                    already_scheduled_ids.add(obj_id)
                            else:
                                obj_info['command_sent'] = True
                        else:
                            obj_info['command_sent'] = True
                                    
                    self.tracker.remove_object(obj_id)

            # 3. Ejection Queuing & Logging
            if disappeared_objs:
                zone_map = GRADE_PORT_MAP.get(self.name, {})
                default_zone_cmd = zone_map.get('default', ZONE_COMMAND_MAP.get(self.name, ''))

                for idx, (obj_id, obj_info, true_exit_time, time_overshoot) in enumerate(disappeared_objs):
                    if hasattr(self.tracker, 'get_robust_size'):
                        max_mm = self.tracker.get_robust_size(obj_id)
                        if max_mm <= 0:
                            max_mm = obj_info['max_mm']
                    else:
                        max_mm = obj_info['max_mm']

                    last_crop = disappeared_crops[idx] if idx < len(disappeared_crops) else None
                    
                    # Check persistent defect history across frames
                    history = obj_info.get('grade_history', [])
                    defect_frames = [g for g in history if g in ['blackdot', 'bad']]
                    
                    if defect_frames:
                        defect_counts = Counter(defect_frames)
                        final_grade = defect_counts.most_common(1)[0][0]
                    else:
                        final_grade = get_grade(max_mm, self.ranges)
                        
                    grade_str = str(final_grade).strip().lower() if final_grade is not None else 'default'
                    command = zone_map.get(grade_str, default_zone_cmd)
                    zone_delay = ZONE_DELAY_MAP.get(self.name, DELAY_SECONDS)

                    if self.ejection_queue is not None:
                        self.ejection_queue.schedule(
                            obj_id=obj_id,
                            command=command,
                            exit_time=true_exit_time,
                            zone_name=self.name,
                            grade=grade_str,
                            size_mm=max_mm,
                            delay_seconds=zone_delay,
                        )
                    else:
                        now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{now_str}] [{self.name}] EXIT ID:{obj_id} (MM:{max_mm:.1f}, Grade:{grade_str}, Cmd:{command.strip()}) -> NO EJECTION QUEUE")

                    if last_crop is not None:
                        tracked_cnt = obj_info.get('latest_contour')
                        ASYNC_IMAGE_SAVER.submit(last_crop, obj_id, final_grade, max_mm, tracked_cnt)
                    
            return valid_contours
        except Exception as e:
            return []
    
    def draw_zone(self, frame):
        """Draw zone boundary and tracked objects with full info"""
        if frame is None or frame.size == 0:
            return
        x, y, w, h = self.zone
        if w <= 0 or h <= 0:
            return
        img_h, img_w = frame.shape[:2]
        x1 = max(0, min(x, img_w - 1))
        y1 = max(0, min(y, img_h - 1))
        x2 = max(0, min(x + w, img_w))
        y2 = max(0, min(y + h, img_h))
        if x2 <= x1 or y2 <= y1:
            return

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(frame, self.name, (x1+5, y1+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        for obj_id, obj_info in self.tracker.objects.items():
            if obj_info.get('disappeared_count', 0) > 0:
                continue
            cnt = obj_info.get('latest_contour')
            
            history = obj_info.get('grade_history', [])
            defect_frames = [g for g in history if g is not None]
            
            # Persistent Defect Tagging: Once a defect is spotted, it displays in RED
            if defect_frames:
                defect_counts = Counter(defect_frames)
                display_defect = defect_counts.most_common(1)[0][0]
                color = (0, 0, 255)
            else:
                display_defect = None
                color = (0, 255, 0)
            
            if cnt is not None and len(cnt) >= 3:
                smooth_cnt = smooth_contour(cnt, window=5)
                cv2.drawContours(frame, [smooth_cnt], -1, color, 3)
                
                cx, cy = obj_info['centroid']
                if hasattr(self.tracker, 'get_robust_size'):
                    disp_mm = self.tracker.get_robust_size(obj_id)
                    if disp_mm <= 0:
                        disp_mm = obj_info.get('max_mm', 0.0)
                else:
                    disp_mm = obj_info.get('max_mm', 0.0)
                x_b, y_b, w_b, h_b = cv2.boundingRect(cnt)
                
                # Line 1: Millimeter size
                line_size = f"{disp_mm:.1f} mm"
                
                # Line 2: Status
                if display_defect:
                    line_status = f"{display_defect.upper()}"
                    status_color = (0, 0, 255)      # Bright Red
                    badge_border = (0, 0, 255)
                else:
                    line_status = "GOOD"
                    status_color = (0, 255, 0)      # Bright Green
                    badge_border = (0, 255, 0)

                font = cv2.FONT_HERSHEY_DUPLEX
                scale_size = 1.05
                scale_status = 1.15
                thick = 2

                (w1, h1), _ = cv2.getTextSize(line_size, font, scale_size, thick)
                (w2, h2), _ = cv2.getTextSize(line_status, font, scale_status, thick)

                box_w = max(w1, w2) + 24
                box_h = h1 + h2 + 20

                # Position badge FLOATING ABOVE the cashew so cashew body is 100% visible
                bx1 = max(0, min(img_w - box_w - 1, cx - box_w // 2))
                by2 = y_b - 10
                by1 = by2 - box_h

                # If cashew is near the top of the frame, position badge below the cashew
                if by1 < 10:
                    by1 = y_b + h_b + 10
                    by2 = by1 + box_h

                bx2 = min(img_w - 1, bx1 + box_w)
                by2 = min(img_h - 1, by2)
                by1 = max(0, by1)

                # Solid dark high-contrast badge background with glowing status border
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), (15, 15, 15), -1)
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), badge_border, 2)

                # Big bold size in mm
                tx1 = bx1 + (box_w - w1) // 2
                ty1 = by1 + h1 + 6
                cv2.putText(frame, line_size, (tx1, ty1), font, scale_size, (255, 255, 255), thick, cv2.LINE_AA)

                # Big bold status (GOOD / BLACKDOT / BAD)
                tx2 = bx1 + (box_w - w2) // 2
                ty2 = ty1 + h2 + 10
                cv2.putText(frame, line_status, (tx2, ty2), font, scale_status, status_color, thick, cv2.LINE_AA)
    
    def close(self):
        pass

# =========================================================
# KEYBOARD CONTROL HANDLER (ZONES 1 TO 10)
# =========================================================

LAST_ESC_PRESS_TIME = 0.0

def handle_keyboard_controls(key, zone_configs, zone_processors):
    """
    Handle keyboard input for selecting and tuning Zone-1 through Zone-10.
    Keys 1-5: Zone 1 to 5 (Camera A)
    Keys 6-9: Zone 6 to 9 (Camera B)
    Key 0: Zone 10 (Camera B)
    Tab / N: Cycle selection
    WASD / Arrows: Movement
    +/- : Width
    [/] : Height
    C: Save config
    Q: Toggle display
    ESC: Exit (Requires double-press within 2.5s to prevent accidental shutdown)
    """
    global SELECTED_ZONE_INDEX, SHOW_DISPLAY, LAST_ESC_PRESS_TIME
    
    should_quit = False
    char_key = key & 0xFF
    
    # 1. Zone selection (1-9 for Zones 1-9, 0 for Zone 10)
    if ord('1') <= char_key <= ord('9'):
        idx = char_key - ord('1')
        if idx < len(zone_configs):
            SELECTED_ZONE_INDEX = idx
            print(f"\n[CONTROL] Selected {zone_configs[SELECTED_ZONE_INDEX]['name']} (Zone {idx+1}) for adjustment")
    elif char_key == ord('0'):
        if len(zone_configs) >= 10:
            SELECTED_ZONE_INDEX = 9
            print(f"\n[CONTROL] Selected {zone_configs[SELECTED_ZONE_INDEX]['name']} (Zone 10) for adjustment")
    elif char_key in [ord('\t'), ord('n'), ord('N')]:
        if SELECTED_ZONE_INDEX is None:
            SELECTED_ZONE_INDEX = 0
        else:
            SELECTED_ZONE_INDEX = (SELECTED_ZONE_INDEX + 1) % len(zone_configs)
        print(f"\n[CONTROL] Selected {zone_configs[SELECTED_ZONE_INDEX]['name']} for adjustment")
    
    # 2. Display window control (Q or q)
    elif char_key == ord('q') or char_key == ord('Q'):
        SHOW_DISPLAY = not SHOW_DISPLAY
        if SHOW_DISPLAY:
            print(f"\n[CONTROL] Display window OPENING...")
        else:
            print(f"\n[CONTROL] Display window HIDDEN (processing continues in background at maximum 60+ FPS). Press Q to reopen.")
    
    # 3. ESC to quit (Double-press confirmation within 2.5s)
    elif char_key == 27:
        now = time.time()
        if now - LAST_ESC_PRESS_TIME < 2.5:
            should_quit = True
            print(f"\n[CONTROL] ESC confirmed - Exiting grading system cleanly...")
        else:
            LAST_ESC_PRESS_TIME = now
            print(f"\n[CONTROL WARNING] ESC pressed once! Press ESC again within 2.5 seconds if you really want to EXIT.")
    
    # 4. Save zones configuration (C or c)
    elif char_key == ord('c') or char_key == ord('C'):
        save_zones_config(zone_configs)
    
    # 5. Zone adjustment (only if a zone is selected)
    elif SELECTED_ZONE_INDEX is not None and SELECTED_ZONE_INDEX < len(zone_configs):
        zone_config = zone_configs[SELECTED_ZONE_INDEX]
        x, y, w, h = zone_config['zone']
        modified = False
        action = ""
        
        # Movement
        if key in [2424832, 81, 37, 2] or char_key in [ord('a'), ord('A')]:
            x -= ZONE_ADJUST_STEP
            modified = True
            action = "moved LEFT"
        elif key in [2555904, 83, 39, 3] or char_key in [ord('d'), ord('D')]:
            x += ZONE_ADJUST_STEP
            modified = True
            action = "moved RIGHT"
        elif key in [2490368, 82, 38, 0] or char_key in [ord('w'), ord('W')]:
            y -= ZONE_ADJUST_STEP
            modified = True
            action = "moved UP"
        elif key in [2621440, 84, 40, 1] or char_key in [ord('s'), ord('S')]:
            y += ZONE_ADJUST_STEP
            modified = True
            action = "moved DOWN"
        
        # Width
        elif char_key in [ord('+'), ord('='), ord('k'), ord('K')]:
            w += ZONE_ADJUST_STEP
            modified = True
            action = "width INCREASED"
        elif char_key in [ord('-'), ord('_'), ord('h'), ord('H')]:
            w = max(50, w - ZONE_ADJUST_STEP)
            modified = True
            action = "width DECREASED"
        
        # Height
        elif char_key in [ord('['), ord('u'), ord('U')]:
            h = max(50, h - ZONE_ADJUST_STEP)
            modified = True
            action = "height DECREASED"
        elif char_key in [ord(']'), ord('j'), ord('J')]:
            h += ZONE_ADJUST_STEP
            modified = True
            action = "height INCREASED"
        
        if modified:
            new_zone = (x, y, w, h)
            zone_config['zone'] = new_zone
            if SELECTED_ZONE_INDEX < len(zone_processors):
                zone_processors[SELECTED_ZONE_INDEX].update_zone(new_zone)
            print(f"[CONTROL] {zone_config['name']} {action} → x={x}, y={y}, w={w}, h={h}")
    
    return should_quit, SHOW_DISPLAY

# =========================================================
# MAIN (MULTI-CAMERA A & B GRADING CORE)
# =========================================================

def main():
    global SELECTED_ZONE_INDEX, SHOW_DISPLAY, ZONE_CONFIGS

    print(f"\n{'='*70}")
    print(f" 360 DUAL-CAMERA INDUSTRIAL GRADING SYSTEM (CAM A & CAM B)")
    print(f"{'='*70}")

    # 1. Load grading ranges
    ranges = load_ranges(RANGES_FILE)
    if not ranges:
        print("Warning: No grading ranges loaded from value.txt")

    # 2. Connect Camera A and Camera B
    cam_a = HIKCashewCamera(cam_name="Cam-A (Zones 1-5)", cam_idx="1", serial_id="a")
    cam_b = HIKCashewCamera(cam_name="Cam-B (Zones 6-10)", cam_idx="2", serial_id="b")

    cam_a_connected = cam_a.connect()
    cam_b_connected = cam_b.connect()

    if not cam_a_connected and not cam_b_connected:
        print("\n[ERROR] Neither Camera A nor Camera B could be connected! Please check USB/GigE connections.")
        return

    # 3. Initialize Shared ONNX GPU Defect Filter
    quality_filter = CashewQualityFilter(YOLO_MODEL_PATH)

    # 4. Open Serial COM Ports for Controller A and Controller B
    com_port_a = read_com_port_from_file(MAIN_COM_FILE_A)
    com_port_b = read_com_port_from_file(MAIN_COM_FILE_B)

    arduino_a = None
    if com_port_a:
        try:
            arduino_a = serial.Serial(port=com_port_a, baudrate=115200, timeout=1)
            print(f"[SERIAL A] Connected on {com_port_a} for Belts 1-5. Waiting for bootloader...")
            time.sleep(1.5)
            arduino_a.reset_input_buffer()
            arduino_a.reset_output_buffer()
            print(f"[SERIAL A] Ready on {com_port_a}!")
        except Exception as e:
            print(f"[SERIAL A ERROR] {com_port_a}: {e}")

    arduino_b = None
    if com_port_b:
        if com_port_a and com_port_b.upper() == com_port_a.upper() and arduino_a is not None:
            # Same COM port used for both cameras -> Share single opened serial connection safely!
            arduino_b = arduino_a
            print(f"[SERIAL B] Sharing {com_port_b} with Camera A (Single Controller / Shared Port Mode)!")
        else:
            try:
                arduino_b = serial.Serial(port=com_port_b, baudrate=115200, timeout=1)
                print(f"[SERIAL B] Connected on {com_port_b} for Belts 6-10. Waiting for bootloader...")
                time.sleep(1.5)
                arduino_b.reset_input_buffer()
                arduino_b.reset_output_buffer()
                print(f"[SERIAL B] Ready on {com_port_b}!")
            except Exception as e:
                print(f"[SERIAL B ERROR] {com_port_b}: {e}")

    # 5. Initialize Ejection Queues (Isolated Worker Threads for Zero Lock Contention)
    ejection_q_a = EjectionQueue(arduino=arduino_a, delay_seconds=DELAY_SECONDS, name="A")
    ejection_q_b = EjectionQueue(arduino=arduino_b, delay_seconds=DELAY_SECONDS, name="B")
    ejection_q_a.start()
    ejection_q_b.start()

    # 6. Initialize Zone Processors:
    # Zone-1 to Zone-5 -> Camera A (ejection_q_a)
    # Zone-6 to Zone-10 -> Camera B (ejection_q_b)
    zone_processors_a = []
    zone_processors_b = []
    all_zone_processors = []

    for i, zone_config in enumerate(ZONE_CONFIGS):
        if i < 5:
            processor = ZoneProcessor(zone_config, ranges, ejection_queue=ejection_q_a)
            zone_processors_a.append(processor)
        else:
            processor = ZoneProcessor(zone_config, ranges, ejection_queue=ejection_q_b)
            zone_processors_b.append(processor)
        all_zone_processors.append(processor)

    try:
        cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
    except Exception as e:
        print(f"[DISPLAY WARNING] GUI windows not supported by current OpenCV build: {e}")

    print(f"\n{'='*70}")
    print(f" 10 INDEPENDENT ZONES ACTIVE ACROSS 2 CAMERAS & 2 COM PORTS")
    print(f"   Camera A: Zones 1-5  -> COM: {com_port_a or 'None'}")
    print(f"   Camera B: Zones 6-10 -> COM: {com_port_b or 'None'}")
    print(f"{'='*70}")
    print(f"\nKEYBOARD CONTROLS:")
    print(f"  1-5      : Select Zone-1 to Zone-5 (Camera A)")
    print(f"  6-9      : Select Zone-6 to Zone-9 (Camera B)")
    print(f"  0        : Select Zone-10 (Camera B)")
    print(f"  TAB / N  : Cycle through selected zone")
    print(f"  Arrows   : Move selected zone (UP/DOWN/LEFT/RIGHT)")
    print(f"  +/-      : Increase/Decrease width")
    print(f"  [ ]      : Decrease/Increase height")
    print(f"  C        : Save all 10 zones configuration to JSON")
    print(f"  Q        : Toggle display window ON/OFF")
    print(f"  ESC      : Quit program")
    print(f"{'='*70}\n")

    # Parallel Camera Processing Pool
    cam_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="CamWorker")
    
    def process_camera_stream(frame, processors, filter_obj):
        if frame is None or frame.size == 0:
            return []
        dets = filter_obj.detect_frame(frame, conf_thresh=THRESH_BLACKDOT) if filter_obj else []
        for p in processors:
            try:
                p.process_frame(frame, quality_filter=filter_obj, frame_detections=dets)
            except Exception:
                pass
        return dets

    last_config_mtime = 0
    if os.path.exists(ZONES_CONFIG_FILE):
        last_config_mtime = os.path.getmtime(ZONES_CONFIG_FILE)

    last_display_time = 0.0

    try:
        frame_counter = 0
        while True:
            frame_counter += 1
            if frame_counter % 1000 == 0:
                gc.collect()

            # Retrieve newest frames from both camera background threads
            frame_a = cam_a.get_frame() if cam_a_connected else None
            frame_b = cam_b.get_frame() if cam_b_connected else None

            if frame_counter % 30 == 0:
                if cam_a_connected:
                    cam_a.check_and_update_parameters()
                if cam_b_connected:
                    cam_b.check_and_update_parameters()

            if frame_a is None and frame_b is None:
                try:
                    cv2.waitKeyEx(1)
                except Exception:
                    pass
                time.sleep(0.002)
                continue

            # Reload zones_config.json dynamically if edited externally
            if frame_counter % 30 == 0:
                try:
                    if os.path.exists(ZONES_CONFIG_FILE):
                        mtime = os.path.getmtime(ZONES_CONFIG_FILE)
                        if mtime > last_config_mtime:
                            last_config_mtime = mtime
                            print("\n[CONFIG] zones_config.json changed! Reloading all 10 zones...")
                            new_configs = load_zones_config()
                            for i, new_z in enumerate(new_configs):
                                if i < len(ZONE_CONFIGS):
                                    ZONE_CONFIGS[i]['zone'] = tuple(new_z['zone'])
                                else:
                                    ZONE_CONFIGS.append({'zone': tuple(new_z['zone']), 'name': new_z.get('name', f'Zone-{i+1}')})
                                if i < len(all_zone_processors):
                                    all_zone_processors[i].update_zone(ZONE_CONFIGS[i]['zone'])
                except Exception as e:
                    print(f"[CONFIG ERROR] {e}")

            # Concurrent Parallel Vision Processing for Cam A & Cam B (60+ FPS Throughput)
            futures = []
            if frame_a is not None:
                futures.append(cam_pool.submit(process_camera_stream, frame_a, zone_processors_a, quality_filter))
            if frame_b is not None:
                futures.append(cam_pool.submit(process_camera_stream, frame_b, zone_processors_b, quality_filter))
            
            for fut in futures:
                try:
                    fut.result()
                except Exception:
                    pass

            now_time = time.perf_counter()
            # Throttle GUI display rendering to 30 FPS to leave 100% compute bandwidth for 60+ FPS AI sorting
            if SHOW_DISPLAY and (now_time - last_display_time >= 0.033):
                last_display_time = now_time

                # Build Display Canvases for Camera A and Camera B
                canvas_a = None
                if frame_a is not None:
                    display_a = np.zeros_like(frame_a)
                    img_h, img_w = frame_a.shape[:2]
                    for z in ZONE_CONFIGS[:5]:
                        x, y, w, h = z['zone']
                        x1, y1 = max(0, min(x, img_w)), max(0, min(y, img_h))
                        x2, y2 = max(0, min(x + w, img_w)), max(0, min(y + h, img_h))
                        if x2 > x1 and y2 > y1:
                            display_a[y1:y2, x1:x2] = frame_a[y1:y2, x1:x2]
                    for processor in zone_processors_a:
                        processor.draw_zone(display_a)
                    
                    # Highlight selected zone if on Camera A (0-4)
                    if SELECTED_ZONE_INDEX is not None and 0 <= SELECTED_ZONE_INDEX < 5:
                        sel_zone = ZONE_CONFIGS[SELECTED_ZONE_INDEX]['zone']
                        sx, sy, sw, sh = sel_zone
                        cv2.rectangle(display_a, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 4)
                        cv2.putText(display_a, f"SELECTED: {ZONE_CONFIGS[SELECTED_ZONE_INDEX]['name']}", (sx+5, sy+40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    canvas_a = display_a
                else:
                    canvas_a = np.zeros((1080, 1920, 3), dtype=np.uint8)
                    cv2.putText(canvas_a, "CAMERA A (ZONES 1-5): OFFLINE / DISCONNECTED", (80, 540),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

                canvas_b = None
                if frame_b is not None:
                    display_b = np.zeros_like(frame_b)
                    img_h, img_w = frame_b.shape[:2]
                    for z in ZONE_CONFIGS[5:10]:
                        x, y, w, h = z['zone']
                        x1, y1 = max(0, min(x, img_w)), max(0, min(y, img_h))
                        x2, y2 = max(0, min(x + w, img_w)), max(0, min(y + h, img_h))
                        if x2 > x1 and y2 > y1:
                            display_b[y1:y2, x1:x2] = frame_b[y1:y2, x1:x2]
                    for processor in zone_processors_b:
                        processor.draw_zone(display_b)
                    
                    # Highlight selected zone if on Camera B (5-9)
                    if SELECTED_ZONE_INDEX is not None and 5 <= SELECTED_ZONE_INDEX < 10:
                        sel_zone = ZONE_CONFIGS[SELECTED_ZONE_INDEX]['zone']
                        sx, sy, sw, sh = sel_zone
                        cv2.rectangle(display_b, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 4)
                        cv2.putText(display_b, f"SELECTED: {ZONE_CONFIGS[SELECTED_ZONE_INDEX]['name']}", (sx+5, sy+40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    canvas_b = display_b
                else:
                    canvas_b = np.zeros((1080, 1920, 3), dtype=np.uint8)
                    cv2.putText(canvas_b, "CAMERA B (ZONES 6-10): OFFLINE / DISCONNECTED", (80, 540),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

                # Resize both views for clean side-by-side split monitor display
                target_h = 720
                target_w = 960
                view_a = cv2.resize(canvas_a, (target_w, target_h))
                view_b = cv2.resize(canvas_b, (target_w, target_h))

                # Add Camera Header Badges
                cv2.rectangle(view_a, (10, 10), (380, 50), (30, 30, 30), -1)
                cv2.putText(view_a, "[ CAMERA A : ZONES 1 - 5 ]", (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                cv2.rectangle(view_b, (10, 10), (380, 50), (30, 30, 30), -1)
                cv2.putText(view_b, "[ CAMERA B : ZONES 6 - 10 ]", (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                combined_display = np.hstack((view_a, view_b))
                # Draw center vertical divider
                cv2.line(combined_display, (target_w, 0), (target_w, target_h), (255, 255, 255), 2)

                try:
                    cv2.imshow("Full Camera", combined_display)
                except Exception:
                    pass

            key = -1
            if SHOW_DISPLAY:
                try:
                    key = cv2.waitKey(1)
                except Exception:
                    pass
            else:
                time.sleep(0.002)

            if key != -1 and key != 255 and (key & 0xFF) != 255:
                should_quit, SHOW_DISPLAY = handle_keyboard_controls(key, ZONE_CONFIGS, all_zone_processors)
                if should_quit:
                    break

    except Exception as e:
        import traceback
        print(f"\n[CRITICAL ERROR in main loop]: {e}")
        traceback.print_exc()
    finally:
        cam_a.close()
        cam_b.close()
        for p in all_zone_processors:
            p.close()
        ejection_q_a.stop()
        ejection_q_b.stop()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        if arduino_a:
            try:
                arduino_a.close()
                print("[SERIAL A] Closed.")
            except Exception:
                pass
        if arduino_b and arduino_b is not arduino_a:
            try:
                arduino_b.close()
                print("[SERIAL B] Closed.")
            except Exception:
                pass
        print("[SYSTEM] Grading stopped cleanly.")

if __name__ == "__main__":
    main()