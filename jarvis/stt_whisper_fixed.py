# stt_whisper.py – Speech recognition using faster-whisper
# FIXED VERSION: Proper VAD, silence detection, and wake word logic

import threading
import time
import queue
import logging
import os
from collections import deque
from pathlib import Path

import numpy as np
try:
    import sounddevice as sd
except Exception:
    sd = None
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)

class SpeechRecognizer:
    """Handles continuous audio capture, wake word detection, and transcription.
    Uses a background thread to capture audio chunks and a Whisper model for inference.
    FIXED: Proper VAD with silence detection and state management.
    """

    def __init__(self, config):
        self.config = config
        self.model = None
        if FASTER_WHISPER_AVAILABLE:
            self.model = WhisperModel(self.config.WHISPER_MODEL, device="cpu", compute_type="int8")
        else:
            logger.warning(
                "[STT] faster-whisper not installed. Voice input is disabled. "
                "Install dependency to enable STT."
            )
        self.sample_rate = int(os.getenv("STT_SAMPLE_RATE", "16000"))
        # Use larger processing blocks + bigger queue to reduce callback overflows on busy systems.
        default_block = 8192 if getattr(self.config, "LOW_RAM_MODE", False) else 4096
        self.block_size = int(os.getenv("STT_BLOCK_SIZE", str(default_block)))
        self.audio_queue = queue.Queue(maxsize=int(os.getenv("STT_QUEUE_SIZE", "128")))
        self.stream_latency = os.getenv("STT_LATENCY", "high").lower()
        self.transcribe_language = (os.getenv("STT_LANGUAGE", "").strip().lower() or None)
        self.transcribe_beam_size = int(os.getenv("STT_BEAM_SIZE", "3"))
        self.transcribe_best_of = int(os.getenv("STT_BEST_OF", "3"))
        self.transcribe_initial_prompt = os.getenv(
            "STT_INITIAL_PROMPT",
            "Roman Urdu aur English commands ko seedha text me likho.",
        )
        self.stop_event = threading.Event()
        self.wake_phrase = self.config.WAKE_PHRASE.lower()
        self.stop_phrase = self.config.STOP_PHRASE.lower()
        wake_aliases_env = os.getenv("STT_WAKE_ALIASES", "jarvis")
        self.wake_aliases = {self.wake_phrase}
        self.wake_aliases.update(
            alias.strip().lower() for alias in wake_aliases_env.split(",") if alias.strip()
        )
        
        # State management
        self.active = False
        self.last_active_time: float | None = None
        self.active_timeout = 300  # 5 minutes
        
        # Audio buffers
        self.buffer = np.array([], dtype=np.float32)
        self.speech_buffer = []
        self.wake_buffer_chunks = deque()
        self.wake_buffer_samples = 0
        self.max_wake_buffer_samples = int(self.sample_rate * 3)
        
        # VAD parameters
        self.ENERGY_THRESHOLD = 0.015
        self.WAKE_ENERGY_THRESHOLD = float(
            os.getenv("STT_WAKE_ENERGY_THRESHOLD", str(self.ENERGY_THRESHOLD))
        )
        self.PAUSE_LIMIT = float(os.getenv("STT_PAUSE_LIMIT", "2.0"))  # seconds
        self.WAKE_CHECK_INTERVAL = float(os.getenv("STT_WAKE_INTERVAL", "1.5"))
        self.MIN_COMMAND_SECONDS = float(os.getenv("STT_MIN_COMMAND_SECONDS", "0.8"))
        self.NO_MATCH_COOLDOWN = float(os.getenv("STT_NO_MATCH_COOLDOWN", "6.0"))
        
        # State flags
        self.is_speaking = False
        self.silence_start: float | None = None
        self.overflow_count = 0
        self.last_overflow_log = 0.0
        self.last_no_match_emit = 0.0
        
        # Callbacks
        self.wake_callback = None
        self.transcript_callback = None
        self.stop_callback = None
        
        logger.info("[STT] SpeechRecognizer initialized")

    def reset_buffer(self):
        """Clears the audio queue and buffers."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        self.buffer = np.array([], dtype=np.float32)
        self.speech_buffer = []
        self.wake_buffer_chunks.clear()
        self.wake_buffer_samples = 0
        self.is_speaking = False
        self.silence_start = None
        logger.info("[STT] Audio buffer and queue reset")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice.InputStream – puts raw audio into queue."""
        if self.stop_event.is_set():
            return
        if status:
            self.overflow_count += 1
            now = time.time()
            if now - self.last_overflow_log >= 5:
                logger.warning(
                    "[STT] Audio callback status: %s (events=%s). "
                    "Mic input is lagging; stream tuned for recovery.",
                    status,
                    self.overflow_count,
                )
                self.last_overflow_log = now
        # Convert to mono float32 numpy array
        audio = indata[:, 0].astype(np.float32)
        try:
            self.audio_queue.put_nowait(audio)
        except queue.Full:
            # Keep most-recent audio to recover from temporary overload.
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.audio_queue.put_nowait(audio)
            except queue.Full:
                pass

    def _calculate_energy(self, audio_chunk):
        """Calculate RMS energy of audio chunk."""
        return np.sqrt(np.mean(audio_chunk ** 2))

    def _handle_segment(self, audio_segment, for_wake: bool = False):
        """Runs Whisper on a segment and checks for wake/stop phrases."""
        if self.model is None:
            return False

        recognized = False
        if for_wake:
            languages_to_try = [self.transcribe_language] if self.transcribe_language else [None, "en", "ur"]
        else:
            languages_to_try = [self.transcribe_language] if self.transcribe_language else ["ur", "en", None]

        for lang in languages_to_try:
            try:
                segments, info = self.model.transcribe(
                    audio_segment,
                    language=lang,
                    beam_size=self.transcribe_beam_size,
                    best_of=self.transcribe_best_of,
                    vad_filter=for_wake,
                    condition_on_previous_text=False,
                    temperature=0.0,
                    initial_prompt=self.transcribe_initial_prompt,
                )
                had_text_for_lang = False
                for segment in segments:
                    text = segment.text.strip().lower()
                    if not text:
                        continue
                    had_text_for_lang = True
                    recognized = True
                    logger.info(f"[STT] Heard: '{text}' (confidence: {segment.avg_logprob:.2f})")

                    # Wake word detection (inactive mode)
                    if not self.active and any(alias in text for alias in self.wake_aliases):
                        self.active = True
                        self.last_active_time = time.time()
                        if callable(self.wake_callback):
                            self.wake_callback()
                        logger.info(f"[STT] [WAKE] Wake phrase detected: {text}")

                    # Command processing (active mode)
                    elif self.active:
                        self.last_active_time = time.time()
                        if callable(self.transcript_callback):
                            self.transcript_callback(text)

                        # Check for stop phrase
                        if self.stop_phrase.lower() in text:
                            self.active = False
                            if callable(self.stop_callback):
                                self.stop_callback()
                            logger.info("[STT] [STOP] Stop phrase detected")

                if had_text_for_lang:
                    break
            except Exception as e:
                logger.error(f"[STT] Whisper transcription error (lang={lang}): {e}")

        if not recognized:
            logger.info("[STT] No clear speech recognized from current segment.")
        return recognized

    def _process_queue(self):
        """Main VAD processing loop with proper state management."""
        logger.info(f"[STT] VAD Engine Started. Threshold: {self.ENERGY_THRESHOLD}, Pause: {self.PAUSE_LIMIT}s")
        
        last_wake_check = time.time()

        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                energy = self._calculate_energy(chunk)
                
                # ACTIVE MODE: VAD + Pause detection for commands
                if self.active:
                    if energy > self.ENERGY_THRESHOLD:
                        # Speech detected
                        if not self.is_speaking:
                            logger.info("[STT] [VOICE] Speech detected...")
                            self.is_speaking = True
                            self.silence_start = None
                        
                        self.speech_buffer.append(chunk)
                        
                    else:
                        # Silence or low energy
                        if self.is_speaking:
                            # First silence frame after speech
                            if self.silence_start is None:
                                self.silence_start = time.time()
                        
                        # Check if silence exceeds pause limit
                        if self.silence_start is not None:
                            if time.time() - self.silence_start > self.PAUSE_LIMIT:
                                if self.speech_buffer:
                                    logger.info(f"[STT] Silence detected ({self.PAUSE_LIMIT}s). Processing command...")
                                    
                                    # Concatenate and process
                                    full_audio = np.concatenate(self.speech_buffer)
                                    duration_sec = len(full_audio) / float(self.sample_rate)
                                    recognized = self._handle_segment(full_audio, for_wake=False)
                                    if (
                                        not recognized
                                        and duration_sec >= self.MIN_COMMAND_SECONDS
                                        and callable(self.transcript_callback)
                                        and (time.time() - self.last_no_match_emit) >= self.NO_MATCH_COOLDOWN
                                    ):
                                        self.last_no_match_emit = time.time()
                                        self.transcript_callback("__stt_no_match__")
                                    
                                    # Reset state
                                    self.speech_buffer = []
                                    self.is_speaking = False
                                    self.silence_start = None
                
                # PASSIVE MODE: Wake word detection
                else:
                    # Keep rolling buffer for wake word detection (chunked to avoid expensive copies).
                    self.wake_buffer_chunks.append(chunk)
                    self.wake_buffer_samples += len(chunk)
                    while self.wake_buffer_samples > self.max_wake_buffer_samples and self.wake_buffer_chunks:
                        removed = self.wake_buffer_chunks.popleft()
                        self.wake_buffer_samples -= len(removed)

                    # Only check wake word if there's decent energy (avoid CPU waste on silence)
                    if energy > self.WAKE_ENERGY_THRESHOLD:
                        # Check wake word periodically
                        current_time = time.time()
                        if current_time - last_wake_check > self.WAKE_CHECK_INTERVAL:
                            if self.wake_buffer_samples >= self.sample_rate * 1.5:
                                self._handle_segment(np.concatenate(tuple(self.wake_buffer_chunks)), for_wake=True)
                            last_wake_check = current_time
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[STT] Queue processing error: {e}")

    def listen_for_wake(self, wake_callback, transcript_callback=None, stop_callback=None):
        """Public method to start listening for the wake phrase."""
        self.wake_callback = wake_callback
        self.transcript_callback = transcript_callback
        self.stop_callback = stop_callback

        if self.model is None:
            logger.warning("[STT] Running in no-STT mode. Waiting for shutdown signal.")
            while not self.stop_event.is_set():
                time.sleep(1)
            logger.info("[STT] No-STT mode stopped")
            return
        if sd is None:
            logger.warning("[STT] sounddevice is not installed. Voice input is disabled.")
            while not self.stop_event.is_set():
                time.sleep(1)
            logger.info("[STT] No-audio mode stopped")
            return
        
        # Start audio stream
        stream = None
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.block_size,
                dtype="float32",
                latency=self.stream_latency,
                callback=self._audio_callback,
            )
            stream.start()
        except Exception as e:
            logger.error(f"[STT] Unable to start audio input stream: {e}")
            while not self.stop_event.is_set():
                time.sleep(1)
            return
        
        # Start processing thread
        processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        processing_thread.start()
        
        logger.info("[STT] Listening for wake phrase...")
        
        # Keep thread alive with timeout monitoring
        try:
            while not self.stop_event.is_set():
                # Check for inactivity timeout
                if self.active and self.last_active_time is not None:
                    if time.time() - self.last_active_time > self.active_timeout:
                        logger.info("[STT] [TIMEOUT] Inactivity timeout – returning to idle")
                        self.active = False
                        if self.stop_callback:
                            self.stop_callback()
                
                time.sleep(0.5)
        finally:
            self.stop_event.set()
            if stream is not None:
                stream.stop()
                stream.close()
            logger.info("[STT] Listening stopped")

    def shutdown(self):
        """Gracefully stop the recognizer."""
        logger.info("[STT] Shutting down...")
        self.stop_event.set()
