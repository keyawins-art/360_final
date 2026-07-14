import os
import sys
import platform
import json
from ctypes import *
import numpy as np
import cv2
from hardware import read_target_serial

if platform.system()=="Windows":
    SDK_PATH=r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
    if os.path.exists(SDK_PATH):
        sys.path.append(SDK_PATH)

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
            # Note: We still point to the main folder's camera_ref.txt
            ref_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wate", "camera_ref.txt")
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
            params_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "camera_params.json")
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
            
            if "exposure" in params and params["exposure"]:
                self.cam.MV_CC_SetFloatValue("ExposureTime", float(params["exposure"]))
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

        if self.cam.MV_CC_StartGrabbing()!=0:
            return False

        self.is_grabbing=True
        print("Camera connected")
        return True

    def check_and_update_parameters(self):
        params_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "camera_params.json")
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
