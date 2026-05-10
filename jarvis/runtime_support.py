import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


def _candidate_ollama_paths() -> list[str]:
    candidates = []
    resolved = shutil.which("ollama")
    if resolved:
        candidates.append(resolved)

    local_appdata = os.getenv("LOCALAPPDATA", "")
    if local_appdata:
        candidates.append(str(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"))

    candidates.extend(
        [
            r"C:\Program Files\Ollama\ollama.exe",
            str(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"),
        ]
    )

    unique = []
    seen = set()
    for path in candidates:
        if path and path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def find_ollama_exe() -> str | None:
    for candidate in _candidate_ollama_paths():
        if candidate and Path(candidate).exists():
            return candidate
    return None


def is_local_ollama_host(host: str) -> bool:
    try:
        parsed = urlparse(host)
        return parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0", None}
    except Exception:
        return False


def wait_for_ollama(host: str, retries: int = 8, delay: float = 1.0) -> bool:
    for _ in range(max(1, retries)):
        try:
            response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=3)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def _port_open(hostname: str, port: int) -> bool:
    try:
        with socket.create_connection((hostname, port), timeout=1.5):
            return True
    except OSError:
        return False


def ensure_ollama_running(host: str, auto_start: bool = True) -> dict:
    host = (host or "http://localhost:11434").rstrip("/")
    if wait_for_ollama(host, retries=1, delay=0.1):
        return {"ok": True, "running": True, "started": False, "path": None}

    if not auto_start or not is_local_ollama_host(host):
        return {"ok": False, "running": False, "started": False, "reason": "not_running"}

    parsed = urlparse(host)
    hostname = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434

    if _port_open(hostname, port):
        return {"ok": False, "running": False, "started": False, "reason": "port_busy"}

    ollama_exe = find_ollama_exe()
    if not ollama_exe:
        return {"ok": False, "running": False, "started": False, "reason": "missing_exe"}

    try:
        subprocess.Popen(
            [ollama_exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as exc:
        return {"ok": False, "running": False, "started": False, "reason": f"start_failed:{exc}"}

    if wait_for_ollama(host, retries=10, delay=1.0):
        return {"ok": True, "running": True, "started": True, "path": ollama_exe}

    return {"ok": False, "running": False, "started": True, "path": ollama_exe, "reason": "startup_timeout"}
