"""WebSocket endpoints for real-time dashboard updates.

Provides live streaming of signals and events to dashboard clients.
Uses Redis Streams XREAD for efficient pub/sub style consumption.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from barnabeenet.services.activity_log import Activity, get_activity_logger
from barnabeenet.services.llm.signals import get_signal_logger

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


# =============================================================================
# Connection Manager
# =============================================================================


class ConnectionManager:
    """Manages active WebSocket connections.

    Handles connection lifecycle, broadcasting, and filtering.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._connection_filters: dict[WebSocket, dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        self._connection_filters[websocket] = filters or {}
        logger.info(
            "WebSocket connected. Total connections: %d",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        if websocket in self._connection_filters:
            del self._connection_filters[websocket]
        logger.info(
            "WebSocket disconnected. Total connections: %d",
            len(self._connections),
        )

    def get_filters(self, websocket: WebSocket) -> dict[str, Any]:
        """Get filters for a specific connection."""
        return self._connection_filters.get(websocket, {})

    def set_filters(self, websocket: WebSocket, filters: dict[str, Any]) -> None:
        """Update filters for a specific connection."""
        self._connection_filters[websocket] = filters

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send message to all connected clients (with filtering)."""
        disconnected = []
        for websocket in self._connections:
            try:
                # Apply filters
                filters = self._connection_filters.get(websocket, {})
                if self._should_send(message, filters):
                    await websocket.send_json(message)
            except Exception as e:
                logger.warning("Failed to send to WebSocket: %s", e)
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

    def _should_send(self, message: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if message passes the client's filters."""
        # Filter by agent_type
        agent_filter = filters.get("agent_type")
        if agent_filter and message.get("agent_type") != agent_filter:
            return False

        # Filter by event_type
        event_filter = filters.get("event_type")
        if event_filter and message.get("event_type") != event_filter:
            return False

        # Filter by minimum latency (for debugging slow requests)
        min_latency = filters.get("min_latency_ms")
        if min_latency:
            latency = message.get("latency_ms", 0)
            if latency < min_latency:
                return False

        # Filter errors only
        errors_only = filters.get("errors_only", False)
        if errors_only and message.get("success", True):
            return False

        return True

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)


# Global connection manager
manager = ConnectionManager()


# =============================================================================
# WebSocket Message Types
# =============================================================================


class WSMessage(BaseModel):
    """WebSocket message wrapper."""

    type: str  # signal, status, error, ping, pong
    data: dict[str, Any]


# =============================================================================
# WebSocket Routes
# =============================================================================


@router.websocket("/ws/activity")
async def websocket_activity_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for live activity stream.

    Clients connect here to receive real-time LLM signals and events.

    Query params (optional):
    - agent_type: Filter by agent (meta, instant, action, interaction, memory)
    - errors_only: Only send error events (true/false)
    - min_latency_ms: Only send events with latency >= this value

    Client can also send filter updates:
    {"type": "filter", "data": {"agent_type": "meta", "errors_only": true}}

    Server sends:
    {"type": "signal", "data": {...signal data...}}
    {"type": "status", "data": {"connections": 5, "streaming": true}}
    """
    # Parse initial filters from query params
    filters: dict[str, Any] = {}
    query_params = websocket.query_params
    if "agent_type" in query_params:
        filters["agent_type"] = query_params["agent_type"]
    if query_params.get("errors_only") == "true":
        filters["errors_only"] = True
    if "min_latency_ms" in query_params:
        try:
            filters["min_latency_ms"] = float(query_params["min_latency_ms"])
        except ValueError:
            pass

    await manager.connect(websocket, filters)

    try:
        # Send initial status
        await websocket.send_json(
            {
                "type": "status",
                "data": {
                    "connected": True,
                    "connections": manager.connection_count,
                    "filters": filters,
                },
            }
        )

        # Handle incoming messages (filter updates, pings)
        while True:
            try:
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,  # Heartbeat check every 30s
                )
                message = json.loads(raw_message)

                if message.get("type") == "filter":
                    # Update filters
                    new_filters = message.get("data", {})
                    manager.set_filters(websocket, new_filters)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "data": {"filters_updated": True, "filters": new_filters},
                        }
                    )

                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "data": {}})

            except TimeoutError:
                # Send heartbeat ping
                try:
                    await websocket.send_json({"type": "ping", "data": {}})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        manager.disconnect(websocket)


# =============================================================================
# Signal Stream Background Task
# =============================================================================


class SignalStreamer:
    """Background task that reads from Redis Streams and broadcasts to WebSockets.

    Uses XREAD with blocking to efficiently wait for new signals.
    """

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_id = "$"  # Start from latest

    async def start(self) -> None:
        """Start the signal streaming background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._stream_loop())
        logger.info("Signal streamer started")

    async def stop(self) -> None:
        """Stop the signal streaming background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal streamer stopped")

    async def _stream_loop(self) -> None:
        """Main loop that reads signals and broadcasts to clients."""
        signal_logger = get_signal_logger()

        while self._running:
            try:
                # Skip if no connections
                if manager.connection_count == 0:
                    await asyncio.sleep(1.0)
                    continue

                # Try to read from Redis Stream
                if signal_logger._redis is not None:
                    await self._read_from_redis(signal_logger)
                else:
                    # Fallback: poll in-memory logs
                    await self._poll_fallback(signal_logger)

            except Exception as e:
                logger.error("Signal stream error: %s", e)
                await asyncio.sleep(1.0)

    async def _read_from_redis(self, signal_logger) -> None:
        """Read new signals from Redis Stream."""
        from barnabeenet.services.llm.signals import SignalLogger

        try:
            # XREAD with 1 second block timeout
            entries = await signal_logger._redis.xread(
                {SignalLogger.STREAM_KEY: self._last_id},
                count=10,
                block=1000,  # 1 second
            )

            if entries:
                for _stream_name, messages in entries:
                    for msg_id, data in messages:
                        self._last_id = msg_id
                        await self._broadcast_signal(data)

        except Exception as e:
            logger.warning("Redis stream read error: %s", e)
            await asyncio.sleep(1.0)

    async def _poll_fallback(self, signal_logger) -> None:
        """Poll in-memory fallback logs when Redis unavailable."""
        # Simple polling - check if new signals added
        await asyncio.sleep(0.5)

        # This is a simplified fallback - in production, we'd track
        # the last seen index and only broadcast new signals

    async def _broadcast_signal(self, data: dict[str, Any]) -> None:
        """Broadcast a signal to all connected WebSocket clients."""
        # Convert Redis stream data to signal format
        message = {
            "type": "signal",
            "data": {
                "signal_id": data.get("signal_id", ""),
                "timestamp": data.get("timestamp", ""),
                "event_type": "llm",
                "agent_type": data.get("agent_type"),
                "model": data.get("model"),
                "success": data.get("success", "True") == "True",
                "latency_ms": float(data.get("latency_ms", 0) or 0),
                "input_preview": data.get("user_input"),
                "output_preview": data.get("response_preview"),
                "cost_usd": float(data.get("cost_usd", 0) or 0),
                "error": data.get("error") or None,
            },
        }

        await manager.broadcast(message["data"])


# Global signal streamer instance
_signal_streamer: SignalStreamer | None = None


def get_signal_streamer() -> SignalStreamer:
    """Get the global signal streamer instance."""
    global _signal_streamer
    if _signal_streamer is None:
        _signal_streamer = SignalStreamer()
    return _signal_streamer


async def start_signal_streamer() -> None:
    """Start the signal streamer (call during app startup)."""
    streamer = get_signal_streamer()
    await streamer.start()


async def stop_signal_streamer() -> None:
    """Stop the signal streamer (call during app shutdown)."""
    streamer = get_signal_streamer()
    await streamer.stop()


# =============================================================================
# Dashboard WebSocket - Real-time push for all dashboard updates
# =============================================================================


class DashboardConnectionManager:
    """Manages WebSocket connections for the dashboard.

    Supports real-time push for:
    - Activity feed updates
    - Metrics updates
    - Test results
    - System status
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._heartbeat_interval = 30.0
        self._subscribed = False

    def _subscribe_to_activities(self) -> None:
        """Subscribe to activity logger updates."""
        if self._subscribed:
            return
        try:
            activity_logger = get_activity_logger()
            activity_logger.subscribe(self._on_activity)
            self._subscribed = True
            logger.info("DashboardManager subscribed to activity logger")
        except Exception as e:
            logger.warning(f"Failed to subscribe to activity logger: {e}")

    async def _on_activity(self, activity: Activity) -> None:
        """Handle incoming activity from the logger."""
        if not self._connections:
            return
        await self.broadcast(
            "activity",
            {
                "id": activity.id,
                "type": activity.type.value,
                "level": activity.level.value,
                "source": activity.source,
                "title": activity.title,
                "detail": activity.detail,
                "timestamp": activity.timestamp.isoformat(),
                "trace_id": activity.trace_id,
                "duration_ms": activity.duration_ms,
            },
        )

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new dashboard WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        self._subscribe_to_activities()
        logger.info(
            "Dashboard WebSocket connected. Total: %d",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a dashboard WebSocket connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(
            "Dashboard WebSocket disconnected. Total: %d",
            len(self._connections),
        )

    async def broadcast(self, message_type: str, data: dict[str, Any]) -> None:
        """Broadcast message to all dashboard connections."""
        message = {"type": message_type, "data": data}
        disconnected = []

        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Dashboard broadcast failed: %s", e)
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_to(self, websocket: WebSocket, message_type: str, data: dict[str, Any]) -> None:
        """Send message to a specific connection."""
        try:
            await websocket.send_json({"type": message_type, "data": data})
        except Exception as e:
            logger.warning("Dashboard send failed: %s", e)
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """Get number of active dashboard connections."""
        return len(self._connections)


# Global dashboard connection manager
dashboard_manager = DashboardConnectionManager()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time dashboard updates.

    Provides:
    - Activity feed updates
    - Metrics updates (latency graphs)
    - Test result streaming
    - System status updates
    - Heartbeat for connection health

    Client messages:
    - {"type": "subscribe", "channels": ["activity", "metrics", "tests", "status"]}
    - {"type": "ping"}
    """
    await dashboard_manager.connect(websocket)

    try:
        # Send initial connection status
        from barnabeenet.services.dashboard_service import get_dashboard_service

        try:
            service = await get_dashboard_service()
            health = await service.get_system_health()
            await dashboard_manager.send_to(
                websocket,
                "status",
                {"connected": True, "health": health.model_dump()},
            )
        except Exception as e:
            await dashboard_manager.send_to(
                websocket,
                "status",
                {"connected": True, "health": None, "error": str(e)},
            )

        # Main message loop
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=dashboard_manager._heartbeat_interval,
                )

                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await dashboard_manager.send_to(websocket, "pong", {})

                elif msg_type == "get_stats":
                    try:
                        service = await get_dashboard_service()
                        stats = await service.get_stats()
                        await dashboard_manager.send_to(
                            websocket,
                            "stats",
                            stats.model_dump(),
                        )
                    except Exception as e:
                        await dashboard_manager.send_to(
                            websocket,
                            "error",
                            {"message": str(e)},
                        )

                elif msg_type == "get_health":
                    try:
                        service = await get_dashboard_service()
                        health = await service.get_system_health()
                        await dashboard_manager.send_to(
                            websocket,
                            "health",
                            health.model_dump(),
                        )
                    except Exception as e:
                        await dashboard_manager.send_to(
                            websocket,
                            "error",
                            {"message": str(e)},
                        )

                elif msg_type == "get_latency_history":
                    component = data.get("component", "pipeline")
                    minutes = data.get("minutes", 60)
                    try:
                        service = await get_dashboard_service()
                        history = await service.get_latency_history(component, minutes)
                        await dashboard_manager.send_to(
                            websocket,
                            "latency_history",
                            {"component": component, "data": history},
                        )
                    except Exception as e:
                        await dashboard_manager.send_to(
                            websocket,
                            "error",
                            {"message": str(e)},
                        )

            except TimeoutError:
                # Send heartbeat
                await dashboard_manager.send_to(websocket, "heartbeat", {})

    except WebSocketDisconnect:
        dashboard_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Dashboard WebSocket error: %s", e)
        dashboard_manager.disconnect(websocket)


async def broadcast_activity(activity: dict[str, Any]) -> None:
    """Broadcast an activity to all dashboard connections."""
    await dashboard_manager.broadcast("activity", activity)


async def broadcast_metrics(metrics: dict[str, Any]) -> None:
    """Broadcast metrics update to all dashboard connections."""
    await dashboard_manager.broadcast("metrics", metrics)


async def broadcast_test_result(result: dict[str, Any]) -> None:
    """Broadcast test result to all dashboard connections."""
    await dashboard_manager.broadcast("test_result", result)
