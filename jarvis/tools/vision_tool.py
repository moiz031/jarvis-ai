# jarvis/tools/vision_tool.py - Vision AI for Screen Understanding
"""
Vision module for JARVIS. 
Uses Gemini Vision (via OpenRouter/OpenAI) to analyze device screenshots.
Enables JARVIS to "see" what's on the phone screen.
"""

import logging
import base64
import os
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    from .adb_core import ADBCore
    from ..llm_ollama import OllamaLLM
    from ..config import Config
except ImportError:
    try:
        from jarvis.tools.adb_core import ADBCore
        from jarvis.llm_ollama import OllamaLLM
        from jarvis.config import Config
    except ImportError:
        from adb_core import ADBCore
        from llm_ollama import OllamaLLM
        from config import Config

logger = logging.getLogger(__name__)

class VisionTool:
    """The 'Eyes' of JARVIS. Analyzes phone screenshots using Vision LLMs."""

    def __init__(self, adb: ADBCore, llm: OllamaLLM):
        self.adb = adb
        self.llm = llm
        self.temp_dir = Path(__file__).parent.parent / "data" / "screenshots"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_screenshot_b64(self) -> Optional[str]:
        """Capture screen via ADB and convert to base64."""
        local_path = self.temp_dir / f"screen_{int(time.time())}.png"
        ok, msg = self.adb.take_screenshot(str(local_path))
        if not ok:
            logger.error(f"[Vision] Screenshot failed: {msg}")
            return None
        
        try:
            with open(local_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("utf-8")
                # Optional: Delete temp file after encoding to save space
                # os.remove(local_path) 
                return encoded
        except Exception as e:
            logger.error(f"[Vision] Encoding error: {e}")
            return None

    def analyze_screen(self, query: str = "Describe the current screen state in detail.") -> str:
        """Analyze the current screen context with a custom query."""
        img_b64 = self._get_screenshot_b64()
        if not img_b64:
            return "Error: Could not capture screen for vision analysis."

        prompt = (
            "You are looking at an Android phone screen. "
            f"Question: {query}\n"
            "Keep the answer concise and helpful for a voice assistant."
        )
        
        try:
            # We use the existing llm.generate which supports images
            response = self.llm.generate(prompt, images=[img_b64])
            return response
        except Exception as e:
            logger.error(f"[Vision] LLM analysis error: {e}")
            return f"Technical error during vision analysis: {e}"

    def find_coordinates(self, target_description: str) -> Optional[Dict[str, int]]:
        """
        Ask the Vision AI to find the center (x, y) coordinates of an element.
        target_description: e.g. 'the WhatsApp send button'
        """
        img_b64 = self._get_screenshot_b64()
        if not img_b64:
            return None

        prompt = (
            "You are an expert at identifying UI elements on Android screens. "
            f"Find the exact center (x, y) coordinates of: {target_description}. "
            "The screen resolution is usually 1080x2400 (if you are unsure, estimate). "
            "Return ONLY a JSON object in this format: {\"x\": integer, \"y\": integer}. "
            "Do not include any other text."
        )

        try:
            response = self.llm.generate(prompt, images=[img_b64])
            import json
            import re
            # Extract JSON from response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                coords = json.loads(match.group(0))
                return {"x": int(coords.get("x", 0)), "y": int(coords.get("y", 0))}
        except Exception as e:
            logger.error(f"[Vision] Coordinate detection error: {e}")
        
        return None

    def identify_app(self) -> str:
        """Use Vision to identify the current app if ADB dumpsys fails."""
        return self.analyze_screen("Which app is currently open?")

    def get_screen_summary(self) -> str:
        """Provide a comprehensive summary of the screen state, intent, and layout."""
        prompt = (
            "Analyze this Android screen comprehensively. "
            "1. What is the primary purpose of this screen? "
            "2. List the key clickable elements and their functions. "
            "3. Describe any notifications or status icons visible. "
            "4. Suggest the most likely next action for a user based on this context. "
            "Respond in a structured yet concise manner suitable for a voice assistant's internal reasoning."
        )
        return self.analyze_screen(prompt)

    def detect_text_and_symbols(self) -> List[Dict[str, Any]]:
        """
        Perform OCR-like detection of text and symbols on the screen.
        Returns a list of detected items with their descriptions and estimated coordinates.
        """
        prompt = (
            "Extract all visible text and recognizable symbols (like icons for Home, Search, Back, etc.) "
            "from this Android screen. For each item, provide: "
            "1. The text content or symbol description. "
            "2. Its approximate (x, y) center coordinates. "
            "Return the result as a JSON list: [{\"text\": \"...\", \"x\": int, \"y\": int}, ...]. "
            "Do not include any other text in your response."
        )
        
        response = self.analyze_screen(prompt)
        import json
        import re
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.error(f"[Vision] Text/Symbol detection error: {e}")
        
        return []

    def get_visual_context(self) -> Dict[str, Any]:
        """Get a full visual context object for the AI Brain."""
        summary = self.get_screen_summary()
        elements = self.detect_text_and_symbols()
        return {
            "summary": summary,
            "visual_elements": elements,
            "timestamp": time.time()
        }
