# jarvis/tools/mobile_intent.py - AI Intent Parser for Mobile Commands
"""
Parses natural-language voice commands into structured mobile intents.
Supports both English and Urdu/Roman Urdu for the JARVIS assistant.
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# ── Intent Definitions ───────────────────────────────────────────────────────

INTENT_OPEN_APP = "open_app"
INTENT_CLOSE_APP = "close_app"
INTENT_SEND_MESSAGE = "send_message"
INTENT_CALL = "make_call"
INTENT_SEARCH = "search"
INTENT_TYPE_TEXT = "type_text"
INTENT_TAP = "tap"
INTENT_SCROLL = "scroll"
INTENT_PRESS_KEY = "press_key"
INTENT_SCREENSHOT = "screenshot"
INTENT_SETTINGS = "change_setting"
INTENT_NAVIGATE = "navigate"
INTENT_READ_SCREEN = "read_screen"
INTENT_SHELL = "shell_command"
INTENT_DEVICE_INFO = "device_info"
INTENT_MULTI_STEP = "multi_step"
INTENT_UNKNOWN = "unknown"


# ── App Name Aliases (English + Urdu) ────────────────────────────────────────

APP_ALIASES = {
    # Social
    "whatsapp": "whatsapp", "wa": "whatsapp",
    "instagram": "instagram", "insta": "instagram",
    "facebook": "facebook", "fb": "facebook",
    "twitter": "twitter", "x": "twitter",
    "telegram": "telegram", "tg": "telegram",
    "tiktok": "tiktok",
    "snapchat": "snapchat",

    # Media
    "youtube": "youtube", "yt": "youtube",
    "spotify": "spotify",
    "netflix": "netflix",

    # Google
    "chrome": "chrome", "browser": "chrome",
    "gmail": "gmail", "email": "gmail", "mail": "gmail",
    "maps": "maps", "google maps": "maps",
    "play store": "play store",

    # System
    "settings": "settings", "setting": "settings",
    "camera": "camera",
    "gallery": "gallery", "photos": "gallery",
    "calculator": "calculator", "calc": "calculator",
    "clock": "clock", "alarm": "clock",
    "phone": "phone", "dialer": "phone",
    "contacts": "contacts", "contact": "contacts",
    "messages": "messages", "sms": "messages",
    "files": "files", "file manager": "files",
}

# ── Keyword Patterns ─────────────────────────────────────────────────────────

OPEN_KEYWORDS = [
    r"open\s+(.+)", r"launch\s+(.+)", r"start\s+(.+)", r"run\s+(.+)",
    r"(.+)\s+open\s+karo", r"(.+)\s+kholo", r"(.+)\s+chala[oy]",
    r"(.+)\s+start\s+karo",
]

CLOSE_KEYWORDS = [
    r"close\s+(.+)", r"exit\s+(.+)", r"quit\s+(.+)", r"kill\s+(.+)",
    r"(.+)\s+band\s+karo", r"(.+)\s+close\s+karo",
]

MESSAGE_KEYWORDS = [
    r"(?:send|type)\s+(?:a\s+)?message\s+(?:to\s+)?(.+?)\s+(?:saying|that|:)\s+(.+)",
    r"(.+)\s+ko\s+message\s+(?:bhejo|karo)\s+(.+)",
    r"(?:send|bhejo)\s+(.+?)\s+(?:on|par|to)\s+whatsapp",
]

CALL_KEYWORDS = [
    r"call\s+(.+)", r"dial\s+(.+)", r"phone\s+(.+)",
    r"(.+)\s+ko\s+call\s+karo",
]

SEARCH_KEYWORDS = [
    r"search\s+(?:for\s+)?(.+)", r"google\s+(.+)", r"look\s+up\s+(.+)",
    r"(.+)\s+search\s+karo",
]

SETTING_KEYWORDS = [
    r"(turn\s+(?:on|off)|enable|disable|increase|decrease|set)\s+(wifi|bluetooth|brightness|volume|airplane\s*mode|dark\s*mode|location|mobile\s*data)",
    r"(wifi|bluetooth|brightness|volume)\s+(on|off|up|down)\s*karo",
]

SCROLL_KEYWORDS = [
    r"scroll\s+(up|down|left|right)",
    r"(upar|neeche)\s+scroll\s+karo",
]

NAVIGATE_KEYWORDS = [
    r"go\s+(?:to\s+)?(.+)", r"navigate\s+(?:to\s+)?(.+)",
    r"press\s+(home|back|recent)",
    r"(home|back|wapas)\s+(?:ja[oy]|karo|press\s+karo)",
]


class MobileIntentParser:
    """Parses natural language into structured mobile intents."""

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse a voice command into a structured intent.

        Returns:
            {
                "intent": str,        # The intent type
                "params": dict,       # Intent-specific parameters
                "raw": str,           # Original text
                "confidence": float,  # 0.0 - 1.0
            }
        """
        text_lower = text.lower().strip()

        # 1. Check for app opening
        for pattern in OPEN_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                app_name = match.group(1).strip().rstrip(".")
                resolved = APP_ALIASES.get(app_name, app_name)
                return self._intent(INTENT_OPEN_APP, {"app": resolved}, text, 0.9)

        # 2. Check for app closing
        for pattern in CLOSE_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                app_name = match.group(1).strip().rstrip(".")
                resolved = APP_ALIASES.get(app_name, app_name)
                return self._intent(INTENT_CLOSE_APP, {"app": resolved}, text, 0.9)

        # 3. Check for messaging
        for pattern in MESSAGE_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return self._intent(INTENT_SEND_MESSAGE, {
                        "contact": groups[0].strip(),
                        "message": groups[1].strip(),
                    }, text, 0.85)

        # 4. Check for calling
        for pattern in CALL_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                return self._intent(INTENT_CALL, {
                    "contact": match.group(1).strip(),
                }, text, 0.9)

        # 5. Check for settings
        for pattern in SETTING_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                action = groups[0].lower()
                setting = groups[1].lower().replace(" ", "_")
                enabled = "on" in action or "enable" in action or "increase" in action or "up" in action
                return self._intent(INTENT_SETTINGS, {
                    "setting": setting,
                    "value": enabled,
                    "action": action,
                }, text, 0.9)

        # 6. Check for scrolling
        for pattern in SCROLL_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                direction = match.group(1).strip()
                direction_map = {"upar": "up", "neeche": "down"}
                direction = direction_map.get(direction, direction)
                return self._intent(INTENT_SCROLL, {"direction": direction}, text, 0.95)

        # 7. Check for navigation
        for pattern in NAVIGATE_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                target = match.group(1).strip()
                key_map = {"home": "home", "back": "back", "wapas": "back", "recent": "recent"}
                if target in key_map:
                    return self._intent(INTENT_PRESS_KEY, {"key": key_map[target]}, text, 0.95)
                return self._intent(INTENT_NAVIGATE, {"target": target}, text, 0.7)

        # 8. Check for search
        for pattern in SEARCH_KEYWORDS:
            match = re.search(pattern, text_lower)
            if match:
                return self._intent(INTENT_SEARCH, {
                    "query": match.group(1).strip(),
                }, text, 0.85)

        # 9. Screenshot
        if any(k in text_lower for k in ["screenshot", "screen capture", "screen shot", "ss le"]):
            return self._intent(INTENT_SCREENSHOT, {}, text, 0.95)

        # 10. Read screen / what's on screen
        if any(k in text_lower for k in [
            "what's on screen", "read screen", "screen kya hai",
            "kya dikh raha", "screen par kya"
        ]):
            return self._intent(INTENT_READ_SCREEN, {}, text, 0.9)

        # 11. Device info
        if any(k in text_lower for k in [
            "battery", "device info", "phone status", "phone info",
            "kitni battery", "phone ki info"
        ]):
            return self._intent(INTENT_DEVICE_INFO, {}, text, 0.9)

        # 12. Type text (fallback for "type ...")
        type_match = re.search(r"type\s+(.+)", text_lower)
        if type_match:
            return self._intent(INTENT_TYPE_TEXT, {
                "text": type_match.group(1).strip()
            }, text, 0.8)

        # Unknown — let the AI agent handle it
        return self._intent(INTENT_UNKNOWN, {"raw_text": text}, text, 0.0)

    def _intent(self, intent: str, params: dict, raw: str, confidence: float) -> Dict[str, Any]:
        return {
            "intent": intent,
            "params": params,
            "raw": raw,
            "confidence": confidence,
        }

    def describe_intent(self, parsed: Dict[str, Any]) -> str:
        """Human-readable description of a parsed intent."""
        intent = parsed["intent"]
        params = parsed["params"]

        descriptions = {
            INTENT_OPEN_APP: f"Opening {params.get('app', '?')}",
            INTENT_CLOSE_APP: f"Closing {params.get('app', '?')}",
            INTENT_SEND_MESSAGE: f"Sending message to {params.get('contact', '?')}: \"{params.get('message', '')}\"",
            INTENT_CALL: f"Calling {params.get('contact', '?')}",
            INTENT_SEARCH: f"Searching for: {params.get('query', '?')}",
            INTENT_TYPE_TEXT: f"Typing: \"{params.get('text', '')}\"",
            INTENT_SCROLL: f"Scrolling {params.get('direction', 'down')}",
            INTENT_PRESS_KEY: f"Pressing {params.get('key', '?')} button",
            INTENT_SCREENSHOT: "Taking screenshot",
            INTENT_SETTINGS: f"Changing {params.get('setting', '?')}",
            INTENT_READ_SCREEN: "Reading current screen",
            INTENT_DEVICE_INFO: "Getting device information",
            INTENT_UNKNOWN: "Understanding command...",
        }
        return descriptions.get(intent, f"Executing: {intent}")
