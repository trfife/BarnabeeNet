"""STT Router - Routes transcription requests to GPU or CPU backend.

GPU (Parakeet TDT 0.6B v2) is primary for low latency (~45ms).
CPU (Distil-Whisper) is fallback when GPU unavailable (~2400ms).
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import httpx
import structlog

if TYPE_CHECKING:
    from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT

logger = structlog.get_logger()


class STTBackend(str, Enum):
    """Available STT backends."""

    GPU = "gpu"
    CPU = "cpu"


@dataclass
class STTResult:
    """Result from STT transcription."""

    text: str
    confidence: float
    latency_ms: float
    backend: STTBackend
    model: str


class STTRouter:
    """Routes STT requests to GPU worker or CPU fallback.

    The router:
    1. Checks GPU worker health on startup and periodically
    2. Routes to GPU if healthy, otherwise falls back to CPU
    3. Provides unified interface for all STT consumers
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
        self._gpu_healthy = False
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

        # Start background health checker
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        self._initialized = True
        logger.info(
            "STT Router initialized",
            gpu_available=self._gpu_healthy,
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
        """Background task to periodically check GPU health."""
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self._check_gpu_health()

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
    ) -> STTResult:
        """Transcribe audio using the best available backend.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit signed integers)
            sample_rate: Audio sample rate in Hz
            language: Language code

        Returns:
            STTResult with transcription and metadata
        """
        if not self._initialized:
            await self.initialize()

        # Try GPU first if healthy
        if self._gpu_healthy:
            result = await self._transcribe_gpu(audio_data, sample_rate, language)
            if result is not None:
                return result
            # GPU failed, will fall through to CPU

        # Fallback to CPU
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

    async def transcribe_base64(
        self,
        audio_base64: str,
        sample_rate: int = 16000,
        language: str = "en",
    ) -> STTResult:
        """Transcribe base64-encoded audio.

        Convenience method for API endpoints.
        """
        audio_data = base64.b64decode(audio_base64)
        return await self.transcribe(audio_data, sample_rate, language)

    def get_status(self) -> dict:
        """Get current router status.

        Returns:
            Dict with backend availability info.
        """
        return {
            "gpu_healthy": self._gpu_healthy,
            "gpu_url": self.gpu_worker_url,
            "cpu_available": self._cpu_backend is not None and self._cpu_backend.is_available(),
            "preferred_backend": STTBackend.GPU.value
            if self._gpu_healthy
            else STTBackend.CPU.value,
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

        self._initialized = False
        logger.info("STT Router shut down")
