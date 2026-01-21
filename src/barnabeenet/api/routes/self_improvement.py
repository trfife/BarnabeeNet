"""API routes for Self-Improvement Agent.

Provides endpoints for:
- Submitting improvement requests
- Checking session status
- Approving/rejecting changes
- Viewing cost reports
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from barnabeenet.agents.self_improvement import get_self_improvement_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/self-improve", tags=["Self-Improvement"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ImprovementRequest(BaseModel):
    """Request to improve the codebase."""

    request: str = Field(..., description="Natural language description of what to improve")
    model: str = Field("sonnet", description="Model to use: 'sonnet' or 'opus'")
    auto_approve: bool = Field(False, description="Auto-commit without approval (dangerous!)")
    max_turns: int = Field(50, description="Maximum Claude Code turns")


class SessionResponse(BaseModel):
    """Response with session details."""

    session_id: str
    status: str
    request: str
    started_at: str
    files_modified: list[str]
    estimated_api_cost_usd: float
    success: bool | None
    error: str | None


class CostReport(BaseModel):
    """Cost comparison report."""

    total_sessions: int
    successful_sessions: int
    total_tokens: dict[str, int]
    estimated_api_costs: dict[str, str]
    subscription_cost: str
    savings_vs_api: str


class UserInputRequest(BaseModel):
    """User input to send to an active session."""

    message: str = Field(..., description="Message to send to Claude Code")


class PlanFeedbackRequest(BaseModel):
    """Feedback when approving or rejecting a plan."""

    feedback: str | None = Field(None, description="Additional guidance or reason")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Check if self-improvement agent is available."""
    agent = await get_self_improvement_agent()
    return {
        "available": agent.is_available(),
        "project_path": str(agent.project_path),
        "active_sessions": len(agent.active_sessions),
    }


@router.post("/improve")
async def start_improvement(req: ImprovementRequest) -> dict[str, Any]:
    """Start an improvement session.

    Returns a session ID. Use /sessions/{session_id} to check status,
    or connect to WebSocket for real-time updates.
    """
    import asyncio

    agent = await get_self_improvement_agent()

    if not agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="Claude Code CLI not available. Install with: npm install -g @anthropic-ai/claude-code",
        )

    # Start the improvement in background and return immediately
    async def run_improvement() -> None:
        async for _event in agent.improve(
            request=req.request,
            model=req.model,
            auto_approve=req.auto_approve,
            max_turns=req.max_turns,
        ):
            pass  # Events are broadcast via Redis

    asyncio.create_task(run_improvement())

    # Wait briefly for session to be created
    await asyncio.sleep(0.5)

    # Get the session
    sessions = agent.get_all_sessions()
    if sessions:
        latest = sessions[-1]
        return {
            "session_id": latest["session_id"],
            "status": latest["status"],
            "message": "Improvement session started. Check status or connect to WebSocket for updates.",
        }

    return {"status": "error", "message": "Failed to start session"}


@router.post("/improve/stream")
async def start_improvement_stream(req: ImprovementRequest) -> StreamingResponse:
    """Start an improvement session with streaming response.

    Returns a stream of JSON events as the improvement progresses.
    """
    agent = await get_self_improvement_agent()

    if not agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="Claude Code CLI not available",
        )

    async def event_generator():
        async for event in agent.improve(
            request=req.request,
            model=req.model,
            auto_approve=req.auto_approve,
            max_turns=req.max_turns,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """List all improvement sessions."""
    agent = await get_self_improvement_agent()
    return agent.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get details of a specific session."""
    agent = await get_self_improvement_agent()
    session = agent.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


@router.post("/sessions/{session_id}/approve")
async def approve_session(session_id: str) -> dict[str, Any]:
    """Approve and commit changes from a session."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.approve_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/sessions/{session_id}/reject")
async def reject_session(session_id: str) -> dict[str, Any]:
    """Reject changes and discard the session branch."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.reject_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str) -> dict[str, Any]:
    """Stop an active session immediately."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.stop_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/sessions/{session_id}/input")
async def send_user_input(session_id: str, req: UserInputRequest) -> dict[str, Any]:
    """Send user input to an active session.

    Use this to provide guidance, answer questions, or course-correct
    Claude Code during execution.
    """
    agent = await get_self_improvement_agent()

    try:
        result = await agent.send_user_input(session_id, req.message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/sessions/{session_id}/approve-plan")
async def approve_plan(session_id: str, req: PlanFeedbackRequest | None = None) -> dict[str, Any]:
    """Approve the proposed plan and continue execution."""
    agent = await get_self_improvement_agent()

    try:
        feedback = req.feedback if req else None
        result = await agent.approve_plan(session_id, feedback)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/sessions/{session_id}/reject-plan")
async def reject_plan(session_id: str, req: PlanFeedbackRequest) -> dict[str, Any]:
    """Reject the proposed plan with feedback."""
    agent = await get_self_improvement_agent()

    if not req.feedback:
        raise HTTPException(status_code=400, detail="Feedback required when rejecting plan")

    try:
        result = await agent.reject_plan(session_id, req.feedback)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    """Stream session events via Server-Sent Events (SSE).

    Connect to this endpoint to receive real-time updates for a session.
    Events include: thinking, tool_use, status_change, plan_proposed, completed, failed.
    """
    import asyncio
    import os

    import redis.asyncio as aioredis

    async def event_generator():
        """Generate SSE events from Redis stream."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = aioredis.from_url(redis_url, decode_responses=True)

        # Get the current session state first
        agent = await get_self_improvement_agent()
        session = agent.get_session(session_id)
        if session:
            # Send current state as initial event
            yield f"data: {json.dumps({'event_type': 'init', 'session': session.to_dict()})}\n\n"

        # Track last ID for stream reads
        last_id = "$"  # Start from now

        try:
            while True:
                # Read from Redis stream
                try:
                    messages = await redis_client.xread(
                        {"barnabeenet:self_improvement:events": last_id},
                        count=10,
                        block=5000,  # 5 second timeout
                    )

                    if messages:
                        for _stream_name, stream_messages in messages:
                            for msg_id, msg_data in stream_messages:
                                last_id = msg_id
                                try:
                                    event_data = json.loads(msg_data.get("data", "{}"))
                                    # Only send events for this session
                                    if event_data.get("session_id") == session_id:
                                        yield f"data: {json.dumps(event_data)}\n\n"

                                        # Check for terminal states
                                        if event_data.get("event_type") in [
                                            "completed",
                                            "failed",
                                            "stopped",
                                        ]:
                                            return
                                except json.JSONDecodeError:
                                    continue

                    # Check if session still exists and is active
                    session = agent.get_session(session_id)
                    if not session:
                        yield f"data: {json.dumps({'event_type': 'session_not_found'})}\n\n"
                        return

                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"

                except Exception as e:
                    logger.warning(f"Redis stream read error: {e}")
                    await asyncio.sleep(1)

        finally:
            await redis_client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/cost-report", response_model=CostReport)
async def get_cost_report() -> dict[str, Any]:
    """Get a cost comparison report.

    Shows total usage and what it would cost via API vs subscription.
    """
    agent = await get_self_improvement_agent()
    return agent.get_cost_report()


@router.post("/gpu/restart/{service}")
async def restart_gpu_service(service: str) -> dict[str, Any]:
    """Restart a GPU service on Man-of-war.

    Available services: parakeet-tdt, kokoro-tts, ecapa-tdnn
    """
    allowed_services = ["parakeet-tdt", "kokoro-tts", "ecapa-tdnn"]
    if service not in allowed_services:
        raise HTTPException(status_code=400, detail=f"Unknown service. Allowed: {allowed_services}")

    agent = await get_self_improvement_agent()
    success = await agent.restart_gpu_service(service)

    if success:
        return {"status": "restarted", "service": service}
    raise HTTPException(status_code=500, detail=f"Failed to restart {service}")
