import serial
import time

PORT = "COM4"
BAUDRATE = 115200
SEND_INTERVAL = 0.10

try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    print(f"Connected to {PORT} at {BAUDRATE} baud. Waiting 2s for Arduino to initialize...")
    time.sleep(2)

    while True:
        ser.write(b"11|")
        print(f"Sent: 11|  Time: {time.strftime('%H:%M:%S')}")
        time.sleep(SEND_INTERVAL)

except KeyboardInterrupt:
    print("\nProgram Stopped")

finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Serial Port Closed")