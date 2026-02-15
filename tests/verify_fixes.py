import sys
import os
import time

# Add parent directory to path (Project Root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_imports():
    print("\n--- Testing Imports ---")
    try:
        import cv2
        print(f"[OK] opencv-python found: {cv2.__version__}")
    except ImportError:
        print("[WARN] opencv-python NOT found (expected if optional in your setup)")

    try:
        import fitz
        print(f"[OK] PyMuPDF found: {fitz.VersionBind}")
    except ImportError:
        print("[WARN] PyMuPDF NOT found (expected if optional in your setup)")

    try:
        import sounddevice
        print("[OK] sounddevice found")
    except ImportError:
        print("[ERROR] sounddevice NOT found (required)")

    try:
        import faster_whisper
        print("[OK] faster-whisper found")
    except ImportError:
        print("[WARN] faster-whisper NOT found (voice STT will be disabled)")


def test_llm_streaming():
    print("\n--- Testing LLM Streaming ---")
    try:
        from jarvis.config import Config
        from jarvis.llm_ollama import OllamaLLM

        config = Config()
        llm = OllamaLLM(config)

        print(f"Targeting Ollama at: {config.OLLAMA_HOST}")
        print(f"Configured model: {config.OLLAMA_MODEL}")
        available = llm._list_local_models()
        if available:
            print(f"Installed models: {', '.join(available)}")
        else:
            print("[WARN] Could not read installed local models from Ollama.")

        print("Sending prompt: 'Say hello in one word'...")
        start_time = time.time()
        full_text = ""
        for chunk in llm.generate_stream("Say hello in one word"):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            full_text += chunk

        elapsed = time.time() - start_time
        if full_text.strip():
            print(f"\n\n[OK] Stream finished in {elapsed:.2f}s")
            print(f"Received: {full_text}")
        else:
            print(f"\n\n[WARN] Empty LLM response in {elapsed:.2f}s")

    except Exception as e:
        print(f"\n[ERROR] LLM Streaming Failed: {e}")


if __name__ == "__main__":
    test_imports()

    # verify config first
    try:
        from jarvis.config import Config
        _ = Config()
    except ImportError as e:
        print(f"[ERROR] Config Import Failed: {e}")

    test_llm_streaming()
