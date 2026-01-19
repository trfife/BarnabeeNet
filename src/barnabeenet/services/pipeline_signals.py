"""Pipeline signal logging for complete request tracing.

Captures the full data flow through BarnabeeNet:
Audio → STT → MetaAgent → Agent Router → Action → Memory → TTS → Audio

Every request gets a trace_id that connects all related signals.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Types of signals in the processing pipeline."""

    # Input
    AUDIO_RECEIVED = "audio_received"
    STT_START = "stt_start"
    STT_COMPLETE = "stt_complete"

    # Classification & Routing
    META_CLASSIFY = "meta_classify"
    AGENT_ROUTE = "agent_route"

    # Agent Processing (generic)
    INSTANT_PROCESS = "instant_process"
    ACTION_PROCESS = "action_process"
    INTERACTION_PROCESS = "interaction_process"
    MEMORY_QUERY = "memory_query"
    MEMORY_STORE = "memory_store"

    # Agent-specific signals (for detailed tracking)
    AGENT_INSTANT = "agent_instant"
    AGENT_ACTION = "agent_action"
    AGENT_INTERACTION = "agent_interaction"
    AGENT_MEMORY = "agent_memory"

    # Memory operations
    MEMORY_RETRIEVE = "memory_retrieve"

    # Home Assistant
    HA_SERVICE_CALL = "ha_service_call"
    HA_STATE_CHECK = "ha_state_check"
    HA_ACTION = "ha_action"

    # LLM
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"

    # Output
    TTS_START = "tts_start"
    TTS_COMPLETE = "tts_complete"
    AUDIO_SENT = "audio_sent"

    # Errors
    ERROR = "error"

    # Pipeline events
    REQUEST_START = "request_start"
    REQUEST_COMPLETE = "request_complete"

    # E2E Testing signals
    E2E_TEST_START = "e2e_test_start"
    E2E_TEST_COMPLETE = "e2e_test_complete"
    E2E_TEST_STEP = "e2e_test_step"
    E2E_ASSERTION_PASS = "e2e_assertion_pass"
    E2E_ASSERTION_FAIL = "e2e_assertion_fail"


class PipelineSignal(BaseModel):
    """A single event in the processing pipeline."""

    # Identifiers
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str  # Groups all signals from same request
    parent_id: str | None = None  # For nested operations

    # Type & Stage
    signal_type: SignalType
    stage: str  # input, classify, process, action, output

    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: float | None = None

    # Context
    speaker: str | None = None
    room: str | None = None

    # Data at this stage
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)

    # Processing details
    component: str  # e.g., "stt_router", "meta_agent", "action_agent"
    model_used: str | None = None  # For LLM/STT/TTS
    provider: str | None = None

    # Status
    success: bool = True
    error: str | None = None
    error_type: str | None = None

    # Metrics
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None

    # Human-readable summary
    summary: str = ""


class RequestTrace(BaseModel):
    """Complete trace of a single request through the pipeline."""

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # Request info
    input_text: str = ""
    input_type: str = "text"  # text, audio
    speaker: str | None = None
    room: str | None = None

    # Classification results
    intent: str | None = None
    intent_confidence: float | None = None
    context_type: str | None = None
    mood: str | None = None

    # Routing
    agent_used: str | None = None
    route_reason: str | None = None

    # Processing
    memories_retrieved: list[str] = Field(default_factory=list)
    memories_stored: list[str] = Field(default_factory=list)
    ha_actions: list[dict[str, Any]] = Field(default_factory=list)

    # Response
    response_text: str = ""
    response_type: str = "spoken"  # spoken, action_only, error

    # Totals
    total_latency_ms: float | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0

    # Status
    success: bool = True
    error: str | None = None

    # All signals in order
    signals: list[PipelineSignal] = Field(default_factory=list)


class PipelineLogger:
    """Logs pipeline signals to Redis for dashboard consumption.

    Provides:
    - Real-time signal stream for live dashboard updates
    - Complete request traces for detailed inspection
    - Searchable history of all requests
    """

    STREAM_KEY = "barnabeenet:signals:pipeline"
    TRACE_PREFIX = "barnabeenet:traces:"
    RECENT_TRACES_KEY = "barnabeenet:traces:recent"
    SIGNAL_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days retention
    MAX_RECENT_TRACES = 500

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client
        self._active_traces: dict[str, RequestTrace] = {}
        self._fallback_signals: list[PipelineSignal] = []
        self._fallback_traces: list[RequestTrace] = []

    async def set_redis(self, redis_client: redis.Redis) -> None:
        """Set Redis client after initialization."""
        self._redis = redis_client

    def start_trace(
        self,
        input_text: str,
        input_type: str = "text",
        speaker: str | None = None,
        room: str | None = None,
    ) -> str:
        """Start a new request trace. Returns trace_id."""
        trace = RequestTrace(
            input_text=input_text,
            input_type=input_type,
            speaker=speaker,
            room=room,
        )
        self._active_traces[trace.trace_id] = trace

        # Log start signal
        self._log_signal_sync(
            PipelineSignal(
                trace_id=trace.trace_id,
                signal_type=SignalType.REQUEST_START,
                stage="input",
                component="pipeline",
                speaker=speaker,
                room=room,
                input_data={"text": input_text, "type": input_type},
                summary=f"Request started: '{input_text[:50]}...' from {speaker or 'unknown'}",
            )
        )

        return trace.trace_id

    def get_trace(self, trace_id: str) -> RequestTrace | None:
        """Get an active trace."""
        return self._active_traces.get(trace_id)

    async def log_signal(self, signal: PipelineSignal) -> None:
        """Log a pipeline signal."""
        # Add to active trace if exists
        if signal.trace_id in self._active_traces:
            self._active_traces[signal.trace_id].signals.append(signal)

        # Log to Python logger
        log_level = logging.INFO if signal.success else logging.WARNING
        logger.log(
            log_level,
            "[%s] %s | %s | %s | %.0fms | %s",
            signal.trace_id[:8],
            signal.signal_type.value,
            signal.component,
            "OK" if signal.success else f"ERR: {signal.error_type}",
            signal.latency_ms or 0,
            signal.summary[:80],
        )

        if self._redis is None:
            self._fallback_signals.append(signal)
            if len(self._fallback_signals) > 2000:
                self._fallback_signals.pop(0)
            return

        try:
            # Add to stream for real-time updates
            stream_data = {
                "signal_id": signal.signal_id,
                "trace_id": signal.trace_id,
                "signal_type": signal.signal_type.value,
                "stage": signal.stage,
                "component": signal.component,
                "timestamp": signal.timestamp.isoformat(),
                "success": str(signal.success),
                "latency_ms": str(signal.latency_ms or 0),
                "summary": signal.summary[:200],
                "speaker": signal.speaker or "",
                "room": signal.room or "",
                "model": signal.model_used or "",
                "error": signal.error or "",
            }

            await self._redis.xadd(
                self.STREAM_KEY,
                stream_data,
                maxlen=5000,
            )

        except Exception as e:
            logger.error("Failed to log signal to Redis: %s", e)
            self._fallback_signals.append(signal)

    def _log_signal_sync(self, signal: PipelineSignal) -> None:
        """Synchronous signal logging (for start_trace)."""
        if signal.trace_id in self._active_traces:
            self._active_traces[signal.trace_id].signals.append(signal)

        logger.info(
            "[%s] %s | %s | %s",
            signal.trace_id[:8],
            signal.signal_type.value,
            signal.component,
            signal.summary[:80],
        )

        self._fallback_signals.append(signal)
        if len(self._fallback_signals) > 2000:
            self._fallback_signals.pop(0)

    async def complete_trace(
        self,
        trace_id: str,
        response_text: str = "",
        success: bool = True,
        error: str | None = None,
        intent: str | None = None,
        agent_used: str | None = None,
        intent_confidence: float | None = None,
        response_type: str | None = None,
        ha_actions: list[dict[str, Any]] | None = None,
        memories_retrieved: list[str] | None = None,
    ) -> RequestTrace | None:
        """Complete a request trace and store it."""
        trace = self._active_traces.pop(trace_id, None)
        if not trace:
            return None

        trace.completed_at = datetime.now(UTC)
        trace.response_text = response_text
        trace.success = success
        trace.error = error
        trace.intent = intent
        trace.agent_used = agent_used
        if intent_confidence is not None:
            trace.intent_confidence = intent_confidence
        if response_type is not None:
            trace.response_type = response_type
        if ha_actions is not None:
            trace.ha_actions = ha_actions
        if memories_retrieved is not None:
            trace.memories_retrieved = memories_retrieved

        # Calculate totals
        if trace.started_at and trace.completed_at:
            trace.total_latency_ms = (trace.completed_at - trace.started_at).total_seconds() * 1000

        for signal in trace.signals:
            if signal.tokens_in:
                trace.total_tokens += signal.tokens_in
            if signal.tokens_out:
                trace.total_tokens += signal.tokens_out
            if signal.cost_usd:
                trace.total_cost_usd += signal.cost_usd

        # Log completion signal
        await self.log_signal(
            PipelineSignal(
                trace_id=trace_id,
                signal_type=SignalType.REQUEST_COMPLETE,
                stage="complete",
                component="pipeline",
                speaker=trace.speaker,
                room=trace.room,
                latency_ms=trace.total_latency_ms,
                success=success,
                error=error,
                output_data={
                    "response": response_text[:100],
                    "agent": trace.agent_used,
                    "intent": trace.intent,
                },
                summary=f"Request complete: {trace.agent_used} → '{response_text[:50]}...'",
            )
        )

        # Store trace
        await self._store_trace(trace)

        return trace

    async def _store_trace(self, trace: RequestTrace) -> None:
        """Store completed trace to Redis."""
        self._fallback_traces.append(trace)
        if len(self._fallback_traces) > 500:
            self._fallback_traces.pop(0)

        if self._redis is None:
            return

        try:
            trace_key = f"{self.TRACE_PREFIX}{trace.trace_id}"
            trace_json = trace.model_dump_json()

            # Store full trace
            await self._redis.setex(trace_key, self.SIGNAL_TTL_SECONDS, trace_json)

            # Add to recent traces list
            await self._redis.lpush(self.RECENT_TRACES_KEY, trace.trace_id)
            await self._redis.ltrim(self.RECENT_TRACES_KEY, 0, self.MAX_RECENT_TRACES - 1)

        except Exception as e:
            logger.error("Failed to store trace: %s", e)

    async def get_recent_traces(self, limit: int = 50) -> list[RequestTrace]:
        """Get recent completed traces."""
        if self._redis is None:
            return self._fallback_traces[-limit:]

        try:
            trace_ids = await self._redis.lrange(self.RECENT_TRACES_KEY, 0, limit - 1)

            traces = []
            for trace_id in trace_ids:
                trace_key = f"{self.TRACE_PREFIX}{trace_id}"
                trace_json = await self._redis.get(trace_key)
                if trace_json:
                    traces.append(RequestTrace.model_validate_json(trace_json))

            return traces

        except Exception as e:
            logger.error("Failed to get recent traces: %s", e)
            return self._fallback_traces[-limit:]

    async def get_trace_by_id(self, trace_id: str) -> RequestTrace | None:
        """Get a specific trace by ID."""
        # Check active traces first
        if trace_id in self._active_traces:
            return self._active_traces[trace_id]

        # Check fallback
        for trace in self._fallback_traces:
            if trace.trace_id == trace_id:
                return trace

        if self._redis is None:
            return None

        try:
            trace_key = f"{self.TRACE_PREFIX}{trace_id}"
            trace_json = await self._redis.get(trace_key)
            if trace_json:
                return RequestTrace.model_validate_json(trace_json)
        except Exception as e:
            logger.error("Failed to get trace: %s", e)

        return None

    def get_fallback_signals(self, limit: int = 100) -> list[PipelineSignal]:
        """Get recent signals from in-memory fallback."""
        return self._fallback_signals[-limit:]


# Global instance
_pipeline_logger: PipelineLogger | None = None


def get_pipeline_logger() -> PipelineLogger:
    """Get the global pipeline logger instance."""
    global _pipeline_logger
    if _pipeline_logger is None:
        _pipeline_logger = PipelineLogger()
    return _pipeline_logger


async def init_pipeline_logger(redis_client: redis.Redis | None = None) -> PipelineLogger:
    """Initialize the pipeline logger with Redis."""
    global _pipeline_logger
    _pipeline_logger = PipelineLogger(redis_client)
    return _pipeline_logger
