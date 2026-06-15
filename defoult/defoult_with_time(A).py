import cv2
import numpy as np
import os
import time
#import serial
from queue import Queue
import threading

input_folder = r"D:\Keya Work\360\wate\Con_1_Images"
output_folder = r"D:\Keya Work\360\wate\Con_2_Images"

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

    orange_detected = np.count_nonzero(mask_orange) > 300
    red_detected = (
        np.count_nonzero(mask_red1) > 500 or
        np.count_nonzero(mask_red2) > 300 or
        np.count_nonzero(mask_red3) > 300 or
        np.count_nonzero(mask_red4) > 300 or
        np.count_nonzero(mask_red5) > 300
    )
    shell_detected = np.count_nonzero(mask_shell) > 500

    return shell_detected, red_detected, orange_detected

def save_image_by_grade(image, filename, grade):
    grade_folder = os.path.join(output_folder, grade)
    os.makedirs(grade_folder, exist_ok=True)
    save_path = os.path.join(grade_folder, filename)
    cv2.imwrite(save_path, image)

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
        valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 1000]

        if len(valid_contours) != 1:
            grade = 'multiple_cashews'
            print(f"Processed: {filename} | Grade: {grade} | Count: {len(valid_contours)} | Time: {time.time() - start_time:.2f}s")
            #command_queue.put('16|')
            save_image_by_grade(image, filename, grade)
            #os.remove(image_path)
            return

        x, y, w, h = cv2.boundingRect(valid_contours[0])
        cropped = image[y:y+h, x:x+w]

        shell_detected, red_detected, orange_detected = check_rgb(cropped)

        if shell_detected:
            grade = 'shell'
            save_image_by_grade(image, filename, grade)
            #command_queue.put('15|')
        elif red_detected:
            grade = 'red'
            save_image_by_grade(image, filename, grade)
            #command_queue.put('15|')
        elif orange_detected:
            grade = 'orange'
            save_image_by_grade(image, filename, grade)
            #command_queue.put('15|')
        else:
            gray_crop = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            _, binary_crop = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            crop_contours, _ = cv2.findContours(binary_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            black_dot_count = sum(1 for cnt in crop_contours if cv2.contourArea(cnt) >= 400)

            """if black_dot_count > 1:
                grade = 'blackdot'
                #command_queue.put('16|')
                save_image_by_grade(image, filename, grade)
                #os.remove(image_path)
                return"""

            laplacian_var = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
            if laplacian_var < 40:
                grade = 'dry'
                #command_queue.put('16|')
                save_image_by_grade(image, filename, grade)
                #os.remove(image_path)
                return

            white_pixel_count = np.count_nonzero(binary_crop)

            if 50001 <= white_pixel_count <= 70000:
                grade = "180"
                save_image_by_grade(image, filename, grade)
                #command_queue.put('14|')
            elif 34001 <= white_pixel_count <= 50000:
                grade = "210"
                save_image_by_grade(image, filename, grade)

            elif 27001 <= white_pixel_count <= 34000:
                grade = "240"
                save_image_by_grade(image, filename, grade)
                #command_queue.put('13|')
            elif 18501 <= white_pixel_count <= 27000:
                grade = "320"
                save_image_by_grade(image, filename, grade) 
                #command_queue.put('12|')
            elif 13000 <= white_pixel_count <= 18500:
                grade = "400"
                save_image_by_grade(image, filename, grade) 
                #command_queue.put('11|')
            else:
                grade = "1000"
                save_image_by_grade(image, filename, grade) 

        print(f"Processed: {filename} | Grade: {grade} | Time: {time.time() - start_time:.2f}s")
        save_image_by_grade(image, filename, grade)
       # os.remove(image_path)

    except Exception as e:
        print(f"Error processing {image_path}: {e}")

def watch_folder():
    print("Watching folder for new images...")
    already_processed = set()

    while True:
        files = sorted([
            os.path.join(input_folder, f)
            for f in os.listdir(input_folder)
            if f.lower().endswith(".bmp")
        ])
        
        for file_path in files:
            if file_path not in already_processed:
                process_image(file_path)
                already_processed.add(file_path)

        time.sleep(0.01) 


if __name__ == "__main__":
    watch_folder()
