"""STT Router - Routes transcription requests to GPU, CPU, or Azure backend.

GPU (Parakeet TDT 0.6B v2) is primary for low latency (~45ms).
Azure is secondary when GPU unavailable but configured.
CPU (Distil-Whisper) is fallback when both GPU and Azure unavailable (~2400ms).

Supports multiple modes:
- COMMAND: Single utterance recognition (default)
- REALTIME: Streaming with partial results
- AMBIENT: Batch processing for background capture
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import httpx
import structlog

from barnabeenet.models.stt_modes import STTEngine, STTMode

if TYPE_CHECKING:
    from barnabeenet.services.stt.azure_stt import AzureSTT
    from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT

logger = structlog.get_logger()


class STTBackend(str, Enum):
    """Available STT backends."""

    GPU = "gpu"
    CPU = "cpu"
    AZURE = "azure"


@dataclass
class STTResult:
    """Result from STT transcription."""

    text: str
    confidence: float
    latency_ms: float
    backend: STTBackend
    model: str
    is_final: bool = True


@dataclass
class StreamingSTTResult:
    """Partial or final result from streaming transcription."""

    text: str
    is_final: bool
    confidence: float = 0.0
    backend: STTBackend = STTBackend.GPU
    latency_ms: float = 0.0


class STTRouter:
    """Routes STT requests to GPU worker, Azure, or CPU fallback.

    The router:
    1. Checks GPU worker health on startup and periodically
    2. Checks Azure availability if configured
    3. Routes based on engine selection or auto-selects best available:
       - AUTO: GPU → Azure → CPU (in order of preference)
       - PARAKEET: GPU only, fail if unavailable
       - AZURE: Azure only, fail if unavailable
       - WHISPER: CPU only
    4. Provides unified interface for all STT consumers
    """

    def __init__(
        self,
        gpu_worker_url: str = "http://localhost:8001",
        health_check_interval: float = 30.0,
        request_timeout: float = 10.0,
    ) -> None:
        """Initialize the STT router.

        Args:
            gpu_worker_url: URL of the GPU STT worker
            health_check_interval: Seconds between health checks
            request_timeout: HTTP request timeout in seconds
        """
        self.gpu_worker_url = gpu_worker_url.rstrip("/")
        self.health_check_interval = health_check_interval
        self.request_timeout = request_timeout

        self._cpu_backend: DistilWhisperSTT | None = None
        self._azure_backend: AzureSTT | None = None
        self._gpu_healthy = False
        self._azure_available = False
        self._health_check_task: asyncio.Task | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the router and backends."""
        if self._initialized:
            return

        logger.info(
            "Initializing STT Router",
            gpu_url=self.gpu_worker_url,
        )

        # Create HTTP client for GPU worker
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.request_timeout),
        )

        # Check GPU health immediately
        await self._check_gpu_health()

        # Check Azure availability
        await self._check_azure_availability()

        # Start background health checker
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        self._initialized = True
        logger.info(
            "STT Router initialized",
            gpu_available=self._gpu_healthy,
            azure_available=self._azure_available,
        )

    async def _check_gpu_health(self) -> bool:
        """Check if GPU worker is healthy.

        Returns:
            True if GPU worker is healthy, False otherwise.
        """
        if self._http_client is None:
            return False

        try:
            response = await self._http_client.get(
                f"{self.gpu_worker_url}/health",
            )
            if response.status_code == 200:
                data = response.json()
                healthy = data.get("status") == "healthy" and data.get("model_loaded", False)
                if healthy != self._gpu_healthy:
                    logger.info(
                        "GPU worker health changed",
                        healthy=healthy,
                        gpu_name=data.get("gpu_name"),
                    )
                self._gpu_healthy = healthy
                return healthy
        except (httpx.RequestError, httpx.TimeoutException) as e:
            if self._gpu_healthy:  # Only log on state change
                logger.warning(
                    "GPU worker unreachable",
                    error=str(e),
                )
            self._gpu_healthy = False

        return False

    async def _health_check_loop(self) -> None:
        """Background task to periodically check GPU and Azure health."""
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self._check_gpu_health()
            await self._check_azure_availability()

    async def _check_azure_availability(self) -> bool:
        """Check if Azure STT is available.

        Returns:
            True if Azure STT is configured and working.
        """
        try:
            azure = await self._ensure_azure_backend()
            self._azure_available = azure.is_available()
        except Exception as e:
            logger.debug("Azure STT not available", error=str(e))
            self._azure_available = False
        return self._azure_available

    async def _ensure_azure_backend(self) -> AzureSTT:
        """Lazily initialize Azure backend when needed."""
        if self._azure_backend is None:
            from barnabeenet.services.stt.azure_stt import AzureSTT

            logger.info("Initializing Azure STT backend")
            self._azure_backend = AzureSTT()
            await self._azure_backend.initialize()

        return self._azure_backend

    async def _ensure_cpu_backend(self) -> DistilWhisperSTT:
        """Lazily initialize CPU backend when needed."""
        if self._cpu_backend is None:
            from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT

            logger.info("Initializing CPU STT backend (fallback)")
            self._cpu_backend = DistilWhisperSTT()
            await self._cpu_backend.initialize()

        return self._cpu_backend

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en",
        engine: STTEngine = STTEngine.AUTO,
        mode: STTMode = STTMode.COMMAND,
    ) -> STTResult:
        """Transcribe audio using the specified or best available backend.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit signed integers)
            sample_rate: Audio sample rate in Hz
            language: Language code
            engine: STT engine to use (AUTO, PARAKEET, WHISPER, AZURE)
            mode: Processing mode (COMMAND, REALTIME, AMBIENT)

        Returns:
            STTResult with transcription and metadata

        Raises:
            RuntimeError: If specified engine is unavailable
        """
        if not self._initialized:
            await self.initialize()

        # Resolve engine selection
        selected_engine = await self._select_engine(engine)

        logger.debug(
            "Transcribing audio",
            requested_engine=engine.value,
            selected_engine=selected_engine.value,
            mode=mode.value,
            audio_bytes=len(audio_data),
        )

        # Route to selected engine
        if selected_engine == STTEngine.PARAKEET:
            result = await self._transcribe_gpu(audio_data, sample_rate, language)
            if result is not None:
                return result
            # GPU failed, try fallback if AUTO mode
            if engine == STTEngine.AUTO:
                return await self._transcribe_with_fallback(audio_data, sample_rate, language)
            raise RuntimeError("GPU STT unavailable")

        elif selected_engine == STTEngine.AZURE:
            result = await self._transcribe_azure(audio_data, sample_rate, language)
            if result is not None:
                return result
            # Azure failed, try fallback if AUTO mode
            if engine == STTEngine.AUTO:
                return await self._transcribe_cpu(audio_data, sample_rate, language)
            raise RuntimeError("Azure STT unavailable")

        else:  # WHISPER / CPU fallback
            return await self._transcribe_cpu(audio_data, sample_rate, language)

    async def _select_engine(self, engine: STTEngine) -> STTEngine:
        """Select the best available engine based on preference.

        Args:
            engine: Requested engine (or AUTO for auto-selection)

        Returns:
            The engine to use.
        """
        if engine == STTEngine.PARAKEET:
            if self._gpu_healthy:
                return STTEngine.PARAKEET
            raise RuntimeError("GPU STT requested but unavailable")

        if engine == STTEngine.AZURE:
            if self._azure_available:
                return STTEngine.AZURE
            raise RuntimeError("Azure STT requested but unavailable")

        if engine == STTEngine.WHISPER:
            return STTEngine.WHISPER

        # AUTO mode: GPU → Azure → CPU
        if self._gpu_healthy:
            return STTEngine.PARAKEET
        if self._azure_available:
            return STTEngine.AZURE
        return STTEngine.WHISPER

    async def _transcribe_with_fallback(
        self,
        audio_data: bytes,
        sample_rate: int,
        language: str,
    ) -> STTResult:
        """Try Azure, then CPU as fallback."""
        if self._azure_available:
            result = await self._transcribe_azure(audio_data, sample_rate, language)
            if result is not None:
                return result
        return await self._transcribe_cpu(audio_data, sample_rate, language)

    async def _transcribe_gpu(
        self,
        audio_data: bytes,
        sample_rate: int,
        language: str,
    ) -> STTResult | None:
        """Transcribe using GPU worker.

        Returns:
            STTResult if successful, None if failed.
        """
        if self._http_client is None:
            return None

        try:
            # GPU worker expects base64-encoded audio
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            response = await self._http_client.post(
                f"{self.gpu_worker_url}/transcribe",
                json={
                    "audio_base64": audio_base64,
                    "language": language,
                    "sample_rate": sample_rate,
                },
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "GPU transcription complete",
                    latency_ms=data.get("latency_ms"),
                    text_length=len(data.get("text", "")),
                )
                return STTResult(
                    text=data["text"],
                    confidence=data.get("confidence", 1.0),
                    latency_ms=data["latency_ms"],
                    backend=STTBackend.GPU,
                    model=data.get("model", "nvidia/parakeet-tdt-0.6b-v2"),
                )
            else:
                logger.warning(
                    "GPU worker returned error",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(
                "GPU transcription failed",
                error=str(e),
            )
            # Mark as unhealthy so next request uses CPU immediately
            self._gpu_healthy = False

        return None

    async def _transcribe_cpu(
        self,
        audio_data: bytes,
        sample_rate: int,
        language: str,
    ) -> STTResult:
        """Transcribe using CPU backend (fallback)."""
        cpu_backend = await self._ensure_cpu_backend()

        result = await cpu_backend.transcribe(
            audio_data=audio_data,
            sample_rate=sample_rate,
            language=language,
        )

        logger.info(
            "CPU transcription complete",
            latency_ms=result["latency_ms"],
            text_length=len(result.get("text", "")),
        )

        return STTResult(
            text=result["text"],
            confidence=result.get("confidence", 0.0),
            latency_ms=result["latency_ms"],
            backend=STTBackend.CPU,
            model="distil-whisper-small.en",
        )

    async def _transcribe_azure(
        self,
        audio_data: bytes,
        sample_rate: int,
        language: str,
    ) -> STTResult | None:
        """Transcribe using Azure Speech Services.

        Returns:
            STTResult if successful, None if failed.
        """
        try:
            azure = await self._ensure_azure_backend()
            if not azure.is_available():
                return None

            result = await azure.transcribe(
                audio_data=audio_data,
                sample_rate=sample_rate,
                language=language,
            )

            logger.info(
                "Azure transcription complete",
                latency_ms=f"{result.latency_ms:.2f}",
                text_length=len(result.text),
            )

            return STTResult(
                text=result.text,
                confidence=result.confidence,
                latency_ms=result.latency_ms,
                backend=STTBackend.AZURE,
                model="azure-speech-sdk",
            )
        except Exception as e:
            logger.warning(
                "Azure transcription failed",
                error=str(e),
            )
            self._azure_available = False
            return None

    async def transcribe_streaming(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
        language: str = "en",
        engine: STTEngine = STTEngine.AUTO,
    ) -> AsyncGenerator[StreamingSTTResult, None]:
        """Transcribe streaming audio with real-time partial results.

        Args:
            audio_stream: Async generator yielding audio chunks
            sample_rate: Audio sample rate in Hz
            language: Language code
            engine: STT engine to use

        Yields:
            StreamingSTTResult with partial and final transcriptions.
        """
        if not self._initialized:
            await self.initialize()

        # For streaming, prefer Azure if available (native streaming support)
        # GPU worker doesn't support streaming yet, so fall back to batch mode
        selected_engine = await self._select_engine(engine)

        if selected_engine == STTEngine.AZURE and self._azure_available:
            # Use Azure's native streaming
            azure = await self._ensure_azure_backend()
            async for result in azure.transcribe_streaming(
                audio_stream=audio_stream,
                sample_rate=sample_rate,
                language=language,
            ):
                yield StreamingSTTResult(
                    text=result.text,
                    is_final=result.is_final,
                    confidence=result.confidence,
                    backend=STTBackend.AZURE,
                )
        else:
            # For non-Azure engines, collect audio and transcribe in batch
            # This is a fallback for engines that don't support streaming
            audio_chunks = []
            async for chunk in audio_stream:
                audio_chunks.append(chunk)

            audio_data = b"".join(audio_chunks)
            result = await self.transcribe(
                audio_data=audio_data,
                sample_rate=sample_rate,
                language=language,
                engine=engine,
            )

            yield StreamingSTTResult(
                text=result.text,
                is_final=True,
                confidence=result.confidence,
                backend=STTBackend(result.backend.value),
                latency_ms=result.latency_ms,
            )

    async def transcribe_base64(
        self,
        audio_base64: str,
        sample_rate: int = 16000,
        language: str = "en",
        engine: STTEngine = STTEngine.AUTO,
        mode: STTMode = STTMode.COMMAND,
    ) -> STTResult:
        """Transcribe base64-encoded audio.

        Convenience method for API endpoints.
        """
        audio_data = base64.b64decode(audio_base64)
        return await self.transcribe(audio_data, sample_rate, language, engine=engine, mode=mode)

    def get_status(self) -> dict:
        """Get current router status.

        Returns:
            Dict with backend availability info.
        """
        # Determine preferred backend based on availability
        if self._gpu_healthy:
            preferred = STTBackend.GPU.value
        elif self._azure_available:
            preferred = STTBackend.AZURE.value
        else:
            preferred = STTBackend.CPU.value

        return {
            "gpu_healthy": self._gpu_healthy,
            "gpu_url": self.gpu_worker_url,
            "azure_available": self._azure_available,
            "cpu_available": self._cpu_backend is not None and self._cpu_backend.is_available(),
            "preferred_backend": preferred,
            "engines": {
                "parakeet": {"available": self._gpu_healthy, "type": "gpu"},
                "azure": {"available": self._azure_available, "type": "cloud"},
                "whisper": {"available": True, "type": "cpu"},  # Always available as fallback
            },
        }

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._http_client is not None:
            await self._http_client.aclose()

        if self._cpu_backend is not None:
            await self._cpu_backend.shutdown()

        if self._azure_backend is not None:
            await self._azure_backend.shutdown()

        self._initialized = False
        logger.info("STT Router shut down")
