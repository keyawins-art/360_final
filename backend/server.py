from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import psutil
import glob
import threading

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_processes = []
current_mode = "Stopped"
BASE_DIR = r"d:\Keya Work\360"
VALUE_FILE = r"d:\Keya Work\360\wate\value.txt"

grade_counts = {
    "180": 0, "210": 0, "240": 0, "320": 0, "400": 0,
    "1000": 0, "dry": 0, "blackdot": 0, "shell": 0, "multiple_cashews": 0
}

class CustomizationsData(BaseModel):
    values: dict


def reset_counts():
    global grade_counts
    for k in grade_counts:
        grade_counts[k] = 0

def output_reader(proc):
    try:
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            if "Grade:" in line:
                parts = line.split("|")
                for part in parts:
                    if "Grade:" in part:
                        grade_val = part.split(":")[1].strip()
                        if grade_val in grade_counts:
                            grade_counts[grade_val] += 1
            print(f"[SCRIPT] {line.strip()}", flush=True)
    except Exception as e:
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
                bufsize=1
            )
            active_processes.append(process)
            
            # Start background thread to read stdout
            t = threading.Thread(target=output_reader, args=(process,), daemon=True)
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

# ----------------- TIME SETTINGS -----------------
TIME_SETTINGS_DIR = r"d:\Keya Work\360\wate"

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
        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 6  # SW_MINIMIZE
        
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

class ValveCommand(BaseModel):
    belt_id: int
    port_id: int

@app.post("/api/fire-valve")
def fire_valve(cmd: ValveCommand):
    print(f"[ACTION] Firing air for Belt {cmd.belt_id}, Port {cmd.port_id}", flush=True)
    return {"status": "success", "message": f"Fired Belt {cmd.belt_id} Port {cmd.port_id}"}

@app.get("/api/status")
def get_status():
    global active_processes, current_mode
    active_processes = [p for p in active_processes if p.poll() is None]
    if len(active_processes) == 0:
        current_mode = "Stopped"
    return {"active_processes": len(active_processes), "current_mode": current_mode}

@app.get("/api/graph-data")
def get_graph_data():
    return grade_counts

# -------------------------------------------------
# CAMERA SETTINGS
# -------------------------------------------------

CAMERA_REF_FILE = os.path.join(BASE_DIR, "wate", "camera_ref.txt")

class CameraRefInput(BaseModel):
    references: list[str]

@app.get("/api/camera-check")
def check_cameras():
    # Mocking camera detection. In the future this can use cv2, wmi or pygrabber.
    import time
    time.sleep(0.5) # Simulate checking delay
    return {"status": "success", "cameras": ["Cam 1", "Cam 2", "Cam 3"]}

@app.get("/api/camera-ref")
def get_camera_ref():
    try:
        if os.path.exists(CAMERA_REF_FILE):
            with open(CAMERA_REF_FILE, "r") as f:
                content = f.read().strip()
            import json
            try:
                refs = json.loads(content)
                if isinstance(refs, list):
                    # Ensure it has exactly 3 elements
                    while len(refs) < 3: refs.append("")
                    return {"status": "success", "references": refs[:3]}
            except Exception:
                pass
    except Exception:
        pass
    return {"status": "success", "references": ["", "", ""]}

@app.post("/api/camera-ref")
def save_camera_ref(payload: CameraRefInput):
    try:
        import json
        with open(CAMERA_REF_FILE, "w") as f:
            f.write(json.dumps(payload.references))
        return {"status": "success", "message": "Reference settings saved"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
