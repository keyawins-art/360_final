import os
import numpy as np

# Hardware Files
SERIAL_FILE = r"C:\Users\i7\Desktop\camera_serial(b).txt" 
RANGES_FILE = r"D:\4_belt_main\4_belt\range\value.txt"
MAIN_COM_FILE = r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt"

# Zone Configurations
DEFAULT_ZONE_CONFIGS = [
    {'zone': (50, 100, 250, 800), 'name': 'Zone-1'},
    {'zone': (350, 100, 250, 800), 'name': 'Zone-2'},
    {'zone': (650, 100, 250, 800), 'name': 'Zone-3'},
    {'zone': (950, 100, 250, 800), 'name': 'Zone-4'},
    {'zone': (1250, 100, 250, 800), 'name': 'Zone-5'}
]

# Path resolution to point to Desktop\360\zones_config.json
ZONES_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zones_config.json")
DETECTIONS_FOLDER = r"f:\server\360\detections"

if not os.path.exists(DETECTIONS_FOLDER):
    os.makedirs(DETECTIONS_FOLDER)

# Sensitivity & Physics Constants
MIN_CASHEW_AREA = 3500       
MIN_MM_SIZE = 15.0           
MAX_CASHEW_MM = 33.0         
MAX_ASPECT_RATIO = 3.0       
PIXEL_TO_MM_RATIO = 0.111  
MAX_TRACKING_DISTANCE = 250 

# Vision / AI Constants
HSV_LOWER = np.array([0, 30, 15])     
HSV_UPPER = np.array([40, 255, 255])  
YOLO_CONF_THRESHOLD = 0.40   
YOLO_STRICT_BYPASS = 0.85    
OILY_RATIO_THRESHOLD = 0.95  
SHELL_PIXEL_THRESHOLD = 15000 
BLACKDOT_RATIO_THRESHOLD = 0.015 
BLACKDOT_MIN_COUNT = 1       

YOLO_MODEL_PATH = r"c:\Users\i7\Desktop\360\best.pt"
GOOD_CLASS_NAMES = ['good', 'cashew', 'white', 'full', 'whole', 'object'] 

# Hardware Mapping
GRADE_PORT_MAP = {
    'Zone-1': {'400': '11|', '320': '11|', '240': '11|', '210': '11|', '180': '11|', 'default': '11|'},
    'Zone-2': {'400': '21|', '320': '21|', '240': '21|', '210': '21|', '180': '21|', 'default': '21|'},
    'Zone-3': {'400': '31|', '320': '31|', '240': '31|', '210': '31|', '180': '31|', 'default': '31|'},
    'Zone-4': {'400': '41|', '320': '41|', '240': '41|', '210': '41|', '180': '41|', 'default': '41|'},
    'Zone-5': {'400': '51|', '320': '51|', '240': '51|', '210': '51|', '180': '51|', 'default': '51|'}
}

# Color Grading Samples
samples = np.array([
    [35.3, 75, 51], [38.2, 74, 29], [34.1, 74, 44], [34.7, 78, 48],
    [38.1, 81, 47], [39.5, 57, 54], [34.7, 82, 40], [35.4, 74, 41],
    [31.5, 71, 33], [39.2, 66, 47], [35.6, 75, 53], [44.5, 57, 43],
    [38.4, 90, 39], [36.3, 73, 38], [43.1, 78, 20], [42.7, 79, 33],
    [29.6, 76, 38], [33.6, 48, 18], [33.6, 100, 93], [37.1, 82, 20]
])
hsv_cv = samples.astype(np.float32)
hsv_cv[:, 0] /= 2            
hsv_cv[:, 1:] *= 2.55        
H, S, V = hsv_cv[:, 0], hsv_cv[:, 1], hsv_cv[:, 2]
H_tol, S_tol, V_tol = 2, 5, 5

LOWER_OILY = np.array([max(int(H.min()) - H_tol, 0), max(int(S.min()) - S_tol, 0), max(int(V.min()) - V_tol, 0)], dtype=np.uint8)
UPPER_OILY = np.array([min(int(H.max()) + H_tol, 179), min(int(S.max()) + S_tol, 255), min(int(V.max()) + V_tol, 255)], dtype=np.uint8)
