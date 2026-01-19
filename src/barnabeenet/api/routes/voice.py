"""Voice API routes - STT, TTS, and full pipeline."""

from __future__ import annotations

import base64
import time

import structlog
from fastapi import APIRouter, HTTPException

from barnabeenet.config import get_settings
from barnabeenet.models.schemas import (
    AudioFormat,
    ErrorDetail,
    LLMDetails,
    STTEngine,
    SynthesizeRequest,
    SynthesizeResponse,
    TextProcessRequest,
    TextProcessResponse,
    TranscribeRequest,
    TranscribeResponse,
    VoicePipelineRequest,
    VoicePipelineResponse,
)
from barnabeenet.services.stt import DistilWhisperSTT
from barnabeenet.services.tts import KokoroTTS
from barnabeenet.services.voice_pipeline import VoicePipelineService

router = APIRouter()
logger = structlog.get_logger()

# Service instances (initialized lazily)
_stt_service: DistilWhisperSTT | None = None
_tts_service: KokoroTTS | None = None


async def get_stt_service() -> DistilWhisperSTT:
    """Get or create the STT service instance."""
    global _stt_service
    if _stt_service is None:
        settings = get_settings()
        _stt_service = DistilWhisperSTT(
            model_size=settings.stt.whisper_model,
            device=settings.stt.whisper_device,
            compute_type=settings.stt.whisper_compute_type,
        )
    if not _stt_service.is_available():
        await _stt_service.initialize()
    return _stt_service


async def get_tts_service() -> KokoroTTS:
    """Get or create the TTS service instance."""
    global _tts_service
    if _tts_service is None:
        settings = get_settings()
        _tts_service = KokoroTTS(
            voice=settings.tts.voice,
            speed=settings.tts.speed,
        )
    if not _tts_service.is_available():
        await _tts_service.initialize()
    return _tts_service


# =============================================================================
# STT Endpoints
# =============================================================================


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
    """Transcribe audio to text.

    Automatically routes to GPU worker (Parakeet) if available,
    falls back to CPU (Distil-Whisper) otherwise.
    """
    from barnabeenet.main import app_state

    start_time = time.perf_counter()

    # Decode audio
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                code="INVALID_AUDIO",
                message="Failed to decode base64 audio",
                details={"error": str(e)},
            ).model_dump(),
        ) from e

    # Determine which engine to use
    use_gpu = app_state.gpu_worker_available and request.engine != STTEngine.DISTIL_WHISPER
    is_fallback = False

    if request.engine == STTEngine.PARAKEET and not app_state.gpu_worker_available:
        use_gpu = False
        is_fallback = True
        logger.warning("GPU worker requested but unavailable, using CPU fallback")

    # Process transcription
    if use_gpu:
        try:
            text, confidence = await _transcribe_gpu(audio_bytes, request.language)
            engine_used = STTEngine.PARAKEET
        except Exception as e:
            logger.warning("GPU transcription failed, falling back to CPU", error=str(e))
            text, confidence = await _transcribe_cpu(audio_bytes, request.language)
            engine_used = STTEngine.DISTIL_WHISPER
            is_fallback = True
    else:
        text, confidence = await _transcribe_cpu(audio_bytes, request.language)
        engine_used = STTEngine.DISTIL_WHISPER

    latency_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "Transcription complete",
        engine=engine_used.value,
        latency_ms=f"{latency_ms:.2f}",
        is_fallback=is_fallback,
        text_length=len(text),
    )

    return TranscribeResponse(
        text=text,
        confidence=confidence,
        language=request.language,
        engine_used=engine_used,
        latency_ms=latency_ms,
        is_fallback=is_fallback,
    )


async def _transcribe_gpu(audio_bytes: bytes, language: str) -> tuple[str, float]:
    """Transcribe using GPU worker (Parakeet on Man-of-war)."""
    import httpx

    settings = get_settings()
    url = f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}/transcribe"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                "audio_base64": base64.b64encode(audio_bytes).decode(),
                "language": language,
            },
            timeout=settings.performance.stt_timeout_ms / 1000,
        )
        response.raise_for_status()
        data = response.json()
        return data["text"], data.get("confidence", 1.0)


async def _transcribe_cpu(audio_bytes: bytes, language: str) -> tuple[str, float]:
    """Transcribe using CPU (Distil-Whisper)."""
    stt = await get_stt_service()
    result = await stt.transcribe(audio_bytes, language=language)
    return result["text"], result["confidence"]


# =============================================================================
# TTS Endpoints
# =============================================================================


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(request: SynthesizeRequest) -> SynthesizeResponse:
    """Synthesize text to speech using Kokoro TTS."""
    start_time = time.perf_counter()

    # Generate audio
    audio_bytes, sample_rate, duration_ms = await _synthesize_kokoro(
        text=request.text,
        voice=request.voice,
        speed=request.speed,
        output_format=request.output_format,
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "Synthesis complete",
        latency_ms=f"{latency_ms:.2f}",
        duration_ms=f"{duration_ms:.2f}",
        text_length=len(request.text),
    )

    return SynthesizeResponse(
        audio_base64=base64.b64encode(audio_bytes).decode(),
        sample_rate=sample_rate,
        duration_ms=duration_ms,
        format=request.output_format,
        latency_ms=latency_ms,
        cached=False,
    )


async def _synthesize_kokoro(
    text: str,
    voice: str | None,
    speed: float,
    output_format: AudioFormat,
) -> tuple[bytes, int, float]:
    """Synthesize using Kokoro TTS."""
    tts = await get_tts_service()

    result = await tts.synthesize(
        text=text,
        voice=voice,
        speed=speed,
    )

    return result["audio_bytes"], result["sample_rate"], result["duration_ms"]


# =============================================================================
# Full Voice Pipeline
# =============================================================================


@router.post("/voice/pipeline", response_model=VoicePipelineResponse)
async def voice_pipeline(request: VoicePipelineRequest) -> VoicePipelineResponse:
    """Full voice pipeline: delegate to `VoicePipelineService`.

    Keeps the router thin and moves pipeline logic into services for reuse.
    """
    return await VoicePipelineService.run(request)


# =============================================================================
# Text-Only Processing (for dashboard testing)
# =============================================================================


@router.post("/voice/process", response_model=TextProcessResponse)
async def text_process(request: TextProcessRequest) -> TextProcessResponse:
    """Process text through the agent orchestrator (no audio).

    This endpoint is useful for:
    - Dashboard testing without audio
    - API integrations that don't need TTS output
    - End-to-end testing of the AI pipeline

    Goes through the full pipeline including:
    - Intent classification (MetaAgent)
    - Memory retrieval
    - Agent routing (Instant/Action/Interaction/Memory)
    - Memory storage

    All processing is logged to the dashboard via pipeline signals.
    """
    from barnabeenet.agents.orchestrator import get_orchestrator
    from barnabeenet.services.pipeline_signals import get_pipeline_logger

    start_time = time.perf_counter()
    pipeline_logger = get_pipeline_logger()

    # Start trace for dashboard visibility
    trace_id = pipeline_logger.start_trace(
        input_text=request.text,
        input_type="text",
        speaker=request.speaker,
        room=request.room,
    )

    try:
        # Process through orchestrator
        orchestrator = get_orchestrator()
        orchestrator_resp = await orchestrator.process(
            text=request.text,
            speaker=request.speaker,
            room=request.room,
            conversation_id=request.conversation_id,
        )

        response_text = orchestrator_resp.get("response", "")
        agent_used = orchestrator_resp.get("agent", "unknown")
        intent = orchestrator_resp.get("intent", "unknown")

        processing_time = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Text processing complete",
            trace_id=trace_id[:8],
            agent=agent_used,
            intent=intent,
            latency_ms=f"{processing_time:.2f}",
        )

        # Complete trace
        await pipeline_logger.complete_trace(
            trace_id=trace_id,
            response_text=response_text,
            success=True,
        )

        # Build LLM details if available
        llm_details_raw = orchestrator_resp.get("llm_details")
        llm_details = None
        if llm_details_raw:
            llm_details = LLMDetails(
                model=llm_details_raw.get("model"),
                input_tokens=llm_details_raw.get("input_tokens"),
                output_tokens=llm_details_raw.get("output_tokens"),
                cost_usd=llm_details_raw.get("cost_usd"),
                llm_latency_ms=llm_details_raw.get("llm_latency_ms"),
                messages_sent=llm_details_raw.get("messages_sent"),
                response_text=llm_details_raw.get("response_text"),
            )

        return TextProcessResponse(
            text=request.text,
            response=response_text,
            intent=intent,
            agent_used=agent_used,
            trace_id=trace_id,
            conversation_id=orchestrator_resp.get("conversation_id") or request.conversation_id,
            latency_ms=processing_time,
            total_latency_ms=processing_time,
            memories_retrieved=orchestrator_resp.get("memories_retrieved", 0),
            memories_stored=orchestrator_resp.get("memories_stored", 0),
            actions=orchestrator_resp.get("actions", []),
            llm_details=llm_details,
        )

    except Exception as e:
        processing_time = (time.perf_counter() - start_time) * 1000

        logger.error(
            "Text processing failed",
            trace_id=trace_id[:8],
            error=str(e),
        )

        # Complete trace with error
        await pipeline_logger.complete_trace(
            trace_id=trace_id,
            response_text="",
            success=False,
            error=str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=ErrorDetail(
                code="PROCESSING_ERROR",
                message="Failed to process text",
                details={"error": str(e)},
            ).model_dump(),
        ) from e
