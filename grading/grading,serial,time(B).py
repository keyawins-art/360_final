import cv2
import os
import numpy as np
import serial
import time
import sys
import re

# ---------- Force console to use UTF-8 encoding ----------
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass  # Older Python versions may not have reconfigure()

# ---------- GRADE → PORT COMMAND MAP ----------
GRADE_PORT_MAP = {
    '400': '11|',
    '320': '12|',
    '240': '13|',
    '210': '14|',
    '180': '15|',
    'default': '16|'
}


# ---------- LOAD RANGE FILE ----------
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


# ---------- GRADE CALCULATOR ----------
def get_grade(white_pixel_count, ranges):
    for start, end, grade in ranges:
        if start <= white_pixel_count <= end:
            return grade
    return None


# ---------- SAFE PRINT ----------
def safe_print(message):
    """Print safely, replacing unsupported characters if needed."""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode('ascii', errors='replace').decode())


# ---------- READ COM PORT FROM FILE ----------
def read_com_port_from_file(file_path):
    """
    Read COM port string from file and normalize to e.g. 'COM6'.
    Accepts '6', 'COM6', 'ASRL6::INSTR', etc.
    Returns normalized COM port string or None on error.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
    except FileNotFoundError:
        safe_print(f"COM port file not found: {file_path}")
        return None
    except Exception as e:
        safe_print(f"Error reading COM port file: {e}")
        return None

    if not content:
        safe_print("COM port file is empty")
        return None

    # Try extract first group of digits
    m = re.search(r'(\d+)', content)
    if m:
        return f"COM{m.group(1)}"

    if content.upper().startswith('COM'):
        return content
    return content


# ---------- MAIN PROCESS ----------
def process_images_continuous(input_folder, ranges_file, serial_port, timing_file):
    ranges = load_ranges(ranges_file)

    try:
        arduino = serial.Serial(port=serial_port, baudrate=115200, timeout=1)
        safe_print(f"Serial connected on {serial_port}")
    except Exception as e:
        safe_print(f"Serial port error: {e}")
        return

    try:
        # Send timing string
        try:
            with open(timing_file, 'r') as file:
                timing_string = file.read().strip()
                time.sleep(0.1)
                arduino.write(timing_string.encode())
                safe_print(f"Sent timing string: {timing_string}")
                time.sleep(0.001)
        except FileNotFoundError:
            safe_print(f"Timing file not found: {timing_file}")
        except Exception as e:
            safe_print(f"Error sending timing string: {e}")

        safe_print("Monitoring folder for new images...")
        while True:
            try:
                bmp_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.bmp')]
            except FileNotFoundError:
                safe_print(f"Input folder not found: {input_folder}")
                break

            if not bmp_files:
                time.sleep(0.001)
                continue

            for filename in bmp_files:
                start = time.time()
                image_path = os.path.join(input_folder, filename)
                img = cv2.imread(image_path)

                if img is None:
                    safe_print(f"Error reading {filename}")
                    time.sleep(0.01)
                    continue

                # ---------- MULTIPLE CASHEW DETECTION ----------
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, bin_img = cv2.threshold(gray, 0, 255,
                                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                dilated = cv2.dilate(bin_img, np.ones((5, 5), np.uint8), 1)
                cnts, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = [c for c in cnts if cv2.contourArea(c) > 8000]

                if len(cnts) != 1:
                    grade = 'multiple_cashews'
                    command = '21|'
                    try:
                        arduino.write(command.encode())
                        safe_print(f"{filename} → {grade} ({len(cnts)} contours) "
                                   f"in {time.time() - start:.2f}s → Sent: {command.strip()}")
                    except Exception as e:
                        safe_print(f"Error sending command for multiple cashews: {e}")

                    try:
                        os.remove(image_path)
                        safe_print(f"Deleted multiple-cashew image: {filename}")
                    except Exception as e:
                        safe_print(f"Error deleting image {filename}: {e}")
                    continue  # skip normal grading

                # ---------- NORMAL SINGLE CASHEW GRADING ----------
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                white_pixel_count = int(np.sum(binary == 255))

                grade = get_grade(white_pixel_count, ranges)
                command = GRADE_PORT_MAP.get(grade, GRADE_PORT_MAP['default'])

                try:
                    arduino.write(command.encode())
                    safe_print(f"{filename}: White Pixels = {white_pixel_count} "
                               f"→ Grade = {grade or 'None'} → Sent: {command.strip()}")
                except Exception as e:
                    safe_print(f"Error sending serial command: {e}")

                try:
                    os.remove(image_path)
                    safe_print(f"Deleted processed image: {filename}")
                except Exception as e:
                    safe_print(f"Error deleting image {filename}: {e}")

            time.sleep(0.001)

    except KeyboardInterrupt:
        safe_print("Monitoring stopped by user.")
    finally:
        try:
            arduino.close()
            safe_print("Serial port closed.")
        except Exception:
            pass


# ---------- MAIN ENTRY POINT ----------
if __name__ == '__main__':
    input_folder = r"D:\Keya Work\360\wate\Con_2_Images"
    ranges_file = r"D:\Keya Work\360\wate\value.txt"
    timing_file = r"D:\Keya Work\360\wate\4(B)-time.txt"
    com_port_file_path = r"D:\Keya Work\360\wate\com_port(b).txt"

    com_port = read_com_port_from_file(com_port_file_path)
    if com_port is None:
        safe_print("No valid COM port found. Exiting.")
        sys.exit(1)

    safe_print(f"Using COM port: {com_port}")
    process_images_continuous(input_folder, ranges_file, com_port, timing_file)
