
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
from dotenv import load_dotenv

# Add project root and jarvis folder to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
jarvis_path = os.path.join(BASE_DIR, "jarvis")
if os.path.exists(jarvis_path):
    sys.path.insert(0, jarvis_path)

# Load environment configuration
load_dotenv(os.path.join(BASE_DIR, "jarvis", ".env"))
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

    def check_server(self, timeout=30):
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

    def run(self, mode: str):
        # 1. Start server in a background thread
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
                while server_thread.is_alive():
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
