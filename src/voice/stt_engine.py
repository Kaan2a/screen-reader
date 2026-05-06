"""
@ai-context: Dedicated Speech-to-Text (STT) engine for v3 architecture.
Implements continuous listening with optional WebRTC VAD and Faster-Whisper.
"""

import logging
import time
import queue
import threading
from typing import Optional
import numpy as np
from pydantic import BaseModel, Field
from faster_whisper import WhisperModel

from src.utils.device_utils import get_best_device, get_compute_type

try:
    import webrtcvad
    HAS_WEBRTCVAD = True
except ImportError:
    HAS_WEBRTCVAD = False

try:
    import pyaudio
except ImportError:
    pyaudio = None

logger = logging.getLogger(__name__)

VAD_FRAME_BYTES = 640  # 20ms of 16kHz 16-bit mono audio
SILENCE_FRAMES = 30    # 600ms (30 * 20ms)

class STTResult(BaseModel):
    text: str = Field(..., description="Transcribed text")
    language: str = Field(..., description="Detected language")
    confidence: float = Field(..., description="Transcription confidence score")
    processing_time: float = Field(..., description="Time taken to transcribe in seconds")

class STTEngine:
    def __init__(self, language: str = "tr", model_size: str = "large-v3-turbo") -> None:
        self.language = language
        self.model_size = model_size
        
        self.device = get_best_device()
        
        fw_device = "cuda" if "cuda" in self.device else "cpu"
        fw_compute_type = get_compute_type(fw_device)
        
        # Faster-whisper generally requires int8 on CPU for reasonable performance
        if fw_device == "cpu" and fw_compute_type == "float32":
            fw_compute_type = "int8"

        logger.info(f"[STTEngine] Loading {model_size} on {fw_device} with {fw_compute_type}...")
        self.model = WhisperModel(
            model_size,
            device=fw_device,
            compute_type=fw_compute_type
        )
        logger.info("[STTEngine] Model loaded successfully.")
        
        self.vad = webrtcvad.Vad(3) if HAS_WEBRTCVAD else None
        if not HAS_WEBRTCVAD:
            logger.warning("[STTEngine] webrtcvad not installed. Using simple energy-based silence detection.")
            
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._result_queue: queue.Queue[STTResult] = queue.Queue()
        
        self.is_listening = False
        self._listen_thread: threading.Thread | None = None
        self._process_thread: threading.Thread | None = None

    def start_listening(self) -> None:
        if self.is_listening:
            return
            
        if pyaudio is None:
            logger.error("[STTEngine] pyaudio is not installed. Cannot start microphone stream.")
            return

        self.is_listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._listen_thread.start()
        self._process_thread.start()
        logger.info("[STTEngine] Started continuous listening.")

    def stop_listening(self) -> None:
        self.is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=1.0)
        if self._process_thread:
            self._process_thread.join(timeout=1.0)
        logger.info("[STTEngine] Stopped listening.")

    def _listen_loop(self) -> None:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=VAD_FRAME_BYTES // 2
        )
        
        audio_buffer: list[bytes] = []
        silence_counter = 0
        is_speaking = False
        
        logger.info("[STTEngine] Microphone stream opened.")
        
        try:
            while self.is_listening:
                try:
                    frame = stream.read(VAD_FRAME_BYTES // 2, exception_on_overflow=False)
                except Exception as e:
                    logger.error(f"[STTEngine] Audio read error: {e}")
                    continue
                    
                is_speech = False
                if self.vad:
                    try:
                        is_speech = self.vad.is_speech(frame, 16000)
                    except Exception:
                        pass
                else:
                    # Simple energy based VAD fallback
                    energy = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                    is_speech = np.sqrt(np.mean(energy**2)) > 500

                if is_speech:
                    if not is_speaking:
                        # Clear buffer up to 1 second of audio context if we were silent for a long time
                        # However, for simplicity and typical wake-word/command use cases, we start fresh
                        audio_buffer = []
                        
                    is_speaking = True
                    silence_counter = 0
                    audio_buffer.append(frame)
                else:
                    if is_speaking:
                        silence_counter += 1
                        audio_buffer.append(frame)
                        
                        if silence_counter >= SILENCE_FRAMES:
                            # 600ms silence detected, flush buffer
                            complete_audio = b"".join(audio_buffer)
                            self._audio_queue.put(complete_audio)
                            
                            audio_buffer = []
                            is_speaking = False
                            silence_counter = 0
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.info("[STTEngine] Microphone stream closed.")

    def _process_loop(self) -> None:
        while self.is_listening:
            try:
                audio_bytes = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            if len(audio_bytes) < VAD_FRAME_BYTES * 10:
                # Too short to be meaningful
                continue
                
            start_time = time.time()
            
            # Convert bytes to float32 numpy array
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            prompt = (
                "Spotify, Chrome, YouTube, Discord, Not Defteri, Dosyalar, Hesap Makinesi, "
                "tıkla, aç, kapat, durdur, oynat, ses aç, ekranı kilitle, sola yasla, ayarları aç."
            )
            
            try:
                segments_generator, info = self.model.transcribe(
                    audio_np,
                    language=self.language,
                    initial_prompt=prompt,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=300,
                    ),
                )
                
                # Consume generator
                segments = list(segments_generator)
                text = " ".join(seg.text.strip() for seg in segments).strip()
                
                if text:
                    proc_time = time.time() - start_time
                    
                    # Calculate average confidence across segments if possible
                    conf = info.language_probability
                    
                    result = STTResult(
                        text=text,
                        language=info.language,
                        confidence=conf,
                        processing_time=proc_time
                    )
                    self._result_queue.put(result)
                    logger.info(f"[STTEngine] Transcribed: '{text}' in {proc_time:.2f}s")
                    
            except Exception as e:
                logger.error(f"[STTEngine] Transcription error: {e}")

    def get_result(self, timeout: float = 0.05) -> STTResult | None:
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
