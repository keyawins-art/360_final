import sys, os, platform
from ctypes import *
import numpy as np
import cv2
import serial
import time
import re
import json
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: 'ultralytics' library not found. YOLO filtering will be disabled.")

# =========================================================


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
        'com_file': r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt",
        'name': 'Zone-1'
    },
    {
        'zone': (350, 100, 250, 800),
        'com_file': r"D:\4_belt_main\4_belt\Test_checkup\com_port(b).txt",
        'name': 'Zone-2'
    },
    {
        'zone': (650, 100, 250, 800),
        'com_file': r"D:\4_belt_main\4_belt\Test_checkup\com_port(c).txt",
        'name': 'Zone-3'
    },
    {
        'zone': (950, 100, 250, 800),
        'com_file': r"D:\4_belt_main\4_belt\Test_checkup\com_port(d).txt",
        'name': 'Zone-4'
    },
    {
        'zone': (1250, 100, 250, 800),
        'com_file': r"D:\4_belt_main\4_belt\Test_checkup\com_port(e).txt",
        'name': 'Zone-5'
    }
]

ZONES_CONFIG_FILE = "zones_config.json"

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

# Adjusted HSV range for better cashew detection
# Lower: More permissive to catch cashews in various lighting
# Upper: Covers orange-yellow-brown tones of cashews
HSV_LOWER = np.array([0, 20, 40])    # Very low hue to catch light cashews
HSV_UPPER = np.array([40, 255, 255])  # Extended to cover all cashew colors
MIN_CASHEW_AREA = 500
PIXEL_TO_MM_RATIO = 0.111  # 1 px = 0.0937 mm
MAX_TRACKING_DISTANCE = 50  # Max pixel distance to consider same object

# =========================================================
# KEYBOARD CONTROL CONFIGURATION
# =========================================================
SELECTED_ZONE_INDEX = None  # Currently selected zone for adjustment (0-4)
SHOW_DISPLAY = True  # Whether to show the display window
ZONE_ADJUST_STEP = 10  # Pixels to move/resize per keypress

# =========================================================
# YOLO CONFIGURATION
# =========================================================
YOLO_MODEL_PATH = r"D:\Project_360\best.pt"  # <--- UPDATE THIS PATH
GOOD_CLASS_NAMES = ['good'] # List of class names to consider as 'Good'
YOLO_CONF_THRESHOLD = 0.25

# =========================================================
# GRADING CONFIGURATION
# =========================================================

# Different commands for each zone to distinguish them on a single COM port
# Using commands 1-6 for Zone-1, and 7-12 for Zone-2 (Total 12 commands out of 20 available)
GRADE_PORT_MAP = {
    'Zone-1': {
        '400': '11|',
        '320': '11|',
        '240': '11|',
        '210': '11|',
        '180': '11|',
        'default': '11|'
    },
    'Zone-2': {
        '400': '21|',
        '320': '21|',  
        '240': '21|',
        '210': '21|',
        '180': '21|',
        'default': '21|'
    }
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
    from MvCameraControl_class import *
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
# YOLO FILTER CLASS
# =========================================================

class CashewQualityFilter:
    def __init__(self, model_path):
        self.model = None
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                print(f"YOLO Model loaded from: {model_path}")
            except Exception as e:
                print(f"Error loading YOLO model: {e}")

    def is_cashew_good(self, crop):
        """
        Run inference on the isolated cashew crop to determine if it is 'good'.
        """
        if self.model is None or crop.size == 0:
            return True # Pass everything if no model or invalid crop
            
        try:
            results = self.model(crop, verbose=False, conf=YOLO_CONF_THRESHOLD)
            for result in results:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = self.model.names[cls_id]
                    if cls_name.lower() in [name.lower() for name in GOOD_CLASS_NAMES]:
                        return True
        except Exception:
            pass
            
        return False

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

        self.cam.MV_CC_SetEnumValue("TriggerMode",MV_TRIGGER_MODE_OFF)

        stParam=MVCC_INTVALUE()
        memset(byref(stParam),0,sizeof(stParam))
        self.cam.MV_CC_GetIntValue("PayloadSize",stParam)
        self.nPayloadSize=stParam.nCurValue

        if self.cam.MV_CC_StartGrabbing()!=0:
            return False

        self.is_grabbing=True
        print("Camera connected")
        return True

    # -------- Frame Capture (all pixel formats) --------
    def get_frame(self):

        if not self.is_grabbing:
            return None

        data=(c_ubyte*self.nPayloadSize)()
        frame_info=MV_FRAME_OUT_INFO_EX()
        memset(byref(frame_info),0,sizeof(frame_info))

        if self.cam.MV_CC_GetOneFrameTimeout(
                byref(data),self.nPayloadSize,frame_info,1000)!=0:
            return None

        w,h=frame_info.nWidth,frame_info.nHeight
        pf=frame_info.enPixelType

        img=np.frombuffer(data,dtype=np.uint8,count=frame_info.nFrameLen)

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
    
    def __init__(self, zone_name, max_distance=300, max_disappeared=15):
        self.zone_name = zone_name
        self.next_id = 1
        self.objects = {}  # {id: {'centroid': (x,y), 'measurements': [], 'max_mm': 0, 'disappeared_count': 0, 'is_good': False}}
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        
    def update(self, contours, is_good_flags=None):
        """
        Update tracked objects with new contours
        Returns: list of object IDs that disappeared (exited ROI)
        """
        if is_good_flags is None:
            is_good_flags = [True] * len(contours)
            
        current_centroids = []
        current_sizes = []
        
        # Calculate centroids and sizes for current frame
        for c in contours:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Calculate size (mm) - using width of rotated rect
                rect = cv2.minAreaRect(c)
                width, height = rect[1]
                mm_size = max(width, height) * PIXEL_TO_MM_RATIO  # Convert pixels to mm
                
                current_centroids.append((cx, cy))
                current_sizes.append(mm_size)
        
        # If no objects currently tracked, create new ones
        if len(self.objects) == 0:
            for centroid, size, is_good in zip(current_centroids, current_sizes, is_good_flags):
                self.objects[self.next_id] = {
                    'centroid': centroid,
                    'measurements': [size],
                    'max_mm': size,
                    'disappeared_count': 0,
                    'is_good': is_good
                }
                self.next_id += 1
            return []
        
        # Match current detections to existing objects
        object_ids = list(self.objects.keys())
        matched_objects = set()
        matched_detections = set()
        
        for i, curr_centroid in enumerate(current_centroids):
            min_dist = float('inf')
            min_id = None
            
            for obj_id in object_ids:
                if obj_id in matched_objects:
                    continue
                
                obj_centroid = self.objects[obj_id]['centroid']
                dist = np.sqrt((curr_centroid[0] - obj_centroid[0])**2 + 
                             (curr_centroid[1] - obj_centroid[1])**2)
                
                if dist < min_dist:
                    min_dist = dist
                    min_id = obj_id
            
            # If close enough, update existing object
            if min_dist < self.max_distance and min_id is not None:
                self.objects[min_id]['centroid'] = curr_centroid
                self.objects[min_id]['measurements'].append(current_sizes[i])
                self.objects[min_id]['max_mm'] = max(self.objects[min_id]['max_mm'], 
                                                     current_sizes[i])
                self.objects[min_id]['disappeared_count'] = 0
                if is_good_flags[i]:
                    self.objects[min_id]['is_good'] = True
                matched_objects.add(min_id)
                matched_detections.add(i)
        
        # Create new objects for unmatched detections
        for i, (centroid, size, is_good) in enumerate(zip(current_centroids, current_sizes, is_good_flags)):
            if i not in matched_detections:
                self.objects[self.next_id] = {
                    'centroid': centroid,
                    'measurements': [size],
                    'max_mm': size,
                    'disappeared_count': 0,
                    'is_good': is_good
                }
                self.next_id += 1
        
        # Find objects that disappeared (exited ROI)
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
# ZONE PROCESSOR CLASS
# =========================================================

class ZoneProcessor:
    """
    Processes a single zone independently
    - Has its own tracker
    - Shares a common serial connection
    - Works like a separate camera
    """
    
    def __init__(self, zone_config, ranges, shared_arduino=None):
        self.zone = zone_config['zone']
        self.name = zone_config.get('name', 'Zone-1')
        self.ranges = ranges
        self.tracker = ObjectTracker(self.name)
        self.arduino = shared_arduino
    
    def update_zone(self, new_zone):
        """Update zone coordinates dynamically"""
        self.zone = new_zone
    
    def get_zone_mask(self, frame_shape):
        """Create mask for this zone only"""
        mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        x, y, w, h = self.zone
        mask[y:y+h, x:x+w] = 255
        return mask
    
    def process_frame(self, frame, quality_filter=None):
        """
        Process frame for this zone
        """
        x, y, w, h = self.zone
        
        # Create zone-specific mask
        zone_mask = self.get_zone_mask(frame.shape)
        
        # Extract zone region from frame
        zone_frame = frame[y:y+h, x:x+w]
        
        # Convert to HSV color space for more robust cashew detection
        hsv = cv2.cvtColor(zone_frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
        
        # Morphological operations to stabilize the mask without over-merging
        kernel_small = np.ones((3, 3), np.uint8)
        
        # 1. Remove small noise pixels (Opening)
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small)
        # 2. Use a tiny Close to fill internal holes without connecting separate cashews
        dilated = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel_small)
        
        # Find contours in the zone
        cnts, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Adjust contour coordinates to full frame
        adjusted_contours = []
        for c in cnts:
            c_adjusted = c.copy()
            c_adjusted[:, 0, 0] += x  # Add zone x offset
            c_adjusted[:, 0, 1] += y  # Add zone y offset
            adjusted_contours.append(c_adjusted)
        
        
        # Filter by area and classify with YOLO safely
        valid_contours = []
        is_good_flags = []
        
        for c in adjusted_contours:
            if cv2.contourArea(c) < MIN_CASHEW_AREA:
                continue

            is_good = True  # Default true if no YOLO model
            # --- YOLO QUALITY FILTER ON CROP ---
            if quality_filter is not None and quality_filter.model is not None:
                x_b, y_b, w_b, h_b = cv2.boundingRect(c)
                # Add 20 pixels padding around the cashew
                px = max(0, x_b - 20)
                py = max(0, y_b - 20)
                pw = min(frame.shape[1] - px, w_b + 40)
                ph = min(frame.shape[0] - py, h_b + 40)
                
                crop = frame[py:py+ph, px:px+pw]
                if not quality_filter.is_cashew_good(crop):
                    is_good = False  # YOLO classified this cashew as bad/shell
            # -----------------------------------

            valid_contours.append(c)
            is_good_flags.append(is_good)
        
        # Debug output removed to keep console clean for final EXITS only
        
        # Update tracker
        disappeared_ids = self.tracker.update(valid_contours, is_good_flags)
        
        # Handle exited objects
        for obj_id in disappeared_ids:
            obj_info = self.tracker.get_object_info(obj_id)
            if obj_info:
                # ONLY process and send command if it was classified as 'good' during its lifetime
                if obj_info.get('is_good', True):
                    max_mm = obj_info['max_mm']
                    grade = get_grade(int(max_mm), self.ranges)
                    
                    zone_map = GRADE_PORT_MAP.get(self.name, GRADE_PORT_MAP['Zone-1'])
                    command = zone_map.get(grade, zone_map['default'])
                    
                    # Send serial command
                    if self.arduino:
                        try:
                            self.arduino.write(command.encode())
                            self.arduino.flush()  # Force write
                            # Add a tiny delay (20ms) between commands to prevent Arduino buffer merge 
                            # and allow hardware solenoid to reset
                            time.sleep(0.02) 
                            print(f"[{self.name}] ✓ FINAL ID:{obj_id} EXIT → MM:{max_mm:.1f} → Grade:{grade or 'None'} → Sent:{command.strip()}")
                        except Exception as e:
                            print(f"[{self.name}] Serial error: {e}")
                    else:
                        print(f"[{self.name}] ✓ FINAL ID:{obj_id} EXIT → MM:{max_mm:.1f} → Grade:{grade or 'None'} → CMD:{command.strip()}")
                
                # Memory cleanup
                self.tracker.remove_object(obj_id)
        
        return valid_contours
    
    def draw_zone(self, frame):
        """Draw zone boundary and tracked objects"""
        x, y, w, h = self.zone
        
        # Draw zone rectangle (yellow)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        
        # Draw zone name
        cv2.putText(frame, self.name, (x+5, y+20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw tracked objects
        for obj_id, obj_info in self.tracker.objects.items():
            cx, cy = obj_info['centroid']
            max_mm = obj_info['max_mm']
            
            # Draw circle at centroid
            cv2.circle(frame, (cx, cy), 5, (255, 0, 255), -1)
            
            # Draw ID and max MM
            label = f"ID:{obj_id} MM:{max_mm:.1f}"
            cv2.putText(frame, label, (cx - 40, cy - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
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
    
    # 1. Zone selection (1-2)
    if ord('1') <= char_key <= ord('2'):
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
    global SELECTED_ZONE_INDEX, SHOW_DISPLAY

    # Load grading ranges
    ranges = load_ranges(RANGES_FILE)
    if not ranges:
        print("Warning: No grading ranges loaded")

    # Initialize camera
    cam = HIKCashewCamera()
    if not cam.connect():
        return

    # Initialize YOLO
    quality_filter = CashewQualityFilter(YOLO_MODEL_PATH)

    cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
    
    # Initialize Shared Serial Connection over main COM PORT file
    com_port = read_com_port_from_file(MAIN_COM_FILE)
    shared_arduino = None
    if com_port:
        try:
            shared_arduino = serial.Serial(port=com_port, baudrate=115200, timeout=1)
            print(f"Main Serial connected on {com_port}. Waiting 2 seconds for Arduino to initialize...")
            time.sleep(2)  # Give Arduino bootloader enough time to start
            shared_arduino.reset_input_buffer()
            shared_arduino.reset_output_buffer()
            print("Main Serial is ready to send commands!")
        except Exception as e:
            print(f"Main Serial error: {e}")
            shared_arduino = None
    else:
        print("No valid MAIN COM port found.")

    # Initialize zone processors using the shared COM connection
    zone_processors = []
    for zone_config in ZONE_CONFIGS:
        processor = ZoneProcessor(zone_config, ranges, shared_arduino)
        zone_processors.append(processor)
    
    print(f"\n{'='*60}")
    print(f"2 INDEPENDENT ZONES INITIALIZED - USING 1 SHARED COM PORT")
    print(f"{'='*60}")
    print(f"\nKEYBOARD CONTROLS:")
    print(f"  1-2      : Select zone for adjustment")
    print(f"  Arrows   : Move selected zone (↑↓←→)")
    print(f"  +/-      : Increase/Decrease width")
    print(f"  [ ]      : Decrease/Increase height")
    print(f"  C        : Save current zone configuration")
    print(f"  Q        : Toggle display window ON/OFF")
    print(f"  ESC      : Quit program completely")
    print(f"{'='*60}\n")

    try:
        while True:

            frame = cam.get_frame()
            if frame is None:
                continue

            # Create black background for display - only show zones
            display_frame = np.zeros_like(frame)
            for z in ZONE_CONFIGS:
                x, y, w, h = z['zone']
                # Copy original pixels for this zone
                display_frame[y:y+h, x:x+w] = frame[y:y+h, x:x+w]
            
            # Process each zone independently
            for processor in zone_processors:
                # Process this zone, passing the YOLO quality filter to evaluate individual crops
                contours = processor.process_frame(frame, quality_filter)
                
                # Draw zone and objects
                processor.draw_zone(display_frame)
                
                # Draw contours (Green for Good/Processed)
                for c in contours:
                    rect = cv2.minAreaRect(c)
                    box = cv2.boxPoints(rect).astype(int)
                    cv2.drawContours(display_frame, [box], -1, (0, 255, 0), 2)
            
            # Draw YOLO boxes visualization is removed since we do it on crops directly
            
            # Highlight selected zone
            if SELECTED_ZONE_INDEX is not None and SELECTED_ZONE_INDEX < len(ZONE_CONFIGS):
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

    finally:
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