@echo off
title JARVIS AI LAUNCHER
set EXE_PATH=%~dp0dist\JarvisAI\JarvisAI.exe
if exist "%EXE_PATH%" (
  start "" "%EXE_PATH%"
  exit /b 0
)
echo Starting JARVIS AI (Python mode)...
python JARVIS.py
pause
