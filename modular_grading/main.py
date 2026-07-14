import os
import time
import gc
import cv2
import serial
import numpy as np

from config import MAIN_COM_FILE, ZONES_CONFIG_FILE, YOLO_MODEL_PATH, RANGES_FILE
from hardware import read_com_port_from_file
from camera import HIKCashewCamera
from vision import CashewQualityFilter
from processor import ZoneProcessor, load_zones_config, load_ranges, handle_keyboard_controls

def main():
    ZONE_CONFIGS = load_zones_config()
    ranges = load_ranges(RANGES_FILE)
    if not ranges:
        print("Warning: No grading ranges loaded")

    cam = HIKCashewCamera()
    
    last_config_mtime = 0
    if os.path.exists(ZONES_CONFIG_FILE):
        last_config_mtime = os.path.getmtime(ZONES_CONFIG_FILE)
    if not cam.connect():
        return

    quality_filter = CashewQualityFilter(YOLO_MODEL_PATH)
    cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
    
    com_port = read_com_port_from_file(MAIN_COM_FILE)
    shared_arduino = None
    if com_port:
        try:
            shared_arduino = serial.Serial(port=com_port, baudrate=115200, timeout=1)
            print(f"Main Serial connected on {com_port}. Waiting 2 seconds for Arduino to initialize...")
            time.sleep(2)
            shared_arduino.reset_input_buffer()
            shared_arduino.reset_output_buffer()
            print("Main Serial is ready to send commands!")
        except Exception as e:
            print(f"Main Serial error: {e}")
            shared_arduino = None
    else:
        print("No valid MAIN COM port found.")

    zone_processors = []
    for zone_config in ZONE_CONFIGS:
        processor = ZoneProcessor(zone_config, ranges, shared_arduino)
        zone_processors.append(processor)
    
    print(f"\n{'='*60}")
    print(f"5 INDEPENDENT ZONES INITIALIZED - USING 1 SHARED COM PORT")
    print(f"{'='*60}")
    print(f"\nKEYBOARD CONTROLS:")
    print(f"  1-5      : Select zone for adjustment")
    print(f"  Arrows   : Move selected zone (↑↓←→)")
    print(f"  +/-      : Increase/Decrease width")
    print(f"  [ ]      : Decrease/Increase height")
    print(f"  C        : Save current zone configuration")
    print(f"  Q        : Toggle display window ON/OFF")
    print(f"  ESC      : Quit program completely")
    print(f"{'='*60}\n")

    selected_zone_index = None
    show_display = True

    try:
        frame_counter = 0
        while True:
            frame_counter += 1
            if frame_counter % 500 == 0:
                gc.collect()

            frame = cam.get_frame()
            cam.check_and_update_parameters()
            if frame is None:
                cv2.waitKeyEx(1)
                time.sleep(0.005)
                continue

            try:
                if os.path.exists(ZONES_CONFIG_FILE):
                    mtime = os.path.getmtime(ZONES_CONFIG_FILE)
                    if mtime > last_config_mtime:
                        last_config_mtime = mtime
                        print("\n[CONFIG] zones_config.json changed! Reloading zones...")
                        new_configs = load_zones_config()
                        
                        for i, new_z in enumerate(new_configs):
                            if i < len(ZONE_CONFIGS):
                                ZONE_CONFIGS[i]['zone'] = tuple(new_z['zone'])
                            else:
                                ZONE_CONFIGS.append({'zone': tuple(new_z['zone']), 'name': new_z.get('name', f'Zone-{i+1}')})
                        
                        for i, processor in enumerate(zone_processors):
                            if i < len(ZONE_CONFIGS):
                                processor.update_zone(ZONE_CONFIGS[i]['zone'])
                        
                        if len(ZONE_CONFIGS) > len(zone_processors):
                            for i in range(len(zone_processors), len(ZONE_CONFIGS)):
                                processor = ZoneProcessor(ZONE_CONFIGS[i], ranges, shared_arduino)
                                zone_processors.append(processor)
            except Exception as e:
                print(f"[CONFIG] Error reloading config: {e}")

            display_frame = np.zeros_like(frame)
            img_h, img_w = frame.shape[:2]
            for z in ZONE_CONFIGS:
                x, y, w, h = z['zone']
                x1, y1 = max(0, min(x, img_w)), max(0, min(y, img_h))
                x2, y2 = max(0, min(x + w, img_w)), max(0, min(y + h, img_h))
                if x2 > x1 and y2 > y1:
                    display_frame[y1:y2, x1:x2] = frame[y1:y2, x1:x2]
            
            for processor in zone_processors:
                _ = processor.process_frame(frame, quality_filter)
                processor.draw_zone(display_frame)
            
            if selected_zone_index is not None and selected_zone_index < len(ZONE_CONFIGS):
                sel_zone = ZONE_CONFIGS[selected_zone_index]['zone']
                sx, sy, sw, sh = sel_zone
                cv2.rectangle(display_frame, (sx, sy), (sx+sw, sy+sh), (0, 0, 255), 4)
                cv2.putText(display_frame, "SELECTED", (sx+5, sy+40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            try:
                if cv2.getWindowProperty("Full Camera", cv2.WND_PROP_VISIBLE) < 1:
                    print("\n[CONTROL] Window closed via 'X'. Entering background mode. Press Q to reopen. ESC to exit.")
                    cv2.namedWindow("Full Camera", cv2.WINDOW_NORMAL)
                    show_display = False
            except: pass

            if show_display:
                cv2.imshow("Full Camera", display_frame)
            else:
                bg_frame = np.zeros((200, 600, 3), dtype=np.uint8)
                cv2.putText(bg_frame, "PROCESS RUNNING IN BACKGROUND", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(bg_frame, "Press 'Q' to show camera view, ESC to exit", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.imshow("Full Camera", bg_frame)
            
            key = cv2.waitKeyEx(1)
            
            if key != -1: 
                should_quit, show_display, selected_zone_index = handle_keyboard_controls(
                    key, ZONE_CONFIGS, zone_processors, selected_zone_index, show_display
                )
                if should_quit: break

    finally:
        cam.close()
        for processor in zone_processors: processor.close()
        cv2.destroyAllWindows()
        if 'shared_arduino' in locals() and shared_arduino:
            try:
                shared_arduino.close()
                print("Main Serial closed")
            except: pass

if __name__ == "__main__":
    main()
