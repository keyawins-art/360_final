import cv2
import numpy as np
import os
import time
import serial
from queue import Queue
import threading


# ------------ CONFIGURATION ------------  n
input_folder = r"D:\Keya Work\360\wate\Con_4_Images"
ranges_file = r"D:\Keya Work\360\wate\value.txt"
timing_file = r"D:\Keya Work\360\wate\4(D)-time.txt"
com_port_file = r"D:\Keya Work\360\wate\com_port(d).txt"

GRADE_PORT_MAP = {
    '400': '11|',
    '320': '12|',
    '240': '13|',
    '210': '14|',
    '180': '15|',
    '1000': '16|' 
}

command_queue = Queue()
arduino = None


def load_ranges(file_path):
    ranges = []
    with open(file_path, 'r') as f:
        for line in f:
            part = line.strip()
            if not part:
                continue
            range_part, grade = part.split(':')
            start, end = map(int, range_part.split('-'))
            ranges.append((start, end, grade.strip()))
    return ranges


def get_grade(white_pixel_count, ranges):
    for start, end, grade in ranges:
        if start <= white_pixel_count <= end:
            return grade
    return '1000'


def safe_imread(path, retries=5, delay=0.001):
    for _ in range(retries):
        img = cv2.imread(path)
        if img is not None:
            return img
        time.sleep(delay)
    return None


# ------------ SERIAL THREAD ------------
def send_commands():
    global arduino
    while True:
        try:
            command = command_queue.get()
            if command is None:
                break
            if arduino and arduino.is_open:
                arduino.write(command.encode('utf-8'))
                print(f"Sent command: {command.strip()}")
            command_queue.task_done()
        except Exception as e:
            print(f"Error in send_commands: {e}")
            command_queue.task_done()


serial_thread = threading.Thread(target=send_commands, daemon=True)
serial_thread.start()


# ------------ OILY DETECTOR ------------
samples = np.array([
    [35.3, 75, 51], [38.2, 74, 29], [34.1, 74, 44], [34.7, 78, 48],
    [38.1, 81, 47], [39.5, 57, 54], [34.7, 82, 40], [35.4, 74, 41],
    [31.5, 71, 33], [39.2, 66, 47], [35.6, 75, 53], [44.5, 57, 43],
    [38.4, 90, 39], [36.3, 73, 38], [43.1, 78, 20], [42.7, 79, 33],
    [29.6, 76, 38], [33.6, 48, 18], [33.6, 100, 93], [37.1, 82, 20]
])
hsv_cv = samples.astype(np.float32)
hsv_cv[:, 0] /= 2            # Hue 0-179
hsv_cv[:, 1:] *= 2.55        # Sat/Val 0-255
H, S, V = hsv_cv[:, 0], hsv_cv[:, 1], hsv_cv[:, 2]
H_tol, S_tol, V_tol = 3, 15, 15

lower_oily = np.array([
    max(int(H.min()) - H_tol, 0),
    max(int(S.min()) - S_tol, 0),
    max(int(V.min()) - V_tol, 0)
], dtype=np.uint8)

upper_oily = np.array([
    min(int(H.max()) + H_tol, 179),
    min(int(S.max()) + S_tol, 255),
    min(int(V.max()) + V_tol, 255)
], dtype=np.uint8)


def is_oily_cashew(img_bgr, min_oily_ratio=0.60):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    oily = cv2.inRange(hsv, lower_oily, upper_oily)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, cashew_bin = cv2.threshold(gray, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cashew_pixels = np.count_nonzero(cashew_bin)
    if cashew_pixels == 0:
        return False
    oily_pixels = np.count_nonzero(cv2.bitwise_and(oily, cashew_bin))
    ratio = oily_pixels / cashew_pixels
    return ratio >= min_oily_ratio


# ------------ COLOR DEFECT CHECKER ------------
def check_rgb(image):
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    except Exception as e:
        print(f"HSV conversion error: {e}")
        return False, False, False

    mask_shell = cv2.inRange(hsv, np.array([8, 30, 9]), np.array([13, 255, 140]))
    mask_orange = cv2.inRange(hsv, np.array([26, 21, 20]), np.array([26, 91, 81])) 
    mask_color = cv2.inRange(hsv,
                             np.array([10, 162, 32], dtype=np.uint8),
                             np.array([26, 255, 72], dtype=np.uint8))

    shell = np.count_nonzero(mask_shell) > 500
    orange = np.count_nonzero(mask_orange) > 500
    color = np.count_nonzero(mask_color) > 500

    return shell, orange, color


def detect_black_dots(gray_crop, min_dot_ratio=0.005, min_dot_count=1):
    gray_crop = cv2.GaussianBlur(gray_crop, (5, 5), 0)
    _, bin_crop = cv2.threshold(gray_crop, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    total_area = np.count_nonzero(bin_crop)
    if total_area == 0:
        return False, 0

    contours, hierarchy = cv2.findContours(bin_crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    black_dots = 0
    if hierarchy is not None:
        for i, contour in enumerate(contours):
            if hierarchy[0][i][3] != -1:  # has parent → hole
                area = cv2.contourArea(contour)
                if area >= total_area * min_dot_ratio:
                    black_dots += 1

    return black_dots >= min_dot_count, black_dots


# ------------ MAIN IMAGE PROCESSOR ------------
def process_image(image_path, ranges):
    try:
        image = cv2.imread(image_path)
        if image is None:
            print(f"Skipping {os.path.basename(image_path)}: Can't read.")
            return False

        start = time.time()
        fname = os.path.basename(image_path)

        # ---------- 0. OILY CHECK ----------
        if is_oily_cashew(image):
            grade = 'oily'
            command_queue.put('21|')
            print(f"{fname} → oily → {grade} in {time.time()-start:.2f}s")
            os.remove(image_path)
            return True

        # ---------- 1. SEGMENT CASHEW ----------
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, bin_img = cv2.threshold(gray, 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)        
        dilated = cv2.dilate(bin_img, np.ones((5, 5), np.uint8), 1)
        cnts, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        cnts = [c for c in cnts if cv2.contourArea(c) > 8000]

        if len(cnts) != 1:
            grade = 'multiple_cashews'
            command_queue.put('21|')
            print(f"{fname} → {grade} ({len(cnts)} contours) in {time.time()-start:.2f}s")
            os.remove(image_path)
            return True

        x, y, w, h = cv2.boundingRect(cnts[0])
        crop = image[y:y+h, x:x+w]
        gray_crop = gray[y:y+h, x:x+w]

        _, bin_crop = cv2.threshold(gray_crop, 0, 255,cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        shell, orange, color = check_rgb(crop)

        if shell:
            grade = 'shell'
            command_queue.put('21|') 
            print(f"Processed: {fname} | Grade: {grade} | Time: {time.time()-start:.2f}s")
            os.remove(image_path)
            return True
        elif orange:
            grade = 'orange'
            command_queue.put('21|')
            print(f"Processed: {fname} | Grade: {grade} | Time: {time.time()-start:.2f}s")
            os.remove(image_path)
            return True
        elif color:
            grade = 'color'
            command_queue.put('21|')
            print(f"Processed: {fname} | Grade: {grade} | Time: {time.time()-start:.2f}s")
            os.remove(image_path)
            return True
        else:
            dot_found, black_dots = detect_black_dots(gray_crop)
            if dot_found:
                grade = 'blackdot'
                command_queue.put('16|')
                print(f"{fname} → {grade} ({black_dots} dots) ({time.time()-start:.2f}s)")
                os.remove(image_path)
                return True

            lap_var = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
            if lap_var < 40:
                grade = 'dry'
                command_queue.put('16|')
                print(f"Processed: {fname} | Grade: {grade} | Time: {time.time()-start:.2f}s")
                os.remove(image_path)
                return True
            else:
                white_pixel_count = np.count_nonzero(bin_crop)
                grade = get_grade(white_pixel_count, ranges)
                command = GRADE_PORT_MAP.get(grade, '16|')
                command_queue.put(command)

        print(f"Processed: {fname} | Grade: {grade} | Time: {time.time()-start:.2f}s")
        os.remove(image_path)
        return True

    except Exception as e:
        print(f"Error on {image_path}: {e}")
        return False


def watch_folder():
    print("Watching folder for new images...")
    ranges = load_ranges(ranges_file)

    while True:
        files = sorted([os.path.join(input_folder, f)
                        for f in os.listdir(input_folder)
                        if f.lower().endswith(".bmp")])
        if files:
            processed = process_image(files[0], ranges)
            if not processed:
                time.sleep(0.001)
        else:
            time.sleep(0.001)


if __name__ == "__main__":
    # read com port 
    try:
        with open(com_port_file, 'r') as file:
            com_port = file.read().strip()
            print(f"Read COM port from file: {com_port}")
    except FileNotFoundError:
        print(f"File not found at: {com_port_file}")
        exit()
    # read time 
    try:
        with open(timing_file, 'r') as file:
            timing_string = file.read().strip()
            print(f"Read timing string from file:\n{timing_string}\n")
    except FileNotFoundError:
        print(f"File not found at: {timing_file}")
        exit()
    # send time and com port 
    try:
        print("Connecting to{com_port} for timing send...")
        arduino = serial.Serial(port=com_port, baudrate=115200)
        time.sleep(0.001)
        arduino.write(timing_string.encode())
        print(f"Sent timing string to {com_port}  : {timing_string}")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        exit()

    watch_folder()
