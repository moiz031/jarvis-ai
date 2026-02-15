# tts_local.py – Unified TTS Provider (Piper + ElevenLabs + pyttsx3)

import os
from pathlib import Path
import subprocess
import threading
import queue
import time
import requests
import pyttsx3
import json
import logging

logger = logging.getLogger(__name__)

class TextToSpeech:
    """Unified TTS wrapper.
    Primary strategy: Piper (Local, High Quality).
    Secondary strategy: ElevenLabs (Cloud, Best Quality).
    Fallback strategy: pyttsx3 (System, Low Quality).
    """

    def __init__(self, config, output_queue=None):
        self.config = config
        self.output_queue = output_queue
        
        # Paths
        self.base_dir = Path(__file__).resolve().parent
        self.models_dir = self.base_dir / "models"
        self.models_dir.mkdir(exist_ok=True)
        self.piper_exe = self._find_piper_exe()
        
        # Configuration
        self.piper_voice = "en_US-lessac-medium" # Default
        # Map common names to piper models
        self.voice_map = {
            "ur_urdu": "ur_PK-dune-medium", # Assuming this exists or we map to it
            "en_us": "en_US-lessac-medium"
        }
        
        # State
        self.audio_queue = queue.Queue()
        self.muted = False
        self.active = True
        self.current_playback = None  # Track current audio playback for stopping
        
        # Cloud
        self.elevenlabs_key = getattr(config, 'ELEVENLABS_API_KEY', None)
        self.voice_id = getattr(config, 'ELEVENLABS_VOICE_ID', "JBFqnCBsd6RMkjVDRZzb")
        
        # Worker
        self.play_thread = threading.Thread(target=self._play_worker, daemon=True)
        self.play_thread.start()

    def _find_piper_exe(self):
        """Check if piper is installed or in local directory."""
        # 1. Check PATH
        import shutil
        if shutil.which("piper"):
             return "piper"
        
        # 2. Check local binary (if user placed it manually)
        local_bin = self.base_dir / "bin" / "piper.exe"
        if local_bin.exists():
            return str(local_bin)
            
        print("[TTS] [WARNING] Piper executable not found. TTS will fallback to pyttsx3 until Piper is installed.")
        return None

    def _ensure_model(self, voice_key):
        """Checks if model exists, downloads if not."""
        if not self.piper_exe: return None
        
        # Map voice keys to specific model names and download paths
        model_info = {
            "en_us": {
                "name": "en_US-lessac-medium",
                "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
                "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
            },
            "ur_urdu": {
                "name": "ur_PK-dune-medium",
                "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/dune/medium/ur_PK-dune-medium.onnx",
                "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/dune/medium/ur_PK-dune-medium.onnx.json"
            }
        }
        
        info = model_info.get(voice_key, model_info["en_us"])
        model_name = info["name"]
        
        onnx_path = self.models_dir / f"{model_name}.onnx"
        json_path = self.models_dir / f"{model_name}.onnx.json"
        
        if onnx_path.exists() and json_path.exists():
            return str(onnx_path)
            
        print(f"[TTS] Downloading Piper model: {model_name}...")
        try:
            # Download ONNX
            print(f"[TTS] Fetching {info['onnx']}...")
            r = requests.get(info['onnx'], stream=True)
            r.raise_for_status()
            with open(onnx_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Download JSON
            print(f"[TTS] Fetching {info['json']}...")
            r = requests.get(info['json'], stream=True)
            r.raise_for_status()
            with open(json_path, 'wb') as f:
                f.write(r.content)
                
            print(f"[TTS] Model downloaded successfully to {self.models_dir}")
            return str(onnx_path)
            
        except Exception as e:
            print(f"[TTS] [ERROR] Model download failed: {e}")
            # Cleanup partial downloads
            if onnx_path.exists(): onnx_path.unlink()
            if json_path.exists(): json_path.unlink()
            return None

    def _synthesize_piper(self, text: str):
        """Synthesize using Piper."""
        model_path = self._ensure_model(self.config.TTS_VOICE)
        if not model_path:
             raise FileNotFoundError("Piper model not found")
             
        out_path = Path("temp_piper.wav")
        # Command: echo "text" | piper --model ... --output_file ...
        cmd = f'echo "{text}" | "{self.piper_exe}" --model "{model_path}" --output_file "{out_path}"'
        
        # PowerShell echo handling is weird, better to pass via stdin in python
        try:
             process = subprocess.Popen([self.piper_exe, "--model", model_path, "--output_file", str(out_path)], 
                                        stdin=subprocess.PIPE, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE)
             stdout, stderr = process.communicate(input=text.encode('utf-8'))
             
             if process.returncode != 0:
                 raise Exception(f"Piper error: {stderr.decode()}")
                 
             return str(out_path)
        except Exception as e:
            raise e

    def _synthesize_elevenlabs(self, text: str) -> str:
        """Call ElevenLabs API."""
        if not self.elevenlabs_key:
            raise ValueError("No API Key")
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2", 
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        out_path = Path("temp_eleven.mp3")
        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return str(out_path)

    def _synthesize_pyttsx3(self, text: str):
        """Fallback System TTS."""
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.save_to_file(text, 'temp_pyttsx3.wav')
        engine.runAndWait()
        return 'temp_pyttsx3.wav'

    def _play_worker(self):
        while True:
             try:
                if not self.active:
                    time.sleep(0.5)
                    continue

                text = self.audio_queue.get()
                if self.muted: continue

                wav_path = None
                
                # 1. Try Piper
                try:
                    wav_path = self._synthesize_piper(text)
                except Exception as e:
                    pass # Piper failed/missing, try next
                
                # 2. Try ElevenLabs (if Piper failed and Key exists)
                if not wav_path and self.elevenlabs_key:
                    try:
                        wav_path = self._synthesize_elevenlabs(text)
                    except Exception as e:
                        pass 

                # 3. Fallback pyttsx3
                if not wav_path:
                    try:
                        wav_path = self._synthesize_pyttsx3(text)
                    except:
                        pass
                
                # Playback
                if wav_path and os.path.exists(wav_path):
                     self._play_audio(wav_path)
                     try: os.remove(wav_path)
                     except: pass
                     
             except Exception as e:
                 print(f"[TTS] Error: {e}")

    def _play_audio(self, path):
        # Use simple playback
        try:
            import soundfile as sf
            import sounddevice as sd
            data, fs = sf.read(path)
            self.current_playback = sd.play(data, fs)  # Store reference for stopping
            sd.wait()
            self.current_playback = None
        except ImportError:
             # Fallback to powershell player if libraries missing
             subprocess.run(["powershell", "-c", f"(New-Object Media.SoundPlayer '{path}').PlaySync();"], check=False)

    def speak(self, text):
        self.audio_queue.put(text)

    def stop(self):
        """Interrupts current speech and clears the queue."""
        logger.info("[TTS] Stop requested. Clearing queue and stopping audio.")
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Stop sounddevice playback
        try:
            import sounddevice as sd
            sd.stop()
        except:
            pass
        
        # We might also need to kill current subprocess if Piper is running
        # But for now, sd.stop() should handle physical audio output if using sounddevice.
