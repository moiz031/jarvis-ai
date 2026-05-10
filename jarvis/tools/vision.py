import base64
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

try:
    import cv2
except ImportError:
    cv2 = None
    print("Warning: opencv-python not found. Vision features will be delegated when possible.")

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    from ..runtime_support import ensure_ollama_running
except Exception:
    try:
        from jarvis.runtime_support import ensure_ollama_running
    except Exception:
        ensure_ollama_running = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "vision"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_cloud_key(config) -> str | None:
    base = (getattr(config, "OPENAI_BASE_URL", "") or "").lower()
    if "openrouter.ai" in base:
        return getattr(config, "OPENROUTER_API_KEY", None) or getattr(config, "OPENAI_API_KEY", None)
    if "api.x.ai" in base or "x.ai" in base:
        return getattr(config, "XAI_API_KEY", None) or getattr(config, "OPENAI_API_KEY", None)
    if "api.groq.com" in base:
        return getattr(config, "GROQ_API_KEY", None) or getattr(config, "OPENAI_API_KEY", None)
    return getattr(config, "OPENAI_API_KEY", None)


def _vision_python_candidates() -> list[str]:
    candidates = [
        REPO_ROOT / "jarvis_backend_env" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    seen = set()
    results = []
    for path in candidates:
        resolved = str(path)
        if path.exists() and resolved not in seen:
            results.append(resolved)
            seen.add(resolved)
    return results


def _python_has_module(python_exe: str, module_name: str) -> bool:
    try:
        proc = subprocess.run(
            [python_exe, "-c", f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec('{module_name}') else 1)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _resolve_cv2_python() -> str | None:
    for python_exe in _vision_python_candidates():
        if _python_has_module(python_exe, "cv2"):
            return python_exe
    return None


def _run_runtime_helper(command: str, *args: str) -> dict:
    python_exe = _resolve_cv2_python()
    if not python_exe:
        return {"ok": False, "error": "cv2_runtime_missing"}

    helper_path = REPO_ROOT / "jarvis" / "tools" / "vision_runtime_helper.py"
    proc = subprocess.run(
        [python_exe, str(helper_path), command, *args],
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if not proc.stdout.strip():
        return {"ok": False, "error": proc.stderr.strip() or "vision_helper_failed"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"ok": False, "error": proc.stdout.strip() or proc.stderr.strip() or "vision_helper_invalid_output"}


def _default_image_path(prefix: str) -> Path:
    return DATA_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"


def _capture_screen_with_powershell(out_path: str) -> bool:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$target=[Environment]::GetEnvironmentVariable('JARVIS_SCREENSHOT_PATH','Process'); "
        "$bounds=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp=New-Object System.Drawing.Bitmap $bounds.Width,$bounds.Height; "
        "$gfx=[System.Drawing.Graphics]::FromImage($bmp); "
        "$gfx.CopyFromScreen($bounds.Location,[System.Drawing.Point]::Empty,$bounds.Size); "
        "$bmp.Save($target,[System.Drawing.Imaging.ImageFormat]::Jpeg); "
        "$gfx.Dispose(); "
        "$bmp.Dispose()"
    )
    env = os.environ.copy()
    env["JARVIS_SCREENSHOT_PATH"] = out_path
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return proc.returncode == 0 and Path(out_path).exists()


def capture_screen(out_path: str | None = None) -> str:
    target = Path(out_path) if out_path else _default_image_path("screen")
    target.parent.mkdir(parents=True, exist_ok=True)

    if pyautogui is not None:
        screenshot = pyautogui.screenshot()
        screenshot.save(str(target))
        return str(target)

    if _capture_screen_with_powershell(str(target)):
        return str(target)

    raise RuntimeError("Screen capture unavailable: pyautogui aur PowerShell screenshot dono fail ho gaye.")


def capture_camera_frame(out_path: str | None = None) -> str:
    target = Path(out_path) if out_path else _default_image_path("capture")
    target.parent.mkdir(parents=True, exist_ok=True)

    if cv2 is not None:
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            raise RuntimeError("Camera accessible nahi hai.")
        ok, frame = cam.read()
        cam.release()
        if not ok:
            raise RuntimeError("Frame capture nahi ho saki.")
        cv2.imwrite(str(target), frame)
        return str(target)

    payload = _run_runtime_helper("capture_camera", str(target), "0")
    if payload.get("ok") and payload.get("path"):
        return str(payload["path"])
    raise RuntimeError(str(payload.get("error", "Camera runtime unavailable")))


def extract_video_frame(video_path: str, out_path: str | None = None) -> str:
    target = Path(out_path) if out_path else Path(video_path).with_suffix(".jarvis_frame.jpg")
    target.parent.mkdir(parents=True, exist_ok=True)

    if cv2 is not None:
        cap = cv2.VideoCapture(video_path)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("Video ka frame read nahi ho saka.")
        cv2.imwrite(str(target), frame)
        return str(target)

    payload = _run_runtime_helper("extract_video_frame", str(video_path), str(target))
    if payload.get("ok") and payload.get("path"):
        return str(payload["path"])
    raise RuntimeError(str(payload.get("error", "Video runtime unavailable")))


def _select_ollama_vision_model(config) -> str:
    preferred = os.getenv("OLLAMA_VISION_MODEL", "").strip()
    if preferred:
        return preferred

    host = getattr(config, "OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        response = requests.get(f"{host}/api/tags", timeout=3)
        response.raise_for_status()
        names = [item.get("name", "") for item in response.json().get("models", [])]
    except Exception:
        names = []

    keywords = ("llava", "moondream", "vision", "bakllava", "minicpm")
    for name in names:
        lowered = name.lower()
        if any(keyword in lowered for keyword in keywords):
            return name
    return getattr(config, "OLLAMA_MODEL", "llava")


def _analyze_with_ollama(config, img_path: str, prompt: str) -> str | None:
    if ensure_ollama_running is not None:
        boot = ensure_ollama_running(
            getattr(config, "OLLAMA_HOST", "http://localhost:11434"),
            auto_start=bool(getattr(config, "OLLAMA_AUTO_START", True)),
        )
        if not boot.get("ok"):
            return None

    try:
        with open(img_path, "rb") as image_file:
            image_b64 = base64.b64encode(image_file.read()).decode("utf-8")
        payload = {
            "model": _select_ollama_vision_model(config),
            "prompt": f"You are Jarvis. Respond in concise Roman Urdu. {prompt}",
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256},
        }
        response = requests.post(
            f"{getattr(config, 'OLLAMA_HOST', 'http://localhost:11434').rstrip('/')}/api/generate",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        return text or None
    except Exception:
        return None


def analyze_image(config, img_path: str, prompt: str = "What do you see in this image?") -> str:
    cloud_key = _resolve_cloud_key(config)
    if cloud_key:
        try:
            with open(img_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cloud_key}",
                "HTTP-Referer": "https://github.com/google/advanced-agentic-coding",
                "X-Title": "Jarvis Desktop AI",
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
                                "text": f"You are Jarvis. Respond in natural Pakistani Roman Urdu. {prompt}",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 500,
            }

            response = requests.post(
                f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"Vision analysis mein masla aya: {str(exc)}"

    local_result = _analyze_with_ollama(config, img_path, prompt)
    if local_result:
        return local_result

    return f"Image save ho gayi hai yahan: {img_path}. Analysis ke liye local vision model ya cloud API key chahiye."


def capture_and_analyze(config, prompt: str = "What do you see in this image?"):
    snap_path = DATA_DIR / "last_snap.jpg"

    try:
        if snap_path.exists():
            img_path = DATA_DIR / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            snap_path.replace(img_path)
            return analyze_image(config, str(img_path), prompt)

        if "screen" in prompt.lower() or "desktop" in prompt.lower():
            img_path = capture_screen()
            return analyze_image(config, img_path, prompt)

        img_path = capture_camera_frame()
        return analyze_image(config, img_path, prompt)
    except Exception as exc:
        return f"Vision capture mein masla aya: {exc}"
