import cv2
import numpy as np
import os
import time
import serial
from queue import Queue
import threading

input_folder = r"D:\Keya Work\360\wate\Con_3_Images"
ranges_file = r"D:\Keya Work\360\wate\value.txt"
timing_file = r"D:\Keya Work\360\wate\4(C)-time.txt"
com_port_file = r"D:\Keya Work\360\wate\com_port(c).txt"

# --- Globals ---
command_queue = Queue()
arduino = None

# --- Serial Thread for Commands ---
def send_commands():
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

# --- Image Check ---
def check_rgb(image):
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    except Exception as e:
        print(f"Error converting image to HSV: {e}")
        return False, False, False

    mask_red1 = cv2.inRange(hsv, np.array([10, 50, 90]), np.array([20, 90, 110]))
    mask_red2 = cv2.inRange(hsv, np.array([21, 59, 13]), np.array([37, 43, 21]))
    mask_red3 = cv2.inRange(hsv, np.array([15, 60, 10]), np.array([20, 70, 20]))
    mask_red4 = cv2.inRange(hsv, np.array([19, 28, 39]), np.array([19, 96, 7]))
    mask_red5 = cv2.inRange(hsv, np.array([25, 50, 70]), np.array([25, 75, 9]))
    mask_shell = cv2.inRange(hsv, np.array([8, 30, 9]), np.array([13, 255, 140]))
    mask_orange = cv2.inRange(hsv, np.array([26, 21, 20]), np.array([26, 91, 81]))

    orange_detected = np.count_nonzero(mask_orange) > 500
    red_detected = (
        np.count_nonzero(mask_red1) > 500 or
        np.count_nonzero(mask_red2) > 500 or
        np.count_nonzero(mask_red3) > 500 or
        np.count_nonzero(mask_red4) > 500 or
        np.count_nonzero(mask_red5) > 500
    )
    shell_detected = np.count_nonzero(mask_shell) > 900

    return shell_detected, red_detected, orange_detected

# --- Image Processing ---
def process_image(image_path):
    try:
        image = cv2.imread(image_path)
        if image is None:
            print(f"Skipping {os.path.basename(image_path)}: Can't read.")
            return

        start_time = time.time()
        filename = os.path.basename(image_path)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 8000]

        if len(valid_contours) != 1:
            grade = 'multiple_cashews'
            command_queue.put('21|') 
            print(f"Processed: {filename} | Grade: {grade} | Count: {len(valid_contours)} | Time: {time.time() - start_time:.2f}s")
            os.remove(image_path)
            return

        x, y, w, h = cv2.boundingRect(valid_contours[0])
        cropped = image[y:y+h, x:x+w]
        shell_detected, red_detected, orange_detected = check_rgb(cropped)

        if shell_detected or red_detected or orange_detected:
            grade = 'shell'
            command_queue.put('21|')
        else:
            gray_crop = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            _, binary_crop = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            crop_contours, _ = cv2.findContours(binary_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            black_dot_count = sum(1 for cnt in crop_contours if cv2.contourArea(cnt) >= 400)

            if black_dot_count > 1:
                grade = 'blackdot'
                command_queue.put('21|')
                os.remove(image_path)
                return

            laplacian_var = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
            if laplacian_var < 40:
                grade = 'dry'
                command_queue.put('16|')
                os.remove(image_path)
                return

            white_pixel_count = np.count_nonzero(binary_crop)

            if 45001 <= white_pixel_count <= 120000:
                grade = "180"
                command_queue.put('15|')
            elif 35001 <= white_pixel_count <= 45000:
                grade = "210"
                command_queue.put('14|')
            elif 28001 <= white_pixel_count <= 35000:
                grade = "240"
                command_queue.put('13|')
            elif 18501 <= white_pixel_count <= 28000:
                grade = "320"
                command_queue.put('12|')
            elif 13000 <= white_pixel_count <= 18500:
                grade = "400"
                command_queue.put('11|')
            else:
                grade = "1000"
                command_queue.put('16|')

        print(f"Processed: {filename} | Grade: {grade} | Time: {time.time() - start_time:.2f}s")
        os.remove(image_path)

    except Exception as e:
        print(f"Error processing {image_path}: {e}")

# --- Folder Watcher ---
def watch_folder():
    print("Watching folder for new images...")
    while True:
        files = sorted([os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(".bmp")])
        if files:
            process_image(files[0])
        else:
            time.sleep(0.001)

# --- Main ---
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
        print(f"Sent timing string to {com_port}: {timing_string}")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        exit()

    # Step 4: Start image processing loop
    watch_folder()
