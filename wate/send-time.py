import serial
import time

COM_PORT = "COM4"
BAUD_RATE = 115200

timing_string = "000000000000000000000000000000000000000000000000000099|"

try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)

    ser.write(timing_string.encode('ascii'))

    print(f"Sent: {timing_string}")

    ser.close()

except serial.SerialException as e:
    print(e)