import serial
import time

def test_serial():
    port = "COM4"
    baud = 115200
    
    try:
        print(f"Connecting to {port} at {baud} baud...")
        s = serial.Serial(port, baud, timeout=1)
        time.sleep(2) # Wait for Arduino reset
        print("Connected! Sending test commands...")
        
        while True:
            cmd = "11|10|\n" # 10ms delay so it executes almost immediately
            print(f"Sending: {cmd.strip()}")
            s.write(cmd.encode())
            s.flush()
            
            # Read any response if there is one
            time.sleep(0.1)
            if s.in_waiting > 0:
                print("Arduino says:", s.read(s.in_waiting).decode(errors='ignore').strip())
                
            time.sleep(2) # Send every 2 seconds
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_serial()
