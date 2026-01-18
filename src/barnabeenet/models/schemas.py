"""Pydantic models for BarnabeeNet API requests and responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class STTEngine(str, Enum):
    """Available STT engines."""

    PARAKEET = "parakeet"
    DISTIL_WHISPER = "distil-whisper"


class TTSEngine(str, Enum):
    """Available TTS engines."""

    KOKORO = "kokoro"


class AudioFormat(str, Enum):
    """Supported audio formats."""

    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"


class RequestStatus(str, Enum):
    """Status of a processing request."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Health & Status
# =============================================================================


class ServiceHealth(BaseModel):
    """Health status of a single service."""

    name: str
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    latency_ms: float | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="healthy, degraded, or unhealthy")
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: list[ServiceHealth] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2026-01-17T12:00:00Z",
                "services": [
                    {"name": "redis", "status": "healthy", "latency_ms": 1.2},
                    {"name": "stt_gpu", "status": "healthy", "latency_ms": 5.3},
                    {"name": "stt_cpu", "status": "healthy", "latency_ms": 2.1},
                    {"name": "tts", "status": "healthy", "latency_ms": 1.8},
                ],
            }
        }


class GPUWorkerStatus(BaseModel):
    """Status of the GPU worker on Man-of-war."""

    available: bool
    last_check: datetime
    latency_ms: float | None = None
    model_loaded: bool = False
    error: str | None = None


# =============================================================================
# STT (Speech-to-Text)
# =============================================================================


class TranscribeRequest(BaseModel):
    """Request to transcribe audio to text."""

    audio_base64: str = Field(..., description="Base64-encoded audio data")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    language: str = Field(default="en", description="Language code (e.g., 'en')")
    engine: STTEngine | None = Field(
        default=None, description="Force specific engine (default: auto-route)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRi...",
                "sample_rate": 16000,
                "language": "en",
            }
        }


class TranscribeResponse(BaseModel):
    """Response from transcription request."""

    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence")
    language: str = Field(..., description="Detected or specified language")
    engine_used: STTEngine = Field(..., description="Which STT engine was used")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    is_fallback: bool = Field(default=False, description="Whether fallback engine was used")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Turn on the living room lights",
                "confidence": 0.95,
                "language": "en",
                "engine_used": "parakeet",
                "latency_ms": 32.5,
                "is_fallback": False,
            }
        }


# =============================================================================
# TTS (Text-to-Speech)
# =============================================================================


class SynthesizeRequest(BaseModel):
    """Request to synthesize text to speech."""

    text: str = Field(..., min_length=1, max_length=5000, description="Text to speak")
    voice: str | None = Field(default=None, description="Voice ID (default: config)")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    output_format: AudioFormat = Field(default=AudioFormat.WAV, description="Output format")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "The living room lights are now on.",
                "voice": "af_bella",
                "speed": 1.0,
                "output_format": "wav",
            }
        }


class SynthesizeResponse(BaseModel):
    """Response from synthesis request."""

    audio_base64: str = Field(..., description="Base64-encoded audio data")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")
    duration_ms: float = Field(..., description="Audio duration in milliseconds")
    format: AudioFormat = Field(..., description="Audio format")
    latency_ms: float = Field(..., description="Processing time in milliseconds")
    cached: bool = Field(default=False, description="Whether response was cached")

    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRi...",
                "sample_rate": 24000,
                "duration_ms": 1250.0,
                "format": "wav",
                "latency_ms": 85.3,
                "cached": False,
            }
        }


# =============================================================================
# Voice Pipeline (Full Round-Trip)
# =============================================================================


class VoicePipelineRequest(BaseModel):
    """Request for full voice pipeline: audio in → audio out."""

    audio_base64: str = Field(..., description="Base64-encoded input audio")
    sample_rate: int = Field(default=16000, description="Input audio sample rate")
    language: str = Field(default="en", description="Language code")
    response_voice: str | None = Field(default=None, description="TTS voice to use")
    output_format: AudioFormat = Field(default=AudioFormat.WAV)

    # Context for orchestrator
    speaker: str | None = Field(default=None, description="Speaker ID if known")
    room: str | None = Field(default=None, description="Room where request originated")
    conversation_id: str | None = Field(
        default=None, description="Conversation ID for context continuity"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRi...",
                "sample_rate": 16000,
                "language": "en",
                "speaker": "thomas",
                "room": "living_room",
            }
        }


class VoicePipelineResponse(BaseModel):
    """Response from full voice pipeline."""

    # Input processing
    input_text: str = Field(..., description="Transcribed input text")
    stt_engine: STTEngine = Field(..., description="STT engine used")
    stt_latency_ms: float = Field(..., description="STT processing time")

    # Orchestrator output
    response_text: str = Field(..., description="Response text")
    intent: str = Field(default="unknown", description="Classified intent category")
    agent: str = Field(default="unknown", description="Agent that handled request")
    request_id: str | None = Field(default=None, description="Unique request ID")
    conversation_id: str | None = Field(default=None, description="Conversation ID")

    # Audio output
    audio_base64: str = Field(..., description="Base64-encoded output audio")
    tts_latency_ms: float = Field(..., description="TTS processing time")

    # Totals
    total_latency_ms: float = Field(..., description="Total pipeline latency")
    sample_rate: int = Field(..., description="Output audio sample rate")
    format: AudioFormat = Field(..., description="Output audio format")

    class Config:
        json_schema_extra = {
            "example": {
                "input_text": "What time is it?",
                "stt_engine": "parakeet",
                "stt_latency_ms": 28.5,
                "response_text": "The current time is 3:45 PM.",
                "intent": "instant",
                "agent": "instant",
                "request_id": "abc12345",
                "audio_base64": "UklGRi...",
                "tts_latency_ms": 92.1,
                "total_latency_ms": 120.6,
                "sample_rate": 24000,
                "format": "wav",
            }
        }


# =============================================================================
# Metrics & Observability
# =============================================================================


class LatencyMetrics(BaseModel):
    """Latency metrics for a component."""

    count: int = 0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


class PipelineMetrics(BaseModel):
    """Overall pipeline metrics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    stt_metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)
    tts_metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)
    total_metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)

    gpu_worker_requests: int = 0
    cpu_fallback_requests: int = 0
    gpu_availability_percent: float = 100.0

    uptime_seconds: float = 0.0
    last_reset: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Errors
# =============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional details")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "STT_TIMEOUT",
                    "message": "Speech-to-text processing timed out",
                    "details": {"timeout_ms": 5000, "engine": "parakeet"},
                },
                "request_id": "abc123",
                "timestamp": "2026-01-17T12:00:00Z",
            }
        }
