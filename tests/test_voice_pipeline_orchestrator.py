"""Tests for voice pipeline integration with AgentOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.models.schemas import AudioFormat, VoicePipelineRequest


@pytest.fixture
def mock_app_state():
    """Mock app state with GPU worker unavailable."""
    mock_state = MagicMock()
    mock_state.gpu_worker_available = False
    return mock_state


@pytest.fixture
def mock_stt():
    """Mock STT service."""
    stt = AsyncMock()
    stt.is_available.return_value = True
    stt.transcribe.return_value = {
        "text": "what time is it",
        "confidence": 0.95,
    }
    return stt


@pytest.fixture
def mock_tts():
    """Mock TTS service."""
    tts = AsyncMock()
    tts.is_available.return_value = True
    tts.synthesize.return_value = {
        "audio_bytes": b"fake_audio_data",
        "sample_rate": 24000,
        "duration_ms": 500.0,
    }
    return tts


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator."""
    orchestrator = AsyncMock()
    orchestrator.process.return_value = {
        "response": "The current time is 3:45 PM.",
        "intent": "instant",
        "agent": "instant",
        "request_id": "abc12345",
        "conversation_id": "conv_xyz789",
    }
    return orchestrator


class TestVoicePipelineOrchestratorIntegration:
    """Tests for voice pipeline + orchestrator integration."""

    @pytest.mark.asyncio
    async def test_pipeline_uses_orchestrator(
        self, mock_app_state, mock_stt, mock_tts, mock_orchestrator
    ):
        """Voice pipeline should dispatch to orchestrator."""
        with (
            patch("barnabeenet.main.app_state", mock_app_state),
            patch(
                "barnabeenet.services.voice_pipeline.DistilWhisperSTT",
                return_value=mock_stt,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.KokoroTTS",
                return_value=mock_tts,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.get_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            from barnabeenet.services.voice_pipeline import VoicePipelineService

            request = VoicePipelineRequest(
                audio_base64="ZmFrZV9hdWRpb19kYXRh",  # base64 encoded "fake_audio_data"
                language="en",
                speaker="thomas",
                room="living_room",
                conversation_id="conv_123",
            )

            response = await VoicePipelineService.run(request)

            # Orchestrator was called with correct params
            mock_orchestrator.process.assert_called_once_with(
                text="what time is it",
                speaker="thomas",
                room="living_room",
                conversation_id="conv_123",
            )

            # Response contains orchestrator output
            assert response.response_text == "The current time is 3:45 PM."
            assert response.intent == "instant"
            assert response.agent == "instant"
            assert response.request_id == "abc12345"
            assert response.conversation_id == "conv_xyz789"

    @pytest.mark.asyncio
    async def test_pipeline_includes_orchestrator_fields_in_response(
        self, mock_app_state, mock_stt, mock_tts, mock_orchestrator
    ):
        """Response should include intent, agent, and IDs from orchestrator."""
        mock_orchestrator.process.return_value = {
            "response": "Turning on the lights.",
            "intent": "action",
            "agent": "action",
            "request_id": "req_action",
            "conversation_id": "conv_action",
        }

        with (
            patch("barnabeenet.main.app_state", mock_app_state),
            patch(
                "barnabeenet.services.voice_pipeline.DistilWhisperSTT",
                return_value=mock_stt,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.KokoroTTS",
                return_value=mock_tts,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.get_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            from barnabeenet.services.voice_pipeline import VoicePipelineService

            request = VoicePipelineRequest(
                audio_base64="ZmFrZV9hdWRpb19kYXRh",
                language="en",
            )

            response = await VoicePipelineService.run(request)

            assert response.intent == "action"
            assert response.agent == "action"
            assert response.request_id == "req_action"

    @pytest.mark.asyncio
    async def test_pipeline_passes_speaker_and_room_to_orchestrator(
        self, mock_app_state, mock_stt, mock_tts, mock_orchestrator
    ):
        """Speaker and room context should be passed to orchestrator."""
        with (
            patch("barnabeenet.main.app_state", mock_app_state),
            patch(
                "barnabeenet.services.voice_pipeline.DistilWhisperSTT",
                return_value=mock_stt,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.KokoroTTS",
                return_value=mock_tts,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.get_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            from barnabeenet.services.voice_pipeline import VoicePipelineService

            request = VoicePipelineRequest(
                audio_base64="ZmFrZV9hdWRpb19kYXRh",
                language="en",
                speaker="viola",
                room="kitchen",
            )

            await VoicePipelineService.run(request)

            call_kwargs = mock_orchestrator.process.call_args.kwargs
            assert call_kwargs["speaker"] == "viola"
            assert call_kwargs["room"] == "kitchen"

    @pytest.mark.asyncio
    async def test_pipeline_handles_orchestrator_without_optional_fields(
        self, mock_app_state, mock_stt, mock_tts
    ):
        """Pipeline handles orchestrator response missing optional fields."""
        minimal_orchestrator = AsyncMock()
        minimal_orchestrator.process.return_value = {
            "response": "Hello there!",
        }

        with (
            patch("barnabeenet.main.app_state", mock_app_state),
            patch(
                "barnabeenet.services.voice_pipeline.DistilWhisperSTT",
                return_value=mock_stt,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.KokoroTTS",
                return_value=mock_tts,
            ),
            patch(
                "barnabeenet.services.voice_pipeline.get_orchestrator",
                return_value=minimal_orchestrator,
            ),
        ):
            from barnabeenet.services.voice_pipeline import VoicePipelineService

            request = VoicePipelineRequest(
                audio_base64="ZmFrZV9hdWRpb19kYXRh",
                language="en",
            )

            response = await VoicePipelineService.run(request)

            # Should have defaults for missing fields
            assert response.response_text == "Hello there!"
            assert response.intent == "unknown"
            assert response.agent == "unknown"


class TestVoicePipelineRequestFields:
    """Tests for VoicePipelineRequest schema updates."""

    def test_request_accepts_speaker_field(self):
        """Request should accept speaker field."""
        request = VoicePipelineRequest(
            audio_base64="test",
            speaker="thomas",
        )
        assert request.speaker == "thomas"

    def test_request_accepts_room_field(self):
        """Request should accept room field."""
        request = VoicePipelineRequest(
            audio_base64="test",
            room="bedroom",
        )
        assert request.room == "bedroom"

    def test_request_accepts_conversation_id_field(self):
        """Request should accept conversation_id field."""
        request = VoicePipelineRequest(
            audio_base64="test",
            conversation_id="conv_123",
        )
        assert request.conversation_id == "conv_123"

    def test_request_context_fields_are_optional(self):
        """Speaker, room, and conversation_id should be optional."""
        request = VoicePipelineRequest(audio_base64="test")
        assert request.speaker is None
        assert request.room is None
        assert request.conversation_id is None


class TestVoicePipelineResponseFields:
    """Tests for VoicePipelineResponse schema updates."""

    def test_response_includes_intent_field(self):
        """Response should include intent field."""
        from barnabeenet.models.schemas import STTEngine, VoicePipelineResponse

        response = VoicePipelineResponse(
            input_text="hello",
            stt_engine=STTEngine.PARAKEET,
            stt_latency_ms=50.0,
            response_text="Hi there!",
            intent="conversation",
            agent="interaction",
            audio_base64="dGVzdA==",
            tts_latency_ms=100.0,
            total_latency_ms=150.0,
            sample_rate=24000,
            format=AudioFormat.WAV,
        )

        assert response.intent == "conversation"
        assert response.agent == "interaction"

    def test_response_intent_defaults_to_unknown(self):
        """Intent and agent should default to unknown."""
        from barnabeenet.models.schemas import STTEngine, VoicePipelineResponse

        response = VoicePipelineResponse(
            input_text="hello",
            stt_engine=STTEngine.PARAKEET,
            stt_latency_ms=50.0,
            response_text="Hi!",
            audio_base64="dGVzdA==",
            tts_latency_ms=100.0,
            total_latency_ms=150.0,
            sample_rate=24000,
            format=AudioFormat.WAV,
        )

        assert response.intent == "unknown"
        assert response.agent == "unknown"
