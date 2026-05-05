"""
@ai-context: Dedicated Speech-to-Text (STT) engine. Converts raw
AudioData into strings using faster-whisper (CTranslate2 backend),
ensuring high performance on CPU with INT8 quantization and VAD
filtering for cleaner transcription results.
"""

import numpy as np
import speech_recognition as sr
from faster_whisper import WhisperModel


class STTEngine:
    """Converts speech audio data into text using faster-whisper (CTranslate2)."""

    def __init__(self, language: str = "tr") -> None:
        """Initializes the faster-whisper model with INT8 quantization."""
        self.language: str = language
        # Fix language code for Whisper (e.g., 'tr-TR' -> 'tr')
        if "-" in self.language:
            self.language = self.language.split("-")[0]

        # CTranslate2 INT8 on CPU: ~4x faster than PyTorch Whisper,
        # ~50% less RAM, no DirectML/CUDA dependency issues.
        self._compute_type: str = "int8"
        self._device: str = "cpu"

        print(f"[STTEngine] faster-whisper modeli ({self._device}, {self._compute_type}) yukleniyor...")
        self.model: WhisperModel = WhisperModel(
            "small",
            device=self._device,
            compute_type=self._compute_type,
        )
        print("[STTEngine] faster-whisper modeli hazir.")

    def transcribe(self, audio_data: sr.AudioData, recognizer: sr.Recognizer) -> str | None:
        """Transcribes AudioData to text using faster-whisper locally."""
        try:
            # Get 16 kHz, 16-bit PCM (mono) raw audio bytes
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)

            # Convert raw bytes to 16-bit integer array
            audio_np = np.frombuffer(raw_data, dtype=np.int16)

            # Convert 16-bit integer to 32-bit float array and normalize between -1.0 and +1.0
            audio_fp32 = audio_np.astype(np.float32) / 32768.0

            # Turkish + English keyword bias using initial_prompt
            # This helps Whisper recognize common English app names spoken by Turkish users
            prompt: str = (
                "Spotify, Chrome, WeChat, WhatsApp, YouTube, Excel, Word, "
                "PowerPoint, Windows, click, open, bas, tıkla, aç."
            )

            # faster-whisper transcription with VAD filtering
            # VAD (Voice Activity Detection) suppresses hallucinations on silence
            segments, info = self.model.transcribe(
                audio_fp32,
                language=None,  # Auto-detect for better mixed language support
                initial_prompt=prompt,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=300,
                ),
            )

            # Segments are a generator; join all segment texts
            text: str = " ".join(seg.text.strip() for seg in segments).strip()

            if not text:
                print("[STTEngine] Uyari: Ses anlasilamadi (Bos metin).")
                return None

            return text

        except Exception as e:
            print(f"[STTEngine] Beklenmeyen hata: {e}")
            return None
