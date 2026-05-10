# jarvis/background_monitor.py
import threading
import time
import logging
import random

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)

class BackgroundMonitor(threading.Thread):
    def __init__(self, emit_callback):
        super().__init__(daemon=True)
        self.emit = emit_callback
        self.running = True
        self.last_battery = 100
        self.last_email_check = time.time()
        
    def run(self):
        logger.info("[Background] Monitor started.")
        while self.running:
            try:
                self._check_vitals()
                self._simulate_email_check()
            except Exception as e:
                logger.error(f"[Background] Error: {e}")
            time.sleep(30)  # Check every 30 seconds

    def _check_vitals(self):
        if not psutil: return
        try:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                is_plugged = battery.power_plugged
                
                # Proactive alert if battery drops low and not plugged
                if percent <= 20 and not is_plugged and self.last_battery > 20:
                    alert_msg = f"Boss, mere hisab se device ki battery bohat low ho gayi hai, sirf {percent} percent baqi hai. Charger laga lein."
                    self.emit("transcript", {"role": "Jarvis", "text": alert_msg})
                    # Force a TTS event out-of-band by injecting a chat-like response
                    self.emit("chat", alert_msg) # The engine will not speak this directly if not wired, so we emit transcript & invoke tts in engine
                    
                self.last_battery = percent
                
            cpu = psutil.cpu_percent(interval=1)
            if cpu > 95:
                # CPU extremely high
                if random.random() > 0.8: # Only alert sometimes to avoid spam
                    alert_msg = "Sir, system ka CPU usage intehai high ja raha hai. Main background processing thodi rokun kya?"
                    self.emit("transcript", {"role": "Jarvis", "text": alert_msg})
                    self.emit("chat", alert_msg)
        except Exception:
            pass

    def _simulate_email_check(self):
        now = time.time()
        # Simulate a random "Urgent Email" every ~5 mins for testing
        if now - self.last_email_check > 300:
            self.last_email_check = now
            if random.random() > 0.7:  # 30% chance every 5 mins
                alert_msg = "Sir, abhi abhi aik urgent email receive hui hai. Main notification screen per show kar raha hoon."
                self.emit("transcript", {"role": "Jarvis", "text": alert_msg})
                # Sending pseudo-chat to trigger speech
                self.emit("chat", alert_msg)
                
    def stop(self):
        self.running = False
