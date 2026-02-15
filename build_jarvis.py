
import PyInstaller.__main__
import os
import shutil

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "jarvis_icon.ico")  # We will check if this exists

# Check if icon exists, otherwise don't use it
icon_args = []
if os.path.exists(ICON_PATH):
    icon_args = ["--icon", ICON_PATH]

print("Building Jarvis AI Desktop App...")

PyInstaller.__main__.run([
    "JARVIS.py",
    "--name=JarvisAI",
    # "--onefile", # Removed for better reliability with heavy libraries
    "--noconsole",
    "--clean",
    # Include the 'jarvis' package (source -> dest)
    "--add-data=jarvis;jarvis",
    # Include the UI file to root and jarvis/ folder to be safe
    "--add-data=jarvis_ui.html;.", 
    "--add-data=jarvis/jarvis_ui_fixed.html;jarvis",
    # Include static assets
    "--add-data=jarvis/static;jarvis/static", 
    "--hidden-import=engineio.async_drivers.threading",
    "--collect-all=jarvis",
    "--exclude-module=webrtcvad",
] + icon_args)

print("Build Complete!")
print("Executable is in 'dist/JarvisAI.exe'")
