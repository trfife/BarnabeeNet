"""Home Assistant data models.

Extended models for comprehensive HA integration:
- Devices (device registry)
- Areas (rooms/zones)
- Automations (automation states and configs)
- Integrations (config entries)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AutomationState(str, Enum):
    """Automation state enum."""

    ON = "on"
    OFF = "off"
    UNAVAILABLE = "unavailable"


@dataclass
class Device:
    """Home Assistant device from device registry.

    Represents a physical or virtual device that may contain multiple entities.
    Devices change infrequently - good candidate for long cache duration.
    """

    id: str
    name: str | None
    manufacturer: str | None = None
    model: str | None = None
    sw_version: str | None = None
    hw_version: str | None = None
    area_id: str | None = None
    config_entry_ids: list[str] = field(default_factory=list)
    identifiers: list[tuple[str, str]] = field(default_factory=list)
    connections: list[tuple[str, str]] = field(default_factory=list)
    via_device_id: str | None = None
    disabled_by: str | None = None

    @property
    def display_name(self) -> str:
        """Get best display name for device."""
        if self.name:
            return self.name
        if self.model:
            return f"{self.manufacturer or 'Unknown'} {self.model}"
        return self.id

    @property
    def is_enabled(self) -> bool:
        """Check if device is enabled."""
        return self.disabled_by is None


@dataclass
class Area:
    """Home Assistant area (room/zone).

    Areas are used to organize devices and entities by location.
    Changes very infrequently - long cache duration.
    """

    id: str
    name: str
    picture: str | None = None
    aliases: list[str] = field(default_factory=list)
    floor_id: str | None = None
    icon: str | None = None
    labels: list[str] = field(default_factory=list)

    def matches_name(self, query: str) -> bool:
        """Check if area matches a name query (case-insensitive)."""
        query_lower = query.lower()
        if query_lower == self.name.lower():
            return True
        if query_lower == self.id.lower():
            return True
        return any(alias.lower() == query_lower for alias in self.aliases)


@dataclass
class Automation:
    """Home Assistant automation.

    Represents an automation with its current state and configuration.
    """

    entity_id: str
    name: str
    state: AutomationState
    last_triggered: datetime | None = None
    mode: str = "single"  # single, restart, queued, parallel
    current_activity: int = 0
    max_activity: int | None = None
    description: str | None = None
    icon: str | None = None

    @property
    def is_on(self) -> bool:
        """Check if automation is enabled."""
        return self.state == AutomationState.ON

    @property
    def automation_id(self) -> str:
        """Get automation ID from entity_id."""
        return self.entity_id.replace("automation.", "")


@dataclass
class Integration:
    """Home Assistant integration (config entry).

    Represents an installed integration with its configuration.
    """

    entry_id: str
    domain: str
    title: str
    state: str  # loaded, setup_error, setup_retry, not_loaded, failed_unload
    version: int = 1
    source: str = "user"  # user, import, discovery, etc.
    disabled_by: str | None = None
    supports_options: bool = False
    supports_remove_device: bool = False
    supports_unload: bool = False
    supports_reconfigure: bool = False
    pref_disable_new_entities: bool = False
    pref_disable_polling: bool = False

    @property
    def is_loaded(self) -> bool:
        """Check if integration is successfully loaded."""
        return self.state == "loaded"

    @property
    def is_enabled(self) -> bool:
        """Check if integration is enabled."""
        return self.disabled_by is None

    @property
    def has_error(self) -> bool:
        """Check if integration has an error."""
        return self.state in ("setup_error", "failed_unload")


@dataclass
class LogEntry:
    """Home Assistant log entry.

    Represents a single log line from error_log.
    """

    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    source: str  # Logger name (e.g., "homeassistant.components.zwave_js")
    message: str
    count: int = 1  # For aggregated entries

    @property
    def is_error(self) -> bool:
        """Check if this is an error-level log."""
        return self.level.upper() in ("ERROR", "CRITICAL")

    @property
    def is_warning(self) -> bool:
        """Check if this is a warning."""
        return self.level.upper() == "WARNING"


@dataclass
class HADataSnapshot:
    """Complete snapshot of Home Assistant data.

    Used for caching with different refresh rates per data type.
    """

    entities_count: int = 0
    devices_count: int = 0
    areas_count: int = 0
    automations_count: int = 0
    integrations_count: int = 0
    last_refresh: dict[str, datetime] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API response."""
        return {
            "entities_count": self.entities_count,
            "devices_count": self.devices_count,
            "areas_count": self.areas_count,
            "automations_count": self.automations_count,
            "integrations_count": self.integrations_count,
            "last_refresh": {k: v.isoformat() for k, v in self.last_refresh.items()},
        }
