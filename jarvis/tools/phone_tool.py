# jarvis/tools/phone_tool.py - Full Android Control Tool
"""
JARVIS Phone Control Tool.
Bridges the AI intent parser with the ADB execution engine.
Supports voice-driven multi-step phone workflows.
"""

import logging
import threading
import time
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    from .adb_core import ADBCore
    from .mobile_intent import (
        MobileIntentParser,
        INTENT_OPEN_APP, INTENT_CLOSE_APP, INTENT_SEND_MESSAGE,
        INTENT_CALL, INTENT_SEARCH, INTENT_TYPE_TEXT, INTENT_TAP,
        INTENT_SCROLL, INTENT_PRESS_KEY, INTENT_SCREENSHOT,
        INTENT_SETTINGS, INTENT_NAVIGATE, INTENT_READ_SCREEN,
        INTENT_SHELL, INTENT_DEVICE_INFO, INTENT_UNKNOWN,
    )
    from .vision_tool import VisionTool
except ImportError:
    try:
        from jarvis.tools.adb_core import ADBCore
        from jarvis.tools.mobile_intent import MobileIntentParser
        from jarvis.tools.vision_tool import VisionTool
        # ... and other intents as needed, or just import the module
    except ImportError:
        from adb_core import ADBCore # fallback for direct execution
        from mobile_intent import MobileIntentParser
        from vision_tool import VisionTool


class PhoneTool:
    """Full Android control through ADB + AI Intent parsing."""

    def __init__(self, emit: Callable, llm: Any = None, adb_path: Optional[str] = None):
        self.emit = emit
        self.adb = ADBCore(adb_path=adb_path)
        self.intent_parser = MobileIntentParser()
        self.vision = VisionTool(self.adb, llm) if llm else None
        self._connected = False
        self._auto_connect()

    def _auto_connect(self):
        """Attempt to connect on startup in the background."""
        def try_connect():
            if not self.adb.available:
                self._emit_log("⚠ ADB not found. Install Android SDK Platform Tools or place adb.exe in bin/platform-tools/")
                self.emit("phone_status", {
                    "connected": False,
                    "error": "ADB not installed",
                    "adb_available": False,
                })
                return

            ok, msg = self.adb.connect()
            if ok:
                self._connected = True
                info = self.adb.get_device_info()
                self._emit_log(f"✓ Connected to {info.get('brand', '').title()} {info.get('model', '')}")
                self.emit("phone_status", {
                    "connected": True,
                    "device": f"{info.get('brand', '').title()} {info.get('model', '')}",
                    "battery": info.get("battery", "?"),
                    "android": info.get("android_version", "?"),
                    "adb_available": True,
                })
            else:
                self._emit_log(f"⚠ No device detected: {msg}")
                self.emit("phone_status", {
                    "connected": False,
                    "error": msg,
                    "adb_available": True,
                })

        threading.Thread(target=try_connect, daemon=True).start()

    def _emit_log(self, message: str, level: str = "info"):
        """Send a message to the Phone Command Log in the UI."""
        self.emit("phone_log", {
            "message": message,
            "level": level,
            "timestamp": time.time(),
        })

    # ── Main Command Handler ─────────────────────────────────────────────

    def handle_command(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming phone control requests from the UI or voice."""
        action = data.get("action")

        # Direct actions from UI buttons
        if action == "connect":
            return self._action_connect(data)
        elif action == "disconnect":
            return self._action_disconnect()
        elif action == "status":
            return self._action_status()
        elif action == "open_app":
            app = data.get("app", "")
            return self._action_open_app(app)
        elif action == "shell":
            command = data.get("command", "")
            return self._action_shell(command)
        elif action == "voice_command":
            text = data.get("text", "")
            return self._action_voice(text)
        elif action == "tap":
            return self._action_tap(data.get("x", 0), data.get("y", 0))
        elif action == "press_key":
            return self._action_press_key(data.get("key", "home"))
        elif action == "type_text":
            return self._action_type_text(data.get("text", ""))
        elif action == "screenshot":
            return self._action_screenshot()
        elif action == "read_screen":
            return self._action_read_screen()
        elif action == "vision_analyze":
            return self._action_vision_analyze(data.get("query", "What's on screen?"))
        elif action == "vision_click":
            return self._action_vision_click(data.get("target", ""))
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    # ── Voice Command Processing ─────────────────────────────────────────

    def _action_voice(self, text: str) -> Dict[str, Any]:
        """Process a voice command through the AI intent parser."""
        parsed = self.intent_parser.parse(text)
        intent = parsed["intent"]
        params = parsed["params"]
        description = self.intent_parser.describe_intent(parsed)

        self._emit_log(f"🎤 Voice: \"{text}\"")
        self._emit_log(f"🧠 Intent: {description} (confidence: {parsed['confidence']:.0%})")

        if not self._connected and intent != INTENT_DEVICE_INFO:
            return {"status": "error", "message": "Phone not connected. Connect via USB or Wi-Fi first."}

        # Dispatch to handler
        intent_handlers = {
            INTENT_OPEN_APP: lambda: self._action_open_app(params.get("app", "")),
            INTENT_CLOSE_APP: lambda: self._action_close_app(params.get("app", "")),
            INTENT_SEND_MESSAGE: lambda: self._action_send_message(params),
            INTENT_CALL: lambda: self._action_call(params.get("contact", "")),
            INTENT_SEARCH: lambda: self._action_search(params.get("query", "")),
            INTENT_TYPE_TEXT: lambda: self._action_type_text(params.get("text", "")),
            INTENT_SCROLL: lambda: self._action_scroll(params.get("direction", "down")),
            INTENT_PRESS_KEY: lambda: self._action_press_key(params.get("key", "home")),
            INTENT_SCREENSHOT: lambda: self._action_screenshot(),
            INTENT_SETTINGS: lambda: self._action_settings(params),
            INTENT_READ_SCREEN: lambda: self._action_read_screen(),
            INTENT_DEVICE_INFO: lambda: self._action_status(),
            INTENT_NAVIGATE: lambda: self._action_navigate(params.get("target", "")),
        }

        handler = intent_handlers.get(intent)
        if handler:
            return handler()

        # Unknown intent — pass raw text to shell as fallback
        self._emit_log(f"❓ Could not parse intent. Try rephrasing.")
        return {"status": "unknown", "message": "Could not understand the command. Please try again."}

    # ── Action Implementations ───────────────────────────────────────────

    def _action_connect(self, data: Dict) -> Dict:
        ip = data.get("ip")
        ok, msg = self.adb.connect(ip)
        if ok:
            self._connected = True
            info = self.adb.get_device_info()
            self._emit_log(f"✓ {msg}")
            self.emit("phone_status", {
                "connected": True,
                "device": f"{info.get('brand', '').title()} {info.get('model', '')}",
                "battery": info.get("battery", "?"),
                "android": info.get("android_version", "?"),
            })
        else:
            self._emit_log(f"✗ {msg}", "error")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_disconnect(self) -> Dict:
        self.adb.run("disconnect")
        self._connected = False
        self._emit_log("Disconnected from device.")
        self.emit("phone_status", {"connected": False})
        return {"status": "ok", "message": "Disconnected"}

    def _action_status(self) -> Dict:
        summary = self.adb.status_summary()
        self.emit("phone_status", summary)
        return {"status": "ok", "data": summary}

    def _action_open_app(self, app: str) -> Dict:
        self._emit_log(f"▶ Opening {app}...")
        ok, msg = self.adb.open_app(app)
        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        self.emit("phone_event", {"type": "app_opened", "app": app, "success": ok})
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_close_app(self, app: str) -> Dict:
        self._emit_log(f"■ Closing {app}...")
        ok, msg = self.adb.close_app(app)
        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_shell(self, command: str) -> Dict:
        self._emit_log(f"$ {command}")
        ok, output = self.adb.shell(command)
        self._emit_log(f"{'✓' if ok else '✗'} {output[:200]}")
        return {"status": "ok" if ok else "error", "output": output}

    def _action_tap(self, x: int, y: int) -> Dict:
        ok, msg = self.adb.tap(x, y)
        self._emit_log(f"👆 Tap ({x}, {y})")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_type_text(self, text: str) -> Dict:
        self._emit_log(f"⌨ Typing: \"{text}\"")
        ok, msg = self.adb.type_text(text)
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_press_key(self, key: str) -> Dict:
        self._emit_log(f"🔘 Pressing {key}")
        ok, msg = self.adb.press_key(key)
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_scroll(self, direction: str) -> Dict:
        self._emit_log(f"📜 Scrolling {direction}")
        if direction == "up":
            ok, msg = self.adb.scroll_up()
        else:
            ok, msg = self.adb.scroll_down()
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_screenshot(self) -> Dict:
        self._emit_log("📸 Taking screenshot...")
        ok, msg = self.adb.take_screenshot()
        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_read_screen(self) -> Dict:
        self._emit_log("👁 Reading screen content...")
        elements = self.adb.parse_screen()
        if not elements:
            self._emit_log("No readable elements found.", "warning")
            return {"status": "ok", "elements": []}

        # Summarize visible text
        texts = [el["text"] for el in elements if el["text"]]
        summary = " | ".join(texts[:15])
        self._emit_log(f"Screen: {summary}")
        self.emit("phone_screen", {"elements": elements[:30], "summary": summary})
        return {"status": "ok", "elements": elements, "summary": summary}

    def _action_vision_analyze(self, query: str) -> Dict:
        if not self.vision:
            return {"status": "error", "message": "Vision AI not initialized (LLM missing)"}
        self._emit_log(f"👁 Vision Query: \"{query}\"")
        analysis = self.vision.analyze_screen(query)
        self._emit_log(f"🧠 AI: {analysis}")
        return {"status": "ok", "analysis": analysis}

    def _action_vision_click(self, target: str) -> Dict:
        if not self.vision:
            return {"status": "error", "message": "Vision AI not initialized"}
        self._emit_log(f"🎯 Finding: {target}")
        coords = self.vision.find_coordinates(target)
        if coords:
            ok, msg = self.adb.tap(coords["x"], coords["y"])
            self._emit_log(f"☝ Clickiing {target} at ({coords['x']}, {coords['y']})")
            return {"status": "ok" if ok else "error", "message": msg}
        self._emit_log(f"✗ Could not find {target} visually", "warning")
        return {"status": "error", "message": "Element not found via vision"}

    def _action_settings(self, params: Dict) -> Dict:
        setting = params.get("setting", "")
        value = params.get("value", True)
        action = params.get("action", "")

        self._emit_log(f"⚙ {action} {setting}")

        if "wifi" in setting:
            ok, msg = self.adb.set_wifi(value)
        elif "bluetooth" in setting:
            ok, msg = self.adb.set_bluetooth(value)
        elif "brightness" in setting:
            level = 200 if value else 50
            ok, msg = self.adb.set_brightness(level)
        elif "volume" in setting:
            level = 10 if value else 3
            ok, msg = self.adb.set_volume(level=level)
        else:
            return {"status": "error", "message": f"Setting '{setting}' not yet supported"}

        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_search(self, query: str) -> Dict:
        """Open Chrome and search for query."""
        self._emit_log(f"🔍 Searching: {query}")
        self.adb.open_app("chrome")
        time.sleep(2)
        # Tap the search bar (typical Chrome location)
        self.adb.tap(540, 150)
        time.sleep(1)
        self.adb.type_text(query)
        time.sleep(0.5)
        self.adb.press_key("enter")
        self._emit_log(f"✓ Searched for '{query}'")
        return {"status": "ok", "message": f"Searched for '{query}'"}

    def _action_call(self, contact: str) -> Dict:
        """Make a phone call."""
        self._emit_log(f"📞 Calling {contact}...")
        # If it looks like a number, dial directly
        clean = contact.replace(" ", "").replace("-", "")
        if clean.replace("+", "").isdigit():
            ok, msg = self.adb.shell(f"am start -a android.intent.action.CALL -d tel:{clean}")
        else:
            # Open dialer with the contact name
            ok, msg = self.adb.shell(f"am start -a android.intent.action.DIAL -d tel:{clean}")
        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_navigate(self, target: str) -> Dict:
        """Navigate to a location in the current app."""
        self._emit_log(f"🧭 Navigating to: {target}")
        # Try to find and click the element
        ok, msg = self.adb.click_element(text=target)
        if not ok:
            ok, msg = self.adb.click_element(description=target)
        self._emit_log(f"{'✓' if ok else '✗'} {msg}")
        return {"status": "ok" if ok else "error", "message": msg}

    def _action_send_message(self, params: Dict) -> Dict:
        """Multi-step: Send a message via the default messaging or WhatsApp."""
        contact = params.get("contact", "")
        message = params.get("message", "")
        self._emit_log(f"💬 Sending '{message}' to {contact}...")

        # Step 1: Open WhatsApp (most common)
        self.adb.open_app("whatsapp")
        time.sleep(3)

        # Step 2: Tap search
        self.adb.tap(540, 150)  # Search icon
        time.sleep(1)

        # Step 3: Type contact name
        self.adb.type_text(contact)
        time.sleep(2)

        # Step 4: Tap first result
        self.adb.tap(540, 350)
        time.sleep(2)

        # Step 5: Type message
        self.adb.tap(540, 2200)  # Message input field
        time.sleep(0.5)
        self.adb.type_text(message)
        time.sleep(0.5)

        # Step 6: Send
        self.adb.tap(980, 2200)  # Send button
        self._emit_log(f"✓ Message sent to {contact}")
        return {"status": "ok", "message": f"Message sent to {contact}"}
