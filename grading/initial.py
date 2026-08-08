import sys, os, platform
from ctypes import *
import numpy as np
import cv2
import serial
import time
import re
import json
# YOLO is disabled permanently to ensure lightning-fast OpenCV processing (< 50ms per cashew)
YOLO_AVAILABLE = False
import concurrent.futures
import threading
from collections import Counter
import gc
import math
import datetime
import ctypes

# Make Windows timer 1ms instead of 15.6ms for highly precise time.sleep()
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except:
    pass

# ========================================================
# CONFIG
# =========================================================

SERIAL_FILE = r"C:\Users\i7\Desktop\camera_serial(b).txt" 
RANGES_FILE = r"D:\4_belt_main\4_belt\range\value.txt"  # Grading ranges file

# ================= CUSTOM PROCESS ZONES =================
# We now use a SINGLE COM PORT for both zones.
# Format: (x, y, width, height)

MAIN_COM_FILE = r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt"

DEFAULT_ZONE_CONFIGS = [
    {
        'zone': (50, 100, 250, 800),
        'name': 'Zone-1'
    },
    {
        'zone': (350, 100, 250, 800),
        'name': 'Zone-2'
    },
    {
        'zone': (650, 100, 250, 800),
        'name': 'Zone-3'
    },
    {
        'zone': (950, 100, 250, 800),
        'name': 'Zone-4'
    },
    {
        'zone': (1250, 100, 250, 800),
        'name': 'Zone-5'
    }
]

ZONES_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zones_config.json")
DETECTIONS_FOLDER = r"f:\server\360\detections"

# Ensure detections folder exists
if not os.path.exists(DETECTIONS_FOLDER):
    os.makedirs(DETECTIONS_FOLDER)
    print(f"Created detections folder: {DETECTIONS_FOLDER}")

def load_zones_config():
    if os.path.exists(ZONES_CONFIG_FILE):
        try:
            with open(ZONES_CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                # Convert list zone back to tuple
                for c in configs:
                    if 'zone' in c and isinstance(c['zone'], list):
                        c['zone'] = tuple(c['zone'])
                print(f"Loaded zone configurations from {ZONES_CONFIG_FILE}")
                return configs
        except Exception as e:
            print(f"Error loading zones config: {e}. Using default.")
    return DEFAULT_ZONE_CONFIGS

def save_zones_config(configs):
    try:
        with open(ZONES_CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=4)
        print(f"\n[SAVE] Zone configuration saved to {ZONES_CONFIG_FILE}")
    except Exception as e:
        print(f"\n[SAVE] Error saving zones config: {e}")

ZONE_CONFIGS = load_zones_config()

# === DETECTION SENSITIVITY CONTROL PANEL (TUNE HERE) ===
MIN_CASHEW_AREA = 2000       # Lowered to 2000 to handle rotating cashews (narrow side has less area)
MIN_MM_SIZE = 15.0           # Minimum measurement to log/act on cashew
MAX_CASHEW_MM = 33.0         # Any object larger than 45mm is likely a roller
MAX_ASPECT_RATIO = 3.0       # Ignore extremely long objects (Rollers)

# General Shape/Color Segmentation (Validation only)
HSV_LOWER = np.array([0, 30, 15])     # Higher Saturation to ensure it's not the belt
HSV_UPPER = np.array([40, 255, 255])  # Upper hue/sat/val for cashew detection

YOLO_CONF_THRESHOLD = 0.40   # [0.1-1.0] AI strictness: Higher = Fewer defect calls
YOLO_STRICT_BYPASS = 0.85    # [0.1-1.0] If AI is 85% sure it is GOOD, skip heuristics

# OpenCV Heuristic Backups (Only used if AI is not 85% sure)
OILY_RATIO_THRESHOLD = 0.95  # [0.1-1.0] Coverage needed to call it OILY 
SHELL_PIXEL_THRESHOLD = 15000 # [Pixels] Brown area needed for SHELL/UNPEEL
BLACKDOT_RATIO_THRESHOLD = 0.015 # [Ratio] INCREASE this to ignore small dots on good ones
BLACKDOT_MIN_COUNT = 1       # [Count] Minimum number of internal dots to eject
# =========================================================

PIXEL_TO_MM_RATIO = 0.111  # 1 px = 0.0937 mm
MAX_TRACKING_DISTANCE = 250 # Increased to 250 to follow fast-moving cashews without duplicate IDs

# =========================================================
# COLOR GRADING SAMPLES (FROM REFERENCE)
# =========================================================
samples = np.array([
    [35.3, 75, 51], [38.2, 74, 29], [34.1, 74, 44], [34.7, 78, 48],
    [38.1, 81, 47], [39.5, 57, 54], [34.7, 82, 40], [35.4, 74, 41],
    [31.5, 71, 33], [39.2, 66, 47], [35.6, 75, 53], [44.5, 57, 43],
    [38.4, 90, 39], [36.3, 73, 38], [43.1, 78, 20], [42.7, 79, 33],
    [29.6, 76, 38], [33.6, 48, 18], [33.6, 100, 93], [37.1, 82, 20]
])
hsv_cv = samples.astype(np.float32)
hsv_cv[:, 0] /= 2            # Hue 0-179
hsv_cv[:, 1:] *= 2.55        # Sat/Val 0-255
H, S, V = hsv_cv[:, 0], hsv_cv[:, 1], hsv_cv[:, 2]
H_tol, S_tol, V_tol = 2, 5, 5

LOWER_OILY = np.array([
    max(int(H.min()) - H_tol, 0),
    max(int(S.min()) - S_tol, 0),
    max(int(V.min()) - V_tol, 0)
], dtype=np.uint8)

UPPER_OILY = np.array([
    min(int(H.max()) + H_tol, 179),
    min(int(S.max()) + S_tol, 255),
    min(int(V.max()) + V_tol, 255)
], dtype=np.uint8)

# =========================================================
# KEYBOARD CONTROL CONFIGURATION
# =========================================================
SELECTED_ZONE_INDEX = None  # Currently selected zone for adjustment (0-4)
SHOW_DISPLAY = True  # Whether to show the display window
ZONE_ADJUST_STEP = 10  # Pixels to move/resize per keypress

# =========================================================
# YOLO CONFIGURATION
# =========================================================
YOLO_MODEL_PATH = r"c:\Users\i7\Desktop\360\best.pt"  # <--- UPDATE THIS PATH
# Broadened 'good' list to match various possible model training class names
GOOD_CLASS_NAMES = ['good', 'cashew', 'white', 'full', 'whole', 'object'] 

# =========================================================
# GRADING CONFIGURATION
# =========================================================

# Commands for all grades depending on the zone they are processed in
ZONE_COMMAND_MAP = {
    'Zone-1': '11|',
    'Zone-2': '16|',
    'Zone-3': '12|',
    'Zone-4': '13|',
    'Zone-5': '14|'
}

# =========================================================
# LOAD SDK
# =========================================================

if platform.system()=="Windows":
    SDK_PATH=r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
    if os.path.exists(SDK_PATH):
        sys.path.append(SDK_PATH)

    # Add runtime DLL path
    DLL_PATH = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
    if os.path.exists(DLL_PATH):
        os.environ['PATH'] = DLL_PATH + os.pathsep + os.environ['PATH']
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(DLL_PATH)

try:
    from MvCameraControl_class import *  # type: ignore
    SDK_IMPORTED=True
except Exception as e:
    print(f"SDK not loaded: {e}")
    SDK_IMPORTED=False

# =========================================================
# READ SERIAL
# =========================================================

def read_target_serial():
    try:
        with open(SERIAL_FILE,"r") as f:
            return f.read().strip()
    except:
        print("Serial file missing")
        return None

# =========================================================
# READ COM PORT FROM FILE
# =========================================================

def read_com_port_from_file(file_path):
    """
    Read COM port string from file and normalize to e.g. 'COM6'.
    Accepts '6', 'COM6', 'ASRL6::INSTR', etc.
    Returns normalized COM port string or None on error.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"COM port file not found: {file_path}")
        return None
    except Exception as e:
        print(f"Error reading COM port file: {e}")
        return None

    if not content:
        print("COM port file is empty")
        return None

    # Try extract first group of digits
    m = re.search(r'(\d+)', content)
    if m:
        return f"COM{m.group(1)}"

    # Fallbacks
    if content.upper().startswith('COM'):
        return content
    return content

# =========================================================
# GRADING SYSTEM
# =========================================================

def load_ranges(file_path):
    """Load grading ranges from file"""
    ranges = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                part = line.strip()
                if not part:
                    continue
                range_part, grade = part.split(':')
                start, end = map(int, range_part.split('-'))
                ranges.append((start, end, grade.strip()))
        print(f"Loaded {len(ranges)} grading ranges")
        return ranges
    except Exception as e:
        print(f"Error loading ranges: {e}")
        return []

def get_grade(mm_value, ranges):
    """Get grade based on mm value"""
    for start, end, grade in ranges:
        if start <= mm_value <= end:
            return grade
    return None

# =========================================================
# COLOR GRADING FUNCTIONS (EXTRACTED)
# =========================================================

def is_oily_cashew(img_bgr, min_oily_ratio=None):
    """Detect if a cashew is oily based on HSV mask ratio"""
    if min_oily_ratio is None:
        min_oily_ratio = OILY_RATIO_THRESHOLD
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    oily = cv2.inRange(hsv, LOWER_OILY, UPPER_OILY)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, cashew_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cashew_pixels = np.count_nonzero(cashew_bin)
    if cashew_pixels == 0:
        return False
    oily_pixels = np.count_nonzero(cv2.bitwise_and(oily, cashew_bin))
    ratio = oily_pixels / cashew_pixels
    return ratio >= min_oily_ratio

def check_rgb_defects(image):
    """Check for Shell, Orange, and Color defects using HSV ranges"""
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    except Exception as e:
        return False, False, False

    mask_shell = cv2.inRange(hsv, np.array([8, 30, 9]), np.array([13, 255, 90]))
    mask_orange = cv2.inRange(hsv, np.array([26, 21, 20]), np.array([26, 91, 81])) 
    mask_color = cv2.inRange(hsv, np.array([10, 162, 32]), np.array([26, 255, 72]))

    # Use manual pixel thresholds from the Control Panel at top
    shell = np.count_nonzero(mask_shell) > SHELL_PIXEL_THRESHOLD
    orange = np.count_nonzero(mask_orange) > 1000
    color = np.count_nonzero(mask_color) > 1000

    return shell, orange, color

def detect_black_dots(gray_crop, min_dot_ratio=None, min_dot_count=None):
    """Detect black dots using contour hierarchy (holes)"""
    if min_dot_ratio is None: min_dot_ratio = BLACKDOT_RATIO_THRESHOLD
    if min_dot_count is None: min_dot_count = BLACKDOT_MIN_COUNT
    blurred = cv2.GaussianBlur(gray_crop, (5, 5), 0)
    _, bin_crop = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    total_area = np.count_nonzero(bin_crop)
    if total_area == 0:
        return False, 0

    contours, hierarchy = cv2.findContours(bin_crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    black_dots = 0
    if hierarchy is not None:
        for i, contour in enumerate(contours):
            if hierarchy[0][i][3] != -1:  # Has a parent (it's a hole)
                area = cv2.contourArea(contour)
                if area >= total_area * min_dot_ratio:
                    black_dots += 1

    return black_dots >= min_dot_count, black_dots

# =========================================================
# YOLO FILTER CLASS
# =========================================================

class CashewQualityFilter:
    def __init__(self, model_path):
        self.model = None
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                print(f"YOLO Model loaded from: {model_path}")
                if self.model and hasattr(self.model, 'names'):
                    print(f"  [STARTUP] YOLO Classes: {self.model.names}")
            except Exception as e:
                print(f"Error loading YOLO model: {e}")

    def get_cashew_categories_batch(self, crops):
        """
        Run inference on a batch of cashew crops.
        Returns a list of (class_name, confidence) or (None, 0).
        """
        if self.model is None or not crops:
            return [(None, 0)] * len(crops)
            
        try:
            start_ai = time.time()
            
            # Force CPU inference because PyTorch currently lacks RTX 5000 (Blackwell) support.
            # With our optimizations, CPU inference now only takes ~100ms which is lightning fast.
            results = self.model(crops, verbose=False, conf=YOLO_CONF_THRESHOLD, device='cpu', imgsz=224)
            
            ai_time = (time.time() - start_ai) * 1000
            if len(crops) > 0:
                print(f"[AI CORE] Processed {len(crops)} cashews in {ai_time:.1f}ms ({(ai_time/len(crops)):.1f}ms/crop)")
            
            batch_results = []
            for result in results:
                if len(result.boxes) > 0:
                    found_good = False
                    for box in result.boxes:
                        cls_name = self.model.names[int(box.cls[0])].lower()
                        if cls_name in [n.lower() for n in GOOD_CLASS_NAMES]:
                            batch_results.append((cls_name, float(box.conf[0])))
                            found_good = True
                            break
                    if not found_good:
                        best_box = result.boxes[0]
                        batch_results.append((self.model.names[int(best_box.cls[0])].lower(), float(best_box.conf[0])))
                else:
                    batch_results.append((None, 0))
            return batch_results
        except Exception as e:
            print(f"    [YOLO BATCH ERROR] {e}")
            return [(None, 0)] * len(crops)

# =========================================================
# CAMERA CLASS
# =========================================================

class HIKCashewCamera:

    def __init__(self):
        self.cam=None
        self.is_grabbing=False
        self.nPayloadSize=0

    def connect(self):

        target_serial=read_target_serial()
        if not target_serial:
            return False

        print("Target Serial:",target_serial)

        self.cam=MvCamera()

        deviceList=MV_CC_DEVICE_INFO_LIST()
        tlayerType=MV_GIGE_DEVICE|MV_USB_DEVICE

        if MvCamera.MV_CC_EnumDevices(tlayerType,deviceList)!=0:
            return False

        selected=None

        for i in range(deviceList.nDeviceNum):

            info=cast(deviceList.pDeviceInfo[i],
                      POINTER(MV_CC_DEVICE_INFO)).contents

            try:
                if info.nTLayerType==MV_GIGE_DEVICE:
                    serial=bytes(info.SpecialInfo.stGigEInfo.chSerialNumber)\
                           .decode(errors="ignore").strip("\x00")

                elif info.nTLayerType==MV_USB_DEVICE:
                    serial=bytes(info.SpecialInfo.stUsb3VInfo.chSerialNumber)\
                           .decode(errors="ignore").strip("\x00")
                else:
                    continue

                print("Camera",i,"Serial:",serial)

                if serial==target_serial:
                    selected=info
                    break
            except:
                pass

        if selected is None:
            print("Camera serial not found")
            return False

        if self.cam.MV_CC_CreateHandle(selected)!=0: return False
        if self.cam.MV_CC_OpenDevice(MV_ACCESS_Control,0)!=0: return False

        self.cam_idx = "1"
        try:
            ref_path = os.path.join(os.path.dirname(__file__), "wate", "camera_ref.txt")
            if os.path.exists(ref_path):
                with open(ref_path, "r") as f:
                    refs = json.load(f).get("references", ["", "", ""])
                    for idx, ref in enumerate(refs):
                        if ref.strip() == target_serial.strip():
                            self.cam_idx = str(idx + 1)
                            break
        except: pass

        params = {}
        try:
            params_path = os.path.join(os.path.dirname(__file__), "camera_params.json")
            if os.path.exists(params_path):
                with open(params_path, "r") as f:
                    params = json.load(f).get(self.cam_idx, {})
        except: pass

        # Set to saved resolution or max if missing
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
            w_val = max(32, min(w_max, w_val))
            w_val = (w_val // 8) * 8
            self.cam.MV_CC_SetIntValue("Width", w_val)
            self.current_width = w_val
            
            h_val = int(params.get("height", h_max))
            h_val = max(8, min(h_max, h_val))
            h_val = (h_val // 4) * 4
            self.cam.MV_CC_SetIntValue("Height", h_val)
            self.current_height = h_val
            
            off_x_val = int(params.get("offsetX", 0))
            off_x_val = (off_x_val // 8) * 8
            self.cam.MV_CC_SetIntValue("OffsetX", off_x_val)
            self.current_offset_x = off_x_val
            
            off_y_val = int(params.get("offsetY", 0))
            off_y_val = (off_y_val // 2) * 2
            self.cam.MV_CC_SetIntValue("OffsetY", off_y_val)
            self.current_offset_y = off_y_val
            
            # --- CRITICAL FIX FOR MOTION BLUR ---
            # Turn off Auto Exposure & Auto Gain to prevent the camera from artificially 
            # increasing exposure time in dark areas, which causes massive motion blur on the belt.
            self.cam.MV_CC_SetEnumValue("ExposureAuto", 0) # 0 = Off
            self.cam.MV_CC_SetEnumValue("GainAuto", 0)     # 0 = Off
            
            if "exposure" in params and params["exposure"]:
                self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
            else:
                # Default to 6000us (6ms) - extremely fast shutter to freeze fast-moving cashews
                self.cam.MV_CC_SetFloatValue("ExposureTime", 6000.0)
                
            if "gain" in params and params["gain"]:
                self.cam.MV_CC_SetFloatValue("Gain", float(params["gain"]))
                
            print(f"[CAMERA] Set initial parameters: {w_val}x{h_val} offsets: {off_x_val},{off_y_val}")
        except Exception as e:
            print(f"[CAMERA] Failed to set parameters: {e}")

        self.cam.MV_CC_SetEnumValue("TriggerMode",MV_TRIGGER_MODE_OFF)

        stParam=MVCC_INTVALUE()
        memset(byref(stParam),0,sizeof(stParam))
        self.cam.MV_CC_GetIntValue("PayloadSize",stParam)
        self.nPayloadSize=stParam.nCurValue

        # Background thread handles buffer clearing now, so we let the camera run at its native speed

        if self.cam.MV_CC_StartGrabbing()!=0:
            return False

        self.is_grabbing=True
        print("Camera connected")
        
        # ==============================================================
        # CRITICAL ZERO-LAG FIX: Background Thread Grabbing
        # This thread runs at maximum speed, constantly pulling frames
        # out of the camera's internal hardware buffer so it NEVER fills up!
        # ==============================================================
        self.frame_lock = threading.Lock()
        self.latest_raw = None
        self.latest_info = None
        self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self.grab_thread.start()
        
        return True
        
    def _grab_loop(self):
        current_data_size = self.nPayloadSize
        data = (c_ubyte * current_data_size)()
        frame_info = MV_FRAME_OUT_INFO_EX()
        
        while self.is_grabbing:
            try:
                # Re-allocate buffer if resolution/payload size was changed dynamically
                if getattr(self, 'nPayloadSize', current_data_size) != current_data_size:
                    current_data_size = self.nPayloadSize
                    data = (c_ubyte * current_data_size)()
                    
                memset(byref(frame_info), 0, sizeof(frame_info))
                ret = self.cam.MV_CC_GetOneFrameTimeout(byref(data), current_data_size, frame_info, 1000)
                
                if ret == 0:
                    grab_time = time.perf_counter()
                    # Copy the raw bytes out of the buffer safely using ctypes
                    raw_bytes = string_at(byref(data), frame_info.nFrameLen)
                    
                    with self.frame_lock:
                        self.latest_raw = raw_bytes
                        self.latest_info = (frame_info.nWidth, frame_info.nHeight, frame_info.enPixelType)
                        self.latest_time = grab_time
                else:
                    # If ret != 0, camera might be temporarily stopped for param updates
                    time.sleep(0.01)
            except Exception as e:
                print(f"[CAMERA_THREAD] Exception: {e}")
                time.sleep(0.1)

    def check_and_update_parameters(self):
        params_path = os.path.join(os.path.dirname(__file__), "camera_params.json")
        if not os.path.exists(params_path): return
        try:
            mtime = os.path.getmtime(params_path)
            if not hasattr(self, 'last_params_mtime'):
                self.last_params_mtime = mtime
                return
            if mtime > self.last_params_mtime:
                self.last_params_mtime = mtime
                print("\n[CAMERA] camera_params.json changed! Reloading...")
                with open(params_path, "r") as f:
                    params = json.load(f).get(self.cam_idx, {})
                if "exposure" in params and params["exposure"] is not None:
                    self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
                if "gain" in params and params["gain"] is not None:
                    self.cam.MV_CC_SetFloatValue("Gain", float(params["gain"]))
                
                res_changed = False
                if "width" in params and params["width"] is not None and int(params["width"]) != getattr(self, 'current_width', -1): res_changed = True
                if "height" in params and params["height"] is not None and int(params["height"]) != getattr(self, 'current_height', -1): res_changed = True
                if "offsetX" in params and params["offsetX"] is not None and int(params["offsetX"]) != getattr(self, 'current_offset_x', -1): res_changed = True
                if "offsetY" in params and params["offsetY"] is not None and int(params["offsetY"]) != getattr(self, 'current_offset_y', -1): res_changed = True
                
                if res_changed:
                    print("[CAMERA] Resolution/Offset changed, restarting grab...")
                    self.cam.MV_CC_StopGrabbing()
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
                    
                    stParam = MVCC_INTVALUE()
                    memset(byref(stParam), 0, sizeof(stParam))
                    self.cam.MV_CC_GetIntValue("PayloadSize", stParam)
                    self.nPayloadSize = stParam.nCurValue
                    self.cam.MV_CC_StartGrabbing()
        except Exception as e:
            print(f"[CAMERA] Error applying parameters: {e}")

    # -------- Frame Capture (all pixel formats) --------
    def get_frame(self):
        if not getattr(self, 'is_grabbing', False):
            return None

        # Instantly retrieve the absolute freshest frame from the background thread
        with self.frame_lock:
            if self.latest_raw is None:
                return None
            raw_bytes = self.latest_raw
            w, h, pf = self.latest_info
            self.last_returned_time = getattr(self, 'latest_time', time.perf_counter())

        # Convert raw bytes to numpy array
        img = np.frombuffer(raw_bytes, dtype=np.uint8)

        try:
            if pf==PixelType_Gvsp_BGR8_Packed:
                return img.reshape((h,w,3))

            elif pf==PixelType_Gvsp_RGB8_Packed:
                rgb=img.reshape((h,w,3))
                return cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)

            elif pf==PixelType_Gvsp_Mono8:
                mono=img.reshape((h,w))
                return cv2.cvtColor(mono,cv2.COLOR_GRAY2BGR)

            elif pf==PixelType_Gvsp_BayerRG8:
                return cv2.cvtColor(img.reshape((h,w)),cv2.COLOR_BAYER_RG2BGR)

            elif pf==PixelType_Gvsp_BayerGB8:
                return cv2.cvtColor(img.reshape((h,w)),cv2.COLOR_BAYER_GB2BGR)

            elif pf==PixelType_Gvsp_BayerBG8:
                return cv2.cvtColor(img.reshape((h,w)),cv2.COLOR_BAYER_BG2BGR)

            elif pf==PixelType_Gvsp_BayerGR8:
                return cv2.cvtColor(img.reshape((h,w)),cv2.COLOR_BAYER_GR2BGR)

            else:
                mono=img.reshape((h,w))
                return cv2.cvtColor(mono,cv2.COLOR_GRAY2BGR)

        except:
            return None

    def close(self):
        if self.is_grabbing:
            self.cam.MV_CC_StopGrabbing()
            self.cam.MV_CC_CloseDevice()
            self.cam.MV_CC_DestroyHandle()

# =========================================================
# OBJECT TRACKING CLASS
# =========================================================

class ObjectTracker:
    """
    Tracks multiple cashew objects independently within a zone
    - Assigns unique IDs
    - Collects size measurements (mm)
    - Stores largest mm per object
    - Detects when objects exit ROI
    - Handles flickering/missing frames
    """
    
    def __init__(self, zone_name, max_distance=4000, max_disappeared=35):
        self.zone_name = zone_name
        self.next_id = 1
        self.objects = {}  # {id: {'centroid': (x,y), 'latest_contour': None, 'is_good': True, ...}}
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        
    def update(self, contours, is_good_flags, grades, crops, frame_timestamp=None):
        """
        Update tracked objects with new contours and their quality assessment
        """
        if frame_timestamp is None:
            frame_timestamp = time.perf_counter()
        current_centroids = []
        current_sizes = []
        
        for i, c in enumerate(contours):
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                rect = cv2.minAreaRect(c)
                w, h = rect[1]
                mm_size = max(w, h) * PIXEL_TO_MM_RATIO
                
                current_centroids.append((cx, cy))
                current_sizes.append(mm_size)
        
        # Match current detections to existing objects
        object_ids = list(self.objects.keys())
        matched_objects = set()
        matched_detections = set()
        
        for i, curr_centroid in enumerate(current_centroids):
            min_dist = float('inf')
            min_id = None
            for obj_id in object_ids:
                if obj_id in matched_objects: continue
                old_centroid = self.objects[obj_id]['centroid']
                dy = curr_centroid[1] - old_centroid[1]
                
                # PREVENT MERGING: Cashews only travel DOWN on the belt.
                # If dy < -150, the new centroid is ABOVE the old one (preventing new cashews from stealing old IDs!).
                if dy < -150:
                    continue
                    
                dist = math.hypot(curr_centroid[0] - old_centroid[0], dy)
                if dist < min_dist:
                    min_dist = dist; min_id = obj_id
            
            if min_dist < self.max_distance and min_id is not None:
                self.objects[min_id]['prev_centroid'] = self.objects[min_id]['centroid']
                self.objects[min_id]['prev_time'] = self.objects[min_id].get('curr_time', frame_timestamp)
                self.objects[min_id]['curr_time'] = frame_timestamp
                
                self.objects[min_id]['centroid'] = curr_centroid
                self.objects[min_id]['measurements'].append(current_sizes[i])
                self.objects[min_id]['max_mm'] = max(self.objects[min_id]['max_mm'], current_sizes[i])
                
                # Update quality history for consensus
                # We record None for 'good' and the class name for defects
                self.objects[min_id]['grade_history'].append(grades[i])
                
                # Store best crop (frame with largest cashew size) for final saving
                if current_sizes[i] >= self.objects[min_id]['max_mm']:
                    self.objects[min_id]['last_crop'] = crops[i].copy()
                self.objects[min_id]['latest_contour'] = contours[i] # Store actual shape
                self.objects[min_id]['is_good'] = is_good_flags[i]   # Store current quality
                self.objects[min_id]['current_grade'] = grades[i]    # Store defect type for display
                
                self.objects[min_id]['disappeared_count'] = 0
                matched_objects.add(min_id)
                matched_detections.add(i)
        
        # New objects
        for i in range(len(current_centroids)):
            if i not in matched_detections:
                self.objects[self.next_id] = {
                    'centroid': current_centroids[i],
                    'prev_centroid': current_centroids[i],
                    'curr_time': frame_timestamp,
                    'prev_time': frame_timestamp,
                    'measurements': [current_sizes[i]],
                    'max_mm': current_sizes[i],
                    'grade_history': [grades[i]],
                    'last_crop': crops[i].copy(),
                    'latest_contour': contours[i],
                    'is_good': is_good_flags[i],
                    'current_grade': grades[i],
                    'disappeared_count': 0,
                    'start_time': frame_timestamp,
                    'start_y': current_centroids[i][1],
                    'command_sent': False
                }
                self.next_id += 1
        
        disappeared = []
        for obj_id in object_ids:
            if obj_id not in matched_objects:
                self.objects[obj_id]['disappeared_count'] += 1
                if self.objects[obj_id]['disappeared_count'] > self.max_disappeared:
                    disappeared.append(obj_id)
        
        return disappeared
    
    def get_object_info(self, obj_id):
        """Get information about a tracked object"""
        return self.objects.get(obj_id, None)
    
    def remove_object(self, obj_id):
        """Remove object from tracking (memory cleanup)"""
        if obj_id in self.objects:
            del self.objects[obj_id]

# =========================================================
# CONTOUR SMOOTHING HELPER
# =========================================================

def smooth_contour(contour, window=9):
    """
    Smooth contour points using circular moving-average convolution.
    This produces ultra-smooth, stable borders that don't jitter.
    """
    if contour is None or len(contour) < window * 2:
        return contour
    pts = contour.reshape(-1, 2).astype(np.float64)
    n = len(pts)
    if n < 5:
        return contour
    
    # Circular padding for seamless smoothing at contour endpoints
    pad = window // 2
    padded_x = np.concatenate([pts[-pad:, 0], pts[:, 0], pts[:pad, 0]])
    padded_y = np.concatenate([pts[-pad:, 1], pts[:, 1], pts[:pad, 1]])
    
    # Moving average kernel
    kernel = np.ones(window) / window
    smooth_x = np.convolve(padded_x, kernel, mode='valid')
    smooth_y = np.convolve(padded_y, kernel, mode='valid')
    
    smoothed = np.stack([smooth_x, smooth_y], axis=1).astype(np.int32)
    return smoothed.reshape(-1, 1, 2)

# =========================================================
# ZONE PROCESSOR CLASS
# =========================================================

class ZoneProcessor:
    """
    Processes a single zone independently
    - Has its own tracker
    - Maintains its own serial connection
    - Works like a separate camera
    """
    
    def __init__(self, zone_config, ranges, shared_arduino=None, serial_lock=None):
        self.zone = zone_config['zone']
        self.name = zone_config.get('name', 'Zone-1')
        self.ranges = ranges
        self.tracker = ObjectTracker(self.name)
        self.arduino = shared_arduino
        self.serial_lock = serial_lock
    
    def update_zone(self, new_zone):
        """Update zone coordinates dynamically"""
        self.zone = new_zone
    
    def get_zone_mask(self, frame_shape):
        """Create mask for this zone only"""
        mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        x, y, w, h = self.zone
        img_h, img_w = frame_shape[:2]
        x1 = max(0, min(x, img_w))
        y1 = max(0, min(y, img_h))
        x2 = max(0, min(x + w, img_w))
        y2 = max(0, min(y + h, img_h))
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255
        return mask
    
    def process_frame(self, frame, frame_timestamp=None, quality_filter=None):
        """
        Process frame for this zone
        """
        if frame_timestamp is None:
            frame_timestamp = time.perf_counter()
        x, y, w, h = self.zone
        
        img_h, img_w = frame.shape[:2]
        x1 = max(0, min(x, img_w))
        y1 = max(0, min(y, img_h))
        x2 = max(0, min(x + w, img_w))
        y2 = max(0, min(y + h, img_h))
        
        # Extract zone region from frame
        zone_frame = frame[y1:y2, x1:x2]
        
        if zone_frame.size == 0 or zone_frame.shape[0] == 0 or zone_frame.shape[1] == 0:
            return []
        
        # Create zone-specific mask using clipped coordinates
        zone_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        zone_mask[y1:y2, x1:x2] = 255
        
        # --- ULTRA-PRECISE EDGE SEGMENTATION ---
        # Step 1: Bilateral filter - smooths texture noise while preserving TRUE edges
        smooth = cv2.GaussianBlur(zone_frame, (7, 7), 0)
        gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
        
        # Step 2: Clean Otsu threshold on pre-smoothed image (high contrast cashew vs dark belt)
        _, mask_raw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Step 3: Morphological refinement with ELLIPTICAL kernels
        kernel_e = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask_clean = cv2.morphologyEx(mask_raw, cv2.MORPH_OPEN, kernel_e, iterations=1)
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close, iterations=1)
        
        # Step 4: ULTRA-SMOOTH EDGES - Lighter Gaussian blur for speed
        mask_smooth = cv2.GaussianBlur(mask_clean, (9, 9), 0)
        _, mask_final = cv2.threshold(mask_smooth, 127, 255, cv2.THRESH_BINARY)
        
        # Step 5: HSV validation mask (for density check only, not contour shape)
        hsv = cv2.cvtColor(zone_frame, cv2.COLOR_BGR2HSV)
        hsv_mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
        
        # Find contours with ALL edge points for maximum smoothness
        cnts, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter by area and perform COLOR GRADING
        valid_contours = []
        is_good_flags = []
        grades = []
        crops = []
        
        # --- PASS 1: Apply Filters and Extract Crops ---
        extracted_crops = []
        valid_contours_indices = []
        adjusted_contours = []
        
        for i, raw_cnt in enumerate(cnts):
            # 1. OPTIMIZATION: Filter by area FIRST before expensive operations!
            raw_area = cv2.contourArea(raw_cnt)
            if raw_area < MIN_CASHEW_AREA:
                adjusted_contours.append(None) # keep indices aligned
                continue
                
            # 2. Offset and Smooth only valid size contours
            c_adjusted = raw_cnt.copy()
            c_adjusted[:, 0, 0] += x1  # Add zone x offset
            c_adjusted[:, 0, 1] += y1  # Add zone y offset
            c_adjusted = smooth_contour(c_adjusted, window=5)
            adjusted_contours.append(c_adjusted)
            
            c = c_adjusted
            area = cv2.contourArea(c)
            
            # Density Check (use original raw contour against zone_mask)
            c_mask = np.zeros(zone_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(c_mask, [raw_cnt], -1, 255, -1)
            cashew_pixels = cv2.countNonZero(cv2.bitwise_and(c_mask, hsv_mask))
            total_pixels = cv2.countNonZero(c_mask)
            density = cashew_pixels / max(1, total_pixels)
            if density < 0.15:
                continue
                
            # Roller / Noise Checks
            rect = cv2.minAreaRect(c)
            (w_p, h_p) = rect[1]
            if max(1, w_p * h_p) == 1: continue
            mm_size = max(w_p, h_p) * PIXEL_TO_MM_RATIO
            
            # Identify rollers by checking if the object spans almost the entire width of the zone
            x_b, y_b, w_b, h_b = cv2.boundingRect(c)
            if w_b > (self.zone[2] * 0.90):
                continue # Ignore horizontal rollers
                
            solidity = area / max(1, w_p * h_p)
            if solidity < 0.35:
                continue
            if min(w_p, h_p) < 12:
                continue
                
            # Crop Extraction
            side = max(w_b, h_b) + 40
            cx_b, cy_b = x_b + w_b//2, y_b + h_b//2
            px = max(0, cx_b - side//2)
            py = max(0, cy_b - side//2)
            pw = min(frame.shape[1] - px, side)
            ph = min(frame.shape[0] - py, side)
            crop = frame[py:py+ph, px:px+pw]
            
            if crop.size > 0:
                extracted_crops.append(crop)
                valid_contours_indices.append(i)
                
        # --- PASS 2: Pass crops to Tracker ---
        for idx, crop_idx in enumerate(valid_contours_indices):
            c = adjusted_contours[crop_idx]
            crop = extracted_crops[idx]
            valid_contours.append(c)
            is_good_flags.append(True)
            grades.append(None)
            crops.append(crop)
        
        # Update tracker with newly determined grades and crops
        disappeared_ids = self.tracker.update(valid_contours, is_good_flags, grades, crops, frame_timestamp)
        
        # --- PASS 3: Evaluate Cashews using LINE CROSSING + DISAPPEARANCE LOGIC ---
        disappeared_crops = []
        disappeared_objs = []
        
        x, y, _, zone_h = self.zone
        
        # Define triggering lines relative to Zone geometry
        min_start_line = y + (zone_h * 0.85)  # 85% prevents 'ghost' respawns from double-firing, but allows manual drops
        trigger_line = y + (zone_h * 0.95)
        disappear_trigger_line = y + (zone_h * 0.20) # If tracker loses it anywhere below 20%, it's definitely an exit
        
        # 1. LINE CROSSING LOGIC: We check ALL active tracked objects to see if they just crossed the line
        for obj_id, obj_info in list(self.tracker.objects.items()):
            if not obj_info.get('command_sent', False):
                cy = obj_info['centroid'][1]
                start_y = obj_info.get('start_y', cy)
                
                if start_y < min_start_line and cy >= trigger_line:
                    max_mm = obj_info['max_mm']
                    frames_tracked = len(obj_info.get('measurements', []))
                    if max_mm >= MIN_MM_SIZE and frames_tracked >= 1:
                        # --- VELOCITY OVERSHOOT COMPENSATION ---
                        prev_cy = obj_info.get('prev_centroid', (0, cy))[1]
                        prev_time = obj_info.get('prev_time', frame_timestamp)
                        curr_time = obj_info.get('curr_time', frame_timestamp)
                        
                        true_exit_time = frame_timestamp
                        dy = cy - prev_cy
                        dt = curr_time - prev_time
                        
                        # Use average velocity over the ENTIRE tracking period for extreme precision
                        # This eliminates 1-pixel jitter from instantaneous frame-to-frame velocity
                        total_dy = cy - start_y
                        total_dt = curr_time - obj_info.get('start_time', curr_time - 0.1)
                        
                        time_overshoot = 0.0
                        if total_dt > 0 and total_dy > 0:
                            velocity = total_dy / total_dt  # Average pixels per second
                            overshoot_px = cy - trigger_line
                            if overshoot_px > 0:
                                time_overshoot = overshoot_px / velocity
                                true_exit_time -= time_overshoot # Shift time BACKWARDS!
                                
                        last_crop = obj_info.get('last_crop')
                        if last_crop is not None:
                            disappeared_crops.append(last_crop)
                            disappeared_objs.append((obj_id, obj_info, true_exit_time, time_overshoot))
                            obj_info['command_sent'] = True # NEVER fire for this ID again
                            self.tracker.remove_object(obj_id) # KILL THE GHOST immediately so it doesn't steal cashews behind it!
                    else:
                        reason = "Too small" if max_mm < MIN_MM_SIZE else "Noise/Flicker (Tracked 1 frame)"
                        print(f"[{self.name}] Cashew ID:{obj_id} crossed 95% line but REJECTED! (Reason: {reason}, Size: {max_mm:.1f}mm)")
                        obj_info['command_sent'] = True # Stop spamming the log
                        self.tracker.remove_object(obj_id) # KILL THE GHOST
                            
        # 2. DISAPPEARANCE LOGIC: Catch cashews that the tracker lost slightly before the line
        for obj_id in disappeared_ids:
            obj_info = self.tracker.get_object_info(obj_id)
            if obj_info:
                if not obj_info.get('command_sent', False):
                    cy = obj_info['centroid'][1]
                    start_y = obj_info.get('start_y', cy)
                    
                    if start_y < min_start_line and cy >= disappear_trigger_line:
                        max_mm = obj_info['max_mm']
                        frames_tracked = len(obj_info.get('measurements', []))
                        if max_mm >= MIN_MM_SIZE and frames_tracked >= 1:
                            last_crop = obj_info.get('last_crop')
                            if last_crop is not None:
                                # PREDICT the exit time since we lost tracking before the 95% line
                                curr_time = obj_info.get('curr_time', frame_timestamp)
                                total_dy = cy - start_y
                                total_dt = curr_time - obj_info.get('start_time', curr_time - 0.1)
                                
                                predicted_exit_time = curr_time
                                if total_dt > 0 and total_dy > 0:
                                    velocity = total_dy / total_dt
                                    distance_remaining = max(0, trigger_line - cy)
                                    time_to_reach = distance_remaining / velocity
                                    predicted_exit_time = curr_time + time_to_reach
                                
                                disappeared_crops.append(last_crop)
                                disappeared_objs.append((obj_id, obj_info, predicted_exit_time, 0))
                                obj_info['command_sent'] = True
                        else:
                            reason = "Too small" if max_mm < MIN_MM_SIZE else "Noise/Flicker (Tracked 1 frame)"
                            print(f"[{self.name}] Cashew ID:{obj_id} disappeared but REJECTED! (Reason: {reason}, Size: {max_mm:.1f}mm)")
                            obj_info['command_sent'] = True
                    else:
                        print(f"[{self.name}] Cashew ID:{obj_id} SILENTLY VANISHED! (Start Y:{start_y:.0f}, End Y:{cy:.0f}, Required:{disappear_trigger_line:.0f})")
                        obj_info['command_sent'] = True
                                
                # Memory cleanup is MANDATORY for all disappeared objects!
                self.tracker.remove_object(obj_id)
        if disappeared_crops:
            # --- START TIMERS IMMEDIATELY (PARALLEL TO PROCESSING) ---
            DELAY_SECONDS = 6.20
            command = ZONE_COMMAND_MAP.get(self.name, '16|')
            
            def send_delayed(cmd, arduino, lock, name, o_id, exit_time):
                target_time = exit_time + DELAY_SECONDS
                
                # 1. Sleep normally until the last 20 milliseconds (Saves CPU, high precision with timeBeginPeriod)
                while True:
                    now = time.perf_counter()
                    if target_time - now > 0.020:
                        time.sleep(0.002)
                    else:
                        break
                        
                # 2. Busy-wait (Spin) for the final 20 milliseconds for EXTREME precision
                while time.perf_counter() < target_time:
                    pass
                
                # Measure exact delay before serial port bottleneck
                actual_delay = time.perf_counter() - exit_time
                
                # Command sends exactly at the target millisecond
                if arduino and lock:
                    try:
                        with lock:
                            if arduino.in_waiting > 0:
                                arduino.read(arduino.in_waiting)
                            arduino.write(cmd.encode())
                            arduino.flush()
                        now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"\n[{now_str}] [{name}] EXIT ID:{o_id} -> COMMAND SENT (Total Time: {actual_delay:.3f}s) -> Sent:{cmd.strip()}")
                    except Exception as e:
                        print(f"\n[{name}] SERIAL WRITE ERROR: {e}")

            for idx, (obj_id, obj_info, true_exit_time, time_overshoot) in enumerate(disappeared_objs):
                t = threading.Thread(target=send_delayed, args=(command, self.arduino, self.serial_lock, self.name, obj_id, true_exit_time))
                t.daemon = True
                t.start()
                now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{now_str}] [{self.name}] EXIT ID:{obj_id} (MM:{obj_info['max_mm']:.1f}) -> QUEUED (Overshoot: {time_overshoot*1000:.1f}ms) -> Target: {DELAY_SECONDS}s")

            # --- NOW PROCEED WITH YOLO PROCESSING ---
            processing_start_time = time.time()
            yolo_results = []
            if quality_filter and quality_filter.model:
                yolo_results = quality_filter.get_cashew_categories_batch(disappeared_crops)
            else:
                yolo_results = [(None, 0)] * len(disappeared_crops)
                
            for idx, (obj_id, obj_info, true_exit_time, time_overshoot) in enumerate(disappeared_objs):
                max_mm = obj_info['max_mm']
                last_crop = disappeared_crops[idx]
                yolo_cat, yolo_conf = yolo_results[idx]
                
                final_grade = None
                yolo_confirmed_good = False
                
                if yolo_cat:
                    if yolo_cat in [name.lower() for name in GOOD_CLASS_NAMES]:
                        if yolo_conf > YOLO_STRICT_BYPASS:
                            yolo_confirmed_good = True
                    else:
                        final_grade = yolo_cat
                        
                if not final_grade and not yolo_confirmed_good:
                    if is_oily_cashew(last_crop):
                        final_grade = 'oily'
                    if not final_grade:
                        shell, orange, color = check_rgb_defects(last_crop)
                        if shell: final_grade = 'shell'
                        elif orange: final_grade = 'orange'
                        elif color: final_grade = 'color'
                    if not final_grade:
                        gray_crop = cv2.cvtColor(last_crop, cv2.COLOR_BGR2GRAY)
                        dot_found, _ = detect_black_dots(gray_crop)
                        if dot_found:
                            final_grade = 'blackdot'
                            
                # If no defect, use size-based grading
                if not final_grade:
                    final_grade = get_grade(int(max_mm), self.ranges)
                    
                # --- SAVE FINAL IMAGE (PERFECT BORDERLINE VIEW) ---
                if last_crop is not None:
                    try:
                        save_img = last_crop.copy()
                        h_s, w_s = save_img.shape[:2]
                        is_defect = final_grade and not any(size in str(final_grade) for size in ['400', '320', '240', '210', '180'])
                        color_border = (0, 0, 255) if is_defect else (0, 255, 0)
                        
                        # --- USE TRACKED CONTOUR (MOST ACCURATE) ---
                        tracked_cnt = obj_info.get('latest_contour')
                        x_b, y_b, w_b, h_b = cv2.boundingRect(tracked_cnt) if tracked_cnt is not None else (0, 0, w_s, h_s)
                        
                        # Compute crop origin to translate contour into crop space
                        side = max(w_b, h_b) + 40
                        cx_b, cy_b = x_b + w_b//2, y_b + h_b//2
                        crop_ox = max(0, cx_b - side//2)
                        crop_oy = max(0, cy_b - side//2)
                        
                        contour_drawn = False
                        if tracked_cnt is not None and len(tracked_cnt) >= 3:
                            # Translate the tracked contour to crop-local coordinates
                            local_cnt = tracked_cnt.copy()
                            local_cnt[:, 0, 0] -= crop_ox
                            local_cnt[:, 0, 1] -= crop_oy
                            
                            # Apply smooth_contour for perfect border
                            smooth_cnt = smooth_contour(local_cnt, window=11)
                            if len(smooth_cnt) >= 3:
                                cv2.drawContours(save_img, [smooth_cnt], -1, color_border, 2)
                                contour_drawn = True
                        
                        if not contour_drawn:
                            # Fallback: re-detect on crop using Gaussian+Otsu+heavy blur
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
                                cv2.rectangle(save_img, (0, 0), (w_s-1, h_s-1), color_border, 2)
                        
                        label_grade = f"{final_grade or 'None'}"
                        label_size = f"{max_mm:.1f}mm"
                        cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                        cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                        cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        filename = f"ID{obj_id}_{final_grade}_{int(max_mm)}mm_{int(time.time())}.jpg"
                        filepath = os.path.join(DETECTIONS_FOLDER, filename)
                        cv2.imwrite(filepath, save_img)
                    except Exception as e:
                        pass
                
                # Object was evaluated and removed during DISAPPEARANCE LOGIC block
                pass
            
            processing_end_time = time.time()
            processing_duration = processing_end_time - processing_start_time
            
            for idx, (obj_id, obj_info, true_exit_time, time_overshoot) in enumerate(disappeared_objs):
                target_time = true_exit_time + DELAY_SECONDS
                remaining_hold = max(0, target_time - processing_end_time)
                now_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{now_str}] [{self.name}] ID:{obj_id} Processing Done (Took: {processing_duration:.3f}s) -> Remaining Hold: {remaining_hold:.3f}s")
                
        return valid_contours
    
    def draw_zone(self, frame):
        """Draw zone boundary and tracked objects with full info"""
        x, y, w, h = self.zone
        
        # Draw zone rectangle (yellow)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        
        # Draw zone name
        cv2.putText(frame, self.name, (x+5, y+20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw tracked objects with contours + full info
        for obj_id, obj_info in self.tracker.objects.items():
            # SKIP disappeared objects - only draw currently visible ones
            if obj_info.get('disappeared_count', 0) > 0:
                continue
            cnt = obj_info.get('latest_contour')
            
            # --- CONSENSUS-BASED COLORING (not single-frame) ---
            history = obj_info.get('grade_history', [])
            defect_frames = [g for g in history if g is not None]
            total_frames = max(1, len(history))
            defect_ratio = len(defect_frames) / total_frames
            
            is_consensus_bad = defect_ratio > 0.40 and len(defect_frames) >= 2
            
            current_grade = obj_info.get('current_grade', None)
            if is_consensus_bad and defect_frames:
                defect_counts = Counter(defect_frames)
                display_defect = defect_counts.most_common(1)[0][0]
                color = (0, 0, 255)
            else:
                display_defect = None
                color = (0, 255, 0)
            
            if cnt is not None and len(cnt) >= 3:
                # Contour is already smoothed in process_frame, draw directly
                cv2.drawContours(frame, [cnt], -1, color, 2)
                
                cx, cy = obj_info['centroid']
                max_mm = obj_info['max_mm']
                
                label_id = f"SR:{obj_id} {max_mm:.1f}mm"
                
                if display_defect:
                    label_status = f"{display_defect.upper()}"
                    status_color = (0, 0, 255)
                else:
                    label_status = "GOOD"
                    status_color = (0, 255, 0)
                
                cv2.putText(frame, label_id, (cx - 40, cy - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
                cv2.putText(frame, label_id, (cx - 40, cy - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, label_status, (cx - 40, cy + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
                cv2.putText(frame, label_status, (cx - 40, cy + 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1)
    
    def close(self):
        """Serial connection is handled and closed by main()"""
        pass

# =========================================================
# KEYBOARD CONTROL HANDLER
# =========================================================

def handle_keyboard_controls(key, zone_configs, zone_processors):
    """
    Handle keyboard input for zone adjustment and display control
    Supports Arrow keys, WASD, and additional resizing keys.
    """
    global SELECTED_ZONE_INDEX, SHOW_DISPLAY
    
    should_quit = False
    
    # Get the masked key for character comparisons
    char_key = key & 0xFF
    
    # 1. Zone selection (1-5)
    if ord('1') <= char_key <= ord('5'):
        SELECTED_ZONE_INDEX = char_key - ord('1')
        print(f"\n[CONTROL] Selected {zone_configs[SELECTED_ZONE_INDEX]['name']} for adjustment")
    
    # 2. Display window control (Q or q)
    elif char_key == ord('q') or char_key == ord('Q'):
        SHOW_DISPLAY = not SHOW_DISPLAY
        if SHOW_DISPLAY:
            print(f"\n[CONTROL] Display window OPENING...")
        else:
            print(f"\n[CONTROL] Display window HIDDEN (processing continues in background). Press Q to reopen.")
    
    # 3. ESC to quit completely
    elif char_key == 27:  # ESC
        should_quit = True
        print(f"\n[CONTROL] ESC pressed - Exiting program...")
    
    # 4. Save zones configuration (C or c)
    elif char_key == ord('c') or char_key == ord('C'):
        save_zones_config(zone_configs)
    
    # 5. Zone adjustment (only if a zone is selected)
    elif SELECTED_ZONE_INDEX is not None:
        zone_config = zone_configs[SELECTED_ZONE_INDEX]
        x, y, w, h = zone_config['zone']
        modified = False
        action = ""
        
        # --- MOVEMENT (Arrows or WASD) ---
        # We check full 'key' codes first for specific Windows Arrow keys
        # Left: Arrow Left (2424832 / 81 / 37) or 'A'
        if key in [2424832, 81, 37, 2] or char_key in [ord('a'), ord('A')]:
            x -= ZONE_ADJUST_STEP
            modified = True
            action = "moved LEFT"
        # Right: Arrow Right (2555904 / 83 / 39) or 'D'
        elif key in [2555904, 83, 39, 3] or char_key in [ord('d'), ord('D')]:
            x += ZONE_ADJUST_STEP
            modified = True
            action = "moved RIGHT"
        # Up: Arrow Up (2490368 / 82 / 38) or 'W'
        elif key in [2490368, 82, 38, 0] or char_key in [ord('w'), ord('W')]:
            y -= ZONE_ADJUST_STEP
            modified = True
            action = "moved UP"
        # Down: Arrow Down (2621440 / 84 / 40) or 'S'
        elif key in [2621440, 84, 40, 1] or char_key in [ord('s'), ord('S')]:
            y += ZONE_ADJUST_STEP
            modified = True
            action = "moved DOWN"
        
        # --- WIDTH (+/- or H/K) ---
        elif char_key in [ord('+'), ord('='), ord('k'), ord('K')]:
            w += ZONE_ADJUST_STEP
            modified = True
            action = "width INCREASED"
        elif char_key in [ord('-'), ord('_'), ord('h'), ord('H')]:
            w = max(50, w - ZONE_ADJUST_STEP)
            modified = True
            action = "width DECREASED"
        
        # --- HEIGHT ([ / ] or U / J) ---
        elif char_key in [ord('['), ord('u'), ord('U')]:
            h = max(50, h - ZONE_ADJUST_STEP)
            modified = True
            action = "height DECREASED"
        elif char_key in [ord(']'), ord('j'), ord('J')]:
            h += ZONE_ADJUST_STEP
            modified = True
            action = "height INCREASED"
        
        # Update zone configuration if modified
        if modified:
            new_zone = (x, y, w, h)
            zone_config['zone'] = new_zone
            zone_processors[SELECTED_ZONE_INDEX].update_zone(new_zone)
            print(f"[CONTROL] {zone_config['name']} {action} → x={x}, y={y}, w={w}, h={h}")
    
    return should_quit, SHOW_DISPLAY

# =========================================================
# MAIN
# =========================================================

def main():
    global SELECTED_ZONE_INDEX, SHOW_DISPLAY, ZONE_CONFIGS

    # Load grading ranges
    ranges = load_ranges(RANGES_FILE)
    if not ranges:
        print("Warning: No grading ranges loaded")

    # Initialize camera
    cam = HIKCashewCamera()
    
    last_config_mtime = 0
    if os.path.exists(ZONES_CONFIG_FILE):
        last_config_mtime = os.path.getmtime(ZONES_CONFIG_FILE)
    if not cam.connect():
        return

    # Initialize YOLO
    quality_filter = CashewQualityFilter(YOLO_MODEL_PATH)

    cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
    
    # Initialize Shared Serial Connection over main COM PORT file
    com_port = read_com_port_from_file(MAIN_COM_FILE)
    shared_arduino = None
    serial_lock = threading.Lock()
    if com_port:
        try:
            shared_arduino = serial.Serial(port=com_port, baudrate=115200, timeout=1)
            print(f"\nMain Serial connected on {com_port}. Waiting 2 seconds for Arduino to initialize...")
            time.sleep(2)  # Give Arduino bootloader enough time to start
            shared_arduino.reset_input_buffer()
            shared_arduino.reset_output_buffer()
            print("Main Serial is ready to send commands!")
        except Exception as e:
            print(f"Main Serial error: {e}")
            shared_arduino = None
    else:
        print("\nNo valid MAIN COM port found.")

    # Initialize zone processors using the shared COM connection
    zone_processors = []
    for zone_config in ZONE_CONFIGS:
        processor = ZoneProcessor(zone_config, ranges, shared_arduino, serial_lock)
        zone_processors.append(processor)
    
    print(f"\n{'='*60}")
    print(f"5 INDEPENDENT ZONES INITIALIZED - USING 1 SHARED COM PORT")
    print(f"{'='*60}")
    print(f"\nKEYBOARD CONTROLS:")
    print(f"  1-5      : Select zone for adjustment")
    print(f"  Arrows   : Move selected zone (UP/DOWN/LEFT/RIGHT)")
    print(f"  +/-      : Increase/Decrease width")
    print(f"  [ ]      : Decrease/Increase height")
    print(f"  C        : Save current zone configuration")
    print(f"  Q        : Toggle display window ON/OFF")
    print(f"  ESC      : Quit program completely")
    print(f"{'='*60}\n")

    # Create ThreadPool ONCE outside loop (creating every frame = massive overhead)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    
    try:
        frame_counter = 0
        none_counter = 0
        while True:
            frame_counter += 1

            frame = cam.get_frame()
            cam.check_and_update_parameters()
            if frame is None:
                none_counter += 1
                # Removed print statement for cleaner console
                cv2.waitKeyEx(1) # Keep UI responsive even if no frames arrive
                time.sleep(0.005) # Prevent 100% CPU pinning
                continue
            none_counter = 0
            
            frame_time = getattr(cam, 'last_returned_time', time.perf_counter())

            # Check for config file updates
            t0 = time.time()
            try:
                if os.path.exists(ZONES_CONFIG_FILE):
                    mtime = os.path.getmtime(ZONES_CONFIG_FILE)
                    if mtime > last_config_mtime:
                        last_config_mtime = mtime
                        print("\n[CONFIG] zones_config.json changed! Reloading zones...")
                        new_configs = load_zones_config()
                        # Update global ZONE_CONFIGS in-place
                        for i, new_z in enumerate(new_configs):
                            if i < len(ZONE_CONFIGS):
                                ZONE_CONFIGS[i]['zone'] = tuple(new_z['zone'])
                            else:
                                ZONE_CONFIGS.append({
                                    'zone': tuple(new_z['zone']),
                                    'name': new_z.get('name', f'Zone-{i+1}')
                                })
                        # Update zone processors
                        for i, processor in enumerate(zone_processors):
                            if i < len(ZONE_CONFIGS):
                                processor.update_zone(ZONE_CONFIGS[i]['zone'])
                        # If new zones were added, initialize new processors
                        if len(ZONE_CONFIGS) > len(zone_processors):
                            for i in range(len(zone_processors), len(ZONE_CONFIGS)):
                                processor = ZoneProcessor(ZONE_CONFIGS[i], ranges, shared_arduino, serial_lock)
                                zone_processors.append(processor)
            except Exception as e:
                print(f"[CONFIG] Error reloading config: {e}")

            # Process each zone in PARALLEL using the pre-created ThreadPool
            total_cashews_in_frame = 0
            future_to_processor = {
                executor.submit(p.process_frame, frame, frame_time, quality_filter): p 
                for p in zone_processors
            }
            for future in concurrent.futures.as_completed(future_to_processor):
                processor = future_to_processor[future]
                try:
                    contours = future.result()
                    total_cashews_in_frame += len(contours)
                except Exception as e:
                    print(f"Error in {processor.name}: {e}")
            
            # Build display frame ONLY when needed (skip heavy work when hidden)
            if SHOW_DISPLAY:
                display_frame = np.zeros_like(frame)
                img_h, img_w = frame.shape[:2]
                for z in ZONE_CONFIGS:
                    zx, zy, zw, zh = z['zone']
                    zx1 = max(0, min(zx, img_w))
                    zy1 = max(0, min(zy, img_h))
                    zx2 = max(0, min(zx + zw, img_w))
                    zy2 = max(0, min(zy + zh, img_h))
                    if zx2 > zx1 and zy2 > zy1:
                        display_frame[zy1:zy2, zx1:zx2] = frame[zy1:zy2, zx1:zx2]
                
                # Draw all zones synchronously after processing
                for processor in zone_processors:
                    processor.draw_zone(display_frame)
            else:
                display_frame = None
            
            # Highlight selected zone (only when display is active)
            if SHOW_DISPLAY and display_frame is not None and SELECTED_ZONE_INDEX is not None and SELECTED_ZONE_INDEX < len(ZONE_CONFIGS):
                sel_zone = ZONE_CONFIGS[SELECTED_ZONE_INDEX]['zone']
                sx, sy, sw, sh = sel_zone
                # Draw thick red border for selected zone
                cv2.rectangle(display_frame, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 4)
                # Add "SELECTED" label
                cv2.putText(display_frame, "SELECTED", (sx+5, sy+40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            try:
                # Catch if user closed the window using 'X' button
                if cv2.getWindowProperty("Full Camera", cv2.WND_PROP_VISIBLE) < 1:
                    print("\n[CONTROL] Window closed via 'X'. Entering background mode. Press Q to reopen. ESC to exit.")
                    cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
                    SHOW_DISPLAY = False
            except:
                pass

            if SHOW_DISPLAY:
                cv2.imshow("Full Camera", display_frame)
            else:
                # Keep a tiny dashboard so waitKey still works
                bg_frame = np.zeros((200, 600, 3), dtype=np.uint8)
                cv2.putText(bg_frame, "PROCESS RUNNING IN BACKGROUND", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(bg_frame, "Press 'Q' to show camera view, ESC to exit", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.imshow("Full Camera", bg_frame)
            
            # --- KEYBOARD PROCESSING ---
            # waitKeyEx is better for Arrow Keys on Windows
            key = cv2.waitKeyEx(1)
            
            if key != -1: # Any key pressed
                should_quit, SHOW_DISPLAY = handle_keyboard_controls(key, ZONE_CONFIGS, zone_processors)
                if should_quit:
                    break
            
            # Performance printing removed for cleaner console
            pass

    finally:
        executor.shutdown(wait=False)
        cam.close()
        for processor in zone_processors:
            processor.close()
        cv2.destroyAllWindows()
        if 'shared_arduino' in locals() and shared_arduino:
            try:
                shared_arduino.close()
                print("Main Serial closed")
            except:
                pass

if __name__ == "__main__":
    main()