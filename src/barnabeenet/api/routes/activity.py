"""Activity Log API routes.

Real-time activity feed and conversation traces.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from barnabeenet.services.activity_log import (
    Activity,
    ActivityLevel,
    ActivityType,
    ConversationTrace,
    get_activity_logger,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity", tags=["Activity"])


class ActivityResponse(BaseModel):
    """Activity list response."""

    activities: list[Activity]
    total: int


class TraceResponse(BaseModel):
    """Trace list response."""

    traces: list[ConversationTrace]
    total: int


@router.get("/feed", response_model=ActivityResponse)
async def get_activity_feed(
    limit: int = Query(100, ge=1, le=500),
    types: str | None = Query(None, description="Comma-separated activity types"),
    level: ActivityLevel | None = None,
    source: str | None = None,
) -> ActivityResponse:
    """Get recent activity feed.

    Supports filtering by type, level, and source.
    """
    activity_logger = get_activity_logger()

    type_filter = None
    if types:
        try:
            type_filter = [ActivityType(t.strip()) for t in types.split(",")]
        except ValueError as e:
            raise HTTPException(400, f"Invalid activity type: {e}") from e

    activities = activity_logger.get_recent_activities(
        limit=limit,
        types=type_filter,
        level=level,
        source=source,
    )

    return ActivityResponse(
        activities=activities,
        total=len(activities),
    )


@router.get("/traces", response_model=TraceResponse)
async def get_traces(
    limit: int = Query(20, ge=1, le=100),
) -> TraceResponse:
    """Get recent conversation traces with full agent reasoning chain."""
    activity_logger = get_activity_logger()
    traces = activity_logger.get_recent_traces(limit=limit)

    return TraceResponse(
        traces=traces,
        total=len(traces),
    )


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> ConversationTrace:
    """Get a specific conversation trace."""
    activity_logger = get_activity_logger()
    trace = activity_logger.get_trace(trace_id)

    if not trace:
        raise HTTPException(404, f"Trace {trace_id} not found")

    return trace


@router.get("/types")
async def get_activity_types() -> dict[str, list[str]]:
    """Get all available activity types grouped by category."""
    types: dict[str, list[str]] = {}
    for t in ActivityType:
        category = t.value.split(".")[0]
        if category not in types:
            types[category] = []
        types[category].append(t.value)
    return types
