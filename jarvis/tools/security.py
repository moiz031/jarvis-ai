# jarvis/tools/security.py

try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: opencv-python not found. Security features will be disabled.")

import time
from pathlib import Path

def verify_face():
    """
    Attempts to detect a face for a few seconds to 'verify' the user.
    Returns (success, message)
    """
    if cv2 is None:
        return False, "OpenCV library not installed. Security features disabled."
    
    # Load Haar Cascade for face detection
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, "Camera access denied."

    start_time = time.time()
    face_detected_frames = 0
    required_frames = 3 # Consecutive frames for "Verification"
    
    while time.time() - start_time < 5: # 5 seconds timeout
        ret, frame = cap.read()
        if not ret: break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            face_detected_frames += 1
        else:
            face_detected_frames = 0
            
        if face_detected_frames >= required_frames:
            cap.release()
            return True, "BIOMETRIC SUCCESS: IDENTITY CONFIRMED"
            
        time.sleep(0.1)
        
    cap.release()
    return False, "BIOMETRIC FAILURE: FACE NOT RECOGNIZED"
