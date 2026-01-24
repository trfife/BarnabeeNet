"""Timer API routes.

Endpoints for timer management:
- Get timer status
- List active timers
- Create timers
- Cancel timers
- Pause/resume timers
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from barnabeenet.services.timers import (
    TimerType,
    format_duration,
    get_timer_manager_sync,
    parse_duration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timers", tags=["Timers"])


# =============================================================================
# Response Models
# =============================================================================


class TimerStatusResponse(BaseModel):
    """Timer manager status response."""

    initialized: bool = Field(description="Whether timer manager is initialized")
    callback_registered: bool = Field(description="Whether state change callback is registered")
    pool_available: int = Field(description="Number of available timer entities")
    pool_in_use: int = Field(description="Number of timer entities in use")
    active_timers: int = Field(description="Number of active timers")
    available_entities: list[str] = Field(description="List of available timer entity IDs")


class TimerInfo(BaseModel):
    """Information about a single timer."""

    id: str
    timer_type: str
    ha_timer_entity: str
    label: str
    duration_seconds: float
    remaining_seconds: float
    started_at: str
    ends_at: str
    speaker: str | None = None
    room: str | None = None
    is_paused: bool = False
    on_complete: dict[str, Any] | None = None


class TimerListResponse(BaseModel):
    """List of active timers."""

    timers: list[TimerInfo]
    count: int


class CreateTimerRequest(BaseModel):
    """Request to create a timer."""

    duration: str = Field(description="Duration (e.g., '5 minutes', '30 seconds')")
    label: str | None = Field(None, description="Timer label (e.g., 'pizza')")
    timer_type: str = Field("alarm", description="Timer type: alarm, device_duration, delayed_action")
    speaker: str | None = Field(None, description="Who created the timer")
    room: str | None = Field(None, description="Where the timer was created")
    on_complete: dict[str, Any] | None = Field(
        None,
        description="Action to execute when timer completes (service call)",
    )


class CreateTimerResponse(BaseModel):
    """Response from creating a timer."""

    success: bool
    timer: TimerInfo | None = None
    message: str


class CancelTimerResponse(BaseModel):
    """Response from cancelling a timer."""

    success: bool
    message: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=TimerStatusResponse)
async def get_timer_status() -> TimerStatusResponse:
    """Get timer manager status.

    Returns information about the timer manager state, pool availability,
    and active timers count.
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return TimerStatusResponse(
            initialized=False,
            callback_registered=False,
            pool_available=0,
            pool_in_use=0,
            active_timers=0,
            available_entities=[],
        )

    status = timer_manager.get_status()
    return TimerStatusResponse(
        initialized=status["initialized"],
        callback_registered=status["callback_registered"],
        pool_available=status["pool_available"],
        pool_in_use=status["pool_in_use"],
        active_timers=status["active_timers"],
        available_entities=status["available_entities"],
    )


@router.get("/", response_model=TimerListResponse)
async def list_timers() -> TimerListResponse:
    """List all active timers.

    Returns a list of all currently active timers with their status.
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return TimerListResponse(timers=[], count=0)

    timers = timer_manager.get_active_timers()
    timer_list = [
        TimerInfo(
            id=t.id,
            timer_type=t.timer_type.value,
            ha_timer_entity=t.ha_timer_entity,
            label=t.label,
            duration_seconds=t.duration.total_seconds(),
            remaining_seconds=t.remaining.total_seconds(),
            started_at=t.started_at.isoformat(),
            ends_at=t.ends_at.isoformat(),
            speaker=t.speaker,
            room=t.room,
            is_paused=t.is_paused,
            on_complete=t.on_complete,
        )
        for t in timers
    ]

    return TimerListResponse(timers=timer_list, count=len(timer_list))


@router.get("/{timer_id}", response_model=TimerInfo)
async def get_timer(timer_id: str) -> TimerInfo:
    """Get a specific timer by ID.

    Args:
        timer_id: The timer ID to look up

    Returns:
        Timer information

    Raises:
        404 if timer not found
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        raise HTTPException(status_code=503, detail="Timer manager not initialized")

    timer = timer_manager.get_timer(timer_id)
    if timer is None:
        raise HTTPException(status_code=404, detail=f"Timer {timer_id} not found")

    return TimerInfo(
        id=timer.id,
        timer_type=timer.timer_type.value,
        ha_timer_entity=timer.ha_timer_entity,
        label=timer.label,
        duration_seconds=timer.duration.total_seconds(),
        remaining_seconds=timer.remaining.total_seconds(),
        started_at=timer.started_at.isoformat(),
        ends_at=timer.ends_at.isoformat(),
        speaker=timer.speaker,
        room=timer.room,
        is_paused=timer.is_paused,
        on_complete=timer.on_complete,
    )


@router.post("/", response_model=CreateTimerResponse)
async def create_timer(request: CreateTimerRequest) -> CreateTimerResponse:
    """Create a new timer.

    Args:
        request: Timer creation request

    Returns:
        Created timer information
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return CreateTimerResponse(
            success=False,
            message="Timer manager not initialized",
        )

    # Parse duration
    duration = parse_duration(request.duration)
    if duration is None:
        return CreateTimerResponse(
            success=False,
            message=f"Could not parse duration: {request.duration}",
        )

    # Parse timer type
    try:
        timer_type = TimerType(request.timer_type)
    except ValueError:
        return CreateTimerResponse(
            success=False,
            message=f"Invalid timer type: {request.timer_type}",
        )

    # Create timer
    timer = await timer_manager.create_timer(
        timer_type=timer_type,
        duration=duration,
        label=request.label,
        speaker=request.speaker,
        room=request.room,
        on_complete=request.on_complete,
    )

    if timer is None:
        return CreateTimerResponse(
            success=False,
            message="No timer entities available",
        )

    return CreateTimerResponse(
        success=True,
        timer=TimerInfo(
            id=timer.id,
            timer_type=timer.timer_type.value,
            ha_timer_entity=timer.ha_timer_entity,
            label=timer.label,
            duration_seconds=timer.duration.total_seconds(),
            remaining_seconds=timer.remaining.total_seconds(),
            started_at=timer.started_at.isoformat(),
            ends_at=timer.ends_at.isoformat(),
            speaker=timer.speaker,
            room=timer.room,
            is_paused=timer.is_paused,
            on_complete=timer.on_complete,
        ),
        message=f"Created {timer.label} timer for {format_duration(timer.duration)}",
    )


@router.delete("/{timer_id}", response_model=CancelTimerResponse)
async def cancel_timer(timer_id: str) -> CancelTimerResponse:
    """Cancel a timer by ID.

    Args:
        timer_id: The timer ID to cancel

    Returns:
        Cancellation result
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return CancelTimerResponse(
            success=False,
            message="Timer manager not initialized",
        )

    success = await timer_manager.cancel_timer(timer_id)
    if success:
        return CancelTimerResponse(
            success=True,
            message=f"Cancelled timer {timer_id}",
        )
    else:
        return CancelTimerResponse(
            success=False,
            message=f"Timer {timer_id} not found",
        )


@router.post("/{timer_id}/pause", response_model=CancelTimerResponse)
async def pause_timer(timer_id: str) -> CancelTimerResponse:
    """Pause a timer by ID.

    Args:
        timer_id: The timer ID to pause

    Returns:
        Pause result
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return CancelTimerResponse(
            success=False,
            message="Timer manager not initialized",
        )

    success = await timer_manager.pause_timer(timer_id)
    if success:
        return CancelTimerResponse(
            success=True,
            message=f"Paused timer {timer_id}",
        )
    else:
        return CancelTimerResponse(
            success=False,
            message=f"Timer {timer_id} not found or could not be paused",
        )


@router.post("/{timer_id}/resume", response_model=CancelTimerResponse)
async def resume_timer(timer_id: str) -> CancelTimerResponse:
    """Resume a paused timer by ID.

    Args:
        timer_id: The timer ID to resume

    Returns:
        Resume result
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return CancelTimerResponse(
            success=False,
            message="Timer manager not initialized",
        )

    success = await timer_manager.resume_timer(timer_id)
    if success:
        return CancelTimerResponse(
            success=True,
            message=f"Resumed timer {timer_id}",
        )
    else:
        return CancelTimerResponse(
            success=False,
            message=f"Timer {timer_id} not found or could not be resumed",
        )


@router.delete("/", response_model=CancelTimerResponse)
async def cancel_all_timers() -> CancelTimerResponse:
    """Cancel all active timers.

    Returns:
        Cancellation result with count
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return CancelTimerResponse(
            success=False,
            message="Timer manager not initialized",
        )

    count = await timer_manager.cancel_all()
    return CancelTimerResponse(
        success=True,
        message=f"Cancelled {count} timer(s)",
    )


# =============================================================================
# Test Endpoint
# =============================================================================


@router.post("/test/{entity_id}")
async def test_timer_action(entity_id: str, action: str = "turn_off", delay_seconds: int = 10) -> dict[str, Any]:
    """Test endpoint: Create a delayed action timer for an entity.

    This is useful for testing timer functionality.

    Args:
        entity_id: Entity ID to control (e.g., "light.office_light")
        action: Action to perform ("turn_on" or "turn_off")
        delay_seconds: Delay in seconds before action

    Returns:
        Timer creation result
    """
    timer_manager = get_timer_manager_sync()

    if timer_manager is None:
        return {"success": False, "message": "Timer manager not initialized"}

    from datetime import timedelta

    # Determine domain and service
    domain = entity_id.split(".")[0] if "." in entity_id else "light"
    service = f"{domain}.{action}"

    timer = await timer_manager.create_timer(
        timer_type=TimerType.DELAYED_ACTION,
        duration=timedelta(seconds=delay_seconds),
        label=f"test_{action}_{entity_id}",
        speaker="api_test",
        room="api",
        on_complete={
            "service": service,
            "entity_id": entity_id,
            "data": {},
        },
    )

    if timer is None:
        return {"success": False, "message": "No timer entities available"}

    return {
        "success": True,
        "timer_id": timer.id,
        "entity": timer.ha_timer_entity,
        "action": service,
        "target": entity_id,
        "delay_seconds": delay_seconds,
        "message": f"Will {action} {entity_id} in {delay_seconds} seconds",
    }
