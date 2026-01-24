"""Tests for dashboard API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from barnabeenet.main import app
from barnabeenet.services.llm.signals import LLMSignal, SignalLogger


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_signal_logger():
    """Create mock signal logger with test data."""
    logger = SignalLogger()

    # Add some test signals to fallback logs
    for i in range(5):
        signal = LLMSignal(
            signal_id=f"test-signal-{i}",
            agent_type="meta" if i % 2 == 0 else "interaction",
            model="deepseek/deepseek-v3",
            timestamp=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            latency_ms=100 + i * 50,
            input_tokens=100 + i * 10,
            output_tokens=50 + i * 5,
            cost_usd=0.001 * (i + 1),
            success=True,
            user_input=f"Test input {i}",
            response_text=f"Test response {i}",
        )
        logger._fallback_logs.append(signal)

    return logger


class TestSystemStatus:
    """Tests for /api/v1/dashboard/status endpoint."""

    def test_status_returns_success(self, client):
        """Test status endpoint returns valid response."""
        response = client.get("/api/v1/dashboard/status")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["ok", "degraded", "error"]
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
        assert "version" in data
        assert "components" in data

    def test_status_includes_components(self, client):
        """Test status includes component health."""
        response = client.get("/api/v1/dashboard/status")

        data = response.json()
        components = data["components"]

        assert "redis" in components
        assert "orchestrator" in components
        assert "gpu_worker" in components


class TestActivityFeed:
    """Tests for /api/v1/dashboard/activity endpoint."""

    def test_activity_returns_empty_list(self, client):
        """Test activity endpoint returns empty list when no signals."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock_logger = AsyncMock()
            mock_logger.get_recent_signals = AsyncMock(return_value=[])
            mock.return_value = mock_logger

            response = client.get("/api/v1/dashboard/activity")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total_count"] == 0
        assert data["has_more"] is False

    def test_activity_returns_signals(self, client, mock_signal_logger):
        """Test activity endpoint returns signals."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/activity")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total_count"] == 5

    def test_activity_respects_limit(self, client, mock_signal_logger):
        """Test activity endpoint respects limit parameter."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/activity?limit=2")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2

    def test_activity_filters_by_agent_type(self, client, mock_signal_logger):
        """Test activity endpoint filters by agent_type."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/activity?agent_type=meta")

        assert response.status_code == 200
        data = response.json()

        # Should only have meta agent signals (indices 0, 2, 4 = 3 total)
        for item in data["items"]:
            assert item["agent_type"] == "meta"

    def test_activity_validates_limit_range(self, client):
        """Test activity endpoint validates limit parameter."""
        # Too high
        response = client.get("/api/v1/dashboard/activity?limit=1000")
        assert response.status_code == 422

        # Too low
        response = client.get("/api/v1/dashboard/activity?limit=0")
        assert response.status_code == 422


class TestSignalDetail:
    """Tests for /api/v1/dashboard/signals/{signal_id} endpoint."""

    def test_signal_detail_returns_signal(self, client, mock_signal_logger):
        """Test signal detail returns full signal info."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/signals/test-signal-0")

        assert response.status_code == 200
        data = response.json()

        assert data["signal_id"] == "test-signal-0"
        assert data["agent_type"] == "meta"
        assert data["model"] == "deepseek/deepseek-v3"
        assert "timestamp" in data
        assert "input_tokens" in data
        assert "output_tokens" in data

    def test_signal_detail_not_found(self, client, mock_signal_logger):
        """Test signal detail returns 404 for unknown signal."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/signals/nonexistent")

        assert response.status_code == 404


class TestDashboardStats:
    """Tests for /api/v1/dashboard/stats endpoint."""

    def test_stats_returns_empty_defaults(self, client):
        """Test stats endpoint returns defaults when no signals."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock_logger = AsyncMock()
            mock_logger.get_recent_signals = AsyncMock(return_value=[])
            mock.return_value = mock_logger

            response = client.get("/api/v1/dashboard/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_requests_24h"] == 0
        assert data["total_cost_24h"] == 0.0
        assert data["avg_latency_ms"] == 0.0
        assert data["error_rate_percent"] == 0.0
        assert data["requests_by_agent"] == {}

    def test_stats_calculates_correctly(self, client, mock_signal_logger):
        """Test stats endpoint calculates metrics correctly."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock.return_value = mock_signal_logger

            response = client.get("/api/v1/dashboard/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_requests_24h"] == 5
        assert data["total_cost_24h"] > 0
        assert data["avg_latency_ms"] > 0
        assert data["error_rate_percent"] == 0.0  # All test signals are success
        assert "meta" in data["requests_by_agent"]
        assert "interaction" in data["requests_by_agent"]
