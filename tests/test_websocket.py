"""Tests for WebSocket endpoints and real-time streaming."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from barnabeenet.api.routes.websocket import (
    ConnectionManager,
    SignalStreamer,
    get_signal_streamer,
)
from barnabeenet.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestConnectionManager:
    """Tests for WebSocket connection manager."""

    @pytest.fixture
    def conn_manager(self):
        """Create a fresh connection manager."""
        return ConnectionManager()

    def test_initial_state(self, conn_manager):
        """Test manager starts with no connections."""
        assert conn_manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_connect_adds_connection(self, conn_manager):
        """Test connecting adds websocket to manager."""
        mock_ws = AsyncMock()
        await conn_manager.connect(mock_ws)

        assert conn_manager.connection_count == 1
        mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_with_filters(self, conn_manager):
        """Test connecting with filters stores them."""
        mock_ws = AsyncMock()
        filters = {"agent_type": "meta", "errors_only": True}

        await conn_manager.connect(mock_ws, filters)

        assert conn_manager.get_filters(mock_ws) == filters

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, conn_manager):
        """Test disconnecting removes websocket."""
        mock_ws = AsyncMock()
        await conn_manager.connect(mock_ws)
        assert conn_manager.connection_count == 1

        conn_manager.disconnect(mock_ws)
        assert conn_manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_set_filters(self, conn_manager):
        """Test updating filters for a connection."""
        mock_ws = AsyncMock()
        await conn_manager.connect(mock_ws, {"agent_type": "meta"})

        conn_manager.set_filters(mock_ws, {"agent_type": "action", "errors_only": True})

        assert conn_manager.get_filters(mock_ws) == {
            "agent_type": "action",
            "errors_only": True,
        }

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, conn_manager):
        """Test broadcast sends to all connected clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await conn_manager.connect(ws1)
        await conn_manager.connect(ws2)

        message = {"signal_id": "test", "agent_type": "meta", "success": True}
        await conn_manager.broadcast(message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_filters_by_agent_type(self, conn_manager):
        """Test broadcast respects agent_type filter."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await conn_manager.connect(ws1, {"agent_type": "meta"})
        await conn_manager.connect(ws2, {"agent_type": "action"})

        message = {"signal_id": "test", "agent_type": "meta", "success": True}
        await conn_manager.broadcast(message)

        ws1.send_json.assert_called_once()  # meta matches
        ws2.send_json.assert_not_called()  # action doesn't match

    @pytest.mark.asyncio
    async def test_broadcast_filters_errors_only(self, conn_manager):
        """Test broadcast respects errors_only filter."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await conn_manager.connect(ws1, {"errors_only": True})
        await conn_manager.connect(ws2, {})

        success_message = {"signal_id": "test", "success": True}
        await conn_manager.broadcast(success_message)

        ws1.send_json.assert_not_called()  # errors_only, but success=True
        ws2.send_json.assert_called_once()  # no filter

    @pytest.mark.asyncio
    async def test_broadcast_filters_min_latency(self, conn_manager):
        """Test broadcast respects min_latency_ms filter."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await conn_manager.connect(ws1, {"min_latency_ms": 1000})
        await conn_manager.connect(ws2, {})

        fast_message = {"signal_id": "test", "latency_ms": 100}
        await conn_manager.broadcast(fast_message)

        ws1.send_json.assert_not_called()  # latency too low
        ws2.send_json.assert_called_once()  # no filter

        ws2.reset_mock()

        slow_message = {"signal_id": "test2", "latency_ms": 1500}
        await conn_manager.broadcast(slow_message)

        ws1.send_json.assert_called_once()  # latency meets threshold

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self, conn_manager):
        """Test broadcast removes clients that fail to receive."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_json.side_effect = Exception("Connection closed")

        await conn_manager.connect(ws1)
        await conn_manager.connect(ws2)
        assert conn_manager.connection_count == 2

        await conn_manager.broadcast({"test": "data"})

        # ws2 should be removed due to error
        assert conn_manager.connection_count == 1


class TestSignalStreamer:
    """Tests for the signal streaming background task."""

    @pytest.fixture
    def streamer(self):
        """Create a fresh signal streamer."""
        return SignalStreamer()

    def test_initial_state(self, streamer):
        """Test streamer starts stopped."""
        assert streamer._running is False
        assert streamer._task is None

    @pytest.mark.asyncio
    async def test_start_sets_running(self, streamer):
        """Test starting sets running flag."""
        with patch.object(streamer, "_stream_loop", new_callable=AsyncMock):
            await streamer.start()
            assert streamer._running is True

            # Clean up
            await streamer.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, streamer):
        """Test stopping clears running flag."""
        with patch.object(streamer, "_stream_loop", new_callable=AsyncMock):
            await streamer.start()
            await streamer.stop()

            assert streamer._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self, streamer):
        """Test calling start multiple times is safe."""
        with patch.object(streamer, "_stream_loop", new_callable=AsyncMock):
            await streamer.start()
            task1 = streamer._task
            await streamer.start()  # Second call
            task2 = streamer._task

            # Same task
            assert task1 is task2

            await streamer.stop()


class TestWebSocketEndpoint:
    """Tests for the /ws/activity endpoint."""

    def test_websocket_connects(self, client):
        """Test WebSocket connection is accepted."""
        with client.websocket_connect("/api/v1/ws/activity") as websocket:
            # Should receive initial status
            data = websocket.receive_json()
            assert data["type"] == "status"
            assert data["data"]["connected"] is True

    def test_websocket_receives_filters_from_query(self, client):
        """Test WebSocket parses query params as filters."""
        with client.websocket_connect(
            "/api/v1/ws/activity?agent_type=meta&errors_only=true"
        ) as websocket:
            data = websocket.receive_json()
            assert data["type"] == "status"
            assert data["data"]["filters"]["agent_type"] == "meta"
            assert data["data"]["filters"]["errors_only"] is True

    def test_websocket_filter_update(self, client):
        """Test client can update filters via message."""
        with client.websocket_connect("/api/v1/ws/activity") as websocket:
            # Get initial status
            websocket.receive_json()

            # Send filter update
            websocket.send_json(
                {"type": "filter", "data": {"agent_type": "action", "errors_only": True}}
            )

            # Should receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "status"
            assert response["data"]["filters_updated"] is True
            assert response["data"]["filters"]["agent_type"] == "action"

    def test_websocket_ping_pong(self, client):
        """Test ping/pong heartbeat works."""
        with client.websocket_connect("/api/v1/ws/activity") as websocket:
            # Get initial status
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "ping", "data": {}})

            # Should receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"


class TestGetSignalStreamer:
    """Tests for signal streamer singleton."""

    def test_returns_same_instance(self):
        """Test get_signal_streamer returns singleton."""
        streamer1 = get_signal_streamer()
        streamer2 = get_signal_streamer()

        assert streamer1 is streamer2
