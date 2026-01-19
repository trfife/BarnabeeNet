"""Mock Home Assistant service for E2E testing.

Provides a fake Home Assistant environment that can be used for testing
device control commands without a real HA instance. Simulates:
- Common entity types (lights, switches, covers, climate, media_player)
- Service calls (turn_on, turn_off, toggle, etc.)
- State changes and retrieval
- Area and device relationships
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class EntityState:
    """State for a mock entity with common attributes."""

    state: str
    brightness: int | None = None
    color_temp: int | None = None
    position: int | None = None
    temperature: float | None = None
    current_temperature: float | None = None
    unit_of_measurement: str | None = None

    @property
    def is_on(self) -> bool:
        """Check if entity is in 'on' state."""
        return self.state.lower() == "on"

    @property
    def is_off(self) -> bool:
        """Check if entity is in 'off' state."""
        return self.state.lower() == "off"

    def to_attributes(self) -> dict[str, Any]:
        """Convert to HA-style attributes dict."""
        attrs = {}
        if self.brightness is not None:
            attrs["brightness"] = self.brightness
        if self.color_temp is not None:
            attrs["color_temp"] = self.color_temp
        if self.position is not None:
            attrs["position"] = self.position
        if self.temperature is not None:
            attrs["temperature"] = self.temperature
        if self.current_temperature is not None:
            attrs["current_temperature"] = self.current_temperature
        if self.unit_of_measurement is not None:
            attrs["unit_of_measurement"] = self.unit_of_measurement
        return attrs


@dataclass
class MockEntity:
    """A mock Home Assistant entity."""

    entity_id: str
    domain: str
    friendly_name: str
    area_id: str | None = None
    device_id: str | None = None
    state: EntityState = field(default_factory=lambda: EntityState(state="off"))

    @property
    def name(self) -> str:
        """Get the best display name for the entity."""
        return self.friendly_name or self.entity_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "friendly_name": self.friendly_name,
            "area_id": self.area_id,
            "state": self.state.state,
            "attributes": self.state.to_attributes(),
        }


logger = logging.getLogger(__name__)

# =============================================================================
# Mock Entity Definitions
# =============================================================================

MOCK_AREAS = [
    {"area_id": "living_room", "name": "Living Room"},
    {"area_id": "kitchen", "name": "Kitchen"},
    {"area_id": "bedroom", "name": "Bedroom"},
    {"area_id": "office", "name": "Office"},
    {"area_id": "bathroom", "name": "Bathroom"},
    {"area_id": "garage", "name": "Garage"},
    {"area_id": "backyard", "name": "Backyard"},
]

MOCK_ENTITIES = [
    # Living Room
    MockEntity(
        entity_id="light.living_room_main",
        domain="light",
        friendly_name="Living Room Main Light",
        area_id="living_room",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="light.living_room_lamp",
        domain="light",
        friendly_name="Living Room Lamp",
        area_id="living_room",
        state=EntityState(state="on", brightness=128),
    ),
    MockEntity(
        entity_id="switch.living_room_fan",
        domain="switch",
        friendly_name="Living Room Fan",
        area_id="living_room",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="cover.living_room_blinds",
        domain="cover",
        friendly_name="Living Room Blinds",
        area_id="living_room",
        state=EntityState(state="open", position=100),
    ),
    MockEntity(
        entity_id="media_player.living_room_tv",
        domain="media_player",
        friendly_name="Living Room TV",
        area_id="living_room",
        state=EntityState(state="off"),
    ),
    # Kitchen
    MockEntity(
        entity_id="light.kitchen_main",
        domain="light",
        friendly_name="Kitchen Light",
        area_id="kitchen",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="switch.kitchen_coffee_maker",
        domain="switch",
        friendly_name="Coffee Maker",
        area_id="kitchen",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="sensor.kitchen_temperature",
        domain="sensor",
        friendly_name="Kitchen Temperature",
        area_id="kitchen",
        state=EntityState(state="72", unit_of_measurement="°F"),
    ),
    # Bedroom
    MockEntity(
        entity_id="light.bedroom_main",
        domain="light",
        friendly_name="Bedroom Light",
        area_id="bedroom",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="light.bedroom_lamp",
        domain="light",
        friendly_name="Bedroom Lamp",
        area_id="bedroom",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="cover.bedroom_blinds",
        domain="cover",
        friendly_name="Bedroom Blinds",
        area_id="bedroom",
        state=EntityState(state="closed", position=0),
    ),
    MockEntity(
        entity_id="climate.bedroom_thermostat",
        domain="climate",
        friendly_name="Bedroom Thermostat",
        area_id="bedroom",
        state=EntityState(state="heat", temperature=70, current_temperature=68),
    ),
    # Office
    MockEntity(
        entity_id="light.office_light",
        domain="light",
        friendly_name="Office Light",
        area_id="office",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="switch.office_fan",
        domain="switch",
        friendly_name="Office Fan",
        area_id="office",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="light.office_desk_lamp",
        domain="light",
        friendly_name="Office Desk Lamp",
        area_id="office",
        state=EntityState(state="on", brightness=255),
    ),
    # Garage
    MockEntity(
        entity_id="cover.garage_door",
        domain="cover",
        friendly_name="Garage Door",
        area_id="garage",
        state=EntityState(state="closed", position=0),
    ),
    MockEntity(
        entity_id="light.garage_light",
        domain="light",
        friendly_name="Garage Light",
        area_id="garage",
        state=EntityState(state="off"),
    ),
    # Backyard
    MockEntity(
        entity_id="light.backyard_lights",
        domain="light",
        friendly_name="Backyard Lights",
        area_id="backyard",
        state=EntityState(state="off"),
    ),
    MockEntity(
        entity_id="switch.backyard_sprinklers",
        domain="switch",
        friendly_name="Backyard Sprinklers",
        area_id="backyard",
        state=EntityState(state="off"),
    ),
]


@dataclass
class MockServiceCallResult:
    """Result of a mock service call."""

    success: bool
    service: str
    entity_id: str | None
    message: str


@dataclass
class MockServiceCall:
    """Record of a service call made to the mock HA."""

    timestamp: datetime
    domain: str
    service: str
    entity_id: str | None
    area_id: str | None
    data: dict[str, Any]
    result: MockServiceCallResult


@dataclass
class MockHomeAssistant:
    """Mock Home Assistant instance for testing.

    Maintains state for all mock entities and records service calls
    for verification in tests.
    """

    _entities: dict[str, MockEntity] = field(default_factory=dict)
    _areas: dict[str, dict] = field(default_factory=dict)
    _service_call_history: list[MockServiceCall] = field(default_factory=list)
    _state_change_callbacks: list[Callable] = field(default_factory=list)
    _enabled: bool = False

    def __post_init__(self) -> None:
        """Initialize with default mock data."""
        self.reset()

    def reset(self) -> None:
        """Reset all entities to default state."""
        self._entities = {}
        self._areas = {}
        self._service_call_history = []

        # Load default areas
        for area in MOCK_AREAS:
            self._areas[area["area_id"]] = area

        # Load default entities (deep copy to avoid mutation)
        for entity in MOCK_ENTITIES:
            self._entities[entity.entity_id] = MockEntity(
                entity_id=entity.entity_id,
                domain=entity.domain,
                friendly_name=entity.friendly_name,
                area_id=entity.area_id,
                state=EntityState(
                    state=entity.state.state,
                    brightness=entity.state.brightness,
                    color_temp=entity.state.color_temp,
                    position=entity.state.position,
                    temperature=entity.state.temperature,
                    current_temperature=entity.state.current_temperature,
                    unit_of_measurement=entity.state.unit_of_measurement,
                ),
            )

    def enable(self) -> None:
        """Enable mock HA mode."""
        self._enabled = True
        logger.info("Mock Home Assistant enabled")

    def disable(self) -> None:
        """Disable mock HA mode."""
        self._enabled = False
        logger.info("Mock Home Assistant disabled")

    @property
    def is_enabled(self) -> bool:
        """Check if mock mode is enabled."""
        return self._enabled

    def get_entities(self, domain: str | None = None) -> list[MockEntity]:
        """Get all entities, optionally filtered by domain."""
        entities = list(self._entities.values())
        if domain:
            entities = [e for e in entities if e.domain == domain]
        return entities

    def get_entity(self, entity_id: str) -> MockEntity | None:
        """Get a specific entity by ID."""
        return self._entities.get(entity_id)

    def get_areas(self) -> list[dict]:
        """Get all areas."""
        return list(self._areas.values())

    def get_service_call_history(self) -> list[MockServiceCall]:
        """Get history of all service calls."""
        return self._service_call_history.copy()

    def clear_service_history(self) -> None:
        """Clear service call history."""
        self._service_call_history = []

    async def call_service(
        self,
        service: str,
        entity_id: str | None = None,
        area_id: str | None = None,
        **data: Any,
    ) -> MockServiceCallResult:
        """Simulate a Home Assistant service call.

        Args:
            service: Service to call (e.g., "light.turn_on", "cover.close_cover")
            entity_id: Target entity ID
            area_id: Target area ID (for area-wide commands)
            **data: Additional service data

        Returns:
            MockServiceCallResult with simulated result
        """
        domain, service_name = service.split(".", 1) if "." in service else ("", service)

        # Find target entities
        target_entities: list[MockEntity] = []

        if entity_id:
            entity = self._entities.get(entity_id)
            if entity:
                target_entities.append(entity)
        elif area_id:
            # Target all entities in the area matching the domain
            target_entities = [
                e
                for e in self._entities.values()
                if e.area_id == area_id and (not domain or e.domain == domain)
            ]

        # Execute the service on each entity
        results = []
        for entity in target_entities:
            result = self._apply_service(entity, domain, service_name, data)
            results.append(result)

        # Create overall result
        success = len(results) > 0 and all(r for r in results)
        if len(target_entities) == 0:
            message = f"No entities found for service {service}"
            success = False
        elif len(target_entities) == 1:
            message = f"Called {service} on {target_entities[0].entity_id}"
        else:
            message = f"Called {service} on {len(target_entities)} entities"

        result = MockServiceCallResult(
            success=success,
            service=service,
            entity_id=entity_id,
            message=message,
        )

        # Record the call
        self._service_call_history.append(
            MockServiceCall(
                timestamp=datetime.now(UTC),
                domain=domain,
                service=service_name,
                entity_id=entity_id,
                area_id=area_id,
                data=data,
                result=result,
            )
        )

        logger.info(
            "Mock HA service call",
            extra={
                "service": service,
                "entity_id": entity_id,
                "area_id": area_id,
                "success": success,
            },
        )

        return result

    def _apply_service(
        self, entity: MockEntity, domain: str, service_name: str, data: dict[str, Any]
    ) -> bool:
        """Apply a service call to an entity, updating its state."""
        # Handle common services
        if service_name in ("turn_on", "on"):
            entity.state.state = "on"
            if "brightness" in data:
                entity.state.brightness = data["brightness"]
            return True

        elif service_name in ("turn_off", "off"):
            entity.state.state = "off"
            return True

        elif service_name == "toggle":
            entity.state.state = "off" if entity.state.is_on else "on"
            return True

        # Cover services
        elif service_name == "open_cover":
            entity.state.state = "open"
            entity.state.position = 100
            return True

        elif service_name == "close_cover":
            entity.state.state = "closed"
            entity.state.position = 0
            return True

        elif service_name == "set_cover_position":
            position = data.get("position", 0)
            entity.state.position = position
            entity.state.state = "open" if position > 0 else "closed"
            return True

        # Climate services
        elif service_name == "set_temperature":
            if "temperature" in data:
                entity.state.temperature = data["temperature"]
            return True

        elif service_name == "set_hvac_mode":
            if "hvac_mode" in data:
                entity.state.state = data["hvac_mode"]
            return True

        # Generic - assume success
        return True


# =============================================================================
# Singleton Instance
# =============================================================================

_mock_ha_instance: MockHomeAssistant | None = None


def get_mock_ha() -> MockHomeAssistant:
    """Get the singleton mock HA instance."""
    global _mock_ha_instance
    if _mock_ha_instance is None:
        _mock_ha_instance = MockHomeAssistant()
    return _mock_ha_instance


def reset_mock_ha() -> None:
    """Reset the mock HA to default state."""
    get_mock_ha().reset()


def enable_mock_ha() -> None:
    """Enable mock HA mode for testing."""
    get_mock_ha().enable()


def disable_mock_ha() -> None:
    """Disable mock HA mode."""
    get_mock_ha().disable()


def is_mock_ha_enabled() -> bool:
    """Check if mock HA mode is enabled."""
    return get_mock_ha().is_enabled
