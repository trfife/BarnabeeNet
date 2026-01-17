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
    STTEngine,
    SynthesizeRequest,
    SynthesizeResponse,
    TranscribeRequest,
    TranscribeResponse,
    VoicePipelineRequest,
    VoicePipelineResponse,
)

router = APIRouter()
logger = structlog.get_logger()


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

    settings = get_settings()
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
        )

    # Determine which engine to use
    use_gpu = app_state.gpu_worker_available and request.engine != STTEngine.DISTIL_WHISPER
    is_fallback = False

    if request.engine == STTEngine.PARAKEET and not app_state.gpu_worker_available:
        # Requested GPU but not available - fallback
        use_gpu = False
        is_fallback = True
        logger.warning("GPU worker requested but unavailable, using CPU fallback")

    # Process transcription
    if use_gpu:
        try:
            text, confidence = await _transcribe_gpu(audio_bytes, request.language)
            engine_used = STTEngine.PARAKEET
        except Exception as e:
            # GPU failed, try CPU fallback
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
    """Transcribe using CPU (Distil-Whisper).
    
    TODO: Implement in Step 3 (STT Services)
    For now, returns a placeholder.
    """
    # Placeholder for Phase 1 Step 3
    logger.warning("CPU STT not yet implemented, returning placeholder")
    return "[CPU STT placeholder - implement in Step 3]", 0.0


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
        cached=False,  # TODO: implement caching
    )


async def _synthesize_kokoro(
    text: str,
    voice: str | None,
    speed: float,
    output_format: AudioFormat,
) -> tuple[bytes, int, float]:
    """Synthesize using Kokoro TTS.
    
    TODO: Implement in Step 4 (TTS Service)
    For now, returns a placeholder.
    """
    settings = get_settings()
    voice = voice or settings.tts.voice

    # Placeholder for Phase 1 Step 4
    logger.warning("Kokoro TTS not yet implemented, returning placeholder")
    
    # Return minimal valid WAV header as placeholder
    placeholder_wav = _generate_placeholder_wav()
    
    return placeholder_wav, settings.tts.sample_rate, 0.0


def _generate_placeholder_wav() -> bytes:
    """Generate a minimal placeholder WAV file."""
    # Minimal WAV header for empty audio
    import struct

    sample_rate = 24000
    num_channels = 1
    bits_per_sample = 16
    
    # WAV header
    data_size = 0
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,  # fmt chunk size
        1,   # audio format (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size,
    )
    
    return header


# =============================================================================
# Full Voice Pipeline
# =============================================================================


@router.post("/voice/pipeline", response_model=VoicePipelineResponse)
async def voice_pipeline(request: VoicePipelineRequest) -> VoicePipelineResponse:
    """Full voice pipeline: audio in → transcribe → process → synthesize → audio out.
    
    For Phase 1, this echoes back what was said.
    Later phases will add agent routing and processing.
    """
    total_start = time.perf_counter()

    # Step 1: Transcribe (STT)
    transcribe_request = TranscribeRequest(
        audio_base64=request.audio_base64,
        sample_rate=request.sample_rate,
        language=request.language,
    )
    transcribe_response = await transcribe(transcribe_request)

    # Step 2: Process (Phase 1: just echo)
    # TODO: In Phase 3, this routes to agents
    response_text = f"You said: {transcribe_response.text}"

    # Step 3: Synthesize (TTS)
    synthesize_request = SynthesizeRequest(
        text=response_text,
        voice=request.response_voice,
        output_format=request.output_format,
    )
    synthesize_response = await synthesize(synthesize_request)

    total_latency_ms = (time.perf_counter() - total_start) * 1000

    logger.info(
        "Voice pipeline complete",
        stt_ms=f"{transcribe_response.latency_ms:.2f}",
        tts_ms=f"{synthesize_response.latency_ms:.2f}",
        total_ms=f"{total_latency_ms:.2f}",
    )

    return VoicePipelineResponse(
        input_text=transcribe_response.text,
        stt_engine=transcribe_response.engine_used,
        stt_latency_ms=transcribe_response.latency_ms,
        response_text=response_text,
        audio_base64=synthesize_response.audio_base64,
        tts_latency_ms=synthesize_response.latency_ms,
        total_latency_ms=total_latency_ms,
        sample_rate=synthesize_response.sample_rate,
        format=synthesize_response.format,
    )
