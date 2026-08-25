# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\i7\\Desktop\\360\\frontend\\dist', 'frontend/dist'), ('C:\\Users\\i7\\Desktop\\360\\grading', 'grading'), ('C:\\Users\\i7\\Desktop\\360\\defoult', 'defoult'), ('C:\\Users\\i7\\Desktop\\360\\grading_color', 'grading_color'), ('C:\\Users\\i7\\Desktop\\360\\wate', 'wate'), ('C:\\Users\\i7\\Desktop\\360\\Python\\MvImport', 'MvImport'), ('C:\\Users\\i7\\Desktop\\360\\Python\\MvImport', 'Python/MvImport'), ('C:\\Users\\i7\\Desktop\\360\\best.onnx', '.'), ('C:\\Users\\i7\\Desktop\\360\\zones_config.json', '.'), ('C:\\Users\\i7\\Desktop\\360\\camera_params.json', '.')]
binaries = []
hiddenimports = ['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi', 'serial', 'serial.tools.list_ports', 'cv2', 'numpy', 'psutil', 'pydantic', 'runpy', 'multiprocessing', 'ctypes', 'PIL', 'asyncio', 'webview', 'webview.platforms.edgechromium', 'webview.platforms.winforms', 'pythonnet', 'clr_loader']
tmp_ret = collect_all('onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pythonnet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('clr_loader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\i7\\Desktop\\360\\backend\\server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'tensorflow', 'keras', 'tensorboard', 'IPython', 'matplotlib', 'scipy', 'sympy', 'onnx', 'jupyter', 'ipykernel'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='360_App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='360_App',
)
