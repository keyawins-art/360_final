import cv2
import numpy as np
from config import *

try:
    from ultralytics import YOLO  # type: ignore
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: 'ultralytics' library not found. YOLO filtering will be disabled.")

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
    
    pad = window // 2
    padded_x = np.concatenate([pts[-pad:, 0], pts[:, 0], pts[:pad, 0]])
    padded_y = np.concatenate([pts[-pad:, 1], pts[:, 1], pts[:pad, 1]])
    
    kernel = np.ones(window) / window
    smooth_x = np.convolve(padded_x, kernel, mode='valid')
    smooth_y = np.convolve(padded_y, kernel, mode='valid')
    
    smoothed = np.stack([smooth_x, smooth_y], axis=1).astype(np.int32)
    return smoothed.reshape(-1, 1, 2)

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

    def get_cashew_category(self, crop):
        """
        Run inference on the isolated cashew crop to determine its category.
        Returns (class_name, confidence) or (None, 0).
        """
        if self.model is None or crop.size == 0:
            return None, 0
            
        try:
            # Force CPU execution: ONNXRuntime-GPU also lacks RTX 5050 (sm_120) compiled kernels
            results = self.model(crop, verbose=False, conf=YOLO_CONF_THRESHOLD, device='cpu')
            for result in results:
                if len(result.boxes) > 0:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        cls_name = self.model.names[cls_id].lower()
                        
                        if cls_name in [name.lower() for name in GOOD_CLASS_NAMES]:
                            return cls_name, conf
                            
                    box = result.boxes[0]
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    cls_name = self.model.names[cls_id].lower()
                    return cls_name, conf
        except Exception as e:
            print(f"    [YOLO ERROR] {e}")
            pass
            
        return None, 0
