#!/usr/bin/env python3
"""Setup wizard for Jarvis AI."""

import shutil
import subprocess
import sys
from pathlib import Path


def print_header(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print("=" * 60)


def print_step(num, text):
    print(f"\n[{num}] {text}")


def run_command(cmd, description=""):
    if description:
        print(f"  -> {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print("  OK")
            return True
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print_header("JARVIS AI - SETUP WIZARD")

    print_step(1, "Checking Python version...")
    if sys.version_info < (3, 10):
        print(f"  FAILED: Python 3.10+ required (you have {sys.version})")
        sys.exit(1)
    print(f"  OK: Python {sys.version.split()[0]} detected")

    print_step(2, "Creating .env file...")
    env_template = Path("jarvis/.env.template")
    env_file = Path("jarvis/.env")

    if not env_template.exists():
        print("  WARNING: jarvis/.env.template not found")
    elif env_file.exists():
        print("  INFO: jarvis/.env already exists, skipping")
    else:
        shutil.copy(env_template, env_file)
        print("  OK: .env created from template")
        print("  NOTE: Edit jarvis/.env and add your API keys")

    print_step(3, "Creating required directories...")
    for directory in ("jarvis/data", "jarvis/logs", "jarvis/static", "jarvis/models"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  OK: {directory}/")

    print_step(4, "Installing Python dependencies...")
    run_command(
        f"{sys.executable} -m pip install -r jarvis/requirements-enhanced.txt",
        "Installing packages",
    )

    print_step(5, "Installing Playwright browsers...")
    run_command(
        f"{sys.executable} -m playwright install chromium",
        "Installing Chromium",
    )

    print_step(6, "Checking Ollama installation...")
    result = subprocess.run("ollama --version", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  OK: Ollama installed: {result.stdout.strip()}")
    else:
        print("  WARNING: Ollama not found. Download from: https://ollama.com")

    print_step(7, "Creating startup scripts...")
    startup_bat = Path("start_jarvis.bat")
    if not startup_bat.exists():
        startup_bat.write_text(
            "@echo off\n"
            "echo Starting Jarvis AI...\n"
            "echo Make sure Ollama is running: ollama serve\n"
            "timeout /t 2 /nobreak >nul\n"
            "python JARVIS.py\n"
            "pause\n",
            encoding="utf-8",
        )
        print("  OK: Created start_jarvis.bat")

    startup_ps1 = Path("start_jarvis.ps1")
    if not startup_ps1.exists():
        startup_ps1.write_text(
            "Write-Host \"Starting Jarvis AI...\" -ForegroundColor Green\n"
            "Write-Host \"Make sure Ollama is running: ollama serve\" -ForegroundColor Yellow\n"
            "Start-Sleep -Seconds 2\n"
            "python JARVIS.py\n"
            "Read-Host \"Press Enter to exit\"\n",
            encoding="utf-8",
        )
        print("  OK: Created start_jarvis.ps1")

    print_step(8, "Verifying installation...")
    required_files = [
        "JARVIS.py",
        "jarvis/main.py",
        "jarvis/.env",
    ]
    if Path("jarvis/core_engine_enhanced.py").exists():
        required_files.append("jarvis/core_engine_enhanced.py")
    else:
        required_files.append("jarvis/core_engine.py")

    all_good = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  OK: {file_path}")
        else:
            print(f"  FAILED: {file_path} (missing)")
            all_good = False

    print_header("SETUP COMPLETE")
    print(
        "Next steps:\n"
        "1. Edit jarvis/.env with your keys\n"
        "2. Start Ollama in another terminal: ollama serve\n"
        "3. Run Jarvis: start_jarvis.bat or python jarvis/main.py\n"
        "4. Open http://localhost:8080\n"
    )

    return all_good


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
