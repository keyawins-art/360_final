import os
import json
import time
from collections import Counter
import cv2
import numpy as np

from config import *
from tracker import ObjectTracker
from vision import is_oily_cashew, check_rgb_defects, detect_black_dots, smooth_contour

def load_zones_config():
    if os.path.exists(ZONES_CONFIG_FILE):
        try:
            with open(ZONES_CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                for c in configs:
                    if 'zone' in c and isinstance(c['zone'], list):
                        c['zone'] = tuple(c['zone'])
                print(f"Loaded zone configurations from {ZONES_CONFIG_FILE}")
                return configs
        except Exception as e:
            print(f"Error loading zones config: {e}. Using default.")
    return DEFAULT_ZONE_CONFIGS

def save_zones_config(configs):
    try:
        with open(ZONES_CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=4)
        print(f"\n[SAVE] Zone configuration saved to {ZONES_CONFIG_FILE}")
    except Exception as e:
        print(f"\n[SAVE] Error saving zones config: {e}")

def load_ranges(file_path):
    ranges = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                part = line.strip()
                if not part: continue
                range_part, grade = part.split(':')
                start, end = map(int, range_part.split('-'))
                ranges.append((start, end, grade.strip()))
        print(f"Loaded {len(ranges)} grading ranges")
        return ranges
    except Exception as e:
        print(f"Error loading ranges: {e}")
        return []

def get_grade(mm_value, ranges):
    for start, end, grade in ranges:
        if start <= mm_value <= end:
            return grade
    return None

class ZoneProcessor:
    def __init__(self, zone_config, ranges, shared_arduino=None):
        self.zone = zone_config['zone']
        self.name = zone_config.get('name', 'Zone-1')
        self.ranges = ranges
        self.tracker = ObjectTracker(self.name)
        self.arduino = shared_arduino
    
    def update_zone(self, new_zone):
        self.zone = new_zone
    
    def get_zone_mask(self, frame_shape):
        mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        x, y, w, h = self.zone
        img_h, img_w = frame_shape[:2]
        x1, y1 = max(0, min(x, img_w)), max(0, min(y, img_h))
        x2, y2 = max(0, min(x + w, img_w)), max(0, min(y + h, img_h))
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = 255
        return mask
    
    def process_frame(self, frame, quality_filter=None):
        x, y, w, h = self.zone
        
        img_h, img_w = frame.shape[:2]
        x1, y1 = max(0, min(x, img_w)), max(0, min(y, img_h))
        x2, y2 = max(0, min(x + w, img_w)), max(0, min(y + h, img_h))
        
        zone_frame = frame[y1:y2, x1:x2]
        
        if zone_frame.size == 0 or zone_frame.shape[0] == 0 or zone_frame.shape[1] == 0:
            return []
        
        zone_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        zone_mask[y1:y2, x1:x2] = 255
        
        smooth = cv2.GaussianBlur(zone_frame, (7, 7), 0)
        gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
        
        _, mask_raw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel_e = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask_clean = cv2.morphologyEx(mask_raw, cv2.MORPH_OPEN, kernel_e, iterations=1)
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close, iterations=1)
        
        mask_smooth = cv2.GaussianBlur(mask_clean, (21, 21), 0)
        _, mask_final = cv2.threshold(mask_smooth, 127, 255, cv2.THRESH_BINARY)
        
        hsv = cv2.cvtColor(zone_frame, cv2.COLOR_BGR2HSV)
        hsv_mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
        
        cnts, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        adjusted_contours = []
        for c in cnts:
            c_adjusted = c.copy()
            c_adjusted[:, 0, 0] += x1
            c_adjusted[:, 0, 1] += y1
            c_adjusted = smooth_contour(c_adjusted, window=5)
            adjusted_contours.append(c_adjusted)
        
        valid_contours = []
        is_good_flags = []
        grades = []
        crops = []
        
        for i, c in enumerate(adjusted_contours):
            area = cv2.contourArea(c)
            if area < MIN_CASHEW_AREA: continue
            
            c_mask = np.zeros(zone_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(c_mask, [cnts[i]], -1, 255, -1)
            cashew_pixels = cv2.countNonZero(cv2.bitwise_and(c_mask, hsv_mask))
            total_pixels = cv2.countNonZero(c_mask)
            density = cashew_pixels / max(1, total_pixels)
            
            if density < 0.15: continue
            
            rect = cv2.minAreaRect(c)
            (w_p, h_p) = rect[1]
            mm_size = max(w_p, h_p) * PIXEL_TO_MM_RATIO
            aspect_ratio = max(w_p, h_p) / max(1, min(w_p, h_p))
            
            if mm_size > MAX_CASHEW_MM or aspect_ratio > MAX_ASPECT_RATIO: continue
            solidity = area / max(1, w_p * h_p)
            if solidity < 0.50: continue
            if min(w_p, h_p) < 20: continue

            current_grade = None
            is_good = True
            
            x_b, y_b, w_b, h_b = cv2.boundingRect(c)
            side = max(w_b, h_b) + 40
            cx_b, cy_b = x_b + w_b//2, y_b + h_b//2
            
            px = max(0, cx_b - side//2)
            py = max(0, cy_b - side//2)
            pw = min(frame.shape[1] - px, side)
            ph = min(frame.shape[0] - py, side)
            crop = frame[py:py+ph, px:px+pw]
            
            if crop.size > 0:
                yolo_confirmed_good = False
                if quality_filter and getattr(quality_filter, 'model', None):
                    yolo_cat, yolo_conf = quality_filter.get_cashew_category(crop)
                    if yolo_cat:
                        if yolo_cat in [name.lower() for name in GOOD_CLASS_NAMES]:
                            if yolo_conf > YOLO_STRICT_BYPASS:
                                current_grade = None 
                                is_good = True
                                yolo_confirmed_good = True
                        else:
                            current_grade = yolo_cat
                            is_good = False
                
                if not current_grade and not yolo_confirmed_good:
                    if is_oily_cashew(crop):
                        current_grade = 'oily'
                        is_good = False
                    if not current_grade:
                        shell, orange, color = check_rgb_defects(crop)
                        if shell: current_grade = 'shell'; is_good = False
                        elif orange: current_grade = 'orange'; is_good = False
                        elif color: current_grade = 'color'; is_good = False
                    if not current_grade:
                        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        dot_found, _ = detect_black_dots(gray_crop)
                        if dot_found:
                            current_grade = 'blackdot'
                            is_good = False

            valid_contours.append(c)
            is_good_flags.append(is_good)
            grades.append(current_grade)
            crops.append(crop)
        
        disappeared_ids = self.tracker.update(valid_contours, is_good_flags, grades, crops)
        
        for obj_id in disappeared_ids:
            obj_info = self.tracker.get_object_info(obj_id)
            if obj_info:
                max_mm = obj_info['max_mm']
                if max_mm >= 15.0 and len(obj_info.get('measurements', [])) >= 2:
                    history = obj_info.get('grade_history', [])
                    last_crop = obj_info.get('last_crop')
                    defect_history = [g for g in history if g is not None]
                    
                    final_grade = None
                    if defect_history:
                        counts = Counter(defect_history)
                        most_common, count = counts.most_common(1)[0]
                        if count >= max(1, len(history) // 3):
                            final_grade = most_common
                    
                    if not final_grade:
                        final_grade = get_grade(int(max_mm), self.ranges)
                    
                    if last_crop is not None:
                        try:
                            save_img = last_crop.copy()
                            h_s, w_s = save_img.shape[:2]
                            is_defect = final_grade and not any(size in str(final_grade) for size in ['400', '320', '240', '210', '180'])
                            color_border = (0, 0, 255) if is_defect else (0, 255, 0)
                            
                            tracked_cnt = obj_info.get('latest_contour')
                            x_b, y_b, w_b, h_b = cv2.boundingRect(tracked_cnt) if tracked_cnt is not None else (0, 0, w_s, h_s)
                            
                            side = max(w_b, h_b) + 40
                            cx_b, cy_b = x_b + w_b//2, y_b + h_b//2
                            crop_ox = max(0, cx_b - side//2)
                            crop_oy = max(0, cy_b - side//2)
                            
                            contour_drawn = False
                            if tracked_cnt is not None and len(tracked_cnt) >= 3:
                                local_cnt = tracked_cnt.copy()
                                local_cnt[:, 0, 0] -= crop_ox
                                local_cnt[:, 0, 1] -= crop_oy
                                smooth_cnt = smooth_contour(local_cnt, window=11)
                                if len(smooth_cnt) >= 3:
                                    cv2.drawContours(save_img, [smooth_cnt], -1, color_border, 2)
                                    contour_drawn = True
                            
                            if not contour_drawn:
                                smooth_s = cv2.GaussianBlur(save_img, (7, 7), 0)
                                gray_s = cv2.cvtColor(smooth_s, cv2.COLOR_BGR2GRAY)
                                _, mask_s = cv2.threshold(gray_s, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                                kernel_e_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                                mask_s = cv2.morphologyEx(mask_s, cv2.MORPH_CLOSE, kernel_e_s, iterations=2)
                                mask_s = cv2.GaussianBlur(mask_s, (15, 15), 0)
                                _, mask_s = cv2.threshold(mask_s, 127, 255, cv2.THRESH_BINARY)
                                cnts_s, _ = cv2.findContours(mask_s, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                if cnts_s:
                                    best_cnt = max(cnts_s, key=cv2.contourArea)
                                    smooth_cnt_s = smooth_contour(best_cnt, window=11)
                                    cv2.drawContours(save_img, [smooth_cnt_s], -1, color_border, 2)
                                else:
                                    cv2.rectangle(save_img, (0, 0), (w_s-1, h_s-1), color_border, 2)
                            
                            label_grade = f"{final_grade or 'None'}"
                            label_size = f"{max_mm:.1f}mm"
                            cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                            cv2.putText(save_img, label_grade, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                            cv2.putText(save_img, label_size, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            filename = f"ID{obj_id}_{final_grade}_{int(max_mm)}mm_{int(time.time())}.jpg"
                            filepath = os.path.join(DETECTIONS_FOLDER, filename)
                            cv2.imwrite(filepath, save_img)
                        except: pass
                    
                    zone_map = GRADE_PORT_MAP.get(self.name, GRADE_PORT_MAP['Zone-1'])
                    command = zone_map.get(final_grade, zone_map['default'])
                    
                    if self.arduino:
                        try:
                            self.arduino.write(command.encode())
                            self.arduino.flush()
                        except: pass
                    
                    print(f"[{self.name}] ✓ EXIT ID:{obj_id} → Grade:{final_grade or 'None'} (MM:{max_mm:.1f}) → Sent:{command.strip()}")
                
                self.tracker.remove_object(obj_id)
        
        return valid_contours
    
    def draw_zone(self, frame):
        x, y, w, h = self.zone
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        cv2.putText(frame, self.name, (x+5, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        for obj_id, obj_info in self.tracker.objects.items():
            if obj_info.get('disappeared_count', 0) > 0: continue
            cnt = obj_info.get('latest_contour')
            
            history = obj_info.get('grade_history', [])
            defect_frames = [g for g in history if g is not None]
            total_frames = max(1, len(history))
            defect_ratio = len(defect_frames) / total_frames
            
            is_consensus_bad = defect_ratio > 0.40 and len(defect_frames) >= 2
            
            current_grade = obj_info.get('current_grade', None)
            if is_consensus_bad and defect_frames:
                defect_counts = Counter(defect_frames)
                display_defect = defect_counts.most_common(1)[0][0]
                color = (0, 0, 255)
            else:
                display_defect = None
                color = (0, 255, 0)
            
            if cnt is not None and len(cnt) >= 3:
                smooth_cnt = smooth_contour(cnt, window=5)
                cv2.drawContours(frame, [smooth_cnt], -1, color, 2)
                
                cx, cy = obj_info['centroid']
                max_mm = obj_info['max_mm']
                
                label_id = f"SR:{obj_id} {max_mm:.1f}mm"
                
                if display_defect:
                    label_status = f"{display_defect.upper()}"
                    status_color = (0, 0, 255)
                else:
                    label_status = "GOOD"
                    status_color = (0, 255, 0)
                
                cv2.putText(frame, label_id, (cx - 40, cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
                cv2.putText(frame, label_id, (cx - 40, cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, label_status, (cx - 40, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
                cv2.putText(frame, label_status, (cx - 40, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1)
    
    def close(self):
        pass

def handle_keyboard_controls(key, zone_configs, zone_processors, selected_zone_index, show_display):
    should_quit = False
    char_key = key & 0xFF
    
    if ord('1') <= char_key <= ord('5'):
        selected_zone_index = char_key - ord('1')
        print(f"\n[CONTROL] Selected {zone_configs[selected_zone_index]['name']} for adjustment")
    
    elif char_key == ord('q') or char_key == ord('Q'):
        show_display = not show_display
        if show_display: print(f"\n[CONTROL] Display window OPENING...")
        else: print(f"\n[CONTROL] Display window HIDDEN. Press Q to reopen.")
    
    elif char_key == 27:
        should_quit = True
        print(f"\n[CONTROL] ESC pressed - Exiting program...")
    
    elif char_key == ord('c') or char_key == ord('C'):
        save_zones_config(zone_configs)
    
    elif selected_zone_index is not None:
        zone_config = zone_configs[selected_zone_index]
        x, y, w, h = zone_config['zone']
        modified = False
        action = ""
        
        if key in [2424832, 81, 37, 2] or char_key in [ord('a'), ord('A')]:
            x -= 10; modified = True; action = "moved LEFT"
        elif key in [2555904, 83, 39, 3] or char_key in [ord('d'), ord('D')]:
            x += 10; modified = True; action = "moved RIGHT"
        elif key in [2490368, 82, 38, 0] or char_key in [ord('w'), ord('W')]:
            y -= 10; modified = True; action = "moved UP"
        elif key in [2621440, 84, 40, 1] or char_key in [ord('s'), ord('S')]:
            y += 10; modified = True; action = "moved DOWN"
        
        elif char_key in [ord('+'), ord('='), ord('k'), ord('K')]:
            w += 10; modified = True; action = "width INCREASED"
        elif char_key in [ord('-'), ord('_'), ord('h'), ord('H')]:
            w = max(50, w - 10); modified = True; action = "width DECREASED"
        
        elif char_key in [ord('['), ord('u'), ord('U')]:
            h = max(50, h - 10); modified = True; action = "height DECREASED"
        elif char_key in [ord(']'), ord('j'), ord('J')]:
            h += 10; modified = True; action = "height INCREASED"
        
        if modified:
            new_zone = (x, y, w, h)
            zone_config['zone'] = new_zone
            zone_processors[selected_zone_index].update_zone(new_zone)
            print(f"[CONTROL] {zone_config['name']} {action} → x={x}, y={y}, w={w}, h={h}")
    
    return should_quit, show_display, selected_zone_index
