@echo off
echo ===================================================
echo   JARVIS NEURAL CORE v7.0 - LOW RAM WEB MODE
echo ===================================================
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
set "HF_HOME=F:\JarvisCache\hf"
set "TRANSFORMERS_CACHE=F:\JarvisCache\hf\transformers"
set "TMP=F:\JarvisCache\tmp"
set "TEMP=F:\JarvisCache\tmp"
if not exist "F:\JarvisCache\hf\transformers" mkdir "F:\JarvisCache\hf\transformers"
if not exist "F:\JarvisCache\tmp" mkdir "F:\JarvisCache\tmp"
echo Starting JARVIS Engine (optimized)...
echo Professional UI available at: http://localhost:8080
echo.
python main.py
pause
