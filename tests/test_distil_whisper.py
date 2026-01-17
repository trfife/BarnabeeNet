"""Tests for Distil-Whisper STT service."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT


@pytest.fixture
def stt_service() -> DistilWhisperSTT:
    """Create a fresh STT service instance for testing."""
    return DistilWhisperSTT(
        model_size="distil-small.en",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
    )


@pytest.fixture
def sample_audio_16khz() -> bytes:
    """Generate sample audio data (1 second at 16kHz)."""
    # 1 second of a 440Hz sine wave at 16kHz, 16-bit PCM
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    samples = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    return samples.tobytes()


@pytest.fixture
def sample_audio_48khz() -> bytes:
    """Generate sample audio data (1 second at 48kHz)."""
    # 1 second at 48kHz (needs resampling)
    sample_rate = 48000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    samples = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    return samples.tobytes()


class TestDistilWhisperSTT:
    """Tests for DistilWhisperSTT class."""

    def test_initialization_defaults(self, stt_service: DistilWhisperSTT) -> None:
        """Test default initialization values."""
        assert stt_service.model_size == "distil-small.en"
        assert stt_service.device == "cpu"
        assert stt_service.compute_type == "int8"
        assert stt_service.cpu_threads == 4
        assert stt_service._initialized is False
        assert stt_service._model is None

    def test_custom_initialization(self) -> None:
        """Test custom initialization values."""
        stt = DistilWhisperSTT(
            model_size="distil-medium.en",
            device="cuda",
            compute_type="float16",
            cpu_threads=8,
        )
        assert stt.model_size == "distil-medium.en"
        assert stt.device == "cuda"
        assert stt.compute_type == "float16"
        assert stt.cpu_threads == 8

    def test_is_available_not_initialized(self, stt_service: DistilWhisperSTT) -> None:
        """Test is_available returns False when not initialized."""
        assert stt_service.is_available() is False

    @pytest.mark.asyncio
    async def test_initialize_loads_model(self, stt_service: DistilWhisperSTT) -> None:
        """Test that initialize loads the model."""
        mock_model = MagicMock()

        with patch("faster_whisper.WhisperModel") as mock_class:
            mock_class.return_value = mock_model

            await stt_service.initialize()

            mock_class.assert_called_once_with(
                "distil-small.en",
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
            )
            assert stt_service._initialized is True
            assert stt_service._model is mock_model

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, stt_service: DistilWhisperSTT) -> None:
        """Test that initialize only loads model once."""
        with patch("faster_whisper.WhisperModel") as mock_class:
            mock_class.return_value = MagicMock()

            await stt_service.initialize()
            await stt_service.initialize()  # Second call

            mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_returns_expected_format(
        self,
        stt_service: DistilWhisperSTT,
        sample_audio_16khz: bytes,
    ) -> None:
        """Test that transcribe returns expected result format."""
        mock_segment = MagicMock()
        mock_segment.text = " hello world "

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        stt_service._model = mock_model
        stt_service._initialized = True

        result = await stt_service.transcribe(sample_audio_16khz)

        assert "text" in result
        assert "confidence" in result
        assert "language" in result
        assert "latency_ms" in result
        assert result["text"] == "hello world"
        assert result["confidence"] == 0.95
        assert result["language"] == "en"
        assert result["latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_transcribe_handles_resampling(
        self,
        stt_service: DistilWhisperSTT,
        sample_audio_48khz: bytes,
    ) -> None:
        """Test that transcribe handles non-16kHz audio."""
        mock_segment = MagicMock()
        mock_segment.text = "test"

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        stt_service._model = mock_model
        stt_service._initialized = True

        # Should not raise, even with 48kHz audio
        result = await stt_service.transcribe(sample_audio_48khz, sample_rate=48000)

        assert result["text"] == "test"
        # Verify transcribe was called (audio was processed)
        mock_model.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_multiple_segments(
        self,
        stt_service: DistilWhisperSTT,
        sample_audio_16khz: bytes,
    ) -> None:
        """Test transcription with multiple segments."""
        segment1 = MagicMock()
        segment1.text = " hello "
        segment2 = MagicMock()
        segment2.text = " world "

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([segment1, segment2], mock_info)

        stt_service._model = mock_model
        stt_service._initialized = True

        result = await stt_service.transcribe(sample_audio_16khz)

        assert result["text"] == "hello world"

    @pytest.mark.asyncio
    async def test_transcribe_base64(
        self,
        stt_service: DistilWhisperSTT,
        sample_audio_16khz: bytes,
    ) -> None:
        """Test transcribe_base64 convenience method."""
        audio_base64 = base64.b64encode(sample_audio_16khz).decode("utf-8")

        mock_segment = MagicMock()
        mock_segment.text = "base64 test"

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.92

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        stt_service._model = mock_model
        stt_service._initialized = True

        result = await stt_service.transcribe_base64(audio_base64)

        assert result["text"] == "base64 test"

    @pytest.mark.asyncio
    async def test_shutdown(self, stt_service: DistilWhisperSTT) -> None:
        """Test shutdown cleans up resources."""
        stt_service._model = MagicMock()
        stt_service._initialized = True

        await stt_service.shutdown()

        assert stt_service._model is None
        assert stt_service._initialized is False

    def test_is_available_when_initialized(self, stt_service: DistilWhisperSTT) -> None:
        """Test is_available returns True when initialized."""
        stt_service._model = MagicMock()
        stt_service._initialized = True

        assert stt_service.is_available() is True
