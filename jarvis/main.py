# jarvis/main.py - ENHANCED MAIN ENTRY POINT WITH LOGGING

import sys
import os
import queue
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_server import JarvisWebServer
from core_engine import CoreEngine
from logger_config import setup_logging
import requests
import logging

# Setup logging FIRST
logger = setup_logging()

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

def main():
    """Main entry point for Jarvis."""
    logger.info("="*60)
    logger.info("JARVIS AI v7.0 - INITIALIZATION")
    logger.info("="*60)
    
    # Load environment
    logger.info("Loading environment configuration...")
    load_dotenv()
    
    # Import config to trigger profile and secret initialization
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
    if not wait_for_ollama(ollama_host):
        logger.warning("[WARNING] OLLAMA NOT RUNNING")
        logger.warning("   Continuing startup. LLM may use fallback or limited mode.")
    
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
