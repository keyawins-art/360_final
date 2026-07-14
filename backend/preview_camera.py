import sys
import os
import json
import time
import ctypes
import numpy as np
import cv2

# Ensure MVS SDK is in path
try:
    from MvCameraControl_class import *
except:
    sys.path.append(r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport")
    try:
        from MvCameraControl_class import *
    except:
        pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python preview_camera.py <camIdx>")
        sys.exit(1)
        
    cam_idx = sys.argv[1]
    
    # Read camera reference
    refs_file = r"d:\Keya Work\360\camera_ref.json"
    params_file = r"d:\Keya Work\360\camera_params.json"
    
    try:
        with open(refs_file, "r") as f:
            refs = json.load(f).get("references", ["", "", ""])
    except:
        refs = ["", "", ""]
        
    target_serial = ""
    try:
        target_serial = refs[int(cam_idx) - 1].strip()
    except:
        pass
        
    if not target_serial:
        print(f"No serial assigned to Camera {cam_idx}")
        sys.exit(1)
        
    # Init MVS
    MvCamera.MV_CC_Initialize()
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    if MvCamera.MV_CC_EnumDevices(tlayerType, deviceList) != 0:
        print("Enum devices failed")
        sys.exit(1)
        
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
                
            if serial == target_serial:
                selected = info
                break
        except:
            pass
            
    if selected is None:
        print(f"Camera with serial {target_serial} not found")
        sys.exit(1)
        
    cam = MvCamera()
    if cam.MV_CC_CreateHandle(selected) != 0:
        print("Create handle failed")
        sys.exit(1)
        
    if cam.MV_CC_OpenDevice(MV_ACCESS_Control, 0) != 0:
        print("Open device failed. Make sure no other script is using it!")
        sys.exit(1)
        
    cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    
    stParam = MVCC_INTVALUE()
    ctypes.memset(ctypes.byref(stParam), 0, ctypes.sizeof(stParam))
    cam.MV_CC_GetIntValue("PayloadSize", stParam)
    nPayloadSize = stParam.nCurValue
    
    data = (ctypes.c_ubyte * nPayloadSize)()
    frame_info = MV_FRAME_OUT_INFO_EX()
    ctypes.memset(ctypes.byref(frame_info), 0, ctypes.sizeof(frame_info))
    
    if cam.MV_CC_StartGrabbing() != 0:
        print("Start grabbing failed")
        sys.exit(1)
        
    print(f"Started Preview for Camera {cam_idx} (Serial: {target_serial})")
    
    window_name = f"Camera {cam_idx} Preview (Press 'Q' to close)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    last_params = {}
    last_check_time = 0
    
    while True:
        # Update params every 1 second
        current_time = time.time()
        if current_time - last_check_time > 1:
            try:
                with open(params_file, "r") as f:
                    all_params = json.load(f)
                    current_params = all_params.get(cam_idx, {})
                    
                    if current_params != last_params:
                        last_params = current_params.copy()
                        if "exposure" in current_params and current_params["exposure"]:
                            cam.MV_CC_SetFloatValue("ExposureTime", float(current_params["exposure"]))
                        if "gain" in current_params and current_params["gain"]:
                            cam.MV_CC_SetFloatValue("Gain", float(current_params["gain"]))
                        if "width" in current_params and current_params["width"]:
                            cam.MV_CC_SetIntValue("Width", int(current_params["width"]))
                        if "height" in current_params and current_params["height"]:
                            cam.MV_CC_SetIntValue("Height", int(current_params["height"]))
                        if "offsetX" in current_params and current_params["offsetX"]:
                            cam.MV_CC_SetIntValue("OffsetX", int(current_params["offsetX"]))
                        if "offsetY" in current_params and current_params["offsetY"]:
                            cam.MV_CC_SetIntValue("OffsetY", int(current_params["offsetY"]))
            except:
                pass
            last_check_time = current_time
            
        ret = cam.MV_CC_GetOneFrameTimeout(ctypes.byref(data), nPayloadSize, frame_info, 1000)
        if ret == 0:
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
            except:
                pass
                
            if display_img is not None:
                # Add text overlay
                cv2.putText(display_img, f"Live Preview - Camera {cam_idx}", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow(window_name, display_img)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27: # q or ESC
            break
            
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

    # Clean up
    cam.MV_CC_StopGrabbing()
    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()
    MvCamera.MV_CC_Finalize()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
