"""Tests for STT Router."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.services.stt.router import STTBackend, STTResult, STTRouter


@pytest.fixture
def router() -> STTRouter:
    """Create a fresh router instance for testing."""
    return STTRouter(
        gpu_worker_url="http://localhost:8001",
        health_check_interval=60.0,  # Long interval to avoid background checks during tests
        request_timeout=5.0,
    )


@pytest.fixture
def sample_audio() -> bytes:
    """Generate sample audio data (1 second of silence)."""
    import numpy as np

    # 1 second of silence at 16kHz, 16-bit PCM
    samples = np.zeros(16000, dtype=np.int16)
    return samples.tobytes()


class TestSTTRouter:
    """Tests for STTRouter class."""

    @pytest.mark.asyncio
    async def test_router_initialization(self, router: STTRouter) -> None:
        """Test that router initializes correctly."""
        assert router._initialized is False
        assert router._gpu_healthy is False
        assert router._cpu_backend is None

    @pytest.mark.asyncio
    async def test_get_status_not_initialized(self, router: STTRouter) -> None:
        """Test status before initialization."""
        status = router.get_status()
        assert status["gpu_healthy"] is False
        assert status["cpu_available"] is False
        assert status["preferred_backend"] == STTBackend.CPU.value

    @pytest.mark.asyncio
    async def test_gpu_health_check_success(self, router: STTRouter) -> None:
        """Test successful GPU health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "model_loaded": True,
            "gpu_name": "RTX 4070 Ti",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            router._http_client = mock_client
            result = await router._check_gpu_health()

            assert result is True
            assert router._gpu_healthy is True

    @pytest.mark.asyncio
    async def test_gpu_health_check_failure(self, router: STTRouter) -> None:
        """Test failed GPU health check."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client_class.return_value = mock_client

            router._http_client = mock_client
            result = await router._check_gpu_health()

            assert result is False
            assert router._gpu_healthy is False

    @pytest.mark.asyncio
    async def test_transcribe_falls_back_to_cpu_when_gpu_unavailable(
        self,
        router: STTRouter,
        sample_audio: bytes,
    ) -> None:
        """Test that transcription falls back to CPU when GPU is unavailable."""
        # Mock CPU backend
        mock_cpu_backend = AsyncMock()
        mock_cpu_backend.is_available.return_value = True
        mock_cpu_backend.transcribe = AsyncMock(
            return_value={
                "text": "hello world",
                "confidence": 0.95,
                "language": "en",
                "latency_ms": 2400.0,
            }
        )

        router._initialized = True
        router._gpu_healthy = False
        router._cpu_backend = mock_cpu_backend

        result = await router.transcribe(sample_audio)

        assert isinstance(result, STTResult)
        assert result.text == "hello world"
        assert result.backend == STTBackend.CPU
        assert result.latency_ms == 2400.0
        mock_cpu_backend.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_uses_gpu_when_healthy(
        self,
        router: STTRouter,
        sample_audio: bytes,
    ) -> None:
        """Test that transcription uses GPU when available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "hello world",
            "confidence": 0.98,
            "latency_ms": 45.0,
            "model": "nvidia/parakeet-tdt-0.6b-v2",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        router._initialized = True
        router._gpu_healthy = True
        router._http_client = mock_client

        result = await router.transcribe(sample_audio)

        assert isinstance(result, STTResult)
        assert result.text == "hello world"
        assert result.backend == STTBackend.GPU
        assert result.latency_ms == 45.0
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_base64(self, router: STTRouter, sample_audio: bytes) -> None:
        """Test transcribe_base64 convenience method."""
        audio_base64 = base64.b64encode(sample_audio).decode("utf-8")

        # Mock CPU backend (GPU not healthy)
        mock_cpu_backend = AsyncMock()
        mock_cpu_backend.is_available.return_value = True
        mock_cpu_backend.transcribe = AsyncMock(
            return_value={
                "text": "test",
                "confidence": 0.9,
                "language": "en",
                "latency_ms": 1000.0,
            }
        )

        router._initialized = True
        router._gpu_healthy = False
        router._cpu_backend = mock_cpu_backend

        result = await router.transcribe_base64(audio_base64)

        assert isinstance(result, STTResult)
        assert result.text == "test"

    @pytest.mark.asyncio
    async def test_shutdown(self, router: STTRouter) -> None:
        """Test router shutdown cleans up resources."""
        mock_client = AsyncMock()
        mock_cpu = AsyncMock()

        router._http_client = mock_client
        router._cpu_backend = mock_cpu
        router._initialized = True

        await router.shutdown()

        mock_client.aclose.assert_called_once()
        mock_cpu.shutdown.assert_called_once()
        assert router._initialized is False


class TestSTTResult:
    """Tests for STTResult dataclass."""

    def test_stt_result_creation(self) -> None:
        """Test STTResult can be created."""
        result = STTResult(
            text="hello",
            confidence=0.95,
            latency_ms=45.0,
            backend=STTBackend.GPU,
            model="nvidia/parakeet-tdt-0.6b-v2",
        )
        assert result.text == "hello"
        assert result.confidence == 0.95
        assert result.backend == STTBackend.GPU


class TestSTTBackend:
    """Tests for STTBackend enum."""

    def test_backend_values(self) -> None:
        """Test backend enum values."""
        assert STTBackend.GPU.value == "gpu"
        assert STTBackend.CPU.value == "cpu"
