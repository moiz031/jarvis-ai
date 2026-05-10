import time
import logging
import cv2
import numpy as np
from vision_monitor import VisionMonitor

logging.basicConfig(level=logging.INFO)

def mock_emit(event, data):
    print(f"\n[EVENT EMITTED] {event}: {data}")

if __name__ == "__main__":
    print("Starting Vision Monitor Test...")
    vision = VisionMonitor(emit_callback=mock_emit)
    
    print("\n--- Simulating Normal Screen ---")
    # Provide a mock normal image
    normal_img = np.zeros((100, 100, 3), dtype=np.uint8)
    vision._detect_anomalies(normal_img)
    
    print("\n--- Simulating Screen Error ---")
    # Provide a mock image that has the word 'error' in it, 
    # but since tesseract is needed we'll mock the OCR output natively
    import pytesseract
    original_ocr = pytesseract.image_to_string
    pytesseract.image_to_string = lambda img: "An unexpected ERROR has occurred in the application."
    
    vision._detect_anomalies(normal_img)
    
    pytesseract.image_to_string = original_ocr
    print("\nTest completed.")
