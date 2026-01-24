"""Azure Speech SDK Integration for STT.

Provides batch and streaming transcription via Azure Cognitive Services.
Used as cloud fallback when GPU is unavailable (e.g., mobile/remote access).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


@dataclass
class AzureSTTConfig:
    """Azure Speech SDK configuration."""

    speech_key: str
    speech_region: str = "eastus"
    language: str = "en-US"
    # Streaming settings
    streaming_interim_results: bool = True
    profanity_filter: str = "raw"  # raw, masked, removed


@dataclass
class TranscriptionResult:
    """Result from Azure transcription."""

    text: str
    confidence: float
    is_final: bool
    latency_ms: float
    offset_ms: float | None = None
    duration_ms: float | None = None


@dataclass
class StreamingResult:
    """Streaming transcription result with partial updates."""

    text: str
    is_final: bool
    confidence: float = 0.0
    result_id: str | None = None


class AzureSTT:
    """Azure Speech SDK client for speech-to-text.

    Supports both batch (single audio file) and streaming modes.
    Streaming provides real-time partial results as audio is processed.
    """

    def __init__(self, config: AzureSTTConfig | None = None) -> None:
        """Initialize Azure STT client.

        Args:
            config: Azure configuration. If None, reads from environment.
        """
        self._config = config or self._load_config_from_env()
        self._initialized = False
        self._speech_config: Any = None
        self._available = False

    def _load_config_from_env(self) -> AzureSTTConfig:
        """Load configuration from environment variables."""
        return AzureSTTConfig(
            speech_key=os.getenv("AZURE_SPEECH_KEY", ""),
            speech_region=os.getenv("AZURE_SPEECH_REGION", "eastus"),
            language=os.getenv("AZURE_SPEECH_LANGUAGE", "en-US"),
        )

    async def initialize(self) -> bool:
        """Initialize the Azure Speech SDK.

        Returns:
            True if initialization successful, False otherwise.
        """
        if self._initialized:
            return self._available

        if not self._config.speech_key:
            logger.warning("Azure Speech key not configured, Azure STT unavailable")
            self._available = False
            self._initialized = True
            return False

        try:
            # Import Azure SDK (optional dependency)
            import azure.cognitiveservices.speech as speechsdk

            self._speech_config = speechsdk.SpeechConfig(
                subscription=self._config.speech_key,
                region=self._config.speech_region,
            )
            self._speech_config.speech_recognition_language = self._config.language

            # Configure profanity handling
            self._speech_config.set_profanity(
                speechsdk.ProfanityOption.Raw
                if self._config.profanity_filter == "raw"
                else speechsdk.ProfanityOption.Masked
            )

            self._available = True
            self._initialized = True

            logger.info(
                "Azure STT initialized",
                region=self._config.speech_region,
                language=self._config.language,
            )
            return True

        except ImportError:
            logger.warning(
                "Azure Speech SDK not installed. "
                "Install with: pip install azure-cognitiveservices-speech"
            )
            self._available = False
            self._initialized = True
            return False
        except Exception as e:
            logger.error("Failed to initialize Azure STT", error=str(e))
            self._available = False
            self._initialized = True
            return False

    def is_available(self) -> bool:
        """Check if Azure STT is available."""
        return self._available

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio data in batch mode.

        Args:
            audio_data: Raw PCM audio bytes (16-bit signed, mono)
            sample_rate: Audio sample rate in Hz
            language: Language code (overrides config if provided)

        Returns:
            TranscriptionResult with transcription text and metadata.
        """
        import time

        if not self._available:
            await self.initialize()
            if not self._available:
                raise RuntimeError("Azure STT not available")

        import azure.cognitiveservices.speech as speechsdk

        start_time = time.perf_counter()

        # Create audio stream from PCM data
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=sample_rate,
            bits_per_sample=16,
            channels=1,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        push_stream.write(audio_data)
        push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Create recognizer
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._speech_config,
            audio_config=audio_config,
            language=language or self._config.language,
        )

        # Perform recognition
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            recognizer.recognize_once,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Get confidence from detailed results if available
            confidence = 1.0
            if result.best():
                confidence = result.best().confidence

            logger.info(
                "Azure transcription complete",
                text_length=len(result.text),
                latency_ms=f"{latency_ms:.2f}",
            )

            return TranscriptionResult(
                text=result.text,
                confidence=confidence,
                is_final=True,
                latency_ms=latency_ms,
            )
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.debug("Azure STT: No speech recognized")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                is_final=True,
                latency_ms=latency_ms,
            )
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = speechsdk.CancellationDetails(result)
            logger.error(
                "Azure STT canceled",
                reason=str(cancellation.reason),
                error_details=cancellation.error_details,
            )
            raise RuntimeError(f"Azure STT canceled: {cancellation.error_details}")
        else:
            raise RuntimeError(f"Unexpected Azure STT result: {result.reason}")

    async def transcribe_streaming(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> AsyncGenerator[StreamingResult, None]:
        """Transcribe audio stream with real-time partial results.

        Args:
            audio_stream: Async generator yielding audio chunks
            sample_rate: Audio sample rate in Hz
            language: Language code (overrides config if provided)

        Yields:
            StreamingResult with partial and final transcriptions.
        """
        if not self._available:
            await self.initialize()
            if not self._available:
                raise RuntimeError("Azure STT not available")

        import azure.cognitiveservices.speech as speechsdk

        # Create push stream
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=sample_rate,
            bits_per_sample=16,
            channels=1,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # Create recognizer for continuous recognition
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._speech_config,
            audio_config=audio_config,
            language=language or self._config.language,
        )

        # Queue for results
        result_queue: asyncio.Queue[StreamingResult | None] = asyncio.Queue()
        recognition_done = asyncio.Event()

        def on_recognizing(evt: Any) -> None:
            """Handle partial recognition results."""
            if evt.result.text:
                asyncio.get_event_loop().call_soon_threadsafe(
                    result_queue.put_nowait,
                    StreamingResult(
                        text=evt.result.text,
                        is_final=False,
                        result_id=evt.result.result_id,
                    ),
                )

        def on_recognized(evt: Any) -> None:
            """Handle final recognition results."""
            if evt.result.text:
                confidence = 1.0
                if hasattr(evt.result, "best") and evt.result.best():
                    confidence = evt.result.best().confidence

                asyncio.get_event_loop().call_soon_threadsafe(
                    result_queue.put_nowait,
                    StreamingResult(
                        text=evt.result.text,
                        is_final=True,
                        confidence=confidence,
                        result_id=evt.result.result_id,
                    ),
                )

        def on_canceled(evt: Any) -> None:
            """Handle cancellation."""
            logger.warning("Azure streaming recognition canceled", reason=str(evt.reason))
            asyncio.get_event_loop().call_soon_threadsafe(recognition_done.set)

        def on_session_stopped(_evt: Any) -> None:
            """Handle session stop."""
            asyncio.get_event_loop().call_soon_threadsafe(recognition_done.set)

        # Connect event handlers
        recognizer.recognizing.connect(on_recognizing)
        recognizer.recognized.connect(on_recognized)
        recognizer.canceled.connect(on_canceled)
        recognizer.session_stopped.connect(on_session_stopped)

        # Start continuous recognition
        recognizer.start_continuous_recognition()

        try:
            # Feed audio chunks to the push stream
            async def feed_audio() -> None:
                async for chunk in audio_stream:
                    push_stream.write(chunk)
                push_stream.close()

            # Start feeding audio in background
            feed_task = asyncio.create_task(feed_audio())

            # Yield results until done
            while not recognition_done.is_set() or not result_queue.empty():
                try:
                    result = await asyncio.wait_for(result_queue.get(), timeout=0.1)
                    if result is not None:
                        yield result
                except TimeoutError:
                    continue

            # Ensure feed task completes
            await feed_task

        finally:
            # Stop recognition
            recognizer.stop_continuous_recognition()

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._speech_config = None
        self._initialized = False
        self._available = False
        logger.info("Azure STT shut down")


# Singleton instance
_azure_stt: AzureSTT | None = None


def get_azure_stt() -> AzureSTT:
    """Get the singleton Azure STT instance."""
    global _azure_stt
    if _azure_stt is None:
        _azure_stt = AzureSTT()
    return _azure_stt
