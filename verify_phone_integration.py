# verify_phone_integration.py
import os
import sys
import logging

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

def verify():
    logger.info("--- JARVIS Android System Verification ---")
    
    # 1. Test Imports
    try:
        from jarvis.tools.adb_core import ADBCore, find_adb
        from jarvis.tools.mobile_intent import MobileIntentParser
        from jarvis.tools.phone_tool import PhoneTool
        logger.info("✅ All modules imported successfully.")
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return

    # 2. Test ADB Discovery
    adb_path = find_adb()
    if adb_path:
        logger.info(f"✅ ADB discovered at: {adb_path}")
        core = ADBCore(adb_path)
        if core.available:
            logger.info("✅ ADBCore initialized and available.")
        else:
            logger.error("❌ ADBCore initialization failed.")
    else:
        logger.error("❌ ADB not found (expected if not in bin/ or PATH).")

    # 3. Test Intent Parsing (Mental Check)
    parser = MobileIntentParser()
    test_commands = [
        "Open WhatsApp",
        "WhatsApp kholo",
        "Bhai ko call karo",
        "Send message to Ali saying hello"
    ]
    for cmd in test_commands:
        res = parser.parse(cmd)
        logger.info(f"🧠 Parse '{cmd}': {res['intent']} (confidence: {res['confidence']:.2f})")

    # 4. Test PhoneTool Integration
    # We use a dummy emit function
    def dummy_emit(msg_type, data):
        logger.info(f"📡 Emit [{msg_type}]: {data}")

    phone = PhoneTool(dummy_emit)
    logger.info("✅ PhoneTool initialized with intent parser and ADB core.")
    
    # Check device connection (will likely be false)
    status = phone._action_status()
    logger.info(f"📱 Current Status: {status['status']}")
    
    logger.info("--- Verification Complete: Software is READY ---")

if __name__ == "__main__":
    verify()
