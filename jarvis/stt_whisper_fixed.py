# stt_whisper.py – Speech recognition using faster-whisper
# FIXED VERSION: Proper VAD, silence detection, and wake word logic

import threading
import time
import queue
import logging
from pathlib import Path

import numpy as np
import sounddevice as sd
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
        self.sample_rate = 16000
        self.block_size = 16000  # 1 second blocks
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.wake_phrase = self.config.WAKE_PHRASE.lower()
        self.stop_phrase = self.config.STOP_PHRASE.lower()
        
        # State management
        self.active = False
        self.last_active_time: float | None = None
        self.active_timeout = 300  # 5 minutes
        
        # Audio buffers
        self.buffer = np.array([], dtype=np.float32)
        self.speech_buffer = []
        
        # VAD parameters
        self.ENERGY_THRESHOLD = 0.015
        self.PAUSE_LIMIT = 2.0  # seconds
        self.WAKE_CHECK_INTERVAL = 1.0
        
        # State flags
        self.is_speaking = False
        self.silence_start: float | None = None
        
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
        self.is_speaking = False
        self.silence_start = None
        logger.info("[STT] Audio buffer and queue reset")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice.InputStream – puts raw audio into queue."""
        if self.stop_event.is_set():
            return
        if status:
            logger.warning(f"[STT] Audio callback status: {status}")
        # Convert to mono float32 numpy array
        audio = indata[:, 0].astype(np.float32)
        self.audio_queue.put(audio)

    def _calculate_energy(self, audio_chunk):
        """Calculate RMS energy of audio chunk."""
        return np.sqrt(np.mean(audio_chunk ** 2))

    def _handle_segment(self, audio_segment):
        """Runs Whisper on a segment and checks for wake/stop phrases."""
        if self.model is None:
            return
        try:
            segments, info = self.model.transcribe(audio_segment, language=None, beam_size=2)
            for segment in segments:
                text = segment.text.strip().lower()
                if not text:
                    continue
                
                logger.info(f"[STT] Heard: '{text}' (confidence: {segment.avg_logprob:.2f})")
                
                # Wake word detection (inactive mode)
                if not self.active and self.wake_phrase in text:
                    self.active = True
                    self.last_active_time = time.time()
                    if hasattr(self, "wake_callback"):
                        self.wake_callback()
                    logger.info(f"[STT] [WAKE] Wake phrase detected: {text}")
                    
                # Command processing (active mode)
                elif self.active:
                    self.last_active_time = time.time()
                    if hasattr(self, "transcript_callback"):
                        self.transcript_callback(text)
                    
                    # Check for stop phrase
                    if self.stop_phrase.lower() in text:
                        self.active = False
                        if hasattr(self, "stop_callback"):
                            self.stop_callback()
                        logger.info("[STT] [STOP] Stop phrase detected")
                        
        except Exception as e:
            logger.error(f"[STT] Whisper transcription error: {e}")

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
                                    self._handle_segment(full_audio)
                                    
                                    # Reset state
                                    self.speech_buffer = []
                                    self.is_speaking = False
                                    self.silence_start = None
                
                # PASSIVE MODE: Wake word detection
                else:
                    # Keep rolling buffer for wake word detection
                    self.buffer = np.concatenate((self.buffer, chunk))
                    if len(self.buffer) > self.sample_rate * 3:
                        self.buffer = self.buffer[-int(self.sample_rate * 3):]
                    
                    # Only check wake word if there's decent energy (avoid CPU waste on silence)
                    if energy > 0.005:
                        # Check wake word periodically
                        current_time = time.time()
                        if current_time - last_wake_check > self.WAKE_CHECK_INTERVAL:
                            if len(self.buffer) >= self.sample_rate * 1.5:
                                self._handle_segment(self.buffer)
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
        
        # Start audio stream
        stream = None
        try:
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self._audio_callback)
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
