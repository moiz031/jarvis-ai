#!/usr/bin/env python3
"""Validate Jarvis dependencies, files, and runtime services."""

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"{text.center(60)}")
    print(f"\n{'=' * 60}")


def print_check(name, status, message=""):
    symbol = "[OK]" if status else "[FAILED]"
    print(f"{symbol} {name:<40} {message}")


def print_optional(name, exists):
    if exists:
        print(f"[OK] {name:<40} Optional module present")
    else:
        print(f"[INFO] {name:<39} Optional module not present")


def validate_core_imports():
    print_header("Core Dependencies")
    imports = [
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("WebSockets", "websockets"),
        ("Ollama", "ollama"),
        ("Faster-Whisper", "faster_whisper"),
        ("SoundDevice", "sounddevice"),
        ("NumPy", "numpy"),
        ("pyttsx3", "pyttsx3"),
        ("PyAutoGUI", "pyautogui"),
        ("PSUtil", "psutil"),
        ("Playwright", "playwright"),
    ]
    results = {}
    for name, module in imports:
        try:
            __import__(module)
            results[name] = True
            print_check(name, True)
        except ImportError as e:
            results[name] = False
            print_check(name, False, f"Missing: {e}")
    return results


def validate_rag_system():
    print_header("RAG System (Optional Enhancements)")
    imports = [
        ("ChromaDB", "chromadb"),
        ("Sentence Transformers", "sentence_transformers"),
        ("FAISS", "faiss"),
    ]
    results = {}
    for name, module in imports:
        try:
            __import__(module)
            results[name] = True
            print_check(name, True)
        except ImportError:
            # Optional modules should not fail overall validation.
            results[name] = True
            print(f"[INFO] {name:<39} Not installed (optional)")
    return results


def validate_integrations():
    print_header("Integrations (Gmail, Calendar, Drive)")
    imports = [
        ("Google API Client", "googleapiclient"),
        ("Google Auth", "google.auth"),
        ("Google OAuth", "google_auth_oauthlib"),
    ]
    results = {}
    for name, module in imports:
        try:
            __import__(module)
            results[name] = True
            print_check(name, True)
        except ImportError:
            results[name] = False
            print_check(name, False, "Not installed (optional)")

    creds_path = Path("jarvis/integrations/credentials.json")
    has_creds = creds_path.exists()
    if has_creds:
        print_check("Google Credentials", True, "credentials.json")
    else:
        print("[INFO] Google Credentials                      Missing (optional, required only for Google features)")
    return results


def validate_files():
    print_header("File Structure")
    required_files = [
        "jarvis/main.py",
        "jarvis/config.py",
        "jarvis/agent.py",
        "jarvis/stt_whisper_fixed.py",
        "jarvis/logger_config.py",
        "jarvis/rag_system.py",
        "jarvis/planner.py",
        "jarvis/memory/db.py",
        "jarvis/integrations/gmail_integration.py",
        "jarvis/integrations/calendar_integration.py",
        "jarvis/integrations/storage_integration.py",
        "jarvis/.env",
        "setup_jarvis.py",
    ]
    optional_files = [
        "jarvis/code_assistant.py",
        "jarvis/voice_enhancement.py",
        "jarvis/authentication.py",
    ]

    results = {}
    for filepath in required_files:
        path = Path(filepath)
        exists = path.exists()
        results[filepath] = exists
        print_check(path.name, exists, str(path.parent) if exists else "Missing")

    for filepath in optional_files:
        path = Path(filepath)
        exists = path.exists()
        print_optional(path.name, exists)

    return results


def validate_ollama():
    print_header("Ollama LLM Backend")
    import requests

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print_check("Ollama Running", True, f"Found {len(models)} models")
            for model in models[:5]:
                print(f"  [MODEL] {model.get('name', 'unknown')}")
            return True
        print_check("Ollama Running", False, f"Server returned: {response.status_code}")
        return False
    except Exception as e:
        print_check("Ollama Running", False, str(e))
        print("  [TIP] Start with: ollama serve")
        return False


def validate_audio():
    print_header("Audio System")
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]
        print_check("Audio Devices", len(input_devices) > 0, f"Found {len(input_devices)} input devices")
        if input_devices:
            default = sd.default.device[0]
            print(f"  [MIC] Default: {devices[default]['name']}")
        return len(input_devices) > 0
    except Exception as e:
        print_check("Audio System", False, str(e))
        return False


def validate_database():
    print_header("Database")
    db_path = Path("jarvis/data/memory.db")
    if not db_path.exists():
        print_check("Database File", False, "Will be created on first run")
        return True

    print_check("Database File", True, f"{db_path.stat().st_size} bytes")
    try:
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  [DB] Tables: {', '.join(tables)}")
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        print(f"  [CONFIG] Mode: {mode}")
        conn.close()
        return True
    except Exception as e:
        print_check("Database Access", False, str(e))
        return False


def main():
    print_header("JARVIS AI - System Validation")
    print("This tool checks if all dependencies and files are properly installed.\n")

    results = {
        "Core Dependencies": validate_core_imports(),
        "RAG System": validate_rag_system(),
        "Integrations": validate_integrations(),
        "Files": validate_files(),
        "Ollama": validate_ollama(),
        "Audio": validate_audio(),
        "Database": validate_database(),
    }

    print_header("Summary")
    total_checks = sum(len(v) if isinstance(v, dict) else 1 for v in results.values())
    passed_checks = sum(
        sum(v.values()) if isinstance(v, dict) else (1 if v else 0)
        for v in results.values()
    )
    print(f"\nTotal Checks: {passed_checks}/{total_checks} passed")

    if passed_checks == total_checks:
        print("\n[OK] All checks passed! Jarvis is ready to run.")
        print("\nStart Jarvis:")
        print("  - Windows: start_jarvis.bat")
        print("  - Linux/Mac: python jarvis/main.py")
        return 0

    print("\n[WARNING] Some checks failed. See above for details.")
    print("\nRecommended actions:")
    print("  1. Run: python setup_jarvis.py")
    print("  2. Install missing dependencies")
    print("  3. Start Ollama: ollama serve")
    return 1


if __name__ == "__main__":
    sys.exit(main())
