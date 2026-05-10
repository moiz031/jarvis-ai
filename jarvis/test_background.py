import time
import logging
from background_monitor import BackgroundMonitor

logging.basicConfig(level=logging.INFO)

def mock_emit(event, data):
    print(f"\n[EVENT EMITTED] {event}: {data}")

if __name__ == "__main__":
    print("Starting Background Monitor Test...")
    monitor = BackgroundMonitor(emit_callback=mock_emit)
    
    # Simulate Battery dropping to 15% and unplugged
    monitor.last_battery = 100
    print("\n--- Simulating Low Battery ---")
    import psutil
    
    class MockBattery:
        percent = 15
        power_plugged = False
        
    original_battery = psutil.sensors_battery
    psutil.sensors_battery = lambda: MockBattery()
    
    monitor._check_vitals()
    
    # Clean up mock
    psutil.sensors_battery = original_battery
    
    # Simulate High CPU
    print("\n--- Simulating High CPU ---")
    original_cpu = psutil.cpu_percent
    psutil.cpu_percent = lambda interval: 99.0
    import random
    original_random = random.random
    random.random = lambda: 0.9  # Force trigger the > 0.8 condition
    
    monitor._check_vitals()
    
    psutil.cpu_percent = original_cpu
    random.random = original_random
    
    print("\nTest completed.")
