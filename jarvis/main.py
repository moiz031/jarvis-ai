# jarvis/main.py - ENHANCED MAIN ENTRY POINT WITH LOGGING

import sys
import os
import queue
import threading
import time
from pathlib import Path

try:
    from dotenv import load_dotenv as _dotenv_load
except Exception:
    _dotenv_load = None

# Add project root to path so package imports work in source mode and packaged mode.
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from jarvis.web_server import JarvisWebServer
    from jarvis.core_engine import CoreEngine
    from jarvis.logger_config import setup_logging
    from jarvis.runtime_support import ensure_ollama_running
except ImportError:
    from web_server import JarvisWebServer
    from core_engine import CoreEngine
    from logger_config import setup_logging
    from runtime_support import ensure_ollama_running
import requests
import logging

# Setup logging FIRST
logger = setup_logging()


def _load_env_file(path: Path | None = None, override: bool = False) -> bool:
    if _dotenv_load is not None:
        return bool(_dotenv_load(dotenv_path=path, override=override))
    if path is None:
        path = Path(".env")
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and (override or key not in os.environ):
                    os.environ[key] = value
        return True
    except Exception:
        return False

def wait_for_ollama(host, retries=5, delay=2):
    """Wait for Ollama to be ready."""
    logger.info(f"[WAIT] Checking Ollama at {host}...")
    for i in range(retries):
        try:
            response = requests.get(f"{host}/api/tags", timeout=3)
            if response.status_code == 200:
                logger.info("[OK] Ollama connected!")
                return True
        except Exception as e:
            logger.debug(f"  Attempt {i+1}/{retries}: {type(e).__name__}")
        
        if i < retries - 1:
            logger.info(f"  Retrying in {delay}s...")
            time.sleep(delay)
    
    return False


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _probe_ollama_async(host: str) -> None:
    def probe():
        if not wait_for_ollama(host, retries=2, delay=1):
            logger.warning("[WARNING] OLLAMA NOT RUNNING")
            logger.warning("   Continuing startup. LLM may use fallback or limited mode.")

    threading.Thread(target=probe, daemon=True, name="jarvis-ollama-probe").start()

def main():
    """Main entry point for Jarvis."""
    logger.info("="*60)
    logger.info("JARVIS AI v7.0 - INITIALIZATION")
    logger.info("="*60)
    
    # Load environment
    logger.info("Loading environment configuration...")
    _load_env_file(Path(".env"))
    
    # Import config to trigger profile and secret initialization
    try:
        from jarvis.config import Config
    except ImportError:
        from config import Config
    cfg = Config()
    
    # Hardware checks
    import psutil
    ram = psutil.virtual_memory()
    total_ram_gb = ram.total / (1024**3)
    logger.info(f"Hardware Check: {total_ram_gb:.1f} GB RAM detected")
    
    if total_ram_gb < 8 and cfg.PROFILE_NAME == "high_quality":
        logger.warning("[PERFORMANCE] High-Quality profile selected on low-RAM system (<8GB)!")
        logger.warning("   Consider switching to 'low_ram' or 'balanced'.")

    # Check Ollama
    ollama_host = cfg.OLLAMA_HOST
    if getattr(cfg, "OLLAMA_AUTO_START", True):
        boot = ensure_ollama_running(ollama_host, auto_start=True)
        if boot.get("started"):
            logger.info("[OLLAMA] Auto-start requested. started=%s path=%s", boot.get("ok"), boot.get("path"))
        elif boot.get("reason") == "missing_exe":
            logger.warning("[OLLAMA] Binary not found. Install Ollama or set OLLAMA_AUTO_START=0.")

    if _bool_env("OLLAMA_STARTUP_BLOCKING", False):
        if not wait_for_ollama(ollama_host):
            logger.warning("[WARNING] OLLAMA NOT RUNNING")
            logger.warning("   Continuing startup. LLM may use fallback or limited mode.")
    else:
        logger.info("Ollama probe moved to background for faster startup.")
        _probe_ollama_async(ollama_host)
    
    # Create communication queues
    logger.info("Creating communication queues...")
    input_queue = queue.Queue()
    output_queue = queue.Queue()
    
    # Start core engine
    logger.info("Starting Core Engine...")
    engine = CoreEngine(input_queue, output_queue)
    engine.start()
    
    # Start web server
    logger.info("Starting Web Server...")
    app = JarvisWebServer(input_queue, output_queue)
    
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info("="*60)
    logger.info(f"[READY] JARVIS READY!")
    logger.info(f"   Web UI: http://localhost:{port}")
    logger.info(f"   Listening on: {host}:{port}")
    logger.info(f"   Press Ctrl+C to shutdown")
    logger.info("="*60)
    
    try:
        app.run(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("[STOP] Shutdown requested")
    finally:
        logger.info("Cleaning up...")
        input_queue.put({"type": "shutdown", "data": None})
        
        # Wait for engine to finish
        engine.join(timeout=3)
        
        logger.info("[OK] Jarvis shutdown complete")
        sys.exit(0)

if __name__ == "__main__":
    main()
