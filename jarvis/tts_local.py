# tts_local.py - Unified TTS Provider (Piper + ElevenLabs + pyttsx3)

import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import sys

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import requests
except Exception:
    requests = None

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

        self.base_dir = Path(__file__).resolve().parent
        self.models_dir = self.base_dir / "models"
        self.models_dir.mkdir(exist_ok=True)
        self.piper_exe = self._find_piper_exe()

        # ur_urdu is mapped to Hindi voice because official Piper Urdu voice
        # is not available in the upstream voices repository.
        self.voice_map = {
            "ur_urdu": "hi_in_pratham",
            "en_us": "en_us",
        }
        self.model_info = {
            "en_us": {
                "name": "en_US-lessac-medium",
                "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
                "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
            },
            "hi_in_pratham": {
                "name": "hi_IN-pratham-medium",
                "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
                "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json",
            },
        }
        self._failed_model_keys = set()
        self._unsupported_voice_logged = set()

        self.audio_queue = queue.Queue()
        self.muted = False
        self.active = True

        self.current_stream = None
        self._playback_lock = threading.Lock()
        self._stop_playback_event = threading.Event()

        self.elevenlabs_key = getattr(config, "ELEVENLABS_API_KEY", None)
        self.voice_id = getattr(config, "ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
        self.tts_prefer_cloud = bool(getattr(config, "TTS_PREFER_CLOUD", True))
        self.elevenlabs_ready = False
        self._elevenlabs_checked = False

        self.play_thread = threading.Thread(target=self._play_worker, daemon=True)
        self.play_thread.start()

    def _find_piper_exe(self):
        """Check if piper is installed or in local directory."""
        import shutil

        if shutil.which("piper"):
            return "piper"

        local_bin = self.base_dir / "bin" / "piper.exe"
        if local_bin.exists():
            return str(local_bin)

        logger.warning("[TTS] Piper executable not found. Falling back to pyttsx3.")
        return None

    def _validate_elevenlabs(self) -> bool:
        """Check whether ElevenLabs API key is configured and reachable."""
        if not self.elevenlabs_key:
            logger.info("[TTS] ElevenLabs disabled (API key missing). Using local voice.")
            return False
        if requests is None:
            logger.warning("[TTS] requests is unavailable, so cloud TTS is disabled.")
            return False

        try:
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": self.elevenlabs_key},
                timeout=8,
            )
            if response.status_code == 200:
                logger.info("[TTS] ElevenLabs connected successfully.")
                return True
            logger.warning(
                "[TTS] ElevenLabs key check failed (status=%s). Using local voice.",
                response.status_code,
            )
            return False
        except Exception as exc:
            logger.warning("[TTS] ElevenLabs connectivity check failed: %s", exc)
            return False

    def _ensure_elevenlabs_ready(self) -> bool:
        if self._elevenlabs_checked:
            return self.elevenlabs_ready
        self._elevenlabs_checked = True
        self.elevenlabs_ready = self._validate_elevenlabs()
        return self.elevenlabs_ready

    def describe_backend(self) -> str:
        if self.elevenlabs_ready and self.tts_prefer_cloud:
            return "ElevenLabs (cloud primary) + Piper fallback"
        if self.elevenlabs_key and self.tts_prefer_cloud:
            return "Piper/Edge (startup mode) + deferred ElevenLabs fallback"
        if self.piper_exe:
            return "Piper (local primary) + ElevenLabs/pyttsx3 fallback"
        return "Edge/pyttsx3/Windows SAPI fallback"

    def _download_file(self, url: str, path: Path):
        if requests is None:
            raise RuntimeError("requests is required to download Piper models")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)

    def _resolve_voice_key(self, voice_key: str) -> str:
        requested = (voice_key or "en_us").strip().lower()
        mapped = self.voice_map.get(requested, requested)
        if mapped not in self.model_info:
            if requested not in self._unsupported_voice_logged:
                logger.warning(
                    "[TTS] Voice '%s' unsupported for Piper. Falling back to en_us.",
                    requested,
                )
                self._unsupported_voice_logged.add(requested)
            mapped = "en_us"
        return mapped

    def _ensure_model(self, voice_key):
        """Checks if model exists, downloads if not."""
        if not self.piper_exe:
            return None

        resolved_key = self._resolve_voice_key(voice_key)
        if resolved_key in self._failed_model_keys:
            return None

        info = self.model_info[resolved_key]
        model_name = info["name"]
        onnx_path = self.models_dir / f"{model_name}.onnx"
        json_path = self.models_dir / f"{model_name}.onnx.json"

        if onnx_path.exists() and json_path.exists():
            return str(onnx_path)

        logger.info("[TTS] Downloading Piper model: %s", model_name)
        try:
            self._download_file(info["onnx"], onnx_path)
            self._download_file(info["json"], json_path)
            logger.info("[TTS] Piper model ready: %s", model_name)
            return str(onnx_path)
        except Exception as exc:
            logger.error("[TTS] Model download failed for %s: %s", model_name, exc)
            self._failed_model_keys.add(resolved_key)
            if onnx_path.exists():
                onnx_path.unlink()
            if json_path.exists():
                json_path.unlink()
            return None

    def _make_temp_file(self, suffix: str) -> str:
        fd, path = tempfile.mkstemp(prefix="jarvis_tts_", suffix=suffix)
        os.close(fd)
        return path

    def _synthesize_piper(self, text: str):
        """Synthesize using Piper."""
        model_path = self._ensure_model(getattr(self.config, "TTS_VOICE", "en_us"))
        if not model_path:
            raise FileNotFoundError("Piper model not available")

        out_path = self._make_temp_file(".wav")
        process = subprocess.Popen(
            [self.piper_exe, "--model", model_path, "--output_file", out_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            _, stderr = process.communicate(input=text.encode("utf-8"), timeout=90)
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError("Piper synthesis timed out")

        if process.returncode != 0:
            raise RuntimeError(f"Piper error: {stderr.decode(errors='ignore')}")
        return out_path

    def _synthesize_elevenlabs(self, text: str) -> str:
        """Call ElevenLabs API."""
        if not self.elevenlabs_key:
            raise ValueError("No ElevenLabs API key configured")
        if requests is None:
            raise RuntimeError("requests is required for ElevenLabs TTS")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
        out_path = self._make_temp_file(".mp3")
        response = requests.post(url, json=payload, headers=headers, timeout=60, stream=True)
        response.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    fh.write(chunk)
        return out_path

    def _synthesize_pyttsx3(self, text: str):
        """Fallback System TTS."""
        if pyttsx3 is None:
            raise RuntimeError("pyttsx3 is not installed")
        out_path = self._make_temp_file(".wav")
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        return out_path

    def _synthesize_edge_tts(self, text: str) -> str:
        """Call Edge-TTS via CLI."""
        out_path = self._make_temp_file(".mp3")
        voice = getattr(self.config, "EDGE_TTS_VOICE", "ur-PK-UzmaNeural")
        
        try:
            # First try edge-tts directly if it's in PATH
            process = subprocess.Popen(
                ["edge-tts", "--voice", voice, "--text", text, "--write-media", out_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        except FileNotFoundError:
            # Fallback to python -m edge_tts
            process = subprocess.Popen(
                [sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text, "--write-media", out_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
        try:
            _, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError("Edge-TTS synthesis timed out")

        if process.returncode != 0:
            raise RuntimeError(f"Edge-TTS failed: {stderr.decode(errors='ignore')}")

        return out_path

    def _speak_windows_sapi(self, text: str) -> bool:
        """Use built-in Windows SpeechSynthesizer when file-based TTS is unavailable."""
        if os.name != "nt":
            return False

        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$speak.Rate = 0; "
            "$speak.Speak([Console]::In.ReadToEnd())"
        )
        process = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            input=text,
            text=True,
            capture_output=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or "Windows SAPI speech failed")
        return True

    def _play_worker(self):
        while True:
            try:
                if not self.active:
                    time.sleep(0.2)
                    continue

                try:
                    text = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if self.muted:
                    continue

                text = str(text).strip()
                if not text:
                    continue

                audio_path = None
                if self.tts_prefer_cloud and self._ensure_elevenlabs_ready():
                    try:
                        audio_path = self._synthesize_elevenlabs(text)
                    except Exception as exc:
                        logger.warning("[TTS] ElevenLabs synthesis failed: %s", exc)

                if not audio_path:
                    try:
                        audio_path = self._synthesize_edge_tts(text)
                    except Exception as exc:
                        logger.warning("[TTS] Edge-TTS synthesis failed: %s", exc)

                if not audio_path:
                    try:
                        audio_path = self._synthesize_piper(text)
                    except Exception as exc:
                        logger.debug("[TTS] Piper synthesis skipped: %s", exc)

                if not audio_path and self.tts_prefer_cloud and self._ensure_elevenlabs_ready():
                    try:
                        audio_path = self._synthesize_elevenlabs(text)
                    except Exception as exc:
                        logger.warning("[TTS] ElevenLabs synthesis failed: %s", exc)

                if not audio_path:
                    try:
                        audio_path = self._synthesize_pyttsx3(text)
                    except Exception as exc:
                        logger.error("[TTS] pyttsx3 fallback failed: %s", exc)

                if not audio_path:
                    try:
                        if self._speak_windows_sapi(text):
                            continue
                    except Exception as exc:
                        logger.error("[TTS] Windows SAPI fallback failed: %s", exc)

                if audio_path and os.path.exists(audio_path):
                    self._play_audio(audio_path)
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
            except Exception as exc:
                logger.error("[TTS] Worker error: %s", exc)

    def _fallback_play(self, path: str):
        if not path.lower().endswith(".wav"):
            logger.warning(
                "[TTS] Cannot play non-WAV file without sounddevice support: %s",
                path,
            )
            return
        subprocess.run(
            [
                "powershell",
                "-c",
                f"(New-Object Media.SoundPlayer '{path}').PlaySync();",
            ],
            check=False,
        )

    def _play_audio(self, path):
        # Use explicit OutputStream instead of sd.play()/sd.wait() to avoid
        # global callback races that can trigger _CallbackContext cleanup errors.
        try:
            import sounddevice as sd
            import soundfile as sf
        except Exception:
            self._fallback_play(path)
            return

        self._stop_playback_event.clear()
        stream = None
        try:
            with sf.SoundFile(path, mode="r") as audio_file:
                stream = sd.OutputStream(
                    samplerate=audio_file.samplerate,
                    channels=audio_file.channels,
                    dtype="float32",
                    latency="high",
                    blocksize=2048,
                )
                with self._playback_lock:
                    self.current_stream = stream
                stream.start()

                while not self._stop_playback_event.is_set() and self.active:
                    chunk = audio_file.read(frames=2048, dtype="float32", always_2d=True)
                    if chunk.size == 0:
                        break
                    stream.write(chunk)
        except Exception as exc:
            if self._stop_playback_event.is_set():
                logger.debug("[TTS] Playback interrupted by stop request.")
            else:
                logger.warning("[TTS] sounddevice playback failed: %s", exc)
                self._fallback_play(path)
        finally:
            with self._playback_lock:
                if self.current_stream is stream:
                    self.current_stream = None
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass
            self._stop_playback_event.clear()

    def speak(self, text):
        self.audio_queue.put(text)

    def set_mute(self, muted: bool):
        """Enable/disable mute state used by CoreEngine."""
        self.muted = bool(muted)
        if self.muted:
            self.stop()

    def stop(self):
        """Interrupt current speech and clear pending queue."""
        logger.info("[TTS] Stop requested. Clearing queue and stopping audio.")
        self._stop_playback_event.set()

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        with self._playback_lock:
            stream = self.current_stream

        if stream is not None:
            try:
                stream.abort()
            except Exception:
                try:
                    stream.stop()
                except Exception:
                    pass
            try:
                stream.close()
            except Exception:
                pass
            with self._playback_lock:
                if self.current_stream is stream:
                    self.current_stream = None

        # Safety net in case any legacy sounddevice play context exists.
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass
