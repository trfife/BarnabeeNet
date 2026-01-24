"""Home Assistant integration service.

Provides:
- HomeAssistantClient for API communication
- Entity registry for device discovery and resolution
- Device/Area/Automation/Integration registries
- Service call execution with feedback
"""

from barnabeenet.services.homeassistant.client import HomeAssistantClient
from barnabeenet.services.homeassistant.context import (
    HAContext,
    HAContextService,
    EntityMetadata,
    get_ha_context_service,
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

__all__ = [
    "Area",
    "Automation",
    "AutomationState",
    "Device",
    "Entity",
    "EntityMetadata",
    "EntityRegistry",
    "EntityState",
    "HAContext",
    "HAContextService",
    "HADataSnapshot",
    "HomeAssistantClient",
    "Integration",
    "LogEntry",
    "get_ha_context_service",
]
