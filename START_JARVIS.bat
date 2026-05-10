@echo off
title JARVIS AI - Low RAM Startup
cd /d "%~dp0"

echo ============================================
echo   JARVIS AI - LOW RAM MODE STARTUP
echo ============================================

set "PYTHONUTF8=1"
set "JARVIS_PROFILE=low_ram"
set "JARVIS_LOW_RAM_MODE=true"
set "MAX_AGENT_WORKERS=1"
set "WHISPER_MODEL=tiny"
set "STT_BLOCK_SIZE=8192"
set "STT_QUEUE_SIZE=256"
set "STT_WAKE_INTERVAL=2.0"
set "STT_WAKE_ENERGY_THRESHOLD=0.02"
set "STT_BEAM_SIZE=1"
set "STT_BEST_OF=1"
set "STT_WAKE_ALIASES=jarvis,jarvis let's start"
set "TTS_PREFER_CLOUD=true"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

set "HF_HOME=%~dp0cache\hf"
set "TRANSFORMERS_CACHE=%~dp0cache\hf\transformers"
set "XDG_CACHE_HOME=%~dp0cache\xdg"
set "PIP_CACHE_DIR=%~dp0cache\pip"
set "TMP=%~dp0cache\tmp"
set "TEMP=%~dp0cache\tmp"

if not exist "%~dp0cache\hf" mkdir "%~dp0cache\hf"
if not exist "%~dp0cache\hf\transformers" mkdir "%~dp0cache\hf\transformers"
if not exist "%~dp0cache\xdg" mkdir "%~dp0cache\xdg"
if not exist "%~dp0cache\pip" mkdir "%~dp0cache\pip"
if not exist "%~dp0cache\tmp" mkdir "%~dp0cache\tmp"

ollama list >nul 2>&1
if errorlevel 1 (
  echo [WARNING] Ollama is not running or not installed.
  echo JARVIS might start in fallback mode.
)

echo Starting JARVIS in browser mode...
"%~dp0.venv\Scripts\python.exe" JARVIS.py --browser
pause
