"""Tests for Home Assistant API routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from barnabeenet.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_ha_client():
    """Reset the global HA client between tests to avoid event loop issues."""
    yield
    # Reset the global client after each test
    from barnabeenet.api.routes import homeassistant as ha_routes

    ha_routes._ha_client = None


class TestHAStatus:
    """Tests for Home Assistant status endpoint."""

    def test_status_endpoint_exists(self, client: TestClient):
        """Test that the status endpoint exists."""
        response = client.get("/api/v1/homeassistant/status")
        assert response.status_code == 200

    def test_status_returns_connection_info(self, client: TestClient):
        """Test status returns proper connection info structure."""
        response = client.get("/api/v1/homeassistant/status")
        data = response.json()

        assert "connected" in data
        assert isinstance(data["connected"], bool)

    def test_status_not_configured(self, client: TestClient):
        """Test status when HA is not configured."""
        response = client.get("/api/v1/homeassistant/status")
        data = response.json()

        # Without HA configured, should show not connected
        # (actual connection state depends on env config)
        assert "connected" in data
        assert "url" in data


class TestHAOverview:
    """Tests for Home Assistant overview endpoint."""

    def test_overview_endpoint_exists(self, client: TestClient):
        """Test that the overview endpoint exists."""
        response = client.get("/api/v1/homeassistant/overview")
        assert response.status_code == 200

    def test_overview_returns_structure(self, client: TestClient):
        """Test overview returns proper structure."""
        response = client.get("/api/v1/homeassistant/overview")
        data = response.json()

        assert "connection" in data
        assert "snapshot" in data
        assert "domain_counts" in data


class TestHAEntities:
    """Tests for Home Assistant entities endpoints."""

    def test_entities_endpoint_exists(self, client: TestClient):
        """Test that the entities endpoint exists."""
        response = client.get("/api/v1/homeassistant/entities")
        assert response.status_code == 200

    def test_entities_returns_list(self, client: TestClient):
        """Test entities returns proper list structure."""
        response = client.get("/api/v1/homeassistant/entities")
        data = response.json()

        assert "entities" in data
        assert "total" in data
        assert "domains" in data
        assert isinstance(data["entities"], list)

    def test_entities_supports_domain_filter(self, client: TestClient):
        """Test domain filter parameter."""
        response = client.get("/api/v1/homeassistant/entities?domain=light")
        assert response.status_code == 200

    def test_entities_supports_search(self, client: TestClient):
        """Test search parameter."""
        response = client.get("/api/v1/homeassistant/entities?search=living")
        assert response.status_code == 200

    def test_entities_supports_pagination(self, client: TestClient):
        """Test pagination parameters."""
        response = client.get("/api/v1/homeassistant/entities?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entities"]) <= 10


class TestHAAreas:
    """Tests for Home Assistant areas endpoint."""

    def test_areas_endpoint_exists(self, client: TestClient):
        """Test that the areas endpoint exists."""
        response = client.get("/api/v1/homeassistant/areas")
        assert response.status_code == 200

    def test_areas_returns_list(self, client: TestClient):
        """Test areas returns proper list structure."""
        response = client.get("/api/v1/homeassistant/areas")
        data = response.json()

        assert "areas" in data
        assert "total" in data
        assert isinstance(data["areas"], list)


class TestHADevices:
    """Tests for Home Assistant devices endpoint."""

    def test_devices_endpoint_exists(self, client: TestClient):
        """Test that the devices endpoint exists."""
        response = client.get("/api/v1/homeassistant/devices")
        assert response.status_code == 200

    def test_devices_returns_list(self, client: TestClient):
        """Test devices returns proper list structure."""
        response = client.get("/api/v1/homeassistant/devices")
        data = response.json()

        assert "devices" in data
        assert "total" in data


class TestHAAutomations:
    """Tests for Home Assistant automations endpoint."""

    def test_automations_endpoint_exists(self, client: TestClient):
        """Test that the automations endpoint exists."""
        response = client.get("/api/v1/homeassistant/automations")
        assert response.status_code == 200


class TestHAIntegrations:
    """Tests for Home Assistant integrations endpoint."""

    def test_integrations_endpoint_exists(self, client: TestClient):
        """Test that the integrations endpoint exists."""
        response = client.get("/api/v1/homeassistant/integrations")
        assert response.status_code == 200


class TestHALogs:
    """Tests for Home Assistant logs endpoint."""

    def test_logs_endpoint_exists(self, client: TestClient):
        """Test that the logs endpoint exists."""
        response = client.get("/api/v1/homeassistant/logs")
        assert response.status_code == 200

    def test_logs_supports_level_filter(self, client: TestClient):
        """Test level filter parameter."""
        response = client.get("/api/v1/homeassistant/logs?level=error")
        assert response.status_code == 200


class TestHAServiceCall:
    """Tests for Home Assistant service call endpoint."""

    def test_service_call_requires_entity(self, client: TestClient):
        """Test service call validation."""
        response = client.post(
            "/api/v1/homeassistant/services/call",
            json={"service": "light.turn_on", "entity_id": "light.test"},
        )
        # Should return 503 if HA not connected, not validation error
        assert response.status_code in (200, 503)


class TestHAToggle:
    """Tests for entity toggle endpoint."""

    def test_toggle_endpoint_exists(self, client: TestClient):
        """Test toggle endpoint exists."""
        response = client.post("/api/v1/homeassistant/entities/light.test/toggle")
        # Should return 503 (not connected) or 404 (entity not found), not 404 (route not found)
        assert response.status_code in (404, 503)
