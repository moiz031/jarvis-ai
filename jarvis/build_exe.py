# jarvis/build_exe.py
import sys
sys.setrecursionlimit(5000) # Fix for RecursionError
import PyInstaller.__main__
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def build():
    print(">>> BUILDING JARVIS STANDALONE EXE...")
    
    # Define assets to bundle
    # Format: "source;dest" (Windows)
    # BASE_DIR is 'jarvis/' folder where this script lives
    project_root = BASE_DIR.parent
    
    assets = [
        f'{project_root / "data"};data',
        f'{BASE_DIR / "static"};static',
        f'{BASE_DIR / "jarvis_ui_fixed.html"};.',
        f'{BASE_DIR / ".env"};.'
    ]
    
    hidden_imports = [
        'webview',
        'flask',
        'engineio.async_drivers.threading',  # Critical for Flask-SocketIO in threaded mode
        'cv2',
        'numpy',
        'sounddevice',
        'faster_whisper',
        'PIL',
    ]

    PyInstaller.__main__.run([
        'JARVIS.py',
        '--onefile',
        '--noconsole',  # Hide terminal window
        '--name=Jarvis_Mark_VII',
        # '--icon=jarvis/static/favicon.ico',
        '--clean',
        *[f'--add-data={asset}' for asset in assets],
        *[f'--hidden-import={imp}' for imp in hidden_imports],
    ])
    
    print(">>> BUILD COMPLETE. CHECK /dist FOLDER.")

if __name__ == "__main__":
    build()
