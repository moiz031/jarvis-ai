# jarvis/tools/system_ops.py
import platform
import time
from dataclasses import dataclass

import psutil
try:
    import pyperclip
except Exception:
    pyperclip = None

try:
    import pygetwindow as gw
except Exception:
    gw = None


def get_system_status() -> dict:
    """Returns CPU/RAM/battery basics."""
    cpu = psutil.cpu_percent(interval=0.3)
    vm = psutil.virtual_memory()
    batt = None
    try:
        b = psutil.sensors_battery()
        if b:
            batt = {
                "percent": int(b.percent) if b.percent is not None else None,
                "plugged": bool(b.power_plugged),
                "secs_left": b.secsleft,
            }
    except Exception:
        batt = None

    return {
        "os": platform.platform(),
        "cpu_percent": cpu,
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / (1024**3), 2),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "battery": batt,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_clipboard_text(max_len: int = 4000) -> str:
    """Returns clipboard text (trimmed)."""
    if pyperclip is None:
        return ""
    try:
        text = pyperclip.paste()
        if not isinstance(text, str):
            return ""
        return text[:max_len]
    except Exception:
        return ""


def set_clipboard_text(text: str) -> bool:
    if pyperclip is None:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def get_active_window_title() -> str:
    """Best-effort active window title on Windows."""
    if gw is None:
        return ""
    try:
        w = gw.getActiveWindow()
        if not w:
            return ""
        return (w.title or "").strip()
    except Exception:
        return ""
def optimize_system() -> str:
    """Performs system cleanup and returns high-memory processes."""
    import gc
    
    # 1. Python Internal Cleanup
    gc.collect()
    
    # 2. Find High Memory Processes
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            mem = p.info['memory_info'].rss / (1024 * 1024) # MB
            if mem > 200: # Only care about > 200MB
                procs.append((p.info['name'], mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Sort by memory usage
    procs.sort(key=lambda x: x[1], reverse=True)
    top_procs = procs[:5]
    
    report = "System Optimization Complete.\nTop Memory Hogs:\n"
    for name, mem in top_procs:
        report += f"- {name}: {int(mem)} MB\n"
        
    return report
