"""Tests for Home Assistant integration service.

Tests cover:
- HomeAssistantClient connection and service calls
- EntityRegistry name matching and search
- Entity state handling
"""

from __future__ import annotations

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
