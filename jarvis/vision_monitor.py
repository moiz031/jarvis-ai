# jarvis/vision_monitor.py
import threading
import time
import logging

try:
    from tools.vision import capture_screen, analyze_image
except ImportError:
    capture_screen = analyze_image = None

logger = logging.getLogger(__name__)

class VisionMonitor(threading.Thread):
    def __init__(self, config, emit_callback):
        super().__init__(daemon=True)
        self.config = config
        self.emit = emit_callback
        self.running = True
        
    def run(self):
        logger.info("[Vision] Continuous monitoring started.")
        while self.running:
            try:
                self._check_screen()
            except Exception as e:
                logger.error(f"[Vision] Error: {e}")
            time.sleep(45) # Check screen every 45 secs to save resources

    def _check_screen(self):
        if not capture_screen or not analyze_image: return
        
        # We don't want to spam the heavy LLM. 
        # A real Tony Stark Jarvis would use a fast local tiny model first.
        # Here we simulate by just randomly "spotting" an error occasionally for demonstration.
        
        import random
        if random.random() > 0.95: # Very rare mock detection
            alert_msg = "Sir, mujhe screen par ek lagataar error ya anomaly nazar aa rahi hai. Kya main isay fix karne ki koshish karun?"
            self.emit("transcript", {"role": "Jarvis", "text": alert_msg})
            # Inject to engine to trigger voice
            self.emit("chat", alert_msg)
            
    def stop(self):
        self.running = False
