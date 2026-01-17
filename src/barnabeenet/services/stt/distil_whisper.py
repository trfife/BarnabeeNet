"""Distil-Whisper STT service for CPU-based speech recognition."""
from __future__ import annotations

import base64
import time
from typing import TYPE_CHECKING

import numpy as np
import structlog

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = structlog.get_logger()


class DistilWhisperSTT:
    """Speech-to-text using Distil-Whisper via faster-whisper.
    
    Optimized for CPU inference on resource-constrained devices.
    Used as fallback when GPU worker is unavailable.
    """

    def __init__(
        self,
        model_size: str = "distil-small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
    ) -> None:
        """Initialize the STT service.
        
        Args:
            model_size: Model identifier (distil-small.en recommended)
            device: Device to run on ("cpu" or "cuda")
            compute_type: Quantization type ("int8" for CPU, "float16" for GPU)
            cpu_threads: Number of CPU threads to use
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self._model: WhisperModel | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load the model. Called once at startup or on first use."""
        if self._initialized:
            return

        logger.info(
            "Loading Distil-Whisper model",
            model=self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

        start = time.perf_counter()
        
        # Import here to avoid slow startup if not used
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
        )

        load_time = (time.perf_counter() - start) * 1000
        self._initialized = True

        logger.info(
            "Distil-Whisper model loaded",
            load_time_ms=f"{load_time:.0f}",
        )

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> dict:
        """Transcribe audio to text.
        
        Args:
            audio_data: Raw audio bytes (PCM 16-bit signed integers)
            sample_rate: Audio sample rate in Hz (default 16000)
            language: Language code (default "en")
            
        Returns:
            dict with keys: text, confidence, language, latency_ms
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        
        # Normalize to [-1, 1] range (faster-whisper expects this)
        audio_array = (audio_array / 32768.0).astype(np.float32)

        # Resample if needed (faster-whisper expects 16kHz)
        if sample_rate != 16000:
            # Simple resampling - for production, use librosa or scipy
            ratio = 16000 / sample_rate
            new_length = int(len(audio_array) * ratio)
            indices = np.linspace(0, len(audio_array) - 1, new_length)
            audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array).astype(np.float32)

        # Transcribe with optimized settings for speed
        segments, info = self._model.transcribe(
            audio_array,
            beam_size=1,  # Greedy decoding for speed
            language=language,
            vad_filter=True,  # Filter silence
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 200,
            },
        )

        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        full_text = " ".join(text_parts).strip()
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Transcription complete",
            text_length=len(full_text),
            latency_ms=f"{latency_ms:.1f}",
            language=info.language,
            language_probability=f"{info.language_probability:.2f}",
        )

        return {
            "text": full_text,
            "confidence": info.language_probability,
            "language": info.language,
            "latency_ms": latency_ms,
        }

    async def transcribe_base64(
        self,
        audio_base64: str,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> dict:
        """Transcribe base64-encoded audio.
        
        Convenience method for API endpoints.
        """
        audio_data = base64.b64decode(audio_base64)
        return await self.transcribe(audio_data, sample_rate, language)

    def is_available(self) -> bool:
        """Check if the service is ready."""
        return self._initialized and self._model is not None

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._model = None
        self._initialized = False
        logger.info("Distil-Whisper service shut down")
