# jarvis/tools/adb_core.py - Real ADB Integration Layer
"""
Android Debug Bridge (ADB) wrapper for JARVIS.
Provides robust command execution, device discovery, and screen parsing.
Auto-discovers adb.exe from system PATH or project-local bin/.
"""

import subprocess
import os
import logging
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ── ADB Path Discovery ──────────────────────────────────────────────────────

def find_adb() -> Optional[str]:
    """Auto-discover the adb executable."""
    # 1. Check project-local bin/
    project_root = Path(__file__).resolve().parent.parent.parent  # jarvis/tools -> jarvis -> project root
    local_paths = [
        project_root / "bin" / "platform-tools" / "adb.exe",
        project_root / "platform-tools" / "adb.exe",
    ]
    for p in local_paths:
        if p.exists():
            logger.info("[ADB] Found local adb: %s", p)
            return str(p)

    # 2. Check common SDK locations
    sdk_locations = [
        Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools" / "adb.exe",
        Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools" / "adb.exe",
        Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path("C:/Android/platform-tools/adb.exe"),
    ]
    for p in sdk_locations:
        if p.exists():
            logger.info("[ADB] Found SDK adb: %s", p)
            return str(p)

    # 3. Fallback to system PATH
    try:
        result = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0].strip()
            if path:
                logger.info("[ADB] Found system adb: %s", path)
                return path
    except Exception:
        pass

    logger.warning("[ADB] adb.exe not found anywhere")
    return None


# ── ADB Command Runner ──────────────────────────────────────────────────────

class ADBCore:
    """Core ADB command execution engine."""

    def __init__(self, adb_path: Optional[str] = None, device_serial: Optional[str] = None):
        self.adb_path = adb_path or find_adb()
        self.device_serial = device_serial
        self._connected = False
        self._device_info: Dict[str, Any] = {}

    @property
    def available(self) -> bool:
        return self.adb_path is not None and os.path.isfile(self.adb_path)

    def _build_cmd(self, *args: str) -> List[str]:
        """Construct the adb command list."""
        cmd = [str(self.adb_path)]
        if self.device_serial:
            cmd.extend(["-s", str(self.device_serial)])
        cmd.extend(list(args))
        return cmd

    def run(self, *args, timeout: int = 15) -> Tuple[bool, str]:
        """Execute an ADB command. Returns (success, output)."""
        if not self.available:
            return False, "ADB not available. Please install Android SDK Platform Tools."
        cmd = self._build_cmd(*args)
        logger.debug("[ADB] Running: %s", " ".join(cmd))
        try:
            # Creation flags for Windows to hide console
            flags = 0
            if os.name == 'nt':
                # Use literal for CREATE_NO_WINDOW if not found
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                creationflags=flags
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                err = result.stderr.strip()
                logger.warning("[ADB] Command failed: %s", err)
                return False, err or f"ADB exited with code {result.returncode}"
            return True, output
        except subprocess.TimeoutExpired:
            return False, "ADB command timed out"
        except FileNotFoundError:
            return False, f"ADB executable not found at: {self.adb_path}"
        except Exception as e:
            return False, f"ADB error: {str(e)}"

    def shell(self, command: str, timeout: int = 15) -> Tuple[bool, str]:
        """Execute an ADB shell command."""
        return self.run("shell", command, timeout=timeout)

    # ── Device Management ────────────────────────────────────────────────

    def get_devices(self) -> List[Dict[str, str]]:
        """List connected ADB devices."""
        ok, output = self.run("devices", "-l")
        if not ok:
            return []
        devices = []
        lines = output.split("\n")
        if len(lines) <= 1:
            return []
            
        for line in lines[1:]:
            line = line.strip()
            if not line or "offline" in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                status = parts[1]
                info = {"serial": serial, "status": status}
                # Parse extra fields like model:, device:, transport_id:
                for part in parts[2:]:
                    if ":" in part:
                        k, v = part.split(":", 1)
                        info[k] = v
                devices.append(info)
        return devices

    def connect(self, ip_port: Optional[str] = None) -> Tuple[bool, str]:
        """Connect to a device. If ip_port given, connect wirelessly."""
        if ip_port:
            ok, msg = self.run("connect", ip_port)
            if ok and "connected" in msg.lower():
                self._connected = True
                self.device_serial = ip_port
                return True, msg
            return False, msg

        # Check for USB devices
        devices = self.get_devices()
        if devices:
            self.device_serial = devices[0]["serial"]
            self._connected = True
            return True, f"Connected to {self.device_serial}"
        return False, "No devices found. Enable USB Debugging on your phone."

    def get_device_info(self) -> Dict[str, Any]:
        """Fetch basic device info."""
        if not self._connected:
            return {"error": "Not connected"}
        info: Dict[str, Any] = {}
        props = {
            "model": "ro.product.model",
            "brand": "ro.product.brand",
            "android_version": "ro.build.version.release",
            "sdk_version": "ro.build.version.sdk",
            "device_name": "ro.product.device",
        }
        for key, prop in props.items():
            ok, val = self.shell(f"getprop {prop}")
            info[key] = val.strip() if ok else "unknown"

        # Battery
        ok, batt = self.shell("dumpsys battery")
        if ok:
            for line in batt.split("\n"):
                line = line.strip()
                if line.startswith("level:"):
                    info["battery"] = line.split(":")[1].strip() + "%"
                elif line.startswith("status:"):
                    code = line.split(":")[1].strip()
                    info["charging"] = code == "2" or code == "5"
        self._device_info = info
        return info

    # ── App Control ──────────────────────────────────────────────────────

    def open_app(self, package_or_name: str) -> Tuple[bool, str]:
        """Open an app by package name or common name."""
        # Map common names to packages
        APP_MAP = {
            "whatsapp": "com.whatsapp",
            "youtube": "com.google.android.youtube",
            "chrome": "com.android.chrome",
            "camera": "com.android.camera2",
            "gallery": "com.google.android.apps.photos",
            "settings": "com.android.settings",
            "maps": "com.google.android.apps.maps",
            "calculator": "com.google.android.calculator",
            "clock": "com.google.android.deskclock",
            "phone": "com.google.android.dialer",
            "contacts": "com.google.android.contacts",
            "messages": "com.google.android.apps.messaging",
            "gmail": "com.google.android.gm",
            "play store": "com.android.vending",
            "spotify": "com.spotify.music",
            "instagram": "com.instagram.android",
            "facebook": "com.facebook.katana",
            "twitter": "com.twitter.android",
            "telegram": "com.telegram.messenger",
            "tiktok": "com.zhiliaoapp.musically",
            "netflix": "com.netflix.mediaclient",
            "files": "com.google.android.documentsui",
        }
        pkg = APP_MAP.get(package_or_name.lower().strip(), package_or_name)

        # Pre-check if package exists
        ok_check, packages = self.shell(f"pm list packages {pkg}")
        if ok_check and pkg not in packages:
            return False, f"App '{package_or_name}' ({pkg}) not installed on device."

        # Try monkey launcher first (most reliable)
        ok, msg = self.shell(
            f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
        )
        if ok and "no activities found" not in msg.lower():
            return True, f"Opened {package_or_name} ({pkg})"
        # Fallback: am start with main intent
        ok, msg = self.shell(
            f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER {pkg}"
        )
        if not ok and "Activity not started" in msg:
            return False, f"Failed to start {package_or_name}: activity not found. App might be restricted or have no launcher."
            
        return ok, msg

    def close_app(self, package_or_name: str) -> Tuple[bool, str]:
        """Force stop an app."""
        APP_MAP = {
            "whatsapp": "com.whatsapp",
            "youtube": "com.google.android.youtube",
            "chrome": "com.android.chrome",
            "settings": "com.android.settings",
        }
        pkg = APP_MAP.get(package_or_name.lower().strip(), package_or_name)
        return self.shell(f"am force-stop {pkg}")

    def get_current_app(self) -> str:
        """Get the currently focused app package and activity."""
        ok, output = self.shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        if ok:
            match = re.search(r'(\S+)/(\S+)\}', output)
            if match:
                return match.group(1)
        return "unknown"

    # ── Input Automation ─────────────────────────────────────────────────

    def tap(self, x: int, y: int) -> Tuple[bool, str]:
        """Tap at screen coordinates."""
        return self.shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> Tuple[bool, str]:
        """Swipe gesture."""
        return self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def type_text(self, text: str) -> Tuple[bool, str]:
        """Type text into the focused input field."""
        # Escape special characters for shell
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace("&", "\\&")
        return self.shell(f"input text '{escaped}'")

    def press_key(self, keycode: str) -> Tuple[bool, str]:
        """Press a key by keycode name (e.g. KEYCODE_HOME, KEYCODE_BACK)."""
        KEY_MAP = {
            "home": "KEYCODE_HOME",
            "back": "KEYCODE_BACK",
            "enter": "KEYCODE_ENTER",
            "volume_up": "KEYCODE_VOLUME_UP",
            "volume_down": "KEYCODE_VOLUME_DOWN",
            "power": "KEYCODE_POWER",
            "tab": "KEYCODE_TAB",
            "delete": "KEYCODE_DEL",
            "menu": "KEYCODE_MENU",
            "recent": "KEYCODE_APP_SWITCH",
        }
        code = KEY_MAP.get(keycode.lower().strip(), keycode)
        return self.shell(f"input keyevent {code}")

    def scroll_down(self) -> Tuple[bool, str]:
        """Scroll down on screen."""
        return self.swipe(540, 1500, 540, 500, 400)

    def scroll_up(self) -> Tuple[bool, str]:
        """Scroll up on screen."""
        return self.swipe(540, 500, 540, 1500, 400)

    # ── Screen Understanding ─────────────────────────────────────────────

    def dump_screen_xml(self) -> Optional[str]:
        """Dump the current screen's UI hierarchy as XML."""
        ok, _ = self.shell("uiautomator dump /sdcard/ui_dump.xml", timeout=10)
        if not ok:
            return None
        ok, xml_content = self.shell("cat /sdcard/ui_dump.xml", timeout=10)
        if ok:
            return xml_content
        return None

    def parse_screen(self) -> List[Dict[str, Any]]:
        """Parse the screen UI hierarchy into a list of interactive elements."""
        xml_content = self.dump_screen_xml()
        if not xml_content:
            return []

        elements = []
        try:
            root = ET.fromstring(xml_content)
            for node in root.iter("node"):
                text = node.get("text", "").strip()
                desc = node.get("content-desc", "").strip()
                clickable = node.get("clickable") == "true"
                bounds_str = node.get("bounds", "")
                class_name = node.get("class", "")
                resource_id = node.get("resource-id", "")

                if not (text or desc) and not clickable:
                    continue

                # Parse bounds "[x1,y1][x2,y2]"
                bounds_match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
                if len(bounds_match) == 2:
                    x1, y1 = int(bounds_match[0][0]), int(bounds_match[0][1])
                    x2, y2 = int(bounds_match[1][0]), int(bounds_match[1][1])
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                else:
                    cx, cy = 0, 0

                elements.append({
                    "text": text,
                    "description": desc,
                    "clickable": clickable,
                    "center_x": cx,
                    "center_y": cy,
                    "class": class_name.split(".")[-1] if class_name else "",
                    "resource_id": resource_id.split("/")[-1] if resource_id else "",
                })
        except ET.ParseError as e:
            logger.error("[ADB] XML parse error: %s", e)
        return elements

    def find_element(self, text: str = "", description: str = "",
                     resource_id: str = "") -> Optional[Dict[str, Any]]:
        """Find a specific UI element on screen by text, description, or resource ID."""
        elements = self.parse_screen()
        for el in elements:
            if text and text.lower() in el["text"].lower():
                return el
            if description and description.lower() in el["description"].lower():
                return el
            if resource_id and resource_id.lower() in el["resource_id"].lower():
                return el
        return None

    def click_element(self, text: str = "", description: str = "",
                      resource_id: str = "") -> Tuple[bool, str]:
        """Find and click a UI element."""
        el = self.find_element(text=text, description=description, resource_id=resource_id)
        if not el:
            target = text or description or resource_id
            return False, f"Element '{target}' not found on screen"
        return self.tap(el["center_x"], el["center_y"])

    # ── System Settings ──────────────────────────────────────────────────

    def set_brightness(self, level: int) -> Tuple[bool, str]:
        """Set screen brightness (0-255)."""
        level = max(0, min(255, level))
        self.shell("settings put system screen_brightness_mode 0")
        return self.shell(f"settings put system screen_brightness {level}")

    def set_wifi(self, enabled: bool) -> Tuple[bool, str]:
        """Enable or disable Wi-Fi."""
        return self.shell(f"svc wifi {'enable' if enabled else 'disable'}")

    def set_bluetooth(self, enabled: bool) -> Tuple[bool, str]:
        """Enable or disable Bluetooth."""
        action = "enable" if enabled else "disable"
        return self.shell(f"settings put global bluetooth_on {'1' if enabled else '0'}")

    def set_volume(self, stream: str = "music", level: int = 7) -> Tuple[bool, str]:
        """Set volume level. Streams: music, ring, alarm, notification."""
        stream_map = {"music": 3, "ring": 2, "alarm": 4, "notification": 5}
        stream_idx = stream_map.get(stream.lower(), 3)
        return self.shell(f"media volume --set {level} --stream {stream_idx}")

    def take_screenshot(self, save_path: str = "") -> Tuple[bool, str]:
        """Take a screenshot and optionally pull it to local machine."""
        remote = "/sdcard/screenshot.png"
        ok, msg = self.shell(f"screencap -p {remote}")
        if not ok:
            return False, msg
        if save_path:
            ok2, msg2 = self.run("pull", remote, save_path)
            return ok2, msg2
        return True, f"Screenshot saved to {remote}"

    # ── Status Summary ───────────────────────────────────────────────────

    def status_summary(self) -> Dict[str, Any]:
        """Return a JSON-ready summary of device state."""
        if not self.available:
            return {"connected": False, "error": "ADB not installed"}
        devices = self.get_devices()
        if not devices:
            return {"connected": False, "error": "No devices connected"}

        info = self.get_device_info()
        current_app = self.get_current_app()
        return {
            "connected": True,
            "device": f"{info.get('brand', '').title()} {info.get('model', '')}",
            "android": info.get("android_version", "?"),
            "battery": info.get("battery", "?"),
            "charging": info.get("charging", False),
            "current_app": current_app,
            "serial": self.device_serial or devices[0].get("serial", "?"),
        }
