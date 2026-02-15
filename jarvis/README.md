# Jarvis-like Voice Assistant for Windows 10

A local-first, bilingual (Urdu + English) voice assistant that runs on your laptop. It features voice activation, continuous listening, valid command execution, and proactive agency.

## Features
- **Hands-free**: Activates with "Jarvis, let's start". Stops with "Jarvis stop".
- **Bilingual**: Understands and speaks mixed Urdu/English.
- **Local Intelligence**: Uses Whisper (STT) and Ollama (LLM) locally.
- **Enhanced Mode**: Optional Cloud Fallback to OpenAI/OpenRouter and ElevenLabs if keys are provided.
- **Tools**: Open apps, manage files, run safe commands, browse the web.
- **Safety**: Confirms risky actions. No passwords stored.
- **Super Mode**: One-time onboarding, multi-channel gateway, plugin runtime, policy guard, background worker jobs.
- **Low-RAM Aware**: Auto profile selection for ~8GB systems with reduced worker and model defaults.

## Prerequisites
- **Windows 10/11**
- **Python 3.10+**
- **RAM**: 8GB+ recommended
- **Ollama**: Installed and running ([Download Ollama](https://ollama.com))
- **Piper TTS**: (Optional for local Urdu voice, but code handles fallback)

## Setup Guide

### 1. Install Dependencies
Open a terminal in this folder and run:
```powershell
pip install -r jarvis/requirements-enhanced.txt
playwright install chromium
```

### 2. Setup Ollama
Ensure Ollama is running, then pull the required models:
```powershell
ollama pull qwen2.5:7b-instruct
ollama pull llama3.1:8b-instruct
```

### 3. Setup Local TTS (Piper)
Download the Urdu model (optional but recommended for local mode):
1. Download `ur_urdu-medium.onnx` and `ur_urdu-medium.onnx.json` from [Piper Voices](https://github.com/rhasspy/piper/releases).
2. Place them in a folder logic `models/` inside `jarvis/`.
3. Rename them to `ur_urdu.piper` and `ur_urdu.piper.json` (or strictly match config).
   *Note: The code defaults to looking for `models/ur_urdu.piper`. You may need to adjust `tts_local.py` or just skip this if using ElevenLabs.*

### 4. Cloud Configuration (Optional)
The system is pre-configured with keys in `.env`.
To change them, edit the `.env` file directly.

## Running the Assistant
1. **Start the Assistant**:
   ```powershell
   python jarvis/main.py
   ```
2. **Wake Word**: Say **"Jarvis, let's start"**.
3. **Stop**: Say **"Jarvis stop"** or press `Ctrl+Shift+K` to kill the process.

### Desktop vs Browser UI
- **Desktop App (native window)**:
  ```powershell
  python JARVIS.py
  ```
- **Browser UI (localhost)**:
  ```powershell
  python JARVIS.py --browser
  ```
- **Quick launchers**:
  - `Launch_JARVIS.bat` (desktop app)
  - `Launch_JARVIS_Browser.bat` (browser UI)

### Android / Mobile Access
1. Start Jarvis on your Windows machine.
2. Make sure the phone is on the same Wi‑Fi network.
3. Open `http://<PC_IP>:8080` in the mobile browser.
4. Use “Add to Home Screen” to install the PWA.

### Super Mode (One-Time Access)
1. Start Jarvis server (`python jarvis/main.py`).
2. Run onboarding once:
   ```powershell
   python jarvis/super_cli.py onboard --profile power --users local-admin --channels telegram,discord,email
   ```
3. Dispatch super task:
   ```powershell
   python jarvis/super_cli.py task "system status check"
   ```
4. Check super state:
   ```powershell
   python jarvis/super_cli.py status
   ```

## Demo Commands (Urdu/English)

| Command | Action |
|qt|---|
| "Jarvis, open Notepad" | Opens Notepad app |
| "Jarvis, mera downloads folder check kro" | Lists files in Downloads |
| "Check internet speed using browser" | Googles speed test |
| "Jarvis, create a file named test.txt on Desktop with content Hello" | Creates file (asks confirm) |
| "Jarvis, what is the time?" | Telling time |
| "Jarvis, screen wazeh karo" (Clear screen) | Runs `cls` equivalent if mapped |
| "Jarvis, stop" | Goes to idle mode |
| "Jarvis, search for cricket score" | Browses google for score |
| "Jarvis, close Notepad" | Closes app (asks confirm) |
| "Shutdown" | Exits the assistant |

## Troubleshooting
- **Microphone**: If not detected, check Windows Sound Settings > Input.
- **Ollama Error**: Ensure `ollama serve` is running in another terminal.
- **Audio Output**: If no sound, check if PowerShell is blocked or volume is low.
- **Permissions**: Run CMD/Powershell as Administrator if file operations fail (though not recommended for safety).

## Performance for 8GB RAM
- Use `qwen2.5:7b-quantized` or smaller models if system lags.
- `faster-whisper` 'small' model is selected by default for speed.
