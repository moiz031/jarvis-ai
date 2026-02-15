"""
JARVIS System Integrity Check
Verifies directory structure, key files, dependencies, and configuration.
"""
import os
import sys
import importlib.util
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_file(path, description):
    """Check if a file exists and print a status message."""
    if os.path.exists(path):
        print(f"[OK] Found {description}: {path}")
        return True
    else:
        print(f"[MISSING] {description}: {path}")
        return False

def check_module(module_name):
    """Try to import a module and return success status."""
    try:
        importlib.import_module(module_name)
        print(f"[OK] Module '{module_name}' installed")
        return True
    except Exception as e:
        print(f"[MISSING] Module '{module_name}' MISSING or error: {e}")
        return False

def main():
    """Run all system integrity checks."""
    print("--- JARVIS System Integrity Check ---")
    
    base_dir = Path(__file__).parent.parent
    jarvis_dir = base_dir / "jarvis"
    
    # 1. Directory Structure
    print("\n[Checking Directories]")
    check_file(jarvis_dir / "models", "Models Directory")
    check_file(jarvis_dir / "data", "Data Directory")
    check_file(jarvis_dir / "logs", "Logs Directory")
    check_file(jarvis_dir / "tools", "Tools Directory")
    
    # 2. Key Files
    print("\n[Checking Key Files]")
    check_file(jarvis_dir / "config.py", "Configuration")
    check_file(jarvis_dir / "agent.py", "Agent Core")
    
    if not check_file(jarvis_dir / "core_engine.py", "Core Engine"):
        check_file(jarvis_dir / "core_engine_enhanced.py", "Core Engine (Enhanced)")
        
    check_file(jarvis_dir / "llm_ollama.py", "LLM Provider")
    check_file(jarvis_dir / "stt_whisper_fixed.py", "STT Module")
    check_file(jarvis_dir / "tts_local.py", "TTS Module")
    
    # 3. Dependencies
    print("\n[Checking Dependencies]")
    required_modules = [
        "requests", "numpy", "sounddevice", "pyttsx3", "PIL", "fastapi", "uvicorn"
    ]
    optional_modules = [
        "cv2", "fitz", "faster_whisper", "pyautogui", "speech_recognition", "pyaudio"
    ]

    missing_required = []
    missing_optional = []

    print("[Required Modules]")
    for mod in required_modules:
        if not check_module(mod):
            missing_required.append(mod)

    print("\n[Optional Modules]")
    for mod in optional_modules:
        if not check_module(mod):
            missing_optional.append(mod)

    if missing_required:
        print(
            f"\n[WARNING] Required modules missing: {', '.join(missing_required)}"
        )
    else:
        print("\n[OK] All required dependencies present.")

    if missing_optional:
        print(
            f"[INFO] Optional modules missing (some features degraded): "
            f"{', '.join(missing_optional)}"
        )

    # 4. Config Check
    print("\n[Checking Config]")
    try:
        from jarvis.config import Config
        c = Config()
        print(f"[INFO] Ollama Host: {c.OLLAMA_HOST}")
        print(f"[INFO] Wake Phrase: {c.WAKE_PHRASE}")
        print("[OK] Config loaded successfully")
    except Exception as e:
        print(f"[ERROR] Config Error: {e}")

if __name__ == "__main__":
    main()
