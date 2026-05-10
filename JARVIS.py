
"""
JARVIS AI - Main Desktop Entry Point
This script launches the JARVIS core and opens the GUI in a native desktop window
or the default browser (for mobile-friendly access).
"""
import os
import sys
import time
import threading
import urllib.request
import urllib.error
import argparse
import webbrowser
import socket

try:
    from dotenv import load_dotenv as _dotenv_load
except Exception:
    _dotenv_load = None


def _load_env_file(path: str, override: bool = False) -> bool:
    if _dotenv_load is not None:
        return bool(_dotenv_load(path, override=override))
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
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

# Add project root and jarvis folder to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
jarvis_path = os.path.join(BASE_DIR, "jarvis")
if os.path.exists(jarvis_path):
    sys.path.insert(0, jarvis_path)

# Load environment configuration
# First load jarvis/.env for defaults, then override with root .env if present
_load_env_file(os.path.join(BASE_DIR, "jarvis", ".env"))
_load_env_file(os.path.join(BASE_DIR, ".env"), override=True)
PORT = int(os.getenv("PORT", "8080"))
URL = f"http://127.0.0.1:{PORT}"
APP_NAME = "JARVIS AI"

class JarvisApp:
    def __init__(self):
        self.window = None

    def start_server(self):
        """Starts the Jarvis backend server"""
        try:
            from jarvis.main import main
            main()
        except (ImportError, RuntimeError) as e:
            print(f"Server Startup Error: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"Unexpected Backend Error: {e}")
            import traceback
            traceback.print_exc()

    def check_server(self, timeout=90):
        """Wait for the server to become available"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(f"{URL}/health", timeout=1) as response:
                    if response.status == 200:
                        return True
            except (urllib.error.URLError, ConnectionRefusedError):
                time.sleep(0.5)
        return False

    def port_in_use(self):
        """Return True if the configured PORT is already bound on localhost."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", PORT)) == 0

    def run(self, mode: str):
        # 1. Reuse existing server if already running
        if self.check_server(timeout=2):
            print(f"Detected existing JARVIS server on port {PORT}. Reusing it.")
            server_thread = None
        else:
            # Guard against port conflicts
            if self.port_in_use():
                print(
                    f"Port {PORT} is already in use by another process. "
                    "Please close the other app or change PORT in .env."
                )
                return

            print(f"Starting JARVIS Core on port {PORT}...")
            server_thread = threading.Thread(target=self.start_server, daemon=True)
            server_thread.start()

            # 2. Wait for server to start
            if not self.check_server():
                print("Failed to start JARVIS server. Check logs/ for details.")
                return

        if mode == "browser":
            print("Opening JARVIS in default browser...")
            webbrowser.open(URL)
            try:
                if server_thread:
                    while server_thread.is_alive():
                        time.sleep(1)
                else:
                    while True:
                        time.sleep(1)
            except KeyboardInterrupt:
                return
            return

        try:
            import webview
        except ImportError:
            print("Error: pywebview is not installed. Run 'pip install pywebview'")
            return

        # 3. Create and start the webview window
        print("Opening JARVIS Desktop App...")
        self.window = webview.create_window(
            title=APP_NAME,
            url=URL,
            width=1400,
            height=900,
            resizable=True,
            background_color='#0a0b10'
        )
        webview.start()

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Launch Jarvis AI")
        parser.add_argument(
            "--browser",
            action="store_true",
            help="Open Jarvis in the default browser instead of desktop window.",
        )
        args = parser.parse_args()
        mode = "browser" if args.browser else "desktop"
        app = JarvisApp()
        app.run(mode)
    except Exception as e:
        import traceback
        error_msg = f"Critical Error:\n{str(e)}\n\n{traceback.format_exc()}"
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, error_msg, "Jarvis AI Error", 0x10)
        except:
            print(error_msg)
        sys.exit(1)
