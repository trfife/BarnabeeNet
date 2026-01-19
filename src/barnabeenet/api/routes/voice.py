"""Voice API routes - STT, TTS, and full pipeline."""

from __future__ import annotations

import base64
import time

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

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
        actions = orchestrator_resp.get("actions", [])
        routing_reason = orchestrator_resp.get("routing_reason")

        processing_time = (time.perf_counter() - start_time) * 1000

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

            # Log LLM signal for trace
            from barnabeenet.services.pipeline_signals import PipelineSignal, SignalType

            await pipeline_logger.log_signal(
                PipelineSignal(
                    trace_id=trace_id,
                    signal_type=SignalType.LLM_RESPONSE,
                    stage="process",
                    component=f"{agent_used}_agent",
                    model_used=llm_details_raw.get("model"),
                    tokens_in=llm_details_raw.get("input_tokens"),
                    tokens_out=llm_details_raw.get("output_tokens"),
                    cost_usd=llm_details_raw.get("cost_usd"),
                    latency_ms=llm_details_raw.get("llm_latency_ms"),
                    success=True,
                    summary=f"LLM: {llm_details_raw.get('model')} → {llm_details_raw.get('output_tokens')} tokens",
                    input_data={"messages": len(llm_details_raw.get("messages_sent", []))},
                    output_data={"response_preview": response_text[:100]},
                )
            )

        # Log agent processing signal
        from barnabeenet.services.pipeline_signals import PipelineSignal, SignalType

        agent_signal_type = {
            "instant": SignalType.AGENT_INSTANT,
            "action": SignalType.AGENT_ACTION,
            "interaction": SignalType.AGENT_INTERACTION,
            "memory": SignalType.AGENT_MEMORY,
        }.get(agent_used, SignalType.AGENT_ROUTE)

        await pipeline_logger.log_signal(
            PipelineSignal(
                trace_id=trace_id,
                signal_type=agent_signal_type,
                stage="process",
                component=f"{agent_used}_agent",
                latency_ms=processing_time,
                success=True,
                summary=f"{agent_used.title()} Agent: {intent} → '{response_text[:50]}...'",
                input_data={
                    "text": request.text,
                    "intent": intent,
                    "routing_reason": routing_reason,
                },
                output_data={
                    "response": response_text[:200],
                    "actions_count": len(actions),
                },
            )
        )

        # Log HA actions if any
        for action in actions:
            await pipeline_logger.log_signal(
                PipelineSignal(
                    trace_id=trace_id,
                    signal_type=SignalType.HA_ACTION,
                    stage="action",
                    component="home_assistant",
                    success=action.get("executed", False),
                    summary=f"HA: {action.get('service', 'unknown')} → {action.get('entity_id', 'unknown')}",
                    input_data={
                        "service": action.get("service"),
                        "entity_id": action.get("entity_id"),
                        "entity_name": action.get("entity_name"),
                    },
                    output_data={
                        "executed": action.get("executed"),
                        "message": action.get("execution_message"),
                    },
                )
            )

        logger.info(
            "Text processing complete",
            trace_id=trace_id[:8],
            agent=agent_used,
            intent=intent,
            latency_ms=f"{processing_time:.2f}",
        )

        # Complete trace with all available data
        await pipeline_logger.complete_trace(
            trace_id=trace_id,
            response_text=response_text,
            success=True,
            intent=intent,
            agent_used=agent_used,
            ha_actions=actions,
            route_reason=routing_reason,
        )

        # Build trace details for enhanced observability
        from barnabeenet.models.schemas import TraceDetails

        trace_details = TraceDetails(
            routing_reason=routing_reason,
            pattern_matched=orchestrator_resp.get("pattern_matched"),
            meta_processing_time_ms=orchestrator_resp.get("meta_processing_time_ms"),
            context_evaluation=orchestrator_resp.get("context_evaluation"),
            memory_queries=orchestrator_resp.get("memory_queries"),
            memories_data=orchestrator_resp.get("memories_data"),
            parsed_segments=orchestrator_resp.get("parsed_segments"),
            resolved_targets=orchestrator_resp.get("resolved_targets"),
            service_calls=orchestrator_resp.get("service_calls"),
            timer_info=orchestrator_resp.get("timer_info"),
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
            actions=actions,
            llm_details=llm_details,
            trace_details=trace_details,
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


# =============================================================================
# Quick Input Endpoints
# =============================================================================


@router.post("/input/text")
async def quick_text_input(
    text: str,
    speaker: str = "api",
    room: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Simple text input - send text, get response.

    This is a convenience endpoint for quick text interactions.
    Returns a simplified response compared to /voice/process.
    """
    from barnabeenet.agents.orchestrator import get_orchestrator

    start_time = time.perf_counter()
    orchestrator = get_orchestrator()

    result = await orchestrator.process(
        text=text,
        speaker=speaker,
        room=room,
        conversation_id=conversation_id,
    )

    latency_ms = (time.perf_counter() - start_time) * 1000

    return {
        "text": text,
        "response": result.get("response", ""),
        "intent": result.get("intent", "unknown"),
        "agent": result.get("agent", "unknown"),
        "conversation_id": result.get("conversation_id"),
        "latency_ms": latency_ms,
    }


@router.post("/input/audio")
async def quick_audio_input(
    audio: UploadFile,
    mode: str = "command",
    engine: str = "auto",
    speaker: str = "api",
    room: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Simple audio input - upload file, get transcription + response.

    Accepts audio file upload (WAV, WebM, OGG) and returns both
    the transcription and the AI response.

    Query parameters:
    - mode: "command" (single utterance), "realtime", "ambient"
    - engine: "auto", "parakeet" (GPU), "whisper" (CPU), "azure" (cloud)
    """
    from barnabeenet.agents.orchestrator import get_orchestrator
    from barnabeenet.models.stt_modes import STTEngine as STTEngineEnum
    from barnabeenet.models.stt_modes import STTMode as STTModeEnum
    from barnabeenet.services.stt.router import STTRouter

    start_time = time.perf_counter()

    # Parse mode and engine
    try:
        stt_mode = STTModeEnum(mode)
    except ValueError:
        stt_mode = STTModeEnum.COMMAND

    try:
        stt_engine = STTEngineEnum(engine)
    except ValueError:
        stt_engine = STTEngineEnum.AUTO

    # Read audio data
    audio_data = await audio.read()

    # Transcribe
    settings = get_settings()
    stt_router = STTRouter(
        gpu_worker_url=f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}",
    )

    try:
        await stt_router.initialize()
        stt_result = await stt_router.transcribe(
            audio_data=audio_data,
            sample_rate=settings.audio.input_sample_rate,
            language="en",
            engine=stt_engine,
            mode=stt_mode,
        )
    finally:
        await stt_router.shutdown()

    # Process through orchestrator
    orchestrator = get_orchestrator()
    ai_result = await orchestrator.process(
        text=stt_result.text,
        speaker=speaker,
        room=room,
        conversation_id=conversation_id,
    )

    total_time = (time.perf_counter() - start_time) * 1000

    return {
        "transcription": stt_result.text,
        "transcription_confidence": stt_result.confidence,
        "stt_engine": stt_result.backend.value,
        "stt_latency_ms": stt_result.latency_ms,
        "response": ai_result.get("response", ""),
        "intent": ai_result.get("intent", "unknown"),
        "agent": ai_result.get("agent", "unknown"),
        "conversation_id": ai_result.get("conversation_id"),
        "total_latency_ms": total_time,
    }


# =============================================================================
# Simple Chat API (for Home Assistant / External Integration)
# =============================================================================


class ChatRequest(BaseModel):
    """JSON body for chat endpoint."""

    text: str
    speaker: str | None = None
    room: str | None = None
    conversation_id: str | None = None


async def _process_chat(
    text: str,
    speaker: str | None = None,
    room: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Internal helper for chat processing."""
    from barnabeenet.agents.orchestrator import get_orchestrator

    orchestrator = get_orchestrator()
    result = await orchestrator.process(
        text=text,
        speaker=speaker,
        room=room,
        conversation_id=conversation_id,
    )

    return {
        "response": result.get("response", ""),
        "intent": result.get("intent"),
        "agent": result.get("agent"),
        "conversation_id": result.get("conversation_id"),
    }


@router.post("/chat")
async def chat(
    request: ChatRequest,
) -> dict:
    """Dead-simple chat endpoint for Home Assistant integration.

    Send text, get response. That's it.

    JSON Body Example:
        POST /api/v1/chat
        Content-Type: application/json
        {"text": "turn on the kitchen lights", "speaker": "thom"}

        Response: {"response": "Done! I've turned on the kitchen lights."}

    For Home Assistant rest_command:
        rest_command:
          barnabee:
            url: "http://192.168.86.51:8000/api/v1/chat"
            method: POST
            content_type: "application/json"
            payload: '{"text": "{{ text }}", "speaker": "{{ speaker }}"}'

    Body Fields:
    - text: The command or question (required)
    - speaker: Who's speaking (e.g., "thom", "viola") - helps personalization
    - room: Which room (e.g., "kitchen", "living_room") - helps context
    - conversation_id: Maintain conversation context across requests
    """
    return await _process_chat(
        text=request.text,
        speaker=request.speaker,
        room=request.room,
        conversation_id=request.conversation_id,
    )


@router.get("/chat")
async def chat_get(
    text: str,
    speaker: str | None = None,
    room: str | None = None,
) -> dict:
    """GET version for easy browser/curl testing.

    Example: GET /api/v1/chat?text=what%20time%20is%20it&speaker=thom

    Query Parameters:
    - text: The command or question (required)
    - speaker: Who's speaking (optional)
    - room: Which room (optional)
    """
    return await _process_chat(text=text, speaker=speaker, room=room)


# =============================================================================
# WebSocket Streaming Transcription
# =============================================================================


@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming audio transcription.

    Client sends: binary audio chunks (16kHz PCM or WebM/Opus)
    Server sends: JSON with partial/final transcription results

    Connection flow:
    1. Client connects to /ws/transcribe
    2. Client sends config message: {"engine": "auto", "language": "en-US"}
    3. Client sends binary audio chunks
    4. Server sends partial results: {"type": "partial", "text": "Hello my", "is_final": false}
    5. Server sends final results: {"type": "final", "text": "Hello my name is", "is_final": true}
    6. Client sends {"type": "end"} to signal end of audio
    7. Server sends final result and closes

    Messages from client:
    - JSON config: {"type": "config", "engine": "auto", "language": "en-US"}
    - Binary audio: raw PCM 16-bit mono 16kHz
    - JSON end: {"type": "end"}

    Messages from server:
    - {"type": "ready", "message": "Ready for audio"}
    - {"type": "partial", "text": "...", "is_final": false}
    - {"type": "final", "text": "...", "is_final": true, "confidence": 0.95, "engine": "parakeet"}
    - {"type": "error", "message": "..."}
    """
    import asyncio
    import json

    from barnabeenet.models.stt_modes import STTEngine as STTEngineEnum
    from barnabeenet.services.stt.router import STTRouter

    await websocket.accept()

    settings = get_settings()
    stt_router = STTRouter(
        gpu_worker_url=f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}",
    )

    try:
        await stt_router.initialize()

        # Send ready message
        await websocket.send_json(
            {
                "type": "ready",
                "message": "Ready for audio",
                "engines": stt_router.get_status()["engines"],
            }
        )

        # Wait for config message or start receiving audio
        engine = STTEngineEnum.AUTO
        language = "en-US"
        audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        streaming_task = None

        async def audio_generator():
            """Generate audio chunks from queue."""
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                yield chunk

        async def process_streaming():
            """Process streaming transcription."""
            async for result in stt_router.transcribe_streaming(
                audio_stream=audio_generator(),
                sample_rate=settings.audio.input_sample_rate,
                language=language,
                engine=engine,
            ):
                await websocket.send_json(
                    {
                        "type": "final" if result.is_final else "partial",
                        "text": result.text,
                        "is_final": result.is_final,
                        "confidence": result.confidence,
                        "engine": result.backend.value,
                        "latency_ms": result.latency_ms,
                    }
                )

        # Main message loop
        while True:
            try:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if "bytes" in message:
                    # Binary audio data
                    if streaming_task is None:
                        streaming_task = asyncio.create_task(process_streaming())

                    await audio_queue.put(message["bytes"])

                elif "text" in message:
                    # JSON message
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "")

                    if msg_type == "config":
                        # Update config
                        try:
                            engine = STTEngineEnum(data.get("engine", "auto"))
                        except ValueError:
                            engine = STTEngineEnum.AUTO
                        language = data.get("language", "en-US")

                        await websocket.send_json(
                            {
                                "type": "config_ack",
                                "engine": engine.value,
                                "language": language,
                            }
                        )

                    elif msg_type == "end":
                        # End of audio stream
                        await audio_queue.put(None)

                        if streaming_task:
                            await streaming_task

                        await websocket.send_json(
                            {
                                "type": "complete",
                                "message": "Transcription complete",
                            }
                        )
                        break

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("WebSocket error", error=str(e))
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
                break

    except Exception as e:
        logger.error("WebSocket transcription error", error=str(e))
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Server error: {str(e)}",
                }
            )
        except Exception:
            pass
    finally:
        await stt_router.shutdown()


# =============================================================================
# STT Status Endpoint
# =============================================================================


@router.get("/stt/status")
async def get_stt_status() -> dict:
    """Get current STT engine status and availability.

    Returns information about all available STT engines:
    - parakeet (GPU): Fastest, requires GPU worker
    - azure (cloud): Good for mobile/remote
    - whisper (CPU): Always available fallback
    """
    from barnabeenet.services.stt.router import STTRouter

    settings = get_settings()
    stt_router = STTRouter(
        gpu_worker_url=f"http://{settings.stt.gpu_worker_host}:{settings.stt.gpu_worker_port}",
    )

    try:
        await stt_router.initialize()
        status = stt_router.get_status()

        return {
            "status": "ok",
            "default_mode": settings.stt.default_mode,
            "default_engine": settings.stt.default_engine,
            **status,
        }
    finally:
        await stt_router.shutdown()
