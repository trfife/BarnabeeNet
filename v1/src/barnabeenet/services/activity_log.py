"""Unified Activity Log System.

Captures ALL system activity and broadcasts to dashboard in real-time:
- User interactions (voice input, text input)
- Agent reasoning chains (meta → action → response)
- Home Assistant events (state changes, service calls)
- Memory operations (store, retrieve, search)
- LLM calls (request, response, tokens, cost)
- System events (startup, errors, health checks)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ActivityType(str, Enum):
    """Types of activities that can be logged."""

    # User activities
    USER_INPUT = "user.input"
    USER_VOICE = "user.voice"
    USER_GESTURE = "user.gesture"

    # Agent activities
    AGENT_THINKING = "agent.thinking"
    AGENT_DECISION = "agent.decision"
    AGENT_HANDOFF = "agent.handoff"
    AGENT_RESPONSE = "agent.response"

    # Specific agent types
    META_CLASSIFY = "meta.classify"
    META_ROUTE = "meta.route"
    INSTANT_MATCH = "instant.match"
    INSTANT_RESPOND = "instant.respond"
    ACTION_PARSE = "action.parse"
    ACTION_EXECUTE = "action.execute"
    ACTION_CONFIRM = "action.confirm"
    INTERACTION_THINK = "interaction.think"
    INTERACTION_RESPOND = "interaction.respond"
    MEMORY_SEARCH = "memory.search"
    MEMORY_RETRIEVE = "memory.retrieve"
    MEMORY_STORE = "memory.store"

    # LLM activities
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"

    # Home Assistant activities
    HA_STATE_CHANGE = "ha.state_change"
    HA_SERVICE_CALL = "ha.service_call"
    HA_EVENT = "ha.event"
    HA_SENSOR_UPDATE = "ha.sensor_update"

    # Memory activities
    MEMORY_FACT_EXTRACTED = "memory.fact_extracted"
    MEMORY_CONSOLIDATED = "memory.consolidated"

    # System activities
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"

    # Self-improvement activities
    SELF_IMPROVE_START = "self_improve.start"
    SELF_IMPROVE_DIAGNOSING = "self_improve.diagnosing"
    SELF_IMPROVE_PLAN_PROPOSED = "self_improve.plan_proposed"
    SELF_IMPROVE_PLAN_APPROVED = "self_improve.plan_approved"
    SELF_IMPROVE_IMPLEMENTING = "self_improve.implementing"
    SELF_IMPROVE_TESTING = "self_improve.testing"
    SELF_IMPROVE_AWAITING_APPROVAL = "self_improve.awaiting_approval"
    SELF_IMPROVE_COMMITTED = "self_improve.committed"
    SELF_IMPROVE_FAILED = "self_improve.failed"
    SELF_IMPROVE_STOPPED = "self_improve.stopped"


class ActivityLevel(str, Enum):
    """Activity importance levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class Activity(BaseModel):
    """A single activity log entry."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Classification
    type: ActivityType
    level: ActivityLevel = ActivityLevel.INFO

    # Context
    trace_id: str | None = None  # Links related activities
    conversation_id: str | None = None
    speaker: str | None = None
    room: str | None = None

    # Content
    source: str  # Component that generated this (meta_agent, ha_client, etc.)
    title: str  # Short description for log display
    detail: str | None = None  # Longer explanation
    data: dict[str, Any] = Field(default_factory=dict)  # Structured data

    # For agent chain visualization
    agent: str | None = None
    parent_id: str | None = None  # For nested activities
    duration_ms: float | None = None

    # For LLM activities
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None


class AgentStep(BaseModel):
    """A step in the agent reasoning chain (for chat display)."""

    step_number: int
    agent: str
    action: str  # "thinking", "decided", "responding", "delegating"
    summary: str
    detail: str | None = None
    duration_ms: float | None = None
    model_used: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationTrace(BaseModel):
    """Complete trace of a conversation turn (for chat display)."""

    trace_id: str
    started_at: datetime
    completed_at: datetime | None = None

    # Input
    user_input: str
    speaker: str | None = None
    room: str | None = None
    input_type: str = "text"  # text, voice, gesture

    # Agent chain
    steps: list[AgentStep] = Field(default_factory=list)

    # Output
    response: str | None = None
    response_type: str = "spoken"  # spoken, action, silent

    # Metrics
    total_duration_ms: float | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Status
    success: bool = True
    error: str | None = None


class ActivityLogger:
    """Central activity logging service.

    Collects activities from all components and broadcasts to dashboard.
    Maintains recent activity buffer and conversation traces.
    """

    def __init__(self, max_activities: int = 5000, max_traces: int = 100) -> None:
        self._activities: list[Activity] = []
        self._traces: dict[str, ConversationTrace] = {}
        self._max_activities = max_activities
        self._max_traces = max_traces
        self._subscribers: list[Callable[[Activity], Any]] = []
        self._trace_subscribers: list[Callable[[ConversationTrace], Any]] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[Activity], Any]) -> None:
        """Subscribe to activity updates."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Activity], Any]) -> None:
        """Unsubscribe from activity updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def subscribe_traces(self, callback: Callable[[ConversationTrace], Any]) -> None:
        """Subscribe to trace updates."""
        self._trace_subscribers.append(callback)

    async def log(self, activity: Activity) -> None:
        """Log an activity and broadcast to subscribers."""
        async with self._lock:
            self._activities.append(activity)
            if len(self._activities) > self._max_activities:
                self._activities = self._activities[-self._max_activities :]

        # Broadcast to subscribers
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(activity)
                else:
                    callback(activity)
            except Exception as e:
                logger.error(f"Activity subscriber error: {e}")

        # Also log to standard logger for debugging
        log_level = getattr(logging, activity.level.value.upper(), logging.INFO)
        logger.log(log_level, f"[{activity.type.value}] {activity.title}")

    async def log_quick(
        self,
        type: ActivityType,
        source: str,
        title: str,
        detail: str | None = None,
        level: ActivityLevel = ActivityLevel.INFO,
        trace_id: str | None = None,
        **data: Any,
    ) -> Activity:
        """Quick helper to log an activity."""
        activity = Activity(
            type=type,
            level=level,
            source=source,
            title=title,
            detail=detail,
            trace_id=trace_id,
            data=data,
        )
        await self.log(activity)
        return activity

    # -------------------------------------------------------------------------
    # Conversation Traces (for chat step-by-step display)
    # -------------------------------------------------------------------------

    async def start_trace(
        self,
        trace_id: str,
        user_input: str,
        speaker: str | None = None,
        room: str | None = None,
        input_type: str = "text",
    ) -> ConversationTrace:
        """Start a new conversation trace."""
        trace = ConversationTrace(
            trace_id=trace_id,
            started_at=datetime.now(UTC),
            user_input=user_input,
            speaker=speaker,
            room=room,
            input_type=input_type,
        )

        async with self._lock:
            self._traces[trace_id] = trace
            # Trim old traces
            if len(self._traces) > self._max_traces:
                oldest = sorted(self._traces.keys())[0]
                del self._traces[oldest]

        # Log the user input as an activity
        await self.log_quick(
            type=ActivityType.USER_INPUT,
            source="user",
            title=f"User ({speaker or 'unknown'}): {user_input[:50]}...",
            detail=user_input,
            trace_id=trace_id,
            speaker=speaker,
            room=room,
        )

        return trace

    async def add_step(
        self,
        trace_id: str,
        agent: str,
        action: str,
        summary: str,
        detail: str | None = None,
        duration_ms: float | None = None,
        model_used: str | None = None,
    ) -> AgentStep | None:
        """Add a step to a conversation trace."""
        if trace_id not in self._traces:
            logger.warning(f"Trace {trace_id} not found")
            return None

        trace = self._traces[trace_id]
        step = AgentStep(
            step_number=len(trace.steps) + 1,
            agent=agent,
            action=action,
            summary=summary,
            detail=detail,
            duration_ms=duration_ms,
            model_used=model_used,
        )
        trace.steps.append(step)

        # Determine activity type based on agent
        type_map = {
            "meta": ActivityType.META_CLASSIFY,
            "instant": ActivityType.INSTANT_RESPOND,
            "action": ActivityType.ACTION_EXECUTE,
            "interaction": ActivityType.INTERACTION_RESPOND,
            "memory": ActivityType.MEMORY_SEARCH,
        }
        activity_type = type_map.get(agent, ActivityType.AGENT_THINKING)

        # Log as activity
        await self.log_quick(
            type=activity_type,
            source=agent,
            title=f"{agent.title()}Agent: {summary}",
            detail=detail,
            trace_id=trace_id,
            agent=agent,
            action=action,
            duration_ms=duration_ms,
            model=model_used,
        )

        # Broadcast trace update
        for callback in self._trace_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trace)
                else:
                    callback(trace)
            except Exception as e:
                logger.error(f"Trace subscriber error: {e}")

        return step

    async def complete_trace(
        self,
        trace_id: str,
        response: str,
        success: bool = True,
        error: str | None = None,
    ) -> ConversationTrace | None:
        """Complete a conversation trace."""
        if trace_id not in self._traces:
            return None

        trace = self._traces[trace_id]
        trace.completed_at = datetime.now(UTC)
        trace.response = response
        trace.success = success
        trace.error = error

        if trace.started_at:
            trace.total_duration_ms = (trace.completed_at - trace.started_at).total_seconds() * 1000

        # Log completion
        await self.log_quick(
            type=ActivityType.AGENT_RESPONSE,
            source="orchestrator",
            title=f"Response: {response[:50]}..." if response else "Empty response",
            detail=response,
            trace_id=trace_id,
            level=ActivityLevel.INFO if success else ActivityLevel.ERROR,
            duration_ms=trace.total_duration_ms,
        )

        return trace

    def get_trace(self, trace_id: str) -> ConversationTrace | None:
        """Get a conversation trace by ID."""
        return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 20) -> list[ConversationTrace]:
        """Get recent conversation traces."""
        traces = sorted(
            self._traces.values(),
            key=lambda t: t.started_at,
            reverse=True,
        )
        return traces[:limit]

    def get_recent_activities(
        self,
        limit: int = 100,
        types: list[ActivityType] | None = None,
        level: ActivityLevel | None = None,
        source: str | None = None,
    ) -> list[Activity]:
        """Get recent activities with optional filtering."""
        activities = self._activities.copy()

        if types:
            activities = [a for a in activities if a.type in types]
        if level:
            activities = [a for a in activities if a.level == level]
        if source:
            activities = [a for a in activities if a.source == source]

        return activities[-limit:][::-1]  # Most recent first


# Global instance
_activity_logger: ActivityLogger | None = None


def get_activity_logger() -> ActivityLogger:
    """Get the global activity logger."""
    global _activity_logger
    if _activity_logger is None:
        _activity_logger = ActivityLogger()
    return _activity_logger


async def log_activity(
    type: ActivityType,
    source: str,
    title: str,
    **kwargs: Any,
) -> Activity:
    """Convenience function to log an activity."""
    return await get_activity_logger().log_quick(type, source, title, **kwargs)
