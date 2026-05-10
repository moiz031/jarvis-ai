import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "backend"


def _pyinstaller_args():
    datas = [
        f"{BASE_DIR / 'jarvis'};jarvis",
        f"{BASE_DIR / 'jarvis' / 'jarvis_ui_fixed.html'};jarvis",
        f"{BASE_DIR / 'jarvis' / 'static'};jarvis/static",
    ]
    return [
        "-m",
        "PyInstaller",
        str(BASE_DIR / "jarvis" / "main.py"),
        "--name=JarvisBackend",
        "--onefile",
        "--noconsole",
        "--clean",
        f"--distpath={DIST_DIR}",
        *[f"--add-data={item}" for item in datas],
        "--hidden-import=engineio.async_drivers.threading",
        "--exclude-module=webrtcvad",
    ]


def build():
    print("Building Jarvis backend executable...")
    result = subprocess.run(
        [sys.executable, *_pyinstaller_args()],
        cwd=str(BASE_DIR),
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    print("Backend build complete.")
    print(f"Output: {DIST_DIR / 'JarvisBackend.exe'}")

if __name__ == "__main__":
    build()
