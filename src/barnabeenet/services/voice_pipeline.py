from __future__ import annotations

import asyncio
import base64
import time

import httpx
import structlog

from barnabeenet.agents.orchestrator import get_orchestrator
from barnabeenet.config import get_settings
from barnabeenet.models.schemas import (
    STTEngine,
    VoicePipelineRequest,
    VoicePipelineResponse,
)
from barnabeenet.services.stt import DistilWhisperSTT
from barnabeenet.services.tts import KokoroTTS

logger = structlog.get_logger()


class VoicePipelineService:
    """Simple pipeline: audio in -> STT -> process -> TTS -> audio out.

    Phase 1 behaviour: echo back the transcribed text.
    """

    @staticmethod
    async def run(request: VoicePipelineRequest) -> VoicePipelineResponse:
        total_start = time.perf_counter()

        # Decode audio
        audio_bytes = base64.b64decode(request.audio_base64)

        # Parallel STT + Speaker ID (preparation for future ECAPA-TDNN)
        # Currently speaker ID is contextual (from HA), but structure allows for voice-based ID
        async def transcribe_audio() -> tuple[str, STTEngine]:
            """Transcribe audio using available STT engine."""
            from barnabeenet.main import app_state

            use_gpu = app_state.gpu_worker_available

            if use_gpu:
                try:
                    settings = get_settings()
                    url = f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}/transcribe"
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            url,
                            json={
                                "audio_base64": base64.b64encode(audio_bytes).decode(),
                                "language": request.language,
                            },
                            timeout=settings.performance.stt_timeout_ms / 1000,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        return data.get("text", ""), STTEngine.PARAKEET
                except Exception as exc:  # pragma: no cover - best-effort fallback
                    logger.warning("GPU STT failed, falling back to CPU", error=str(exc))
                    use_gpu = False

            if not use_gpu:
                stt = DistilWhisperSTT(model_size=get_settings().stt.whisper_model)
                if not stt.is_available():
                    await stt.initialize()
                res = await stt.transcribe(audio_bytes, language=request.language)
                return res["text"], STTEngine.DISTIL_WHISPER

        async def identify_speaker_voice() -> tuple[str, float]:
            """Identify speaker from audio (placeholder for future ECAPA-TDNN).
            
            Currently returns contextual speaker from request.
            Future: Will use ECAPA-TDNN model to identify speaker from voice.
            """
            # TODO: Implement ECAPA-TDNN speaker identification
            # For now, use contextual speaker from HA
            if request.speaker:
                return request.speaker, 1.0
            return "unknown", 0.0

        # Run STT and speaker ID in parallel
        stt_start = time.perf_counter()
        stt_task = asyncio.create_task(transcribe_audio())
        speaker_task = asyncio.create_task(identify_speaker_voice())
        
        input_text, engine_used = await stt_task
        identified_speaker, speaker_confidence = await speaker_task
        
        stt_latency_ms = (time.perf_counter() - stt_start) * 1000
        
        # Use identified speaker if available, otherwise fall back to request.speaker
        final_speaker = identified_speaker if identified_speaker != "unknown" else request.speaker

        # Process: dispatch to AgentOrchestrator (full multi-agent pipeline)
        orchestrator = get_orchestrator()
        orchestrator_resp = await orchestrator.process(
            text=input_text,
            speaker=final_speaker,  # Use identified speaker
            room=request.room,
            conversation_id=request.conversation_id,
        )

        response_text = orchestrator_resp.get("response", f"You said: {input_text}")
        agent_used = orchestrator_resp.get("agent", "unknown")
        intent = orchestrator_resp.get("intent", "unknown")

        logger.info(
            "Orchestrator processed request",
            agent=agent_used,
            intent=intent,
            input_text=input_text[:50],
            response_text=response_text[:50],
        )

        # TTS
        tts = KokoroTTS(voice=request.response_voice or get_settings().tts.voice)
        if not tts.is_available():
            await tts.initialize()
        synth_start = time.perf_counter()
        synth_res = await tts.synthesize(
            text=response_text, voice=request.response_voice, speed=1.0
        )
        tts_latency_ms = (time.perf_counter() - synth_start) * 1000

        total_latency_ms = (time.perf_counter() - total_start) * 1000

        return VoicePipelineResponse(
            input_text=input_text,
            stt_engine=engine_used,
            stt_latency_ms=stt_latency_ms,
            response_text=response_text,
            intent=intent,
            agent=agent_used,
            request_id=orchestrator_resp.get("request_id"),
            conversation_id=orchestrator_resp.get("conversation_id"),
            audio_base64=synth_res["audio_base64"]
            if "audio_base64" in synth_res
            else base64.b64encode(synth_res["audio_bytes"]).decode(),
            tts_latency_ms=tts_latency_ms,
            total_latency_ms=total_latency_ms,
            sample_rate=synth_res.get("sample_rate", get_settings().tts.sample_rate),
            format=request.output_format,
        )


__all__ = ["VoicePipelineService"]
