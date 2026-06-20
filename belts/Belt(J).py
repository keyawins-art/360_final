import cv2
import numpy as np
import os
import time
import serial
from queue import Queue
import threading

input_folder = r"D:\Kesyu_250524_4_Belts\Images\Con_10_Images"
timing_file_path = r"D:\4_belt_main\4_belt\time\4(J)-time.txt"
com_file_path = r"D:\4_belt_main\4_belt\comport info\comport(j).txt"
com_port_file_path = r"D:\4_belt_main\4_belt\Test_checkup\com_port(j).txt"

command_queue = Queue()

arduino = None

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

def get_command_value():
    try:
        with open(com_file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        return "180"

def process_image(image_path):
    try:
        image = cv2.imread(image_path)
        if image is None:
            print(f"Skipping {os.path.basename(image_path)}: Can't read.")
            return

        start_time = time.time()
        filename = os.path.basename(image_path)

        gray_crop = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary_crop = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        white_pixel_count = np.count_nonzero(binary_crop)
        command_value = get_command_value()

        if 33001 <= white_pixel_count <= 102000:
            grade = "180"
            command_queue.put(command_value)
        else:
            grade = "1000"
            command_queue.put(command_value)

        print(f"Processed: {filename} | Grade: {grade} | Time: {time.time() - start_time:.3f}s")
        os.remove(image_path)

    except Exception as e:
        print(f"Error processing {image_path}: {e}")

def watch_folder():
    print("Watching folder for new images...")
    while True:
        try:
            if not os.path.exists(input_folder):
                os.makedirs(input_folder, exist_ok=True)
            files = sorted([os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(".bmp")])
            if files:
                process_image(files[0])
            else:
                time.sleep(0.001)
        except Exception as e:
            print(f"Folder error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        with open(timing_file_path, 'r') as file:
            timing_string = file.read().strip()
            print(f"Read timing string from file:\n{timing_string}\n")
    except FileNotFoundError:
        print(f"File not found at: {timing_file_path}")
        exit()

    try:
        with open(com_port_file_path, 'r') as file:
            com_port = file.read().strip()
            print(f"Read COM port from file: {com_port}")
    except FileNotFoundError:
        print(f"File not found at: {com_port_file_path}")
        exit()

    try:
        print(f"Connecting to {com_port} for timing send...")
        arduino = serial.Serial(port=com_port, baudrate=115200)
        time.sleep(0.001)
        arduino.write(timing_string.encode())
        print(f"Sent timing string to {com_port}: {timing_string}")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        exit()

    watch_folder()
