# hotkey_listener.py – Global Hotkey Handler

import keyboard
import threading
import time
from config import Config

class HotkeyListener:
    """
    Listens for global hotkeys (e.g., Ctrl+Shift+K) to trigger emergency stop
    or other system-wide commands.
    """
    def __init__(self, core_engine):
        self.config = Config()
        self.core = core_engine
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        """Starts the hotkey listener in a background thread."""
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        print(f"[Hotkey] Listening for {self.config.KILL_HOTKEY}...")

    def _listen_loop(self):
        """Blocking loop to check for hotkeys."""
        # registier hotkey
        try:
            keyboard.add_hotkey(self.config.KILL_HOTKEY, self._on_kill_switch)
            
            # Keep thread alive
            while not self.stop_event.is_set():
                time.sleep(0.5)
        except Exception as e:
            print(f"[Hotkey] Error: {e}")

    def _on_kill_switch(self):
        """Callback when kill switch is pressed."""
        print("\n[Hotkey] [KILL] KILL SWITCH ACTIVATED")
        # Stop TTS
        if hasattr(self.core, 'tts'):
            self.core.tts.active = False
            self.core.tts.audio_queue.queue.clear()
            # If playing via sounddevice or subprocess, we might need a harder stop.
            # But clearing queue is a good start.
        
        # Stop STT
        if hasattr(self.core, 'stt'):
            self.core.stt.active = False
        
        # Reset Core State
        self.core.is_processing = False
        print("[Hotkey] System Reset.")

    def stop(self):
        self.stop_event.set()
        keyboard.remove_hotkey(self.config.KILL_HOTKEY)
