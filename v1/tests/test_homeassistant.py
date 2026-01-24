"""Tests for Home Assistant integration service.

Tests cover:
- HomeAssistantClient connection and service calls
- EntityRegistry name matching and search
- Entity state handling
- Device/Area/Automation/Integration models
- Extended registry fetching
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.services.homeassistant.client import (
    HomeAssistantClient,
    ServiceCallResult,
)
from barnabeenet.services.homeassistant.entities import (
    Entity,
    EntityRegistry,
    EntityState,
)
from barnabeenet.services.homeassistant.models import (
    Area,
    Automation,
    AutomationState,
    Device,
    HADataSnapshot,
    Integration,
    LogEntry,
)

# =============================================================================
# EntityState Tests
# =============================================================================


class TestEntityState:
    """Tests for EntityState model."""

    def test_is_on_returns_true_for_on_state(self) -> None:
        """State 'on' should return is_on=True."""
        state = EntityState(state="on")
        assert state.is_on is True
        assert state.is_off is False

    def test_is_off_returns_true_for_off_state(self) -> None:
        """State 'off' should return is_off=True."""
        state = EntityState(state="off")
        assert state.is_off is True
        assert state.is_on is False

    def test_is_unavailable_detects_unavailable_states(self) -> None:
        """Should detect unavailable and unknown states."""
        assert EntityState(state="unavailable").is_unavailable is True
        assert EntityState(state="unknown").is_unavailable is True
        assert EntityState(state="on").is_unavailable is False

    def test_state_is_case_insensitive(self) -> None:
        """State checks should be case-insensitive."""
        assert EntityState(state="ON").is_on is True
        assert EntityState(state="Off").is_off is True
        assert EntityState(state="UNAVAILABLE").is_unavailable is True


# =============================================================================
# Entity Tests
# =============================================================================


class TestEntity:
    """Tests for Entity model."""

    def test_name_returns_friendly_name(self) -> None:
        """name property should return friendly_name."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Light",
        )
        assert entity.name == "Living Room Light"

    def test_name_falls_back_to_entity_id(self) -> None:
        """name should return entity_id if friendly_name is empty."""
        entity = Entity(
            entity_id="light.test",
            domain="light",
            friendly_name="",
        )
        assert entity.name == "light.test"

    def test_matches_name_exact_entity_id(self) -> None:
        """Should match exact entity_id."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Light",
        )
        assert entity.matches_name("light.living_room") is True

    def test_matches_name_exact_friendly_name(self) -> None:
        """Should match exact friendly_name case-insensitive."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Light",
        )
        assert entity.matches_name("Living Room Light") is True
        assert entity.matches_name("living room light") is True

    def test_matches_name_partial_word(self) -> None:
        """Should match whole word in friendly_name."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Ceiling Light",
        )
        assert entity.matches_name("living room") is True
        assert entity.matches_name("ceiling") is True

    def test_matches_name_rejects_non_match(self) -> None:
        """Should reject non-matching queries."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Light",
        )
        assert entity.matches_name("bedroom") is False
        assert entity.matches_name("kitchen") is False

    def test_match_score_exact_match(self) -> None:
        """Exact matches should have highest score."""
        entity = Entity(
            entity_id="light.test",
            domain="light",
            friendly_name="Test Light",
        )
        assert entity.match_score("Test Light") == 1.0
        assert entity.match_score("light.test") == 1.0

    def test_match_score_starts_with(self) -> None:
        """Names starting with query should score high."""
        entity = Entity(
            entity_id="light.test",
            domain="light",
            friendly_name="Living Room Main",
        )
        score = entity.match_score("living")
        assert score == 0.9

    def test_match_score_word_boundary(self) -> None:
        """Whole word matches should score well."""
        entity = Entity(
            entity_id="light.test",
            domain="light",
            friendly_name="Living Room Main Light",
        )
        score = entity.match_score("main")
        assert score == 0.8


# =============================================================================
# EntityRegistry Tests
# =============================================================================


class TestEntityRegistry:
    """Tests for EntityRegistry."""

    @pytest.fixture
    def sample_entities(self) -> list[Entity]:
        """Create sample entities for testing."""
        return [
            Entity(
                entity_id="light.living_room",
                domain="light",
                friendly_name="Living Room Light",
                area_id="living_room",
            ),
            Entity(
                entity_id="light.bedroom",
                domain="light",
                friendly_name="Bedroom Light",
                area_id="bedroom",
            ),
            Entity(
                entity_id="switch.tv",
                domain="switch",
                friendly_name="TV Power",
                area_id="living_room",
            ),
            Entity(
                entity_id="climate.thermostat",
                domain="climate",
                friendly_name="Main Thermostat",
                area_id="hallway",
            ),
        ]

    @pytest.fixture
    def registry(self, sample_entities: list[Entity]) -> EntityRegistry:
        """Create a populated registry."""
        reg = EntityRegistry()
        for entity in sample_entities:
            reg.add(entity)
        return reg

    def test_add_and_get(self, sample_entities: list[Entity]) -> None:
        """Should add and retrieve entities by ID."""
        registry = EntityRegistry()
        registry.add(sample_entities[0])

        result = registry.get("light.living_room")
        assert result is not None
        assert result.friendly_name == "Living Room Light"

    def test_len(self, registry: EntityRegistry) -> None:
        """Should report correct length."""
        assert len(registry) == 4

    def test_get_by_domain(self, registry: EntityRegistry) -> None:
        """Should return entities filtered by domain."""
        lights = registry.get_by_domain("light")
        assert len(lights) == 2
        assert all(e.domain == "light" for e in lights)

    def test_get_by_area(self, registry: EntityRegistry) -> None:
        """Should return entities filtered by area."""
        living_room = registry.get_by_area("living_room")
        assert len(living_room) == 2
        entity_ids = [e.entity_id for e in living_room]
        assert "light.living_room" in entity_ids
        assert "switch.tv" in entity_ids

    def test_find_by_name_exact_id(self, registry: EntityRegistry) -> None:
        """Should find entity by exact ID."""
        result = registry.find_by_name("light.living_room")
        assert result is not None
        assert result.entity_id == "light.living_room"

    def test_find_by_name_fuzzy(self, registry: EntityRegistry) -> None:
        """Should find entity by fuzzy name match."""
        result = registry.find_by_name("living room")
        assert result is not None
        assert result.entity_id == "light.living_room"

    def test_find_by_name_with_domain_filter(self, registry: EntityRegistry) -> None:
        """Should filter search by domain."""
        # Without domain filter, finds light
        result = registry.find_by_name("living room")
        assert result is not None
        assert result.domain == "light"

        # With switch domain, finds TV (also in living room)
        result = registry.find_by_name("living", domain="switch")
        # TV is in living room but named "TV Power"
        # This shouldn't match since "living" isn't in the name
        assert result is None

    def test_find_by_name_returns_none_for_no_match(self, registry: EntityRegistry) -> None:
        """Should return None when no match found."""
        result = registry.find_by_name("nonexistent device")
        assert result is None

    def test_search_returns_sorted_results(self, registry: EntityRegistry) -> None:
        """Search should return results sorted by relevance."""
        results = registry.search("light")
        assert len(results) >= 2
        # All results should contain "light" in name or be light domain
        for entity in results:
            assert "light" in entity.friendly_name.lower() or entity.domain == "light"

    def test_search_with_limit(self, registry: EntityRegistry) -> None:
        """Search should respect limit parameter."""
        results = registry.search("", limit=2)  # Empty query matches all
        # Empty query won't match anything with score > 0
        assert len(results) <= 2

    def test_remove(self, registry: EntityRegistry) -> None:
        """Should remove entity from all indices."""
        assert registry.remove("light.living_room") is True
        assert registry.get("light.living_room") is None
        assert len(registry.get_by_domain("light")) == 1

    def test_remove_nonexistent(self, registry: EntityRegistry) -> None:
        """Remove should return False for nonexistent entity."""
        assert registry.remove("nonexistent") is False

    def test_clear(self, registry: EntityRegistry) -> None:
        """Clear should remove all entities."""
        registry.clear()
        assert len(registry) == 0
        assert registry.get_by_domain("light") == []

    def test_domains_property(self, registry: EntityRegistry) -> None:
        """Should list all domains."""
        domains = registry.domains
        assert "light" in domains
        assert "switch" in domains
        assert "climate" in domains

    def test_areas_property(self, registry: EntityRegistry) -> None:
        """Should list all areas."""
        areas = registry.areas
        assert "living_room" in areas
        assert "bedroom" in areas
        assert "hallway" in areas


# =============================================================================
# HomeAssistantClient Tests
# =============================================================================


class TestHomeAssistantClient:
    """Tests for HomeAssistantClient."""

    @pytest.fixture
    def mock_httpx_client(self) -> MagicMock:
        """Create a mock httpx.AsyncClient."""
        mock = AsyncMock()
        mock.get = AsyncMock()
        mock.post = AsyncMock()
        mock.aclose = AsyncMock()
        return mock

    @pytest.fixture
    def client(self) -> HomeAssistantClient:
        """Create a HomeAssistantClient instance."""
        return HomeAssistantClient(
            url="http://homeassistant.local:8123",
            token="test_token",
        )

    async def test_init_properties(self, client: HomeAssistantClient) -> None:
        """Should initialize with correct properties."""
        assert client.url == "http://homeassistant.local:8123"
        assert client.connected is False

    async def test_ping_success(self, client: HomeAssistantClient) -> None:
        """Ping should return True on successful response."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_class:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_class.return_value = mock_instance

            await client.connect()
            client._client = mock_instance  # Ensure we use our mock

            result = await client.ping()
            assert result is True

    async def test_ping_failure(self, client: HomeAssistantClient) -> None:
        """Ping should return False on failed response."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_class:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_class.return_value = mock_instance

            client._client = mock_instance
            result = await client.ping()
            assert result is False

    async def test_ping_without_client(self, client: HomeAssistantClient) -> None:
        """Ping should return False when not connected."""
        result = await client.ping()
        assert result is False

    async def test_call_service_success(self, client: HomeAssistantClient) -> None:
        """Service call should return success result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"entity_id": "light.test"}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.call_service(
            "light.turn_on",
            entity_id="light.living_room",
            brightness=255,
        )

        assert result.success is True
        assert result.service == "light.turn_on"
        assert result.entity_id == "light.living_room"
        mock_client.post.assert_called_once()

    async def test_call_service_without_client(self, client: HomeAssistantClient) -> None:
        """Service call should fail when not connected."""
        result = await client.call_service("light.turn_on", entity_id="light.test")
        assert result.success is False
        assert "not connected" in result.message.lower()

    async def test_call_service_invalid_format(self, client: HomeAssistantClient) -> None:
        """Service call should fail with invalid service format."""
        client._client = AsyncMock()

        result = await client.call_service("invalid_service", entity_id="light.test")
        assert result.success is False
        assert "invalid service format" in result.message.lower()

    async def test_get_state_success(self, client: HomeAssistantClient) -> None:
        """Should return EntityState for valid entity."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "on",
            "attributes": {"brightness": 255},
            "last_changed": "2026-01-17T10:00:00Z",
            "last_updated": "2026-01-17T10:00:00Z",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.get_state("light.living_room")
        assert result is not None
        assert result.state == "on"
        assert result.attributes["brightness"] == 255

    async def test_get_state_not_found(self, client: HomeAssistantClient) -> None:
        """Should return None for nonexistent entity."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        result = await client.get_state("light.nonexistent")
        assert result is None

    async def test_get_state_without_client(self, client: HomeAssistantClient) -> None:
        """Should return None when not connected."""
        result = await client.get_state("light.test")
        assert result is None

    async def test_resolve_entity_exact_match(self, client: HomeAssistantClient) -> None:
        """Should resolve exact entity_id match."""
        entity = Entity(
            entity_id="light.test",
            domain="light",
            friendly_name="Test Light",
        )
        client._entity_registry.add(entity)

        result = client.resolve_entity("light.test")
        assert result is not None
        assert result.entity_id == "light.test"

    async def test_resolve_entity_fuzzy_match(self, client: HomeAssistantClient) -> None:
        """Should resolve fuzzy name match."""
        entity = Entity(
            entity_id="light.living_room",
            domain="light",
            friendly_name="Living Room Light",
        )
        client._entity_registry.add(entity)

        result = client.resolve_entity("living room")
        assert result is not None
        assert result.entity_id == "light.living_room"

    async def test_get_entities_all(self, client: HomeAssistantClient) -> None:
        """Should return all entities when no domain specified."""
        client._entity_registry.add(Entity(entity_id="light.a", domain="light", friendly_name="A"))
        client._entity_registry.add(
            Entity(entity_id="switch.b", domain="switch", friendly_name="B")
        )

        result = await client.get_entities()
        assert len(result) == 2

    async def test_get_entities_by_domain(self, client: HomeAssistantClient) -> None:
        """Should filter entities by domain."""
        client._entity_registry.add(Entity(entity_id="light.a", domain="light", friendly_name="A"))
        client._entity_registry.add(
            Entity(entity_id="switch.b", domain="switch", friendly_name="B")
        )

        result = await client.get_entities(domain="light")
        assert len(result) == 1
        assert result[0].domain == "light"

    async def test_context_manager(self) -> None:
        """Should work as async context manager."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_class:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.aclose = AsyncMock()
            mock_class.return_value = mock_instance

            async with HomeAssistantClient(url="http://test:8123", token="token") as client:
                assert client._client is not None


# =============================================================================
# ServiceCallResult Tests
# =============================================================================


class TestServiceCallResult:
    """Tests for ServiceCallResult dataclass."""

    def test_success_result(self) -> None:
        """Should create successful result."""
        result = ServiceCallResult(
            success=True,
            service="light.turn_on",
            entity_id="light.test",
            message="OK",
        )
        assert result.success is True
        assert result.service == "light.turn_on"

    def test_failure_result(self) -> None:
        """Should create failure result."""
        result = ServiceCallResult(
            success=False,
            service="light.turn_on",
            entity_id="light.test",
            message="Connection refused",
        )
        assert result.success is False
        assert "Connection refused" in result.message


# =============================================================================
# Device Model Tests
# =============================================================================


class TestDevice:
    """Tests for Device model."""

    def test_display_name_uses_name(self) -> None:
        """Should use name for display."""
        device = Device(
            id="abc123",
            name="Living Room Lamp",
            manufacturer="Philips",
            model="Hue Bulb",
        )
        assert device.display_name == "Living Room Lamp"

    def test_display_name_falls_back_to_model(self) -> None:
        """Should fall back to manufacturer + model."""
        device = Device(
            id="abc123",
            name=None,
            manufacturer="Philips",
            model="Hue Bulb",
        )
        assert device.display_name == "Philips Hue Bulb"

    def test_display_name_falls_back_to_id(self) -> None:
        """Should fall back to ID if no name or model."""
        device = Device(
            id="abc123",
            name=None,
            manufacturer=None,
            model=None,
        )
        assert device.display_name == "abc123"

    def test_is_enabled(self) -> None:
        """Should check if device is enabled."""
        enabled = Device(id="1", name="Test", disabled_by=None)
        disabled = Device(id="2", name="Test", disabled_by="user")

        assert enabled.is_enabled is True
        assert disabled.is_enabled is False


# =============================================================================
# Area Model Tests
# =============================================================================


class TestArea:
    """Tests for Area model."""

    def test_matches_name_exact(self) -> None:
        """Should match exact name."""
        area = Area(id="living_room", name="Living Room")
        assert area.matches_name("Living Room") is True
        assert area.matches_name("living room") is True

    def test_matches_name_id(self) -> None:
        """Should match by ID."""
        area = Area(id="living_room", name="Living Room")
        assert area.matches_name("living_room") is True

    def test_matches_name_alias(self) -> None:
        """Should match by alias."""
        area = Area(id="living_room", name="Living Room", aliases=["Lounge", "Den"])
        assert area.matches_name("Lounge") is True
        assert area.matches_name("den") is True

    def test_matches_name_no_match(self) -> None:
        """Should return False for no match."""
        area = Area(id="living_room", name="Living Room")
        assert area.matches_name("Bedroom") is False


# =============================================================================
# Automation Model Tests
# =============================================================================


class TestAutomation:
    """Tests for Automation model."""

    def test_is_on(self) -> None:
        """Should check if automation is enabled."""
        on_auto = Automation(
            entity_id="automation.test",
            name="Test",
            state=AutomationState.ON,
        )
        off_auto = Automation(
            entity_id="automation.test2",
            name="Test 2",
            state=AutomationState.OFF,
        )

        assert on_auto.is_on is True
        assert off_auto.is_on is False

    def test_automation_id(self) -> None:
        """Should extract automation ID from entity_id."""
        auto = Automation(
            entity_id="automation.turn_on_lights",
            name="Turn On Lights",
            state=AutomationState.ON,
        )
        assert auto.automation_id == "turn_on_lights"


# =============================================================================
# Integration Model Tests
# =============================================================================


class TestIntegration:
    """Tests for Integration model."""

    def test_is_loaded(self) -> None:
        """Should check if integration is loaded."""
        loaded = Integration(
            entry_id="1",
            domain="hue",
            title="Philips Hue",
            state="loaded",
        )
        unloaded = Integration(
            entry_id="2",
            domain="zwave",
            title="Z-Wave",
            state="not_loaded",
        )

        assert loaded.is_loaded is True
        assert unloaded.is_loaded is False

    def test_is_enabled(self) -> None:
        """Should check if integration is enabled."""
        enabled = Integration(
            entry_id="1",
            domain="hue",
            title="Philips Hue",
            state="loaded",
            disabled_by=None,
        )
        disabled = Integration(
            entry_id="2",
            domain="zwave",
            title="Z-Wave",
            state="loaded",
            disabled_by="user",
        )

        assert enabled.is_enabled is True
        assert disabled.is_enabled is False

    def test_has_error(self) -> None:
        """Should detect error states."""
        error = Integration(
            entry_id="1",
            domain="hue",
            title="Philips Hue",
            state="setup_error",
        )
        ok = Integration(
            entry_id="2",
            domain="zwave",
            title="Z-Wave",
            state="loaded",
        )

        assert error.has_error is True
        assert ok.has_error is False


# =============================================================================
# LogEntry Model Tests
# =============================================================================


class TestLogEntry:
    """Tests for LogEntry model."""

    def test_is_error(self) -> None:
        """Should detect error-level logs."""
        error = LogEntry(
            timestamp=datetime.now(),
            level="ERROR",
            source="test",
            message="Something broke",
        )
        warning = LogEntry(
            timestamp=datetime.now(),
            level="WARNING",
            source="test",
            message="Something might break",
        )

        assert error.is_error is True
        assert warning.is_error is False

    def test_is_warning(self) -> None:
        """Should detect warning-level logs."""
        warning = LogEntry(
            timestamp=datetime.now(),
            level="WARNING",
            source="test",
            message="Watch out",
        )
        info = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            source="test",
            message="All good",
        )

        assert warning.is_warning is True
        assert info.is_warning is False


# =============================================================================
# HADataSnapshot Tests
# =============================================================================


class TestHADataSnapshot:
    """Tests for HADataSnapshot model."""

    def test_to_dict(self) -> None:
        """Should convert to dict for API response."""
        now = datetime.now()
        snapshot = HADataSnapshot(
            entities_count=100,
            devices_count=20,
            areas_count=5,
            automations_count=10,
            integrations_count=15,
            last_refresh={"entities": now},
        )
        result = snapshot.to_dict()

        assert result["entities_count"] == 100
        assert result["devices_count"] == 20
        assert "entities" in result["last_refresh"]


# =============================================================================
# Extended HomeAssistantClient Tests
# =============================================================================


class TestHomeAssistantClientExtended:
    """Tests for extended HomeAssistantClient functionality."""

    @pytest.fixture
    def client(self) -> HomeAssistantClient:
        """Create a HomeAssistantClient instance."""
        return HomeAssistantClient(
            url="http://homeassistant.local:8123",
            token="test_token",
        )

    async def test_refresh_devices_success(self, client: HomeAssistantClient) -> None:
        """Should parse and store devices from API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "device1",
                "name": "Living Room Lamp",
                "manufacturer": "Philips",
                "model": "Hue Bulb",
                "area_id": "living_room",
                "config_entries": ["entry1"],
                "disabled_by": None,
            },
            {
                "id": "device2",
                "name": "Kitchen Switch",
                "manufacturer": "Shelly",
                "model": "1PM",
                "area_id": "kitchen",
                "config_entries": ["entry2"],
                "disabled_by": None,
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        count = await client.refresh_devices()

        assert count == 2
        assert len(client.devices) == 2
        assert "device1" in client.devices
        assert client.devices["device1"].name == "Living Room Lamp"

    async def test_refresh_devices_not_found(self, client: HomeAssistantClient) -> None:
        """Should handle 404 gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        count = await client.refresh_devices()
        assert count == 0

    async def test_refresh_areas_success(self, client: HomeAssistantClient) -> None:
        """Should parse and store areas from API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "area_id": "living_room",
                "name": "Living Room",
                "aliases": ["Lounge"],
            },
            {
                "area_id": "kitchen",
                "name": "Kitchen",
                "aliases": [],
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        count = await client.refresh_areas()

        assert count == 2
        assert len(client.areas) == 2
        assert "living_room" in client.areas
        assert client.areas["living_room"].name == "Living Room"

    async def test_refresh_automations_success(self, client: HomeAssistantClient) -> None:
        """Should parse automations from states."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "entity_id": "automation.morning_lights",
                "state": "on",
                "attributes": {
                    "friendly_name": "Morning Lights",
                    "last_triggered": "2026-01-18T07:00:00+00:00",
                    "mode": "single",
                },
            },
            {
                "entity_id": "automation.night_mode",
                "state": "off",
                "attributes": {
                    "friendly_name": "Night Mode",
                    "mode": "single",
                },
            },
            {
                "entity_id": "light.living_room",  # Not an automation
                "state": "on",
                "attributes": {"friendly_name": "Living Room"},
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        count = await client.refresh_automations()

        assert count == 2  # Only automations
        assert len(client.automations) == 2
        assert "automation.morning_lights" in client.automations
        assert client.automations["automation.morning_lights"].is_on is True

    async def test_refresh_integrations_success(self, client: HomeAssistantClient) -> None:
        """Should parse and store integrations."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "entry_id": "entry1",
                "domain": "hue",
                "title": "Philips Hue",
                "state": "loaded",
                "source": "user",
                "disabled_by": None,
            },
            {
                "entry_id": "entry2",
                "domain": "zwave_js",
                "title": "Z-Wave JS",
                "state": "setup_error",
                "source": "user",
                "disabled_by": None,
            },
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        count = await client.refresh_integrations()

        assert count == 2
        assert len(client.integrations) == 2
        assert "entry1" in client.integrations
        assert client.integrations["entry1"].is_loaded is True
        assert client.integrations["entry2"].has_error is True

    async def test_get_error_log_success(self, client: HomeAssistantClient) -> None:
        """Should parse error log entries."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """2026-01-18 10:00:00 ERROR (MainThread) [homeassistant.core] Test error
2026-01-18 10:01:00 WARNING (MainThread) [homeassistant.components.hue] Connection lost
2026-01-18 10:02:00 INFO (MainThread) [homeassistant.core] Starting Home Assistant"""
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        entries = await client.get_error_log()

        assert len(entries) == 3
        assert entries[0].level == "ERROR"
        assert entries[1].level == "WARNING"
        assert entries[2].level == "INFO"

    async def test_refresh_all(self, client: HomeAssistantClient) -> None:
        """Should refresh all registries."""

        # Create mock that returns different data for different endpoints
        def mock_get_side_effect(url: str) -> MagicMock:
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()

            if "device_registry" in url:
                response.json.return_value = [{"id": "d1", "name": "Device"}]
            elif "area_registry" in url:
                response.json.return_value = [{"area_id": "a1", "name": "Area"}]
            elif "config_entries" in url:
                response.json.return_value = [
                    {"entry_id": "e1", "domain": "test", "title": "Test", "state": "loaded"}
                ]
            else:  # /api/states
                response.json.return_value = [
                    {
                        "entity_id": "light.test",
                        "state": "on",
                        "attributes": {"friendly_name": "Test Light"},
                    },
                    {
                        "entity_id": "automation.test",
                        "state": "on",
                        "attributes": {"friendly_name": "Test Auto"},
                    },
                ]
            return response

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get_side_effect)
        client._client = mock_client

        snapshot = await client.refresh_all()

        assert snapshot.entities_count >= 1
        assert snapshot.devices_count == 1
        assert snapshot.areas_count == 1
        assert snapshot.automations_count == 1
        assert snapshot.integrations_count == 1

    def test_find_area_by_name(self, client: HomeAssistantClient) -> None:
        """Should find area by name."""
        client._areas = {
            "living_room": Area(id="living_room", name="Living Room"),
            "kitchen": Area(id="kitchen", name="Kitchen"),
        }

        result = client.find_area_by_name("Living Room")
        assert result is not None
        assert result.id == "living_room"

        result = client.find_area_by_name("Bedroom")
        assert result is None

    def test_get_devices_in_area(self, client: HomeAssistantClient) -> None:
        """Should get devices in specific area."""
        client._devices = {
            "d1": Device(id="d1", name="Lamp", area_id="living_room"),
            "d2": Device(id="d2", name="TV", area_id="living_room"),
            "d3": Device(id="d3", name="Oven", area_id="kitchen"),
        }

        devices = client.get_devices_in_area("living_room")
        assert len(devices) == 2
        assert all(d.area_id == "living_room" for d in devices)
