# jarvis/tools/vision.py

try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: opencv-python not found. Vision features will be disabled.")

import base64
import requests
import os
from pathlib import Path
from datetime import datetime

try:
    import pyautogui
except Exception:
    pyautogui = None


# We'll use the OpenRouter/OpenAI key from config if available
# Vision tasks are hard for local 8GB RAM, so cloud fallback is preferred here.

def analyze_image(config, img_path: str, prompt="What do you see in this image?") -> str:
    """Analyze an image file using cloud vision API."""
    if not config.OPENAI_API_KEY:
        return f"Image save ho gayi hai yahan: {img_path}. Magar analysis ke liye OpenAI key chahiye."

    try:
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "HTTP-Referer": "https://github.com/google/advanced-agentic-coding",
            "X-Title": "Jarvis Desktop AI"
        }

        model = "google/gemini-flash-1.5" if "openrouter" in config.OPENAI_BASE_URL.lower() else "gpt-4o"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"You are Jarvis. Respond in natural Pakistani Roman Urdu. {prompt}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }

        response = requests.post(
            f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

    except Exception as e:
        return f"Vision analysis mein masla aya: {str(e)}"


def capture_and_analyze(config, prompt="What do you see in this image?"):
    """Uses a pre-captured frame from the UI or takes a new one."""
    temp_dir = Path(__file__).resolve().parent.parent / "data" / "vision"
    temp_dir.mkdir(parents=True, exist_ok=True)
    snap_path = temp_dir / "last_snap.jpg"

    if snap_path.exists():
        img_path = temp_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        os.rename(str(snap_path), str(img_path))
    elif "screen" in prompt.lower() or "desktop" in prompt.lower():
        # Screenshot Mode
        if pyautogui is None:
            return "Ghalti! pyautogui install nahi hai. Screenshot mode unavailable hai."

        img_path = temp_dir / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        screenshot = pyautogui.screenshot()
        screenshot.save(str(img_path))
    else:
        # Webcam Mode
        if cv2 is None:
            return "Ghalti! OpenCV library install nahi hai. Vision features disabled hain."

        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            return "Ghalti! Camera accessible nahi hai."
        ret, frame = cam.read()
        cam.release()
        if not ret:
            return "Ghalti! Frame capture nahi ho saki."
        img_path = temp_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(str(img_path), frame)

    return analyze_image(config, str(img_path), prompt)
