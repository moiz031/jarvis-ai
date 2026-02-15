import sys
import os
from pathlib import Path

# Add project root needed for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.system_ops import get_system_status
from tools.apps import open_app

def validate_tools():
    print("--- JARVIS TOOL VALIDATION ---")
    
    # 1. Test System Status
    print("\n[1] Testing system_ops.get_system_status()...")
    try:
        status = get_system_status()
        print(f"Result: {status}")
        if status.get("cpu_percent") is not None:
            print("OK: System status retrieved.")
        else:
            print("FAIL: Status response incomplete.")
    except Exception as e:
        print(f"ERROR: {e}")

    # 2. Test App Launch (Non-destructive test - trying to 'start notepad')
    print("\n[2] Testing apps.open_app('notepad')...")
    try:
        res = open_app("notepad")
        print(f"Result: {res}")
        if "Opened" in res:
            print ("OK: App launch triggered.")
        else:
            print(f"FAIL: {res}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n--- VALIDATION COMPLETE ---")

if __name__ == "__main__":
    validate_tools()
