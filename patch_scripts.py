import os, glob

base_dirs = [r'd:\Keya Work\360\grading', r'd:\Keya Work\360\grading_color']
target_line = 'self.cam.MV_CC_SetEnumValue("TriggerMode",MV_TRIGGER_MODE_OFF)'
patch = '''        # Apply custom camera parameters from JSON
        try:
            import json
            with open(r"d:\Keya Work\360\camera_ref.json", "r") as f:
                refs = json.load(f).get("references", ["", "", ""])
            # find matching camIdx (1, 2, or 3) based on target_serial
            cam_idx = None
            for idx, ref in enumerate(refs):
                if ref.strip() == target_serial.strip():
                    cam_idx = str(idx + 1)
                    break
            
            if cam_idx is not None:
                with open(r"d:\Keya Work\360\camera_params.json", "r") as f:
                    params = json.load(f).get(cam_idx, {})
                
                # Apply Parameters
                if "exposure" in params and params["exposure"]:
                    self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
                if "gain" in params and params["gain"]:
                    self.cam.MV_CC_SetFloatValue("Gain", float(params["gain"]))
                if "width" in params and params["width"]:
                    self.cam.MV_CC_SetIntValue("Width", int(params["width"]))
                if "height" in params and params["height"]:
                    self.cam.MV_CC_SetIntValue("Height", int(params["height"]))
                if "offsetX" in params and params["offsetX"]:
                    self.cam.MV_CC_SetIntValue("OffsetX", int(params["offsetX"]))
                if "offsetY" in params and params["offsetY"]:
                    self.cam.MV_CC_SetIntValue("OffsetY", int(params["offsetY"]))
                print(f"Applied Camera Parameters for Cam {cam_idx}: {params}")
            else:
                print(f"Serial {target_serial} not found in camera references, skipping custom parameters.")
        except Exception as e:
            print(f"Error applying camera parameters: {e}")
'''

for d in base_dirs:
    for f in glob.glob(os.path.join(d, '*.py')):
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
        if target_line in content and 'camera_ref.json' not in content:
            content = content.replace(target_line, target_line + '\n\n' + patch)
            with open(f, 'w', encoding='utf-8') as file:
                file.write(content)
            print(f'Patched {f}')
