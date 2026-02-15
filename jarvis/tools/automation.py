# jarvis/tools/automation.py

import time

try:
    import pyautogui
except Exception:
    pyautogui = None


# Security Note: All automation tasks MUST go through the safety gate in agent.py
# pyautogui.FAILSAFE is enabled by default (move mouse to corner to abort)

def _ensure_available() -> None:
    if pyautogui is None:
        raise RuntimeError(
            "Automation unavailable: install 'pyautogui' to enable keyboard/mouse control."
        )


def type_text(text: str):
    """Types text at the current cursor position."""
    _ensure_available()
    pyautogui.typewrite(text, interval=0.01)
    return f"Typed: {text}"


def press_key(key: str):
    """Presses a specific key (e.g., 'enter', 'tab', 'win')."""
    _ensure_available()
    pyautogui.press(key)
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
    _ensure_available()
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey: {'+'.join(keys)}"
