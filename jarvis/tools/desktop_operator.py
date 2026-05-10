"""Desktop operator workflows built on local automation tools."""

from __future__ import annotations

import re
import time
from typing import Callable, List

try:
    from .apps import open_app
    from .automation import hotkey, mouse_click, move_mouse, press_key, scroll, type_text
except Exception:
    from jarvis.tools.apps import open_app
    from jarvis.tools.automation import hotkey, mouse_click, move_mouse, press_key, scroll, type_text


def _split_goal(goal: str) -> List[str]:
    parts = re.split(r"\bthen\b|,", goal, flags=re.IGNORECASE)
    expanded: List[str] = []
    for part in parts:
        if " and " in part.lower():
            expanded.extend([x.strip() for x in re.split(r"\band\b", part, flags=re.IGNORECASE) if x.strip()])
        else:
            item = part.strip()
            if item:
                expanded.append(item)
    return expanded


class DesktopOperator:
    def __init__(self, sleeper: Callable[[float], None] | None = None):
        self._sleep = sleeper or time.sleep

    def execute(self, goal: str) -> str:
        steps = _split_goal(goal)
        if not steps:
            return "Desktop workflow ke liye koi step nahi mila."

        results = []
        for step in steps:
            results.append(self._execute_step(step))
        return "Desktop workflow complete: " + " | ".join(results)

    def _execute_step(self, step: str) -> str:
        raw = step.strip()
        lowered = raw.lower()

        match = re.search(r"^(?:open|launch|start)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            app = match.group(1).strip()
            result = open_app(app)
            self._sleep(1.0)
            return result

        match = re.search(r"^(?:type|write)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            return type_text(match.group(1).strip())

        match = re.search(r"^(?:press)\s+([a-zA-Z_]+)$", raw, re.IGNORECASE)
        if match:
            return press_key(match.group(1).strip())

        match = re.search(r"^(?:hotkey|shortcut)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            keys = [item.strip() for item in re.split(r"\s*\+\s*|\s+", match.group(1)) if item.strip()]
            return hotkey(*keys)

        match = re.search(r"^(?:wait)\s+(\d+(?:\.\d+)?)", raw, re.IGNORECASE)
        if match:
            seconds = float(match.group(1))
            self._sleep(seconds)
            return f"Waited {seconds} seconds"

        if lowered.startswith("scroll down"):
            return scroll(-600)
        if lowered.startswith("scroll up"):
            return scroll(600)

        match = re.search(r"^(?:click at)\s+(\d+)\s*[,\s]\s*(\d+)$", raw, re.IGNORECASE)
        if match:
            return mouse_click(int(match.group(1)), int(match.group(2)))

        match = re.search(r"^(?:move mouse to)\s+(\d+)\s*[,\s]\s*(\d+)$", raw, re.IGNORECASE)
        if match:
            return move_mouse(int(match.group(1)), int(match.group(2)))

        match = re.search(r"^(?:search windows for|start menu search)\s+(.+)$", raw, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            hotkey("win")
            self._sleep(0.5)
            type_text(query)
            self._sleep(0.3)
            press_key("enter")
            return f"Windows search run ki: {query}"

        return f"Unsupported desktop step: {raw}"


def desktop_task(goal: str) -> str:
    return DesktopOperator().execute(goal)
