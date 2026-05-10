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
pip install -r jarvis/requirements.txt
playwright install chromium
```

### 2. Setup Ollama
Ensure Ollama is running, then pull the required models:
```powershell
ollama pull llama3.2:1b
ollama pull qwen2.5:3b
```

### 3. Setup Local TTS (Piper)
Piper models are auto-downloaded by `tts_local.py` when first needed.
If you want to pre-download manually, place these exact filenames in `jarvis/models/`:
1. `ur_PK-dune-medium.onnx` and `ur_PK-dune-medium.onnx.json` (for Urdu voice)
2. `en_US-lessac-medium.onnx` and `en_US-lessac-medium.onnx.json` (for English fallback)

### 4. Cloud Configuration (Optional)
The system is pre-configured with placeholders in `.env`.
For production, add your API keys:
- `OPENAI_API_KEY`: OpenAI/OpenRouter API key (for cloud fallback)
- `ELEVENLABS_API_KEY`: ElevenLabs API key (for premium voice quality)
**Security Note**: Never commit API keys to git. Use environment variables in production.

## Running the Assistant

### Quick Start
1. **Start Backend**:
   ```powershell
   python jarvis/main.py
   ```
2. **Wake Word**: Say **"Jarvis, let's start"**.
3. **Stop**: Say **"Jarvis stop"** or press `Ctrl+Shift+K` to kill the process.

### Desktop App (Electron)
For the full desktop experience with UI:
```powershell
npm install
npm start
```

### Browser UI
Access via `http://localhost:8080` once backend is running.

## Build Windows Desktop App (No Console)
This produces a normal Windows app (double-clickable) with background commands hidden.

```powershell
pip install pyinstaller
python build_jarvis.py
```

Result:
- `dist/JarvisAI/JarvisAI.exe`

Optional release folder:
```powershell
python deploy_release.py
```

## Build Installer (Setup.exe)
This creates a proper Windows installer (like other software), with no console window.

```powershell
npm install
pip install pyinstaller
npm run dist
```

Output:
- `dist/Jarvis AI Setup.exe`

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
