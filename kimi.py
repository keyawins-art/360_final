import sys
import os
import json
import time
import ctypes
import numpy as np
import cv2
from threading import Thread, Lock
from queue import Queue

# Ensure MVS SDK is in path
try:
    from MvCameraControl_class import *
except:
    sys.path.append(r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport")
    from MvCameraControl_class import *

class CameraPreview:
    def __init__(self, cam_idx):
        self.cam_idx = cam_idx
        self.cam = None
        self.running = False
        
        # Threading components
        self.frame_queue = Queue(maxsize=2)  # Only keep latest 2 frames
        self.params_lock = Lock()
        self.current_params = {}
        self.last_params_update = 0
        
        # Window setup
        self.window_name = f"Camera {cam_idx} Preview (Press 'Q' to close)"
        
    def load_camera_ref(self):
        refs_file = r"d:\Keya Work\360\camera_ref.json"
        try:
            with open(refs_file, "r") as f:
                refs = json.load(f).get("references", ["", "", ""])
            return refs[int(self.cam_idx) - 1].strip()
        except:
            return ""
    
    def params_watcher(self):
        """Separate thread for file watching - NO blocking in main loop"""
        params_file = r"d:\Keya Work\360\camera_params.json"
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_params_update > 1:
                    with open(params_file, "r") as f:
                        all_params = json.load(f)
                        new_params = all_params.get(self.cam_idx, {})
                    
                    with self.params_lock:
                        if new_params != self.current_params:
                            self.current_params = new_params.copy()
                            self.apply_params(new_params)
                    self.last_params_update = current_time
            except:
                pass
            time.sleep(0.5)  # Reduce CPU usage
    
    def apply_params(self, params):
        """Apply camera parameters safely"""
        if not self.cam:
            return
        try:
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
        except Exception as e:
            print(f"Param apply error: {e}")
    
    def grab_frames(self):
        """Dedicated thread for camera grabbing"""
        data = (ctypes.c_ubyte * self.nPayloadSize)()
        frame_info = MV_FRAME_OUT_INFO_EX()
        ctypes.memset(ctypes.byref(frame_info), 0, ctypes.sizeof(frame_info))
        
        while self.running:
            ret = self.cam.MV_CC_GetOneFrameTimeout(
                ctypes.byref(data), self.nPayloadSize, frame_info, 100
            )
            if ret == 0:
                # Create copy of frame data
                frame_data = {
                    'data': bytes(data[:frame_info.nFrameLen]),
                    'width': frame_info.nWidth,
                    'height': frame_info.nHeight,
                    'pixel_type': frame_info.enPixelType,
                    'frame_len': frame_info.nFrameLen
                }
                
                # Drop old frame if queue full - ALWAYS keep latest
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except:
                        pass
                self.frame_queue.put(frame_data)
    
    def convert_frame(self, frame_data):
        """Fast pixel format conversion"""
        img = np.frombuffer(frame_data['data'], dtype=np.uint8, count=frame_data['frame_len'])
        h, w = frame_data['height'], frame_data['width']
        pf = frame_data['pixel_type']
        
        # Fast path for common formats
        if pf == PixelType_Gvsp_Mono8:
            return img.reshape((h, w))
        elif pf == PixelType_Gvsp_BGR8_Packed:
            return img.reshape((h, w, 3))
        elif pf == PixelType_Gvsp_RGB8_Packed:
            img = img.reshape((h, w, 3))
            return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pf in (PixelType_Gvsp_BayerRG8, PixelType_Gvsp_BayerGB8, 
                    PixelType_Gvsp_BayerBG8, PixelType_Gvsp_BayerGR8):
            img = img.reshape((h, w))
            # Map Bayer to OpenCV constants
            bayer_map = {
                PixelType_Gvsp_BayerRG8: cv2.COLOR_BAYER_RG2BGR,
                PixelType_Gvsp_BayerGB8: cv2.COLOR_BAYER_GB2BGR,
                PixelType_Gvsp_BayerBG8: cv2.COLOR_BAYER_BG2BGR,
                PixelType_Gvsp_BayerGR8: cv2.COLOR_BAYER_GR2BGR,
            }
            return cv2.cvtColor(img, bayer_map.get(pf, cv2.COLOR_BAYER_RG2BGR))
        
        return img.reshape((h, w))  # Fallback
    
    def display_loop(self):
        """Main display thread"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
        fps_counter = 0
        fps_time = time.time()
        display_fps = 0
        
        while self.running:
            # Get latest frame (non-blocking with timeout)
            try:
                frame_data = self.frame_queue.get(timeout=0.1)
            except:
                continue
            
            # Convert and display
            try:
                display_img = self.convert_frame(frame_data)
                
                # FPS overlay
                fps_counter += 1
                if time.time() - fps_time >= 1.0:
                    display_fps = fps_counter
                    fps_counter = 0
                    fps_time = time.time()
                
                # Minimal overlay
                cv2.putText(display_img, f"Cam {self.cam_idx} | FPS: {display_fps}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow(self.window_name, display_img)
                
            except Exception as e:
                print(f"Display error: {e}")
            
            # Check for exit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                self.running = False
                break
            
            # Window closed check
            if cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1:
                self.running = False
                break
        
        cv2.destroyAllWindows()
    
    def run(self):
        # Get camera serial
        target_serial = self.load_camera_ref()
        if not target_serial:
            print(f"No serial assigned to Camera {self.cam_idx}")
            return
        
        # Initialize MVS
        MvCamera.MV_CC_Initialize()
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        
        if MvCamera.MV_CC_EnumDevices(tlayerType, deviceList) != 0:
            print("Enum devices failed")
            return
        
        # Find camera
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
        
        if not selected:
            print(f"Camera {target_serial} not found")
            return
        
        # Create handle and open
        self.cam = MvCamera()
        if self.cam.MV_CC_CreateHandle(selected) != 0:
            print("Create handle failed")
            return
        
        if self.cam.MV_CC_OpenDevice(MV_ACCESS_Control, 0) != 0:
            print("Open device failed")
            return
        
        # Set continuous mode
        self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        
        # Get payload size
        stParam = MVCC_INTVALUE()
        ctypes.memset(ctypes.byref(stParam), 0, ctypes.sizeof(stParam))
        self.cam.MV_CC_GetIntValue("PayloadSize", stParam)
        self.nPayloadSize = stParam.nCurValue
        
        # Start grabbing
        if self.cam.MV_CC_StartGrabbing() != 0:
            print("Start grabbing failed")
            return
        
        print(f"Started Camera {self.cam_idx} (Serial: {target_serial})")
        
        # Start threads
        self.running = True
        grab_thread = Thread(target=self.grab_frames, daemon=True)
        params_thread = Thread(target=self.params_watcher, daemon=True)
        
        grab_thread.start()
        params_thread.start()
        
        # Run display in main thread
        self.display_loop()
        
        # Cleanup
        self.cam.MV_CC_StopGrabbing()
        self.cam.MV_CC_CloseDevice()
        self.cam.MV_CC_DestroyHandle()
        MvCamera.MV_CC_Finalize()



def main():
    if len(sys.argv) < 2:
        print("Usage: python preview_camera.py <camIdx>")
        sys.exit(1)
    
    cam_idx = sys.argv[1]
    preview = CameraPreview(cam_idx)
    preview.run()

if __name__ == "__main__":
    main()