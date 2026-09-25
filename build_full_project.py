import os
import sys
import subprocess
import shutil
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def build():
    print("=" * 70)
    print(" [START] BUILDING 360 SORTING SYSTEM STANDALONE APPLICATION (.EXE)")
    print("=" * 70)

    # 0. Kill any existing running instance
    try:
        subprocess.run(["taskkill", "/F", "/IM", "360_App.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # 1. Build Frontend (React + Vite)
    print("\n[STEP 1/4] Building Frontend (React + Vite)...")
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    res = subprocess.run(["npm", "run", "build"], cwd=frontend_dir, shell=True)
    if res.returncode != 0:
        print("[ERROR] Frontend build failed!")
        return False
    print("[SUCCESS] Frontend build completed!")

    # 2. Prepare PyInstaller Command
    print("\n[STEP 2/4] Bundling Backend, AI Engine, SDK & Dependencies with PyInstaller...")
    
    frontend_dist = os.path.join(BASE_DIR, "frontend", "dist")
    grading_dir = os.path.join(BASE_DIR, "grading")
    defoult_dir = os.path.join(BASE_DIR, "defoult")
    grading_color_dir = os.path.join(BASE_DIR, "grading_color")
    wate_dir = os.path.join(BASE_DIR, "wate")
    mvimport_dir = os.path.join(BASE_DIR, "Python", "MvImport")
    best_onnx = os.path.join(BASE_DIR, "best.onnx")
    zones_json = os.path.join(BASE_DIR, "zones_config.json")
    camera_json = os.path.join(BASE_DIR, "camera_params.json")
    server_py = os.path.join(BASE_DIR, "backend", "server.py")

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name", "360_App",
        "--clean",
        "--add-data", f"{frontend_dist};frontend/dist",
        "--add-data", f"{grading_dir};grading",
        "--add-data", f"{defoult_dir};defoult",
        "--add-data", f"{grading_color_dir};grading_color",
        "--add-data", f"{wate_dir};wate",
        "--add-data", f"{mvimport_dir};MvImport",
        "--add-data", f"{mvimport_dir};Python/MvImport",
        "--add-data", f"{best_onnx};.",
        "--add-data", f"{zones_json};.",
        "--add-data", f"{camera_json};.",
        "--collect-all", "onnxruntime",
        "--collect-all", "cv2",
        "--collect-all", "webview",
        "--collect-all", "pythonnet",
        "--collect-all", "clr_loader",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "fastapi",
        "--hidden-import", "serial",
        "--hidden-import", "serial.tools.list_ports",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "psutil",
        "--hidden-import", "pydantic",
        "--hidden-import", "runpy",
        "--hidden-import", "multiprocessing",
        "--hidden-import", "ctypes",
        "--hidden-import", "PIL",
        "--hidden-import", "asyncio",
        "--hidden-import", "webview",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "webview.platforms.winforms",
        "--hidden-import", "pythonnet",
        "--hidden-import", "clr_loader",
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "torchaudio",
        "--exclude-module", "tensorflow",
        "--exclude-module", "keras",
        "--exclude-module", "tensorboard",
        "--exclude-module", "IPython",
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "sympy",
        "--exclude-module", "onnx",
        "--exclude-module", "jupyter",
        "--exclude-module", "ipykernel",
        server_py
    ]

    res = subprocess.run(pyinstaller_cmd, cwd=BASE_DIR)
    if res.returncode != 0:
        print("[ERROR] PyInstaller packaging failed!")
        return False

    dist_app_dir = os.path.join(BASE_DIR, "dist", "360_App")
    exe_path = os.path.join(dist_app_dir, "360_App.exe")

    # 3. Copy runtime configs and helper batch launcher
    print("\n[STEP 3/4] Preparing runtime folders and launchers in dist/360_App...")
    for item in ["zones_config.json", "camera_params.json", "best.onnx", "best.pt", "camera_serial(a).txt", "camera_serial(b).txt"]:
        src = os.path.join(BASE_DIR, item)
        dst = os.path.join(dist_app_dir, item)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    for folder in ["wate", "grading", "defoult", "grading_color"]:
        src_f = os.path.join(BASE_DIR, folder)
        dst_f = os.path.join(dist_app_dir, folder)
        if os.path.exists(src_f):
            try:
                if os.path.exists(dst_f):
                    shutil.rmtree(dst_f, ignore_errors=True)
                shutil.copytree(src_f, dst_f)
            except Exception:
                pass

    # Launcher batch file inside dist/360_App
    launcher_bat = os.path.join(dist_app_dir, "START_APP.bat")
    with open(launcher_bat, "w") as f:
        f.write("@echo off\r\ntitle 360 Sorting Application\r\ncd /d \"%~dp0\"\r\nstart \"\" \"360_App.exe\"\r\n")

    # Root START_360_APP.bat
    root_launcher_bat = os.path.join(BASE_DIR, "START_360_APP.bat")
    with open(root_launcher_bat, "w") as f:
        f.write("@echo off\r\ntitle 360 Machine Sorting Application\r\ncd /d \"%~dp0dist\\360_App\"\r\nstart \"\" \"360_App.exe\"\r\n")

    # 4. Create Portable ZIP for direct distribution to any PC
    print("\n[STEP 4/4] Creating Standalone Portable ZIP (360_App_Portable.zip)...")
    zip_path = os.path.join(BASE_DIR, "dist", "360_App_Portable.zip")
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception:
            pass

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_app_dir):
            for file in files:
                file_abs = os.path.join(root, file)
                rel_path = os.path.relpath(file_abs, os.path.dirname(dist_app_dir))
                zipf.write(file_abs, rel_path)

    print("=" * 70)
    print(" [BUILD COMPLETE] STANDALONE APPLICATION READY!")
    print("=" * 70)
    print(f" -> Standalone Folder : {dist_app_dir}")
    print(f" -> Executable File   : {exe_path}")
    print(f" -> Portable ZIP      : {zip_path}")
    print("\n[HOW TO RUN ON ANY PC]:")
    print(" 1. Copy '360_App_Portable.zip' (or the '360_App' folder) to any Windows PC.")
    print(" 2. Extract it and double-click 'START_APP.bat' or '360_App.exe'.")
    print(" 3. No Python, Node.js, or external library installation is required!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    build()
