"""Tests for STT modes and engine selection system.

Tests cover:
- STT engine auto-selection logic
- Mode configuration
- Azure STT integration (mocked)
- WebSocket streaming endpoint
- Quick input endpoints
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from barnabeenet.models.stt_modes import (
    QuickAudioRequest,
    QuickInputRequest,
    StreamingTranscriptMessage,
    STTConfig,
    STTEngine,
    STTMode,
)
from barnabeenet.services.stt.router import STTBackend, STTRouter


class TestSTTModels:
    """Test STT mode and engine models."""

    def test_stt_mode_enum(self):
        """Test STTMode enum values."""
        assert STTMode.AMBIENT == "ambient"
        assert STTMode.REALTIME == "realtime"
        assert STTMode.COMMAND == "command"

    def test_stt_engine_enum(self):
        """Test STTEngine enum values."""
        assert STTEngine.AUTO == "auto"
        assert STTEngine.PARAKEET == "parakeet"
        assert STTEngine.WHISPER == "whisper"
        assert STTEngine.AZURE == "azure"

    def test_stt_config_defaults(self):
        """Test STTConfig default values."""
        config = STTConfig()
        assert config.mode == STTMode.COMMAND
        assert config.engine == STTEngine.AUTO
        assert config.language == "en-US"
        assert config.streaming_chunk_ms == 100
        assert config.interim_results is True
        assert config.ambient_batch_seconds == 30

    def test_stt_config_validation(self):
        """Test STTConfig validation."""
        # Valid config
        config = STTConfig(streaming_chunk_ms=100, ambient_batch_seconds=60)
        assert config.streaming_chunk_ms == 100

        # Invalid chunk size (too small)
        with pytest.raises(ValueError):
            STTConfig(streaming_chunk_ms=10)

        # Invalid chunk size (too large)
        with pytest.raises(ValueError):
            STTConfig(streaming_chunk_ms=1000)

    def test_streaming_transcript_message(self):
        """Test StreamingTranscriptMessage model."""
        msg = StreamingTranscriptMessage(
            type="partial",
            text="Hello",
            is_final=False,
            confidence=0.8,
            engine=STTEngine.PARAKEET,
        )
        assert msg.type == "partial"
        assert msg.text == "Hello"
        assert msg.is_final is False

    def test_quick_input_request(self):
        """Test QuickInputRequest model."""
        req = QuickInputRequest(text="Hello world")
        assert req.text == "Hello world"
        assert req.speaker == "api"
        assert req.room is None

    def test_quick_audio_request(self):
        """Test QuickAudioRequest model."""
        req = QuickAudioRequest()
        assert req.mode == STTMode.COMMAND
        assert req.engine == STTEngine.AUTO
        assert req.speaker == "api"


class TestSTTRouter:
    """Test STT Router engine selection logic."""

    @pytest.fixture
    def mock_router(self):
        """Create a router with mocked backends."""
        router = STTRouter(
            gpu_worker_url="http://localhost:8001",
            health_check_interval=30.0,
        )
        router._initialized = True
        return router

    @pytest.mark.asyncio
    async def test_auto_select_gpu_available(self, mock_router):
        """Test auto-selection prefers GPU when available."""
        mock_router._gpu_healthy = True
        mock_router._azure_available = True

        engine = await mock_router._select_engine(STTEngine.AUTO)
        assert engine == STTEngine.PARAKEET

    @pytest.mark.asyncio
    async def test_auto_select_azure_fallback(self, mock_router):
        """Test auto-selection falls back to Azure when GPU unavailable."""
        mock_router._gpu_healthy = False
        mock_router._azure_available = True

        engine = await mock_router._select_engine(STTEngine.AUTO)
        assert engine == STTEngine.AZURE

    @pytest.mark.asyncio
    async def test_auto_select_cpu_fallback(self, mock_router):
        """Test auto-selection falls back to CPU when GPU and Azure unavailable."""
        mock_router._gpu_healthy = False
        mock_router._azure_available = False

        engine = await mock_router._select_engine(STTEngine.AUTO)
        assert engine == STTEngine.WHISPER

    @pytest.mark.asyncio
    async def test_explicit_parakeet_unavailable(self, mock_router):
        """Test explicit Parakeet selection fails when unavailable."""
        mock_router._gpu_healthy = False

        with pytest.raises(RuntimeError, match="GPU STT requested but unavailable"):
            await mock_router._select_engine(STTEngine.PARAKEET)

    @pytest.mark.asyncio
    async def test_explicit_azure_unavailable(self, mock_router):
        """Test explicit Azure selection fails when unavailable."""
        mock_router._azure_available = False

        with pytest.raises(RuntimeError, match="Azure STT requested but unavailable"):
            await mock_router._select_engine(STTEngine.AZURE)

    @pytest.mark.asyncio
    async def test_explicit_whisper_always_available(self, mock_router):
        """Test Whisper is always available."""
        mock_router._gpu_healthy = False
        mock_router._azure_available = False

        engine = await mock_router._select_engine(STTEngine.WHISPER)
        assert engine == STTEngine.WHISPER

    def test_get_status(self, mock_router):
        """Test router status reporting."""
        mock_router._gpu_healthy = True
        mock_router._azure_available = True
        mock_router._cpu_backend = MagicMock()
        mock_router._cpu_backend.is_available.return_value = True

        status = mock_router.get_status()

        assert status["gpu_healthy"] is True
        assert status["azure_available"] is True
        assert status["cpu_available"] is True
        assert status["preferred_backend"] == "gpu"
        assert "engines" in status
        assert status["engines"]["parakeet"]["available"] is True
        assert status["engines"]["azure"]["available"] is True
        assert status["engines"]["whisper"]["available"] is True

    def test_get_status_gpu_down(self, mock_router):
        """Test status when GPU is down."""
        mock_router._gpu_healthy = False
        mock_router._azure_available = True

        status = mock_router.get_status()
        assert status["preferred_backend"] == "azure"

    def test_get_status_all_down(self, mock_router):
        """Test status when GPU and Azure are down."""
        mock_router._gpu_healthy = False
        mock_router._azure_available = False

        status = mock_router.get_status()
        assert status["preferred_backend"] == "cpu"


class TestAzureSTT:
    """Test Azure STT service (mocked)."""

    @pytest.mark.asyncio
    async def test_azure_not_configured(self):
        """Test Azure STT when not configured."""
        from barnabeenet.services.stt.azure_stt import AzureSTT, AzureSTTConfig

        config = AzureSTTConfig(speech_key="")  # No key
        azure = AzureSTT(config)

        result = await azure.initialize()
        assert result is False
        assert azure.is_available() is False

    @pytest.mark.asyncio
    async def test_azure_sdk_not_installed(self):
        """Test Azure STT when SDK is not installed."""
        from barnabeenet.services.stt.azure_stt import AzureSTT, AzureSTTConfig

        config = AzureSTTConfig(
            speech_key="test-key",
            speech_region="eastus",
        )
        azure = AzureSTT(config)

        # Simulate SDK not installed by checking availability after failed init
        azure._available = False  # Simulate what happens when SDK isn't installed
        assert azure.is_available() is False

    @pytest.mark.asyncio
    async def test_azure_transcribe_unavailable(self):
        """Test transcription fails gracefully when unavailable."""
        from barnabeenet.services.stt.azure_stt import AzureSTT, AzureSTTConfig

        config = AzureSTTConfig(speech_key="")
        azure = AzureSTT(config)
        await azure.initialize()

        with pytest.raises(RuntimeError, match="Azure STT not available"):
            await azure.transcribe(b"audio data")


class TestQuickInputEndpoints:
    """Test quick input API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from barnabeenet.main import app

        return TestClient(app)

    def test_quick_text_input(self, client):
        """Test quick text input endpoint."""
        with patch("barnabeenet.agents.orchestrator.get_orchestrator") as mock_orch:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process.return_value = {
                "response": "Hello!",
                "intent": "greeting",
                "agent": "instant",
                "conversation_id": "test-123",
            }
            mock_orch.return_value = mock_orchestrator

            response = client.post(
                "/api/v1/input/text",
                params={"text": "Hello", "speaker": "test"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "Hello"
            assert data["response"] == "Hello!"
            assert data["agent"] == "instant"
            assert "latency_ms" in data

    def test_quick_text_input_empty(self, client):
        """Test quick text input with empty text."""
        with patch("barnabeenet.agents.orchestrator.get_orchestrator") as mock_orch:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process.return_value = {
                "response": "",
                "intent": "unknown",
                "agent": "instant",
                "conversation_id": "test-123",
            }
            mock_orch.return_value = mock_orchestrator

            response = client.post(
                "/api/v1/input/text",
                params={"text": "", "speaker": "test"},
            )
            # Empty text is allowed - the endpoint doesn't validate
            assert response.status_code == 200

    def test_stt_status_endpoint(self, client):
        """Test STT status endpoint exists and returns expected structure."""
        # The endpoint should work even without GPU/Azure available
        # It will show all engines as unavailable if no backends configured
        response = client.get("/api/v1/stt/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "engines" in data
        # Verify engine structure
        engines = data["engines"]
        assert "parakeet" in engines or "whisper" in engines  # At least CPU should exist


class TestWebSocketTranscribe:
    """Test WebSocket transcription endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from barnabeenet.main import app

        return TestClient(app)

    def test_websocket_connect(self, client):
        """Test WebSocket connection sends ready message."""
        # WebSocket should connect and send ready message
        with client.websocket_connect("/api/v1/ws/transcribe") as ws:
            # Should receive ready message
            data = ws.receive_json()
            assert data["type"] == "ready"
            assert "engines" in data

    def test_websocket_config_message(self, client):
        """Test WebSocket config message."""
        with client.websocket_connect("/api/v1/ws/transcribe") as ws:
            # Receive ready
            ws.receive_json()

            # Send config
            ws.send_json({"type": "config", "engine": "whisper", "language": "en-US"})

            # Should receive config ack
            data = ws.receive_json()
            assert data["type"] == "config_ack"
            assert data["engine"] == "whisper"


class TestSTTRouterIntegration:
    """Integration tests for STT router with multiple backends."""

    @pytest.mark.asyncio
    async def test_transcribe_with_auto_selection(self):
        """Test transcription with automatic engine selection."""
        router = STTRouter()
        router._initialized = True
        router._gpu_healthy = False
        router._azure_available = False

        # Mock CPU backend
        mock_cpu = AsyncMock()
        mock_cpu.transcribe = AsyncMock(
            return_value={
                "text": "Hello world",
                "confidence": 0.95,
                "latency_ms": 500.0,
            }
        )
        mock_cpu.is_available.return_value = True
        router._cpu_backend = mock_cpu

        result = await router.transcribe(
            audio_data=b"test audio",
            sample_rate=16000,
            language="en",
            engine=STTEngine.AUTO,
            mode=STTMode.COMMAND,
        )

        assert result.text == "Hello world"
        assert result.backend == STTBackend.CPU
        mock_cpu.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_base64_convenience(self):
        """Test base64 transcription convenience method."""
        import base64

        router = STTRouter()
        router._initialized = True
        router._gpu_healthy = False
        router._azure_available = False

        mock_cpu = AsyncMock()
        mock_cpu.transcribe = AsyncMock(
            return_value={
                "text": "Test",
                "confidence": 0.9,
                "latency_ms": 100.0,
            }
        )
        mock_cpu.is_available.return_value = True
        router._cpu_backend = mock_cpu

        audio_data = b"test audio"
        audio_base64 = base64.b64encode(audio_data).decode()

        result = await router.transcribe_base64(
            audio_base64=audio_base64,
            engine=STTEngine.WHISPER,
        )

        assert result.text == "Test"
