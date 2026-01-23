"""Tests to verify dashboard API contract is maintained.

These tests ensure that all dashboard pages have working API endpoints.
Run these tests after any API changes to verify backward compatibility.

The contract is defined in src/barnabeenet/dashboard_contract.yaml.

Note: Some tests may be skipped if dependencies (Redis, sentence_transformers)
are not available in the test environment.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

# Skip all tests if FastAPI app can't be imported due to missing dependencies
try:
    from fastapi.testclient import TestClient
    from barnabeenet.main import app
    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    app = None


@pytest.fixture
def client():
    """Create test client."""
    if not APP_AVAILABLE:
        pytest.skip("App not available - missing dependencies")
    return TestClient(app)


@pytest.fixture
def contract():
    """Load the dashboard contract YAML."""
    contract_path = Path(__file__).parent.parent / "src/barnabeenet/dashboard_contract.yaml"
    with open(contract_path) as f:
        return yaml.safe_load(f)


class TestDashboardContract:
    """Verify all dashboard contract endpoints exist and return expected fields."""

    def test_contract_file_exists(self):
        """Verify the contract file exists."""
        contract_path = Path(__file__).parent.parent / "src/barnabeenet/dashboard_contract.yaml"
        assert contract_path.exists(), "Dashboard contract file not found"

    def test_contract_has_pages(self, contract):
        """Verify contract has required page definitions."""
        assert "pages" in contract, "Contract missing 'pages' section"
        assert len(contract["pages"]) > 0, "Contract has no pages defined"

    def test_dashboard_status_endpoint(self, client):
        """Test /api/v1/dashboard/status returns required fields."""
        response = client.get("/api/v1/dashboard/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data, "Response missing 'status' field"
        assert "uptime_seconds" in data, "Response missing 'uptime_seconds' field"
        assert "version" in data, "Response missing 'version' field"

    def test_dashboard_stats_endpoint(self, client):
        """Test /api/v1/dashboard/stats returns required fields."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock_logger = AsyncMock()
            mock_logger.get_recent_signals = AsyncMock(return_value=[])
            mock.return_value = mock_logger

            response = client.get("/api/v1/dashboard/stats")

        assert response.status_code == 200

        data = response.json()
        assert "total_requests_24h" in data, "Response missing 'total_requests_24h' field"
        assert "total_cost_24h" in data, "Response missing 'total_cost_24h' field"
        assert "avg_latency_ms" in data, "Response missing 'avg_latency_ms' field"

    def test_dashboard_activity_endpoint(self, client):
        """Test /api/v1/dashboard/activity returns required fields."""
        with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock:
            mock_logger = AsyncMock()
            mock_logger.get_recent_signals = AsyncMock(return_value=[])
            mock.return_value = mock_logger

            response = client.get("/api/v1/dashboard/activity")

        assert response.status_code == 200

        data = response.json()
        assert "items" in data, "Response missing 'items' field"
        assert "total_count" in data, "Response missing 'total_count' field"
        assert "has_more" in data, "Response missing 'has_more' field"

    def test_chat_endpoint_exists(self, client):
        """Test /api/v1/chat endpoint exists (POST method)."""
        # Just verify the endpoint exists and accepts POST
        # Full functionality requires orchestrator initialization
        response = client.post(
            "/api/v1/chat",
            json={"text": "hello"},
        )
        # Endpoint should exist - may return 500 if orchestrator not initialized
        # but should not return 404 or 405
        assert response.status_code in (200, 500, 503), (
            f"Chat endpoint returned unexpected status {response.status_code}"
        )

    def test_memory_stats_endpoint(self, client):
        """Test /api/v1/memory/stats returns required fields."""
        with patch("barnabeenet.api.routes.memory._get_memory_storage") as mock:
            mock_storage = AsyncMock()
            mock_storage.get_all_memories = AsyncMock(return_value=[])
            mock_storage._use_redis = True
            mock.return_value = mock_storage

            response = client.get("/api/v1/memory/stats")

        assert response.status_code == 200

        data = response.json()
        assert "total_memories" in data, "Response missing 'total_memories' field"
        assert "by_type" in data, "Response missing 'by_type' field"
        assert "recent_24h" in data, "Response missing 'recent_24h' field"
        assert "recent_7d" in data, "Response missing 'recent_7d' field"
        assert "storage_backend" in data, "Response missing 'storage_backend' field"

    def test_memory_list_endpoint(self, client):
        """Test /api/v1/memory/ returns required fields."""
        with patch("barnabeenet.api.routes.memory._get_memory_storage") as mock:
            mock_storage = AsyncMock()
            mock_storage.get_all_memories = AsyncMock(return_value=[])
            mock.return_value = mock_storage

            response = client.get("/api/v1/memory/")

        assert response.status_code == 200

        data = response.json()
        assert "memories" in data, "Response missing 'memories' field"
        assert "total" in data, "Response missing 'total' field"
        assert "page" in data, "Response missing 'page' field"
        assert "page_size" in data, "Response missing 'page_size' field"

    def test_timers_endpoint(self, client):
        """Test /api/v1/timers returns required fields."""
        response = client.get("/api/v1/timers")
        assert response.status_code == 200

        data = response.json()
        assert "timers" in data, "Response missing 'timers' field"

    def test_config_providers_endpoint(self, client):
        """Test /api/v1/config/providers returns required fields."""
        response = client.get("/api/v1/config/providers")
        # May return 500 if Redis not connected, but endpoint should exist
        assert response.status_code in (200, 500, 503), (
            f"Config providers endpoint returned unexpected status {response.status_code}"
        )

        if response.status_code == 200:
            data = response.json()
            assert "providers" in data, "Response missing 'providers' field"

    def test_self_improvement_sessions_endpoint(self, client):
        """Test /api/v1/self-improve/sessions returns required fields."""
        response = client.get("/api/v1/self-improve/sessions")
        assert response.status_code == 200

        # Sessions endpoint returns a list directly
        data = response.json()
        assert isinstance(data, list), "Response should be a list of sessions"


class TestContractCompleteness:
    """Verify all pages in contract have working endpoints."""

    def test_all_get_endpoints_exist(self, client, contract):
        """Verify all GET endpoints in contract return 2xx or 4xx (not 404)."""
        skip_endpoints = contract.get("testing", {}).get("skip_endpoints", [])

        for page_name, page_config in contract["pages"].items():
            for endpoint in page_config.get("required_endpoints", []):
                if endpoint["method"] != "GET":
                    continue

                path = endpoint["path"]

                # Skip endpoints that require special setup
                if path in skip_endpoints:
                    continue

                # Replace path parameters with test values
                test_path = path.replace("{memory_id}", "test-id")
                test_path = test_path.replace("{session_id}", "test-session")
                test_path = test_path.replace("{member_id}", "test-member")

                # Make request (with mocking for endpoints that need it)
                with patch("barnabeenet.api.routes.memory._get_memory_storage") as mock_storage:
                    mock_storage_obj = AsyncMock()
                    mock_storage_obj.get_all_memories = AsyncMock(return_value=[])
                    mock_storage_obj.get_memory = AsyncMock(return_value=None)
                    mock_storage_obj._use_redis = True
                    mock_storage.return_value = mock_storage_obj

                    with patch("barnabeenet.api.routes.dashboard.get_signal_logger") as mock_logger:
                        mock_logger_obj = AsyncMock()
                        mock_logger_obj.get_recent_signals = AsyncMock(return_value=[])
                        mock_logger.return_value = mock_logger_obj

                        response = client.get(test_path)

                # Endpoint should exist (not 404)
                # 404 for specific resources (like memory/{id}) is OK
                assert response.status_code != 404 or "{" in path, (
                    f"Endpoint {path} for page '{page_name}' returned 404"
                )
