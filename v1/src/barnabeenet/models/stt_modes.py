"""STT Mode and Engine configuration models.

Defines the different transcription modes and engine options
for the tiered STT input system.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class STTMode(str, Enum):
    """Speech-to-text processing modes.

    Different modes are optimized for different use cases:
    - AMBIENT: Batch processing every 30-60s, for background audio capture
    - REALTIME: Streaming with word-by-word results, for conversations
    - COMMAND: Single utterance recognition, for wake-word triggered commands
    """

    AMBIENT = "ambient"
    REALTIME = "realtime"
    COMMAND = "command"


class STTEngine(str, Enum):
    """Available STT engines.

    Engines are prioritized by speed and availability:
    - AUTO: Automatically select best available (GPU → Azure → CPU)
    - PARAKEET: NVIDIA Parakeet TDT on GPU (fastest, ~45ms)
    - WHISPER: Distil-Whisper on CPU (fallback, ~2400ms)
    - AZURE: Azure Cognitive Services (cloud, for mobile/remote)
    """

    AUTO = "auto"
    PARAKEET = "parakeet"
    WHISPER = "whisper"
    AZURE = "azure"


class STTEngineStatus(BaseModel):
    """Status of an STT engine."""

    engine: STTEngine
    available: bool
    latency_ms: float | None = None
    model: str | None = None
    error: str | None = None


class STTRouterStatus(BaseModel):
    """Current status of all STT engines."""

    preferred_engine: STTEngine
    engines: list[STTEngineStatus]


class STTConfig(BaseModel):
    """Configuration for STT processing."""

    mode: STTMode = Field(default=STTMode.COMMAND, description="Processing mode")
    engine: STTEngine = Field(default=STTEngine.AUTO, description="Engine to use")
    language: str = Field(default="en-US", description="Recognition language")

    # Streaming settings (for REALTIME mode)
    streaming_chunk_ms: int = Field(
        default=100,
        ge=50,
        le=500,
        description="Chunk size for streaming in milliseconds",
    )
    interim_results: bool = Field(
        default=True,
        description="Return partial results during streaming",
    )

    # Ambient settings
    ambient_batch_seconds: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Batch duration for ambient mode in seconds",
    )


class StreamingTranscriptMessage(BaseModel):
    """WebSocket message for streaming transcription results."""

    type: str = Field(description="Message type: 'partial', 'final', 'error', 'status'")
    text: str | None = Field(default=None, description="Transcribed text")
    is_final: bool = Field(default=False, description="Whether this is a final result")
    confidence: float | None = Field(default=None, description="Recognition confidence")
    engine: STTEngine | None = Field(default=None, description="Engine that produced this result")
    latency_ms: float | None = Field(default=None, description="Processing latency")
    message: str | None = Field(default=None, description="Status or error message")


class QuickInputRequest(BaseModel):
    """Request for quick text input."""

    text: str = Field(..., min_length=1, max_length=10000, description="Input text")
    speaker: str = Field(default="api", description="Speaker identifier")
    room: str | None = Field(default=None, description="Room/location context")
    conversation_id: str | None = Field(default=None, description="Conversation ID for context")


class QuickInputResponse(BaseModel):
    """Response from quick input processing."""

    text: str = Field(description="Input text that was processed")
    response: str = Field(description="AI response")
    intent: str = Field(description="Detected intent")
    agent_used: str = Field(description="Agent that handled the request")
    conversation_id: str | None = Field(default=None, description="Conversation ID")
    latency_ms: float = Field(description="Total processing time")


class QuickAudioRequest(BaseModel):
    """Metadata for quick audio input (audio sent as file upload)."""

    mode: STTMode = Field(default=STTMode.COMMAND, description="STT mode")
    engine: STTEngine = Field(default=STTEngine.AUTO, description="Preferred engine")
    language: str = Field(default="en-US", description="Recognition language")
    speaker: str = Field(default="api", description="Speaker identifier")
    room: str | None = Field(default=None, description="Room/location context")
    conversation_id: str | None = Field(default=None, description="Conversation ID")
