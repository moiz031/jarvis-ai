# jarvis/tools/automation.py

import os
import subprocess

try:
    import pyautogui
except Exception:
    pyautogui = None


# Security Note: All automation tasks MUST go through the safety gate in agent.py
# pyautogui.FAILSAFE is enabled by default (move mouse to corner to abort)

_SENDKEY_MAP = {
    "enter": "{ENTER}",
    "return": "{ENTER}",
    "tab": "{TAB}",
    "esc": "{ESC}",
    "escape": "{ESC}",
    "space": " ",
    "backspace": "{BACKSPACE}",
    "delete": "{DELETE}",
    "del": "{DELETE}",
    "up": "{UP}",
    "down": "{DOWN}",
    "left": "{LEFT}",
    "right": "{RIGHT}",
    "home": "{HOME}",
    "end": "{END}",
    "pgup": "{PGUP}",
    "pageup": "{PGUP}",
    "pgdn": "{PGDN}",
    "pagedown": "{PGDN}",
    "f1": "{F1}",
    "f2": "{F2}",
    "f3": "{F3}",
    "f4": "{F4}",
    "f5": "{F5}",
    "f6": "{F6}",
    "f7": "{F7}",
    "f8": "{F8}",
    "f9": "{F9}",
    "f10": "{F10}",
    "f11": "{F11}",
    "f12": "{F12}",
}


def _ensure_available() -> None:
    if pyautogui is None:
        raise RuntimeError(
            "Automation unavailable: install 'pyautogui' to enable keyboard/mouse control."
        )


def _escape_sendkeys(text: str) -> str:
    escaped = []
    for char in text:
        if char in "+^%~(){}[]":
            escaped.append("{" + char + "}")
        else:
            escaped.append(char)
    return "".join(escaped)


def _run_sendkeys(sequence: str) -> None:
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "Start-Sleep -Milliseconds 120; "
        "$seq = [Environment]::GetEnvironmentVariable('JARVIS_SENDKEYS','Process'); "
        "$ws.SendKeys($seq)"
    )
    env = os.environ.copy()
    env["JARVIS_SENDKEYS"] = sequence
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows SendKeys failed")


def _modifier_prefix(key: str) -> str:
    normalized = key.lower().strip()
    return {
        "ctrl": "^",
        "control": "^",
        "alt": "%",
        "shift": "+",
    }.get(normalized, "")


def _non_modifier_token(key: str) -> str:
    normalized = key.lower().strip()
    if normalized in {"win", "windows", "cmd", "super"}:
        raise RuntimeError("Windows key automation fallback supported nahi hai.")
    return _SENDKEY_MAP.get(normalized, _escape_sendkeys(key))


def type_text(text: str):
    """Types text at the current cursor position."""
    if pyautogui is not None:
        pyautogui.typewrite(text, interval=0.01)
    else:
        _run_sendkeys(_escape_sendkeys(text))
    return f"Typed: {text}"


def press_key(key: str):
    """Presses a specific key (e.g., 'enter', 'tab', 'win')."""
    if pyautogui is not None:
        pyautogui.press(key)
    else:
        _run_sendkeys(_non_modifier_token(key))
    return f"Pressed key: {key}"


def scroll(amount: int):
    """Scrolls up (positive) or down (negative)."""
    _ensure_available()
    pyautogui.scroll(amount)
    return f"Scrolled {amount}"


def mouse_click(x: int = None, y: int = None):
    """Clicks at (x, y) or current position if None."""
    _ensure_available()
    if x is not None and y is not None:
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"

    pyautogui.click()
    return "Clicked current position"


def move_mouse(x: int, y: int):
    """Moves mouse to (x, y)."""
    _ensure_available()
    pyautogui.moveTo(x, y, duration=0.2)
    return f"Moved mouse to ({x}, {y})"


def hotkey(*keys):
    """Presses a combination of keys."""
    if pyautogui is not None:
        pyautogui.hotkey(*keys)
    else:
        modifiers = "".join(_modifier_prefix(key) for key in keys if _modifier_prefix(key))
        non_modifiers = [key for key in keys if not _modifier_prefix(key)]
        if not non_modifiers:
            raise RuntimeError("Hotkey ke liye kam az kam ek non-modifier key chahiye.")
        for key in non_modifiers:
            _run_sendkeys(modifiers + _non_modifier_token(key))
    return f"Pressed hotkey: {'+'.join(keys)}"
