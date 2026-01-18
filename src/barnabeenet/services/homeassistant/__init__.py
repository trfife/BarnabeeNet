"""Home Assistant integration service.

Provides:
- HomeAssistantClient for API communication
- Entity registry for device discovery and resolution
- Service call execution with feedback
"""

from barnabeenet.services.homeassistant.client import HomeAssistantClient
from barnabeenet.services.homeassistant.entities import (
    Entity,
    EntityRegistry,
    EntityState,
)

__all__ = [
    "Entity",
    "EntityRegistry",
    "EntityState",
    "HomeAssistantClient",
]
