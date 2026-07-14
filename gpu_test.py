import time
import numpy as np
try:
    from ultralytics import YOLO
    import torch
except ImportError:
    print("YOLO or PyTorch not installed.")
    exit()

print("Checking PyTorch GPU...")
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")

print("\nLoading YOLO model...")
model = YOLO(r"c:\Users\i7\Desktop\360\best.pt")

print("\nModel loaded. Simulating 25 cashews per frame...")
# Create a dummy crop representing a cashew (e.g. 150x150 pixels)
dummy_crop = np.zeros((150, 150, 3), dtype=np.uint8)

# Warmup GPU
print("Warming up GPU (Compiling kernels)...")
for _ in range(10):
    model(dummy_crop, verbose=False, conf=0.40, device=0)

print("\n=======================================================")
print("STARTING TEST! CHECK TASK MANAGER NOW (CPU vs GPU 3D)")
print("=======================================================")
print("Press Ctrl+C in terminal to stop if running manually.\n")

frames_processed = 0
start_time = time.time()
last_print_time = time.time()

try:
    # Run for 2 minutes maximum so it doesn't get stuck forever
    while time.time() - start_time < 120:
        frame_start = time.time()
        
        # Simulate 25 cashews being processed in one single frame
        for i in range(25):
            results = model(dummy_crop, verbose=False, conf=0.40, device=0)
            
        frame_time = time.time() - frame_start
        fps = 1.0 / frame_time if frame_time > 0 else 999.0
        
        frames_processed += 1
        
        # Print stats every second
        if time.time() - last_print_time >= 1.0:
            elapsed = time.time() - start_time
            avg_fps = frames_processed / elapsed
            print(f"[GPU TEST] 1 Frame (25 cashews) Time: {frame_time*1000:.1f}ms | Current FPS: {fps:.1f} | Avg FPS: {avg_fps:.1f}")
            last_print_time = time.time()
            
except KeyboardInterrupt:
    print("\nTest stopped by user.")

print("\nTest Finished.")
