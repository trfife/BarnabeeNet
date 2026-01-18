"""Signal logging for LLM requests.

Every LLM call is logged with full context for dashboard observability.
This is the foundation for the BarnabeeNet dashboard's request inspector.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)


class LLMSignal(BaseModel):
    """Complete record of an LLM request/response for dashboard visibility.

    Based on SkyrimNet's request logging pattern - capture everything needed
    to debug and understand why Barnabee responded a certain way.
    """

    # Identifiers
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str | None = None
    trace_id: str | None = None
    request_id: str | None = None

    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: float | None = None

    # Agent context
    agent_type: str  # meta, instant, action, interaction, memory
    agent_name: str | None = None

    # Model configuration
    model: str
    provider: str = "openrouter"
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None

    # Request content
    system_prompt: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    full_prompt_tokens: int | None = None

    # Context that was injected (for debugging)
    injected_context: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"home_state": {...}, "speaker_profile": {...}, "memories": [...]}

    # Response
    response_text: str | None = None
    response_tokens: int | None = None
    finish_reason: str | None = None

    # Cost tracking
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None

    # Status
    success: bool = False
    error: str | None = None
    error_type: str | None = None

    # Metadata
    room: str | None = None
    speaker: str | None = None
    user_input: str | None = None

    def calculate_latency(self) -> None:
        """Calculate latency from start/end times."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.latency_ms = delta.total_seconds() * 1000


class SignalLogger:
    """Logs LLM signals to Redis for dashboard consumption.

    Signals are stored in:
    - Redis Stream: barnabeenet:signals:llm (real-time feed for dashboard)
    - Redis Hash: barnabeenet:signals:llm:{signal_id} (detailed lookup)

    The dashboard can:
    - Stream live signals via XREAD
    - Query historical signals
    - Inspect full request/response details
    """

    STREAM_KEY = "barnabeenet:signals:llm"
    SIGNAL_PREFIX = "barnabeenet:signals:llm:"
    SIGNAL_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days retention

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client
        self._fallback_logs: list[LLMSignal] = []  # In-memory fallback if no Redis

    async def set_redis(self, redis_client: redis.Redis) -> None:
        """Set Redis client after initialization."""
        self._redis = redis_client

    async def log_signal(self, signal: LLMSignal) -> None:
        """Log an LLM signal for dashboard visibility."""
        signal.calculate_latency()

        # Log to Python logger for file/console output
        log_level = logging.INFO if signal.success else logging.WARNING
        logger.log(
            log_level,
            "LLM %s | %s | %s | %d→%d tokens | %.0fms | $%.5f | %s",
            signal.agent_type,
            signal.model,
            "OK" if signal.success else f"ERR: {signal.error_type}",
            signal.input_tokens or 0,
            signal.output_tokens or 0,
            signal.latency_ms or 0,
            signal.cost_usd or 0,
            signal.user_input[:50] if signal.user_input else "N/A",
        )

        if self._redis is None:
            # Fallback: store in memory (limited to last 1000)
            self._fallback_logs.append(signal)
            if len(self._fallback_logs) > 1000:
                self._fallback_logs.pop(0)
            return

        try:
            # Store full signal details
            signal_key = f"{self.SIGNAL_PREFIX}{signal.signal_id}"
            signal_json = signal.model_dump_json()
            await self._redis.setex(signal_key, self.SIGNAL_TTL_SECONDS, signal_json)

            # Add to stream for real-time dashboard feed
            # Stream entry contains summary; full details via signal_id lookup
            stream_data = {
                "signal_id": signal.signal_id,
                "timestamp": signal.timestamp.isoformat(),
                "agent_type": signal.agent_type,
                "model": signal.model,
                "success": str(signal.success),
                "latency_ms": str(signal.latency_ms or 0),
                "input_tokens": str(signal.input_tokens or 0),
                "output_tokens": str(signal.output_tokens or 0),
                "cost_usd": str(signal.cost_usd or 0),
                "user_input": (signal.user_input or "")[:100],
                "response_preview": (signal.response_text or "")[:200],
                "error": signal.error or "",
            }
            await self._redis.xadd(
                self.STREAM_KEY,
                stream_data,
                maxlen=10000,  # Keep last 10k signals in stream
            )

        except Exception as e:
            logger.error("Failed to log signal to Redis: %s", e)
            self._fallback_logs.append(signal)

    async def get_signal(self, signal_id: str) -> LLMSignal | None:
        """Retrieve full signal details by ID."""
        if self._redis is None:
            for sig in self._fallback_logs:
                if sig.signal_id == signal_id:
                    return sig
            return None

        signal_key = f"{self.SIGNAL_PREFIX}{signal_id}"
        data = await self._redis.get(signal_key)
        if data:
            return LLMSignal.model_validate_json(data)
        return None

    async def get_recent_signals(
        self,
        count: int = 100,
        agent_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent signals from the stream for dashboard display."""
        if self._redis is None:
            signals = self._fallback_logs[-count:]
            if agent_type:
                signals = [s for s in signals if s.agent_type == agent_type]
            return [s.model_dump() for s in reversed(signals)]

        # Read from stream (most recent first)
        entries = await self._redis.xrevrange(self.STREAM_KEY, count=count)
        results = []
        for entry_id, data in entries:
            if agent_type and data.get("agent_type") != agent_type:
                continue
            data["stream_id"] = entry_id
            results.append(data)
        return results


# Global signal logger instance
_signal_logger: SignalLogger | None = None


def get_signal_logger() -> SignalLogger:
    """Get the global signal logger instance."""
    global _signal_logger
    if _signal_logger is None:
        _signal_logger = SignalLogger()
    return _signal_logger
