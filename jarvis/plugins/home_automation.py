# jarvis/plugins/home_automation.py
import logging

logger = logging.getLogger(__name__)

# Simulated Home Automation API
class HomeAutomation:
    def __init__(self):
        self.devices = {
            "lights": {"status": "off", "brightness": 0},
            "ac": {"status": "off", "temp": 24},
            "door": {"status": "locked"}
        }

    def turn_on_lights(self):
        self.devices["lights"] = {"status": "on", "brightness": 100}
        logger.info("[IoT] Lights turned ON")
        return "Room lights has been turned on."

    def turn_off_lights(self):
        self.devices["lights"] = {"status": "off", "brightness": 0}
        logger.info("[IoT] Lights turned OFF")
        return "Room lights turned off."

    def set_temperature(self, temp: int):
        self.devices["ac"] = {"status": "on", "temp": temp}
        logger.info(f"[IoT] AC set to {temp}")
        return f"AC temperature is now set to {temp} degrees."

    def lock_doors(self):
        self.devices["door"] = {"status": "locked"}
        logger.info("[IoT] Doors locked")
        return "All doors are now locked and secured."
        
    def unlock_doors(self):
        self.devices["door"] = {"status": "unlocked"}
        logger.info("[IoT] Doors unlocked")
        return "Doors have been unlocked. Please be careful."

# Expose a singleton instance for tools
IoT = HomeAutomation()
