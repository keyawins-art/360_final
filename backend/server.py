from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import psutil
import glob
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import sys
import ctypes
import numpy as np
import cv2
import time
import json
import serial

try:
    from MvCameraControl_class import *
except:
    sys.path.append(r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport")
    try:
        from MvCameraControl_class import *
    except:
        pass

app = FastAPI()

# --- SYSTEM TELEMETRY API ---
system_start_time = time.time()

@app.get("/api/telemetry")
def get_telemetry():
    # 1. CPU Load
    try:
        cpu_load = psutil.cpu_percent(interval=None)
    except:
        cpu_load = 0
        
    # 2. GPU Stats (using nvidia-smi if available)
    gpu_load = 0
    gpu_temp = 0
    try:
        output = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'],
            stderr=subprocess.STDOUT, timeout=1
        ).decode('utf-8').strip()
        parts = output.split(',')
        if len(parts) >= 2:
            gpu_load = int(parts[0].strip())
            gpu_temp = int(parts[1].strip())
    except Exception:
        pass
        
    # 3. Uptime
    uptime_seconds = int(time.time() - system_start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m"
    
    return {
        "cpu_load": cpu_load,
        "gpu_load": gpu_load,
        "gpu_temp": gpu_temp,
        "uptime": uptime_str,
        "fps": getattr(app, "camera_fps", 60.0) # Placeholder or actual from camera
    }
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_processes = []
current_mode = "Stopped"
last_terminal_message = "System Ready"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALUE_FILE = os.path.join(BASE_DIR, "wate", "value.txt")
CAMERA_PARAMS_FILE = os.path.join(BASE_DIR, "camera_params.json")

grade_counts = {
    "180": 0, "210": 0, "240": 0, "320": 0, "400": 0,
    "1000": 0, "dry": 0, "blackdot": 0, "shell": 0, "multiple_cashews": 0
}

class CustomizationsData(BaseModel):
    values: dict

class CameraParamsData(BaseModel):
    params: dict


def reset_counts():
    global grade_counts
    for k in grade_counts:
        grade_counts[k] = 0

def output_reader(proc, filename):
    global last_terminal_message
    try:
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            line_str = line.strip()
            if "Grade:" in line_str:
                try:
                    grade_val = line_str.split("Grade:")[1].split()[0].strip()
                    if grade_val in grade_counts:
                        grade_counts[grade_val] += 1
                except Exception:
                    pass
            else:
                last_terminal_message = f"[{filename}] {line_str}"
            print(f"[SCRIPT] {line_str}", flush=True)
            
        proc.wait()
        if proc.returncode != 0:
            last_terminal_message = f"Error: {filename} crashed (code {proc.returncode})"
            print(last_terminal_message)
    except Exception as e:
        last_terminal_message = f"Error reading {filename}: {e}"
        print(f"Stdout read error: {e}")

def run_scripts_in_folder(folder_name: str):
    global active_processes
    reset_counts()
    
    folder_path = os.path.join(BASE_DIR, folder_name)
    if not os.path.exists(folder_path):
        return {"error": f"Folder '{folder_name}' not found at {folder_path}"}
    
    python_files = glob.glob(os.path.join(folder_path, "*.py"))
    
    if not python_files:
         return {"message": f"No Python files found in {folder_name}"}

    started_count = 0
    for py_file in python_files:
        try:
            process = subprocess.Popen(
                ["python", "-u", py_file],
                cwd=folder_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
            active_processes.append(process)
            
            # Start background thread to read stdout
            t = threading.Thread(target=output_reader, args=(process, os.path.basename(py_file)), daemon=True)
            t.start()
            
            started_count += 1
        except Exception as e:
            print(f"Failed to start {py_file}: {e}")
            
    return {"message": f"Started {started_count} scripts in {folder_name}"}

@app.post("/api/run-default")
def run_default():
    global current_mode
    current_mode = "Default Mode"
    return run_scripts_in_folder("defoult")

@app.post("/api/run-grading")
def run_grading():
    global current_mode
    current_mode = "Grading Mode"
    return run_scripts_in_folder("grading")

@app.post("/api/run-color")
def run_color():
    global current_mode
    current_mode = "Color Grading Mode"
    return run_scripts_in_folder("grading_color")

@app.post("/api/stop-all")
def stop_all():
    global active_processes, current_mode
    killed_count = 0
    for process in active_processes:
        try:
            # On Windows, we may need to kill the process tree or just the process
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            killed_count += 1
        except Exception as e:
            print(f"Error killing process {process.pid}: {e}")
    
    active_processes.clear()
    current_mode = "Stopped"
    reset_counts()
    return {"message": f"Stopped {killed_count} process groups."}

@app.get("/api/customizations")
def get_customizations():
    data = {}
    if os.path.exists(VALUE_FILE):
        with open(VALUE_FILE, "r") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    data[parts[0]] = {"min": parts[1], "max": parts[2]}
    return data

def log_camera(message: str):
    try:
        log_path = os.path.join(BASE_DIR, "camera_log.txt")
        with open(log_path, "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    except:
        pass

def generate_camera_frames(cam_idx: str):
    log_camera(f"generate_camera_frames called for cam_idx={cam_idx}")
    refs_file = CAMERA_REF_FILE
    params_file = CAMERA_PARAMS_FILE
    
    try:
        with open(refs_file, "r") as f:
            content = f.read().strip()
            log_camera(f"Refs file content: {content}")
            data = json.loads(content)
            if isinstance(data, dict):
                refs = data.get("references", ["", "", ""])
            elif isinstance(data, list):
                refs = data
            else:
                refs = ["", "", ""]
    except Exception as e:
        log_camera(f"Error loading references: {e}")
        refs = ["", "", ""]
        
    target_serial = ""
    try:
        target_serial = refs[int(cam_idx) - 1].strip()
        log_camera(f"Target serial for cam_idx={cam_idx}: {target_serial}")
    except Exception as e:
        log_camera(f"Error getting target serial: {e}")
        pass
        
    if not target_serial:
        log_camera("No target serial found, returning.")
        return
        
    # Init MVS
    log_camera("Initializing MVS...")
    try:
        MvCamera.MV_CC_Initialize()
    except Exception as e:
        log_camera(f"MvCamera.MV_CC_Initialize raised exception: {e}")
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    log_camera(f"Enum devices return: {ret}, count: {deviceList.nDeviceNum}")
    if ret != 0:
        return
        
    selected = None
    for i in range(deviceList.nDeviceNum):
        info = ctypes.cast(deviceList.pDeviceInfo[i], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
        try:
            if info.nTLayerType == MV_GIGE_DEVICE:
                serial = bytes(info.SpecialInfo.stGigEInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
            elif info.nTLayerType == MV_USB_DEVICE:
                serial = bytes(info.SpecialInfo.stUsb3VInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
            else:
                continue
            log_camera(f"Found device serial: {serial}")
            if serial == target_serial:
                selected = info
                log_camera(f"Matched target serial: {serial}")
                break
        except Exception as e:
            log_camera(f"Error reading device info: {e}")
            pass
            
    if selected is None:
        log_camera("No matching device found, returning.")
        return
        
    cam = MvCamera()
    ret = cam.MV_CC_CreateHandle(selected)
    log_camera(f"Create handle return: {ret}")
    if ret != 0:
        return
        
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Control, 0)
    log_camera(f"Open device return: {ret}")
    if ret != 0:
        cam.MV_CC_DestroyHandle()
        return
        
    cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    
    # Disable auto exposure and auto gain so manual settings can be modified
    try:
        cam.MV_CC_SetEnumValue("ExposureAuto", 0) # 0 = Off
        cam.MV_CC_SetEnumValue("GainAuto", 0) # 0 = Off
    except Exception as e:
        log_camera(f"Warning: could not disable auto exposure/gain: {e}")
    
    stParam = MVCC_INTVALUE()
    ctypes.memset(ctypes.byref(stParam), 0, ctypes.sizeof(stParam))
    cam.MV_CC_GetIntValue("PayloadSize", stParam)
    nPayloadSize = stParam.nCurValue
    log_camera(f"Payload size: {nPayloadSize}")
    
    data = (ctypes.c_ubyte * nPayloadSize)()
    frame_info = MV_FRAME_OUT_INFO_EX()
    ctypes.memset(ctypes.byref(frame_info), 0, ctypes.sizeof(frame_info))
    
    ret = cam.MV_CC_StartGrabbing()
    log_camera(f"Start grabbing return: {ret}")
    if ret != 0:
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        return
        
    last_params = {}
    last_check_time = 0
    
    try:
        log_camera("Entering frame grab loop...")
        consecutive_failures = 0
        while True:
            current_time = time.time()
            if current_time - last_check_time > 0.5:
                try:
                    with open(params_file, "r") as f:
                        all_params = json.load(f)
                        current_params = all_params.get(cam_idx, {})
                        
                        if current_params != last_params:
                            # Detect changes in resolution or offsets
                            res_changed = False
                            for key in ["width", "height", "offsetX", "offsetY"]:
                                if current_params.get(key) != last_params.get(key):
                                    res_changed = True
                                    break
                            
                            # If resolution/offset changed, we must stop grabbing before setting them
                            if res_changed:
                                log_camera("Stopping grabbing to apply resolution/offset changes...")
                                cam.MV_CC_StopGrabbing()
                                
                                # Set offsets to 0 first to prevent out-of-bounds parameter errors when shrinking width/height
                                cam.MV_CC_SetIntValue("OffsetX", 0)
                                cam.MV_CC_SetIntValue("OffsetY", 0)
                                
                                # Query actual camera limits
                                w_limit = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("Width", w_limit)
                                h_limit = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("Height", h_limit)
                                
                                # Apply Width / Height (must be multiples of 8 or 4 for Hikvision)
                                if "width" in current_params and current_params["width"] is not None:
                                    w_val = int(current_params["width"])
                                    w_min = w_limit.nMin if w_limit.nMin > 0 else 32
                                    w_max = w_limit.nMax if w_limit.nMax > 0 else 2448
                                    w_val = max(w_min, min(w_max, w_val))
                                    w_val = (w_val // 8) * 8
                                    r = cam.MV_CC_SetIntValue("Width", w_val)
                                    log_camera(f"Set Width to {w_val} (limits: {w_min}-{w_max}) ret={r}")
                                    
                                if "height" in current_params and current_params["height"] is not None:
                                    h_val = int(current_params["height"])
                                    h_min = h_limit.nMin if h_limit.nMin > 0 else 8
                                    h_max = h_limit.nMax if h_limit.nMax > 0 else 2048
                                    h_val = max(h_min, min(h_max, h_val))
                                    h_val = (h_val // 4) * 4
                                    r = cam.MV_CC_SetIntValue("Height", h_val)
                                    log_camera(f"Set Height to {h_val} (limits: {h_min}-{h_max}) ret={r}")
                                    
                                # Query the actual applied width/height and offsets limits
                                actual_w = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("Width", actual_w)
                                actual_h = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("Height", actual_h)
                                
                                ox_limit = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("OffsetX", ox_limit)
                                oy_limit = MVCC_INTVALUE()
                                cam.MV_CC_GetIntValue("OffsetY", oy_limit)
                                
                                # Now apply Offsets using hardware-reported maximums
                                if "offsetX" in current_params and current_params["offsetX"] is not None:
                                    ox = int(current_params["offsetX"])
                                    ox = max(ox_limit.nMin, min(ox_limit.nMax, ox))
                                    ox = (ox // 8) * 8
                                    r = cam.MV_CC_SetIntValue("OffsetX", ox)
                                    log_camera(f"Set OffsetX to {ox} (max: {ox_limit.nMax}) ret={r}")
                                    
                                if "offsetY" in current_params and current_params["offsetY"] is not None:
                                    oy = int(current_params["offsetY"])
                                    oy = max(oy_limit.nMin, min(oy_limit.nMax, oy))
                                    oy = (oy // 4) * 4
                                    r = cam.MV_CC_SetIntValue("OffsetY", oy)
                                    log_camera(f"Set OffsetY to {oy} (max: {oy_limit.nMax}) ret={r}")
                                    
                                # Re-retrieve payload size and reallocate buffer
                                ctypes.memset(ctypes.byref(stParam), 0, ctypes.sizeof(stParam))
                                cam.MV_CC_GetIntValue("PayloadSize", stParam)
                                nPayloadSize = stParam.nCurValue
                                data = (ctypes.c_ubyte * nPayloadSize)()
                                log_camera(f"New payload size: {nPayloadSize}")
                                
                                # Restart grabbing
                                ret = cam.MV_CC_StartGrabbing()
                                log_camera(f"Restart grabbing return: {ret}")
                                
                            # ExposureTime and Gain can be updated while grabbing
                            if "exposure" in current_params and current_params["exposure"] is not None:
                                exp_val = float(current_params["exposure"])
                                # Clip to valid camera range [100.0, 100000.0]
                                exp_val = max(100.0, min(100000.0, exp_val))
                                r = cam.MV_CC_SetFloatValue("ExposureTime", exp_val)
                                log_camera(f"Set ExposureTime to {exp_val} (original: {current_params['exposure']}) ret={r}")
                                
                            if "gain" in current_params and current_params["gain"] is not None:
                                g_val = float(current_params["gain"])
                                # Clip to valid camera range [0.0, 23.98]
                                g_val = max(0.0, min(23.98, g_val))
                                r = cam.MV_CC_SetFloatValue("Gain", g_val)
                                log_camera(f"Set Gain to {g_val} (original: {current_params['gain']}) ret={r}")
                                
                            last_params = current_params.copy()
                except Exception as pe:
                    log_camera(f"Error updating params: {pe}")
                last_check_time = current_time
                
            ret = cam.MV_CC_GetOneFrameTimeout(ctypes.byref(data), nPayloadSize, frame_info, 1000)
            if ret == 0:
                consecutive_failures = 0
                w, h = frame_info.nWidth, frame_info.nHeight
                pf = frame_info.enPixelType
                img = np.frombuffer(data, dtype=np.uint8, count=frame_info.nFrameLen)
                
                display_img = None
                try:
                    if pf == PixelType_Gvsp_BGR8_Packed:
                        display_img = img.reshape((h, w, 3))
                    elif pf == PixelType_Gvsp_RGB8_Packed:
                        display_img = cv2.cvtColor(img.reshape((h, w, 3)), cv2.COLOR_RGB2BGR)
                    elif pf == PixelType_Gvsp_Mono8:
                        display_img = img.reshape((h, w))
                    elif pf == PixelType_Gvsp_BayerRG8:
                        display_img = cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_RG2BGR)
                    elif pf == PixelType_Gvsp_BayerGB8:
                        display_img = cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_GB2BGR)
                    elif pf == PixelType_Gvsp_BayerBG8:
                        display_img = cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_BG2BGR)
                    elif pf == PixelType_Gvsp_BayerGR8:
                        display_img = cv2.cvtColor(img.reshape((h, w)), cv2.COLOR_BAYER_GR2BGR)
                    else:
                        display_img = img.reshape((h, w))
                except Exception as re:
                    log_camera(f"Reshape/color error: {re}")
                    
                if display_img is not None:
                    # Draw zone borders on the frame
                    try:
                        zones_file = os.path.join(BASE_DIR, "zones_config.json")
                        if os.path.exists(zones_file):
                            with open(zones_file, "r") as zf:
                                zone_data = json.load(zf)
                            if isinstance(zone_data, list):
                                for zi, zinfo in enumerate(zone_data):
                                    zcoords = zinfo.get("zone", [])
                                    zname = zinfo.get("name", f"Zone-{zi+1}")
                                    if len(zcoords) == 4:
                                        zx, zy, zw, zh = int(zcoords[0]), int(zcoords[1]), int(zcoords[2]), int(zcoords[3])
                                        # Clamp to image bounds
                                        img_h, img_w = display_img.shape[:2]
                                        zx1 = max(0, min(zx, img_w - 1))
                                        zy1 = max(0, min(zy, img_h - 1))
                                        zx2 = max(0, min(zx + zw, img_w))
                                        zy2 = max(0, min(zy + zh, img_h))
                                        # Red rectangle border (thickness 2)
                                        if len(display_img.shape) == 3:
                                            cv2.rectangle(display_img, (zx1, zy1), (zx2, zy2), (0, 0, 255), 2)
                                            # Zone label with background
                                            label = zname
                                            font = cv2.FONT_HERSHEY_SIMPLEX
                                            font_scale = 0.7
                                            thickness = 2
                                            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
                                            cv2.rectangle(display_img, (zx1, zy1), (zx1 + tw + 8, zy1 + th + 10), (0, 0, 255), -1)
                                            cv2.putText(display_img, label, (zx1 + 4, zy1 + th + 5), font, font_scale, (255, 255, 255), thickness)
                                        else:
                                            cv2.rectangle(display_img, (zx1, zy1), (zx2, zy2), 255, 2)
                    except Exception as ze:
                        pass  # Don't crash video feed if zones file is broken
                    
                    if h > 1080 or w > 1920:
                        display_img = cv2.resize(display_img, (w//2, h//2))
                    ret_encode, buffer = cv2.imencode('.jpg', display_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret_encode:
                        frame = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                consecutive_failures += 1
                if consecutive_failures % 30 == 0:
                    log_camera(f"GetOneFrameTimeout returned error code: {ret} ({consecutive_failures} consecutive failures)")
                time.sleep(0.03)
    finally:
        log_camera("Exiting frame grab loop and releasing resources.")
        cam.MV_CC_StopGrabbing()
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()

@app.get("/api/video_feed/{cam_idx}")
def video_feed(cam_idx: str):
    return StreamingResponse(generate_camera_frames(cam_idx), media_type="multipart/x-mixed-replace; boundary=frame")

CAMERA_REF_FILE = os.path.join(BASE_DIR, "wate", "camera_ref.txt")
CAMERA_PARAMS_FILE = os.path.join(BASE_DIR, "camera_params.json")

class CameraRefData(BaseModel):
    references: list

class CameraParamsData(BaseModel):
    params: dict

@app.get("/api/camera-ref")
def get_camera_ref():
    if os.path.exists(CAMERA_REF_FILE):
        with open(CAMERA_REF_FILE, "r") as f:
            return json.load(f)
    return {"references": ["", "", ""]}

@app.post("/api/camera-ref")
def save_camera_ref(req: CameraRefData):
    with open(CAMERA_REF_FILE, "w") as f:
        json.dump({"references": req.references}, f)
    return {"message": "Camera references saved successfully"}

@app.get("/api/camera-params")
def get_camera_params():
    if os.path.exists(CAMERA_PARAMS_FILE):
        with open(CAMERA_PARAMS_FILE, "r") as f:
            return json.load(f)
    return {}

@app.post("/api/camera-params")
def save_camera_params(req: CameraParamsData):
    with open(CAMERA_PARAMS_FILE, "w") as f:
        json.dump(req.params, f)
    return {"message": "Camera parameters saved successfully"}

@app.post("/api/customizations")
def save_customizations(req: CustomizationsData):
    os.makedirs(os.path.dirname(VALUE_FILE), exist_ok=True)
    with open(VALUE_FILE, "w") as f:
        levels = ["400", "320", "240", "210", "180"]
        for level in levels:
            if level in req.values:
                val = req.values[level]
                f.write(f"{level},{val['min']},{val['max']}\n")
    return {"message": "Customizations saved successfully"}

@app.get("/api/camera-params")
def get_camera_params():
    if os.path.exists(CAMERA_PARAMS_FILE):
        import json
        try:
            with open(CAMERA_PARAMS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            return {}
    return {}

@app.post("/api/camera-params")
def save_camera_params(req: CameraParamsData):
    import json
    os.makedirs(os.path.dirname(CAMERA_PARAMS_FILE), exist_ok=True)
    with open(CAMERA_PARAMS_FILE, "w") as f:
        json.dump(req.params, f)
    return {"message": "Camera parameters saved successfully"}

# ----------------- TIME SETTINGS -----------------
TIME_SETTINGS_DIR = os.path.join(BASE_DIR, "wate")

@app.get("/api/time-settings/{belt_id}")
def get_time_settings(belt_id: int):
    file_path = os.path.join(TIME_SETTINGS_DIR, f"{belt_id}(A)-time.txt")
    if not os.path.exists(file_path):
        return {"values": ["", "", "", "", "", "", ""]}
    
    try:
        with open(file_path, "r") as f:
            content = f.read().strip()
        
        values = []
        if len(content) >= 34:
            for i in range(7):
                idx = 6 + i * 4
                val = content[idx:idx+4]
                values.append(val if val != "0000" else "")
            return {"values": values}
    except Exception as e:
        print(f"Error reading time settings: {e}")
        
    return {"values": ["", "", "", "", "", "", ""]}

class TimeSettingInput(BaseModel):
    values: list[str]

@app.post("/api/time-settings/{belt_id}")
def save_time_settings(belt_id: int, payload: TimeSettingInput):
    belt_code = str(10 + belt_id)
    box_str = ""
    for i in range(7):
        val = payload.values[i] if i < len(payload.values) else ""
        if not val:
            box_str += "0000"
        else:
            box_str += str(val).zfill(4)[:4]
            
    extra_zeros = "0000" * 4 # 4 remaining zero blocks since 11 total
    # wait, the example had 6 numbers + 5 zero blocks = 11 total. So 7 boxes + 4 zero blocks = 11.
    final_str = f"0000{belt_code}{box_str}{extra_zeros}0099|"
    
    file_path = os.path.join(TIME_SETTINGS_DIR, f"{belt_id}(A)-time.txt")
    try:
        with open(file_path, "w") as f:
            f.write(final_str)
        return {"status": "success", "message": f"Saved {belt_id}(A)-time.txt"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
# -------------------------------------------------

class TimeSettingsAllInput(BaseModel):
    belts: dict[str, list[str]]

@app.get("/api/time-settings-all")
def get_time_settings_all():
    all_values = {}
    for belt_id in range(1, 16):
        file_path = os.path.join(TIME_SETTINGS_DIR, f"{belt_id}(A)-time.txt")
        values = ["", "", "", "", "", "", ""]
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    content = f.read().strip()
                if len(content) >= 34:
                    for i in range(7):
                        idx = 6 + i * 4
                        val = content[idx:idx+4]
                        values[i] = val if val != "0000" else ""
            except:
                pass
        all_values[str(belt_id)] = values
    return {"all_values": all_values}

@app.post("/api/time-settings-all")
def save_time_settings_all(payload: TimeSettingsAllInput):
    try:
        for belt_id_str, values in payload.belts.items():
            belt_id = int(belt_id_str)
            belt_code = str(10 + belt_id)
            box_str = ""
            for i in range(7):
                val = values[i] if i < len(values) else ""
                if not val:
                    box_str += "0000"
                else:
                    box_str += str(val).zfill(4)[:4]
                    
            extra_zeros = "0000" * 4 
            final_str = f"0000{belt_code}{box_str}{extra_zeros}0099|"
            
            file_path = os.path.join(TIME_SETTINGS_DIR, f"{belt_id}(A)-time.txt")
            with open(file_path, "w") as f:
                f.write(final_str)
                
        return {"status": "success", "message": "Saved all belts"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------

@app.post("/api/restart-device")
def restart_device():
    try:
        os.system("shutdown /r /t 0")
        return {"status": "success", "message": "Device is restarting..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/shutdown-device")
def shutdown_device():
    try:
        os.system("shutdown /s /t 0")
        return {"status": "success", "message": "Device is shutting down..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/open-teamviewer")
def open_teamviewer():
    try:
        import psutil
        # Check if already running
        for p in psutil.process_iter(['name']):
            if p.info['name'] and 'teamviewer' in p.info['name'].lower():
                return {"status": "success", "message": "TeamViewer is already running in background"}

        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE
        
        tv_path = r"C:\Program Files\TeamViewer\TeamViewer.exe"
        if os.path.exists(tv_path):
            subprocess.Popen([tv_path], startupinfo=startupinfo)
        else:
            tv_path_x86 = r"C:\Program Files (x86)\TeamViewer\TeamViewer.exe"
            if os.path.exists(tv_path_x86):
                subprocess.Popen([tv_path_x86], startupinfo=startupinfo)
            else:
                return {"status": "error", "message": "TeamViewer not found at default paths"}
        return {"status": "success", "message": "TeamViewer started in background"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/open-wifi")
def open_wifi():
    try:
        os.system("start ms-availablenetworks:")
        return {"status": "success", "message": "Wi-Fi settings opened"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/open-keyboard")
def open_keyboard():
    try:
        # Use osk.exe (On-Screen Keyboard)
        os.system("start osk")
        return {"status": "success", "message": "Keyboard opened"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class ValveCommand(BaseModel):
    belt_id: int
    port_id: int

@app.post("/api/fire-valve")
def fire_valve(cmd: ValveCommand):
    print(f"[ACTION] Firing air for Belt {cmd.belt_id}, Port {cmd.port_id}", flush=True)
    
    # Read the COM port from the shared configuration file
    com_file = r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt"
    com_port = None
    if os.path.exists(com_file):
        try:
            with open(com_file, 'r') as f:
                content = f.read().strip()
                if content.startswith("COM"):
                    com_port = content
        except Exception as e:
            print(f"Error reading COM file: {e}")
            
    if not com_port:
        return {"status": "error", "message": "COM port file not found or invalid."}
        
    try:
        # Open port, send command, close port immediately
        with serial.Serial(port=com_port, baudrate=115200, timeout=1) as ser:
            command_str = f"{cmd.port_id}|"
            ser.write(command_str.encode())
        return {"status": "success", "message": f"Fired {command_str} on {com_port}"}
    except Exception as e:
        print(f"Serial Error in fire_valve: {e}")
        return {"status": "error", "message": f"Serial Error: {e}"}

@app.get("/api/status")
def get_status():
    global active_processes, current_mode, last_terminal_message
    active_processes = [p for p in active_processes if p.poll() is None]
    if len(active_processes) == 0:
        if current_mode != "Stopped" and not last_terminal_message.startswith("Error"):
            last_terminal_message = "All scripts stopped."
        current_mode = "Stopped"
    return {
        "active_processes": len(active_processes), 
        "current_mode": current_mode,
        "terminal_message": last_terminal_message
    }

@app.get("/api/graph-data")
def get_graph_data():
    return grade_counts

# -------------------------------------------------
# CAMERA SETTINGS
# -------------------------------------------------


class CameraRefInput(BaseModel):
    references: list[str]

@app.get("/api/camera-check")
def check_cameras():
    try:
        MvCamera.MV_CC_Initialize()
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            return {"status": "success", "cameras": []}
            
        cameras = []
        for i in range(deviceList.nDeviceNum):
            info = ctypes.cast(deviceList.pDeviceInfo[i], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
            serial = ""
            try:
                if info.nTLayerType == MV_GIGE_DEVICE:
                    serial = bytes(info.SpecialInfo.stGigEInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
                elif info.nTLayerType == MV_USB_DEVICE:
                    serial = bytes(info.SpecialInfo.stUsb3VInfo.chSerialNumber).decode(errors="ignore").strip("\x00")
            except Exception:
                pass
            if serial:
                cameras.append(serial)
                
        return {"status": "success", "cameras": cameras}
    except Exception as e:
        print(f"Error checking cameras: {e}")
        return {"status": "error", "message": str(e), "cameras": []}



class MainSettingsInput(BaseModel):
    value: str
    belt_number: int

@app.post("/api/main-settings")
def save_main_settings(payload: MainSettingsInput):
    try:
        letters = "abcdefghijklmno"
        if 1 <= payload.belt_number <= 15:
            letter = letters[payload.belt_number - 1]
            comport_dir = r"D:\4_belt_main\4_belt\comport info"
            os.makedirs(comport_dir, exist_ok=True)
            file_path = os.path.join(comport_dir, f"comport({letter}).txt")
            with open(file_path, "w") as f:
                f.write(str(payload.value))
            return {"status": "success", "message": f"Saved setting for Belt {payload.belt_number}"}
        else:
            return {"status": "error", "message": "Invalid belt number"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

COMPORT_REF_FILE = os.path.join(BASE_DIR, "wate", "comport_ref.txt")

@app.get("/api/comport-check")
def comport_check():
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        comports = []
        for p in ports:
            comports.append(p.device)
        return {"status": "success", "comports": comports}
    except ImportError:
        # Fallback: scan common COM ports manually
        import ctypes
        comports = []
        for i in range(1, 21):
            try:
                port = f"COM{i}"
                handle = ctypes.windll.kernel32.CreateFileW(
                    f"\\\\.\\{port}", 0xC0000000, 0, None, 3, 0, None
                )
                if handle != -1:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    comports.append(port)
            except:
                pass
        return {"status": "success", "comports": comports}
    except Exception as e:
        return {"status": "error", "message": str(e), "comports": []}

@app.get("/api/comport-ref")
def get_comport_ref():
    if os.path.exists(COMPORT_REF_FILE):
        try:
            with open(COMPORT_REF_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"references": ["", "", ""]}

class ComportRefData(BaseModel):
    references: list

@app.post("/api/comport-ref")
def save_comport_ref(req: ComportRefData):
    os.makedirs(os.path.dirname(COMPORT_REF_FILE), exist_ok=True)
    with open(COMPORT_REF_FILE, "w") as f:
        json.dump({"references": req.references}, f)
    return {"message": "Comport references saved successfully"}
@app.get("/api/zones")
def get_zones():
    zones_file = os.path.join(BASE_DIR, "zones_config.json")
    default_zones = [
        {"zone": [100, 100, 370, 1920], "name": "Zone-1"},
        {"zone": [540, 100, 350, 1910], "name": "Zone-2"},
        {"zone": [960, 100, 360, 1910], "name": "Zone-3"},
        {"zone": [1400, 100, 340, 1910], "name": "Zone-4"},
        {"zone": [1840, 100, 370, 1910], "name": "Zone-5"}
    ]
    if os.path.exists(zones_file):
        try:
            with open(zones_file, "r") as f:
                zones = json.load(f)
                if isinstance(zones, list) and len(zones) >= 5:
                    return zones
                else:
                    return default_zones
        except Exception as e:
            pass
            
    # If missing or broken, create default to avoid empty UI
    try:
        with open(zones_file, "w") as f:
            json.dump(default_zones, f, indent=4)
    except:
        pass
        
    return default_zones

@app.post("/api/zones")
async def save_zones(request: Request):
    zones_file = os.path.join(BASE_DIR, "zones_config.json")
    try:
        payload = await request.json()
        with open(zones_file, "w") as f:
            json.dump(payload, f, indent=4)
        return {"status": "success", "message": "Zones configuration saved successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Serve static frontend files
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

# Mount everything except index.html as static assets
if os.path.exists(FRONTEND_DIST) and os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve specific requested files if they exist in dist (like favicon)
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
