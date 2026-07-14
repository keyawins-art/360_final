import sys
import ctypes

sys.path.append(r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport")
from MvCameraControl_class import *

def main():
    MvCamera.MV_CC_Initialize()
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    r = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if r != 0 or deviceList.nDeviceNum == 0:
        print("No devices found")
        return

    info = ctypes.cast(deviceList.pDeviceInfo[0], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
    cam = MvCamera()
    cam.MV_CC_CreateHandle(info)
    
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Control, 0)
    print(f"OpenDevice: {ret}")
    if ret != 0:
        return

    for node in ["Width", "Height", "OffsetX", "OffsetY"]:
        val = MVCC_INTVALUE()
        ret = cam.MV_CC_GetIntValue(node, val)
        if ret == 0:
            print(f"{node} Limits - Min: {val.nMin}, Max: {val.nMax}, Step: {val.nInc}, Cur: {val.nCurValue}")
        else:
            print(f"Failed to get {node} limits: {ret}")

    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()

if __name__ == "__main__":
    main()
