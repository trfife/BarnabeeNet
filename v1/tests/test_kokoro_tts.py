"""Tests for Kokoro TTS service."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from barnabeenet.services.tts.kokoro_tts import KokoroTTS


@pytest.fixture
def tts_service() -> KokoroTTS:
    """Create a fresh TTS service instance for testing."""
    return KokoroTTS(
        voice="bm_fable",
        speed=1.0,
        lang_code="b",
    )


class TestKokoroTTS:
    """Tests for KokoroTTS class."""

    def test_initialization_defaults(self, tts_service: KokoroTTS) -> None:
        """Test default initialization values."""
        assert tts_service.voice == "bm_fable"
        assert tts_service.speed == 1.0
        assert tts_service.lang_code == "b"
        assert tts_service.sample_rate == 24000
        assert tts_service._initialized is False
        assert tts_service._pipeline is None

    def test_custom_initialization(self) -> None:
        """Test custom initialization values."""
        tts = KokoroTTS(
            voice="bf_emma",
            speed=1.2,
            lang_code="a",
        )
        assert tts.voice == "bf_emma"
        assert tts.speed == 1.2
        assert tts.lang_code == "a"

    def test_voices_available(self, tts_service: KokoroTTS) -> None:
        """Test that voices dictionary is populated."""
        voices = tts_service.get_voices()
        assert "bm_fable" in voices
        assert "bf_emma" in voices
        assert "bm_daniel" in voices
        assert len(voices) == 8  # 8 voices defined

    def test_is_available_not_initialized(self, tts_service: KokoroTTS) -> None:
        """Test is_available returns False when not initialized."""
        assert tts_service.is_available() is False

    @pytest.mark.asyncio
    async def test_initialize_loads_pipeline(self, tts_service: KokoroTTS) -> None:
        """Test that initialize loads the pipeline."""
        mock_pipeline = MagicMock()

        with patch("kokoro.KPipeline") as mock_class:
            mock_class.return_value = mock_pipeline

            await tts_service.initialize()

            mock_class.assert_called_once_with(lang_code="b")
            assert tts_service._initialized is True
            assert tts_service._pipeline is mock_pipeline

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, tts_service: KokoroTTS) -> None:
        """Test that initialize only loads pipeline once."""
        with patch("kokoro.KPipeline") as mock_class:
            mock_class.return_value = MagicMock()

            await tts_service.initialize()
            await tts_service.initialize()  # Second call

            mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_returns_expected_format(self, tts_service: KokoroTTS) -> None:
        """Test that synthesize returns expected result format."""
        # Create mock audio output (1 second at 24kHz)
        mock_audio = np.zeros(24000, dtype=np.float32)

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter([("graphemes", "phonemes", mock_audio)])

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        result = await tts_service.synthesize("Hello world")

        assert "audio_bytes" in result
        assert "audio_base64" in result
        assert "sample_rate" in result
        assert "duration_ms" in result
        assert "latency_ms" in result
        assert result["sample_rate"] == 24000
        assert result["duration_ms"] > 0
        assert result["latency_ms"] > 0
        assert len(result["audio_bytes"]) > 0
        assert len(result["audio_base64"]) > 0

    @pytest.mark.asyncio
    async def test_synthesize_applies_pronunciation(self, tts_service: KokoroTTS) -> None:
        """Test that pronunciation corrections are applied."""
        mock_audio = np.zeros(24000, dtype=np.float32)

        mock_pipeline = MagicMock()
        # Capture what text was passed to the pipeline
        calls = []

        def capture_call(text, voice, speed):
            calls.append(text)
            return iter([("g", "p", mock_audio)])

        mock_pipeline.side_effect = capture_call

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        # "Viola" should be converted to "Vyola"
        await tts_service.synthesize("Hello Viola")

        assert len(calls) == 1
        assert "Vyola" in calls[0]
        assert "Viola" not in calls[0]

    @pytest.mark.asyncio
    async def test_synthesize_voice_override(self, tts_service: KokoroTTS) -> None:
        """Test that voice can be overridden per call."""
        mock_audio = np.zeros(24000, dtype=np.float32)

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter([("g", "p", mock_audio)])

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        await tts_service.synthesize("Hello", voice="bf_emma")

        # Check that pipeline was called with the override voice
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args
        assert call_kwargs[1]["voice"] == "bf_emma"

    @pytest.mark.asyncio
    async def test_synthesize_speed_override(self, tts_service: KokoroTTS) -> None:
        """Test that speed can be overridden per call."""
        mock_audio = np.zeros(24000, dtype=np.float32)

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter([("g", "p", mock_audio)])

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        await tts_service.synthesize("Hello", speed=1.5)

        # Check that pipeline was called with the override speed
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args
        assert call_kwargs[1]["speed"] == 1.5

    @pytest.mark.asyncio
    async def test_synthesize_multiple_chunks(self, tts_service: KokoroTTS) -> None:
        """Test synthesis with multiple audio chunks."""
        chunk1 = np.zeros(12000, dtype=np.float32)
        chunk2 = np.zeros(12000, dtype=np.float32)

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter(
            [
                ("g1", "p1", chunk1),
                ("g2", "p2", chunk2),
            ]
        )

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        result = await tts_service.synthesize("Long text here")

        # Duration should be ~1 second (24000 samples at 24kHz)
        assert result["duration_ms"] == pytest.approx(1000, rel=0.1)

    @pytest.mark.asyncio
    async def test_synthesize_empty_result(self, tts_service: KokoroTTS) -> None:
        """Test synthesis with no audio generated."""
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter([])  # No chunks

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        result = await tts_service.synthesize("")

        assert result["audio_bytes"] == b""
        assert result["audio_base64"] == ""
        assert result["duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_shutdown(self, tts_service: KokoroTTS) -> None:
        """Test shutdown cleans up resources."""
        tts_service._pipeline = MagicMock()
        tts_service._initialized = True

        await tts_service.shutdown()

        assert tts_service._pipeline is None
        assert tts_service._initialized is False

    def test_is_available_when_initialized(self, tts_service: KokoroTTS) -> None:
        """Test is_available returns True when initialized."""
        tts_service._pipeline = MagicMock()
        tts_service._initialized = True

        assert tts_service.is_available() is True

    def test_get_voices_returns_copy(self, tts_service: KokoroTTS) -> None:
        """Test that get_voices returns a copy, not the original."""
        voices1 = tts_service.get_voices()
        voices2 = tts_service.get_voices()

        # Modifying one shouldn't affect the other
        voices1["test"] = "value"
        assert "test" not in voices2

    @pytest.mark.asyncio
    async def test_audio_is_valid_wav(self, tts_service: KokoroTTS) -> None:
        """Test that output audio is valid WAV format."""
        mock_audio = np.sin(np.linspace(0, 2 * np.pi * 440, 24000)).astype(np.float32)

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = iter([("g", "p", mock_audio)])

        tts_service._pipeline = mock_pipeline
        tts_service._initialized = True

        result = await tts_service.synthesize("Test")

        # WAV files start with "RIFF"
        assert result["audio_bytes"][:4] == b"RIFF"

        # Can decode base64 back to same bytes
        decoded = base64.b64decode(result["audio_base64"])
        assert decoded == result["audio_bytes"]
