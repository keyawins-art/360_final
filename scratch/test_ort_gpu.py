import onnxruntime as ort
import numpy as np
import time

def test_ort():
    print("Testing ONNX GPU inference...")
    try:
        session = ort.InferenceSession(r"c:\Users\i7\Desktop\360\best.onnx", providers=['CUDAExecutionProvider'])
        
        # Get input shape
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        
        print(f"Input Name: {input_name}, Shape: {input_shape}")
        
        # create dummy input
        dummy_input = np.random.randn(1, 3, 704, 704).astype(np.float32)
        
        print("Running warmup...")
        for _ in range(3):
            session.run(None, {input_name: dummy_input})
            
        print("Running speed test...")
        start = time.time()
        for _ in range(10):
            session.run(None, {input_name: dummy_input})
        end = time.time()
        
        print(f"ONNX GPU 10 inferences: {(end-start)*1000:.2f} ms")
        print(f"Average: {(end-start)*100:.2f} ms per inference")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_ort()
