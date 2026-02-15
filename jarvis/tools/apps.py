# tools/apps.py

import os
import subprocess
import json
import time
from pathlib import Path

# Load apps registry
BASE_DIR = Path(__file__).resolve().parent.parent
APPS_JSON = BASE_DIR / "data" / "apps.json"

def _load_apps():
    if not APPS_JSON.exists():
        return {}
    try:
        with open(APPS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_apps(apps):
    APPS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(APPS_JSON, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2)

def open_app(app_name: str) -> str:
    """Try to open an application.
    1. Check if known in apps.json.
    2. Try generic Windows 'start' command.
    3. If failed, return instruction to ask user for path.
    """
    app_name = app_name.lower().strip()
    apps = _load_apps()
    
    # 1. Known path
    if app_name in apps:
        path = apps[app_name]
        try:
            os.startfile(path)
            return f"Opened {app_name} from stored path."
        except Exception as e:
            return f"Failed to open stored path for {app_name}: {e}"

    # 2. Generic Windows attempt
    try:
        # Try just the name
        subprocess.run(["cmd", "/c", "start", app_name], check=True)
        return f"Opened {app_name} via system default."
    except Exception:
        pass
        
    try:
        # Try finding aliases like 'notepad' -> 'notepad.exe'
        if "notepad" in app_name:
             subprocess.run(["notepad.exe"], check=True)
             return "Opened Notepad."
    except:
        pass

    # 3. Fail
    return f"Could not find '{app_name}'. Please provide the full path to executable so I can learn it."

def save_app_path(app_name: str, path: str) -> str:
    """Save a learned app path."""
    apps = _load_apps()
    apps[app_name.lower().strip()] = path
    _save_apps(apps)
    return f"Saved path for {app_name}."

def close_app(app_name: str) -> str:
    """Close an application using taskkill."""
    # Warning: This is forceful if /f is used, or might fail if unsaved.
    # We'll try graceful close first.
    try:
        # taskkill /im app_name.exe
        # We need to guess the executable name or use window title.
        # Simple guess: name + .exe
        exe_name = f"{app_name}.exe" if not app_name.endswith(".exe") else app_name
        
        # Try graceful
        result = subprocess.run(["taskkill", "/IM", exe_name], capture_output=True, text=True)
        if result.returncode == 0:
            return f"Closed {app_name}."
        
        # If failed, maybe name is wrong or needs force. 
        # For now, report failure to avoid data loss.
        return f"Could not close {app_name}. Error: {result.stderr.strip() or 'Unknown'}"
    except Exception as e:
        return f"Error closing app: {e}"
