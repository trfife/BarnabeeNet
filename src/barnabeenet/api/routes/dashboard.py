"""Dashboard API routes.

Endpoints for the BarnabeeNet dashboard:
- Activity stream (live feed of signals)
- Signal history and search
- System status
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from barnabeenet.services.llm.signals import get_signal_logger

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# =============================================================================
# Response Models
# =============================================================================


class SystemStatus(BaseModel):
    """System status response."""

    status: str = Field(description="Overall system status: ok, degraded, error")
    uptime_seconds: float = Field(description="Server uptime in seconds")
    version: str = Field(description="BarnabeeNet version")
    components: dict[str, str] = Field(description="Component health status")


class ActivityItem(BaseModel):
    """Single activity item in the feed."""

    signal_id: str
    timestamp: str
    event_type: str = Field(description="Type of event: llm, voice, action, memory")
    agent_type: str | None = None
    model: str | None = None
    success: bool = True
    latency_ms: float | None = None
    input_preview: str | None = Field(None, description="First 100 chars of input")
    output_preview: str | None = Field(None, description="First 200 chars of output")
    cost_usd: float | None = None
    error: str | None = None


class ActivityFeed(BaseModel):
    """Activity feed response."""

    items: list[ActivityItem]
    total_count: int
    has_more: bool


class SignalDetail(BaseModel):
    """Full signal details for inspector."""

    signal_id: str
    conversation_id: str | None = None
    trace_id: str | None = None
    timestamp: str
    agent_type: str
    agent_name: str | None = None
    model: str
    provider: str
    temperature: float
    max_tokens: int | None = None
    system_prompt: str | None = None
    messages: list[dict[str, Any]]
    injected_context: dict[str, Any]
    response_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    success: bool
    error: str | None = None
    error_type: str | None = None
    room: str | None = None
    speaker: str | None = None
    user_input: str | None = None


class DashboardStats(BaseModel):
    """Dashboard statistics summary."""

    total_requests_24h: int
    total_cost_24h: float
    avg_latency_ms: float
    error_rate_percent: float
    requests_by_agent: dict[str, int]


# =============================================================================
# Routes
# =============================================================================


@router.get("/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    """Get current system status for dashboard header.

    Returns overall system health, uptime, and component statuses.
    """
    from barnabeenet import __version__
    from barnabeenet.main import app_state

    # Determine component health
    components = {
        "redis": "unknown",
        "orchestrator": "unknown",
        "gpu_worker": "unknown",
    }

    # Check Redis
    if app_state.redis_client:
        try:
            await app_state.redis_client.ping()
            components["redis"] = "healthy"
        except Exception:
            components["redis"] = "unhealthy"
    else:
        components["redis"] = "not_configured"

    # Check Orchestrator
    if app_state.orchestrator:
        components["orchestrator"] = "healthy"
    else:
        components["orchestrator"] = "not_initialized"

    # Check GPU Worker
    if app_state.gpu_worker_available:
        components["gpu_worker"] = "healthy"
    else:
        components["gpu_worker"] = "unavailable"

    # Determine overall status
    healthy_count = sum(1 for v in components.values() if v == "healthy")
    if healthy_count == len(components):
        overall_status = "ok"
    elif healthy_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "error"

    return SystemStatus(
        status=overall_status,
        uptime_seconds=app_state.uptime_seconds,
        version=__version__,
        components=components,
    )


@router.get("/activity", response_model=ActivityFeed)
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=500, description="Number of items to return"),
    agent_type: str | None = Query(None, description="Filter by agent type"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ActivityFeed:
    """Get the activity feed for dashboard display.

    Returns recent LLM signals with filtering and pagination.
    """
    signal_logger = get_signal_logger()

    # Get signals (fetch extra for offset handling)
    fetch_count = limit + offset
    raw_signals = await signal_logger.get_recent_signals(
        count=fetch_count,
        agent_type=agent_type,
    )

    # Apply offset
    signals = raw_signals[offset : offset + limit]

    items = []
    for sig in signals:
        # Handle timestamp - could be datetime or string depending on source
        timestamp = sig.get("timestamp", "")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        # Handle success - could be bool or string depending on source
        success_val = sig.get("success", True)
        if isinstance(success_val, str):
            success = success_val == "True"
        else:
            success = bool(success_val)

        items.append(
            ActivityItem(
                signal_id=sig.get("signal_id", ""),
                timestamp=str(timestamp),
                event_type="llm",
                agent_type=sig.get("agent_type"),
                model=sig.get("model"),
                success=success,
                latency_ms=float(sig.get("latency_ms", 0) or 0),
                input_preview=sig.get("user_input"),
                output_preview=sig.get("response_preview"),
                cost_usd=float(sig.get("cost_usd", 0) or 0) if sig.get("cost_usd") else None,
                error=sig.get("error") or None,
            )
        )

    return ActivityFeed(
        items=items,
        total_count=len(raw_signals),
        has_more=len(raw_signals) > offset + limit,
    )


@router.get("/signals/{signal_id}", response_model=SignalDetail)
async def get_signal_detail(signal_id: str) -> SignalDetail:
    """Get full details of a specific signal.

    This is the "request inspector" - shows complete prompt, response,
    injected context, and all metadata for debugging.
    """
    signal_logger = get_signal_logger()
    signal = await signal_logger.get_signal(signal_id)

    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    return SignalDetail(
        signal_id=signal.signal_id,
        conversation_id=signal.conversation_id,
        trace_id=signal.trace_id,
        timestamp=signal.timestamp.isoformat(),
        agent_type=signal.agent_type,
        agent_name=signal.agent_name,
        model=signal.model,
        provider=signal.provider,
        temperature=signal.temperature,
        max_tokens=signal.max_tokens,
        system_prompt=signal.system_prompt,
        messages=signal.messages,
        injected_context=signal.injected_context,
        response_text=signal.response_text,
        input_tokens=signal.input_tokens,
        output_tokens=signal.output_tokens,
        total_tokens=signal.total_tokens,
        latency_ms=signal.latency_ms,
        cost_usd=signal.cost_usd,
        success=signal.success,
        error=signal.error,
        error_type=signal.error_type,
        room=signal.room,
        speaker=signal.speaker,
        user_input=signal.user_input,
    )


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats() -> DashboardStats:
    """Get statistics summary for dashboard widgets.

    Calculates 24h stats for cost, latency, error rate, and usage.
    """
    signal_logger = get_signal_logger()

    # Get recent signals (last 24h would require timestamp filtering)
    # For now, we get recent signals and compute stats
    recent = await signal_logger.get_recent_signals(count=1000)

    if not recent:
        return DashboardStats(
            total_requests_24h=0,
            total_cost_24h=0.0,
            avg_latency_ms=0.0,
            error_rate_percent=0.0,
            requests_by_agent={},
        )

    total_cost = 0.0
    total_latency = 0.0
    error_count = 0
    requests_by_agent: dict[str, int] = {}

    for sig in recent:
        # Cost
        cost = sig.get("cost_usd", 0)
        total_cost += float(cost) if cost else 0

        # Latency
        latency = sig.get("latency_ms", 0)
        total_latency += float(latency) if latency else 0

        # Errors - handle both bool and string "True"/"False"
        success_val = sig.get("success", True)
        if isinstance(success_val, str):
            is_success = success_val == "True"
        else:
            is_success = bool(success_val)
        if not is_success:
            error_count += 1

        # Agent breakdown
        agent = sig.get("agent_type", "unknown")
        requests_by_agent[agent] = requests_by_agent.get(agent, 0) + 1

    total_requests = len(recent)
    avg_latency = total_latency / total_requests if total_requests > 0 else 0
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

    return DashboardStats(
        total_requests_24h=total_requests,
        total_cost_24h=round(total_cost, 4),
        avg_latency_ms=round(avg_latency, 2),
        error_rate_percent=round(error_rate, 2),
        requests_by_agent=requests_by_agent,
    )
