"""Kokoro TTS service for fast, high-quality speech synthesis."""

from __future__ import annotations

import base64
import io
import time
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf
import structlog

from barnabeenet.services.tts.pronunciation import preprocess_text

if TYPE_CHECKING:
    from kokoro import KPipeline

logger = structlog.get_logger()


class KokoroTTS:
    """Text-to-speech using Kokoro-82M.

    Fast, high-quality local TTS with multiple voice options.
    Default voice: bm_fable (British male)
    """

    VOICES = {
        "bf_alice": "British female, clear",
        "bf_emma": "British female, warm",
        "bf_isabella": "British female, soft",
        "bf_lily": "British female, bright",
        "bm_daniel": "British male, clear",
        "bm_fable": "British male, storyteller (Barnabee default)",
        "bm_george": "British male, deep",
        "bm_lewis": "British male, warm",
    }

    def __init__(
        self,
        voice: str = "bm_fable",
        speed: float = 1.0,
        lang_code: str = "b",  # 'b' = British English
    ) -> None:
        """Initialize the TTS service.

        Args:
            voice: Voice ID (default bm_fable for Barnabee)
            speed: Speech speed multiplier (0.5-2.0)
            lang_code: Language code ('a'=American, 'b'=British)
        """
        self.voice = voice
        self.speed = speed
        self.lang_code = lang_code
        self.sample_rate = 24000
        self._pipeline: KPipeline | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load the TTS pipeline."""
        if self._initialized:
            return

        logger.info(
            "Loading Kokoro TTS pipeline",
            voice=self.voice,
            lang_code=self.lang_code,
        )

        start = time.perf_counter()

        from kokoro import KPipeline

        self._pipeline = KPipeline(lang_code=self.lang_code)

        load_time = (time.perf_counter() - start) * 1000
        self._initialized = True

        logger.info(
            "Kokoro TTS pipeline loaded",
            load_time_ms=f"{load_time:.0f}",
        )

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float | None = None,
    ) -> dict:
        """Synthesize text to speech audio.

        Args:
            text: Text to synthesize
            voice: Override voice (or use default)
            speed: Override speed (or use default)

        Returns:
            dict with keys: audio_bytes, audio_base64, sample_rate, duration_ms, latency_ms
        """
        if not self._initialized:
            await self.initialize()

        voice = voice or self.voice
        speed = speed or self.speed

        start = time.perf_counter()

        # Apply pronunciation corrections
        processed_text = preprocess_text(text)

        if processed_text != text:
            logger.debug(
                "Applied pronunciation corrections",
                original=text,
                processed=processed_text,
            )

        # Generate audio chunks
        audio_chunks = []
        for _, _, audio in self._pipeline(processed_text, voice=voice, speed=speed):
            audio_chunks.append(audio)

        if not audio_chunks:
            logger.warning("No audio generated", text=text[:50])
            return {
                "audio_bytes": b"",
                "audio_base64": "",
                "sample_rate": self.sample_rate,
                "duration_ms": 0,
                "latency_ms": 0,
            }

        full_audio = np.concatenate(audio_chunks)

        buffer = io.BytesIO()
        sf.write(buffer, full_audio, self.sample_rate, format="WAV")
        audio_bytes = buffer.getvalue()

        duration_ms = (len(full_audio) / self.sample_rate) * 1000
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Speech synthesized",
            text_length=len(text),
            duration_ms=f"{duration_ms:.0f}",
            latency_ms=f"{latency_ms:.0f}",
            voice=voice,
        )

        return {
            "audio_bytes": audio_bytes,
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
            "sample_rate": self.sample_rate,
            "duration_ms": duration_ms,
            "latency_ms": latency_ms,
        }

    def is_available(self) -> bool:
        """Check if the service is ready."""
        return self._initialized and self._pipeline is not None

    def get_voices(self) -> dict[str, str]:
        """Get available voices."""
        return self.VOICES.copy()

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._pipeline = None
        self._initialized = False
        logger.info("Kokoro TTS service shut down")
