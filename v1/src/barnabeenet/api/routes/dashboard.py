"""Dashboard API routes.

Endpoints for the BarnabeeNet dashboard:
- Activity stream (live feed of signals)
- Request traces (full pipeline flow)
- Signal history and search
- System status
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from barnabeenet.services.llm.signals import get_signal_logger
from barnabeenet.services.pipeline_signals import get_pipeline_logger

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


# =============================================================================
# Request Trace Models & Endpoints
# =============================================================================


class PipelineSignalResponse(BaseModel):
    """A single signal in a pipeline trace."""

    signal_id: str
    signal_type: str
    stage: str
    component: str
    timestamp: str
    latency_ms: float | None = None
    success: bool = True
    error: str | None = None
    model_used: str | None = None
    summary: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None


class RequestTraceResponse(BaseModel):
    """Complete trace of a request through the pipeline."""

    trace_id: str
    started_at: str
    completed_at: str | None = None
    input_text: str
    input_type: str = "text"
    speaker: str | None = None
    room: str | None = None

    # Classification
    intent: str | None = None
    intent_confidence: float | None = None
    context_type: str | None = None
    mood: str | None = None

    # Routing & Processing
    agent_used: str | None = None
    route_reason: str | None = None
    memories_retrieved: list[str] = Field(default_factory=list)
    ha_actions: list[dict[str, Any]] = Field(default_factory=list)

    # Response
    response_text: str = ""
    response_type: str = "spoken"

    # Totals
    total_latency_ms: float | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Status
    success: bool = True
    error: str | None = None

    # All signals
    signals: list[PipelineSignalResponse] = Field(default_factory=list)


class TraceListItem(BaseModel):
    """Summary of a trace for list display."""

    trace_id: str
    timestamp: str
    input_preview: str
    response_preview: str
    intent: str | None = None
    agent_used: str | None = None
    success: bool = True
    total_latency_ms: float | None = None
    signal_count: int = 0


class TraceListResponse(BaseModel):
    """List of recent traces."""

    traces: list[TraceListItem]
    total_count: int


@router.get("/traces", response_model=TraceListResponse)
async def get_recent_traces(
    limit: int = Query(50, ge=1, le=200, description="Number of traces to return"),
) -> TraceListResponse:
    """Get recent request traces for the dashboard.

    Shows the full list of processed requests with summary info.
    """
    pipeline_logger = get_pipeline_logger()
    traces = await pipeline_logger.get_recent_traces(limit=limit)

    items = []
    for trace in traces:
        items.append(
            TraceListItem(
                trace_id=trace.trace_id,
                timestamp=trace.started_at.isoformat(),
                input_preview=trace.input_text[:100] if trace.input_text else "",
                response_preview=trace.response_text[:100] if trace.response_text else "",
                intent=trace.intent,
                agent_used=trace.agent_used,
                success=trace.success,
                total_latency_ms=trace.total_latency_ms,
                signal_count=len(trace.signals),
            )
        )

    return TraceListResponse(
        traces=items,
        total_count=len(items),
    )


@router.get("/traces/{trace_id}", response_model=RequestTraceResponse)
async def get_trace_detail(trace_id: str) -> RequestTraceResponse:
    """Get full details of a specific request trace.

    Shows complete pipeline flow with all signals.
    """
    pipeline_logger = get_pipeline_logger()
    trace = await pipeline_logger.get_trace_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    signals = [
        PipelineSignalResponse(
            signal_id=sig.signal_id,
            signal_type=sig.signal_type.value,
            stage=sig.stage,
            component=sig.component,
            timestamp=sig.timestamp.isoformat(),
            latency_ms=sig.latency_ms,
            success=sig.success,
            error=sig.error,
            model_used=sig.model_used,
            summary=sig.summary,
            input_data=sig.input_data,
            output_data=sig.output_data,
            tokens_in=sig.tokens_in,
            tokens_out=sig.tokens_out,
            cost_usd=sig.cost_usd,
        )
        for sig in trace.signals
    ]

    return RequestTraceResponse(
        trace_id=trace.trace_id,
        started_at=trace.started_at.isoformat(),
        completed_at=trace.completed_at.isoformat() if trace.completed_at else None,
        input_text=trace.input_text,
        input_type=trace.input_type,
        speaker=trace.speaker,
        room=trace.room,
        intent=trace.intent,
        intent_confidence=trace.intent_confidence,
        context_type=trace.context_type,
        mood=trace.mood,
        agent_used=trace.agent_used,
        route_reason=trace.route_reason,
        memories_retrieved=trace.memories_retrieved,
        ha_actions=trace.ha_actions,
        response_text=trace.response_text,
        response_type=trace.response_type,
        total_latency_ms=trace.total_latency_ms,
        total_tokens=trace.total_tokens,
        total_cost_usd=trace.total_cost_usd,
        success=trace.success,
        error=trace.error,
        signals=signals,
    )


@router.get("/pipeline/signals")
async def get_pipeline_signals(
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get recent pipeline signals for real-time display."""
    pipeline_logger = get_pipeline_logger()
    signals = pipeline_logger.get_fallback_signals(limit=limit)

    return [
        {
            "signal_id": sig.signal_id,
            "trace_id": sig.trace_id,
            "signal_type": sig.signal_type.value,
            "stage": sig.stage,
            "component": sig.component,
            "timestamp": sig.timestamp.isoformat(),
            "latency_ms": sig.latency_ms,
            "success": sig.success,
            "error": sig.error,
            "summary": sig.summary,
            "speaker": sig.speaker,
            "room": sig.room,
            "model": sig.model_used,
        }
        for sig in signals
    ]


# =============================================================================
# Metrics Endpoints
# =============================================================================


class LatencyHistoryPoint(BaseModel):
    """Single point in latency history."""

    timestamp: str
    unix_ts: int
    avg_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    count: int


class LatencyStats(BaseModel):
    """Latency statistics."""

    component: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    sample_count: int


class MetricsResponse(BaseModel):
    """Response with metrics data."""

    component: str
    history: list[LatencyHistoryPoint]
    stats: LatencyStats | None = None


class SystemHealthResponse(BaseModel):
    """System health response."""

    status: str
    services: list[dict[str, Any]]
    uptime_seconds: float
    memory_mb: float | None = None
    cpu_percent: float | None = None
    active_connections: int = 0


@router.get("/metrics/{component}", response_model=MetricsResponse)
async def get_component_metrics(
    component: str,
    minutes: int = Query(default=60, ge=1, le=1440),
) -> MetricsResponse:
    """Get latency metrics for a component.

    Args:
        component: Component name (stt, tts, llm, pipeline, memory, action)
        minutes: Time window in minutes (default 60, max 1440)

    Returns:
        Latency history and statistics
    """
    import logging

    from barnabeenet.services.metrics_store import get_metrics_store

    logger = logging.getLogger(__name__)

    try:
        store = await get_metrics_store()
        history = await store.get_latency_history(component, minutes)
        stats = await store.get_latency_stats(component, minutes * 60)

        return MetricsResponse(
            component=component,
            history=[LatencyHistoryPoint(**h) for h in history],
            stats=LatencyStats(
                component=stats.component,
                p50_ms=stats.p50_ms,
                p95_ms=stats.p95_ms,
                p99_ms=stats.p99_ms,
                avg_ms=stats.avg_ms,
                min_ms=stats.min_ms,
                max_ms=stats.max_ms,
                sample_count=stats.sample_count,
            )
            if stats
            else None,
        )
    except Exception as e:
        logger.error("Failed to get metrics for %s: %s", component, e)
        return MetricsResponse(
            component=component,
            history=[],
            stats=None,
        )


@router.get("/health", response_model=SystemHealthResponse)
async def get_health() -> SystemHealthResponse:
    """Get detailed system health status."""
    import logging

    from barnabeenet.services.dashboard_service import get_dashboard_service

    logger = logging.getLogger(__name__)

    try:
        service = await get_dashboard_service()
        health = await service.get_system_health()
        return SystemHealthResponse(
            status=health.status,
            services=[s.model_dump() for s in health.services],
            uptime_seconds=health.uptime_seconds,
            memory_mb=health.memory_mb,
            cpu_percent=health.cpu_percent,
            active_connections=health.active_connections,
        )
    except Exception as e:
        logger.error("Failed to get health: %s", e)
        return SystemHealthResponse(
            status="error",
            services=[],
            uptime_seconds=0,
        )


@router.post("/metrics/{component}/record")
async def record_metric(
    component: str,
    latency_ms: float = Query(..., gt=0),
) -> dict[str, str]:
    """Record a latency measurement (for testing/debugging)."""
    import logging

    from barnabeenet.services.metrics_store import get_metrics_store

    logger = logging.getLogger(__name__)

    try:
        store = await get_metrics_store()
        await store.record_latency(component, latency_ms, None)
        return {"status": "recorded", "component": component, "latency_ms": str(latency_ms)}
    except Exception as e:
        logger.error("Failed to record metric: %s", e)
        return {"status": "error", "message": str(e)}
