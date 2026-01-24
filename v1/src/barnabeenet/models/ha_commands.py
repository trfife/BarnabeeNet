"""Home Assistant target and service call models.

These models represent the native HA service call format, preferring
area_id over pre-resolved entity_ids for cleaner, more maintainable code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HATarget:
    """Target for HA service call - prefer area_id over entity_id.

    When targeting devices, the priority order is:
    1. area_id - Let HA filter by domain within the area
    2. device_id - Target a specific device
    3. entity_id - Target a specific entity (fallback)

    Using area_id is preferred because:
    - HA automatically filters by the service's domain
    - No need to pre-resolve entities
    - Works with any future entities added to the area
    """

    area_id: str | list[str] | None = None
    device_id: str | list[str] | None = None
    entity_id: str | list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to HA target format, excluding None values."""
        result: dict[str, Any] = {}
        if self.area_id:
            result["area_id"] = self.area_id
        if self.device_id:
            result["device_id"] = self.device_id
        if self.entity_id:
            result["entity_id"] = self.entity_id
        return result

    def is_empty(self) -> bool:
        """Check if target has no values set."""
        return not self.area_id and not self.device_id and not self.entity_id

    @classmethod
    def from_area(cls, area_id: str | list[str]) -> HATarget:
        """Create a target from area_id(s)."""
        return cls(area_id=area_id)

    @classmethod
    def from_device(cls, device_id: str | list[str]) -> HATarget:
        """Create a target from device_id(s)."""
        return cls(device_id=device_id)

    @classmethod
    def from_entity(cls, entity_id: str | list[str]) -> HATarget:
        """Create a target from entity_id(s)."""
        return cls(entity_id=entity_id)


@dataclass
class HAServiceCall:
    """A Home Assistant service call.

    Represents a complete service call ready to be executed against HA.
    Includes the service (domain.action), target, and any additional data.
    """

    service: str  # e.g., "light.turn_on", "cover.close_cover"
    target: HATarget
    data: dict[str, Any] = field(default_factory=dict)
    # Optional metadata for tracking
    source_text: str = ""  # Original user text that generated this call
    execution_mode: str = "parallel"  # "parallel" or "sequential"

    def to_dict(self) -> dict[str, Any]:
        """Convert to HA REST API format."""
        result: dict[str, Any] = {
            "service": self.service,
        }

        target_dict = self.target.to_dict()
        if target_dict:
            result["target"] = target_dict

        if self.data:
            result["data"] = self.data

        return result

    @property
    def domain(self) -> str:
        """Extract domain from service (e.g., 'light' from 'light.turn_on')."""
        return self.service.split(".")[0] if "." in self.service else ""

    @property
    def action(self) -> str:
        """Extract action from service (e.g., 'turn_on' from 'light.turn_on')."""
        return self.service.split(".")[-1] if "." in self.service else self.service


@dataclass
class CommandSegment:
    """A parsed segment of a compound command.

    Represents one action from a compound command like:
    "turn on the lights in the kitchen and close the blinds"
    """

    action: str  # "turn_on", "turn_off", "set", "dim", "open", "close"
    target_noun: str  # "light", "lights", "fan", "blinds"
    location: str | None = None  # "kitchen", "living room", "downstairs"
    value: str | None = None  # "50%", "72 degrees"
    raw_text: str = ""  # Original segment text for debugging
    confidence: float = 0.9


@dataclass
class ParsedCommand:
    """Result of parsing a command (potentially compound).

    Contains one or more CommandSegments that can be converted to HAServiceCalls.
    """

    segments: list[CommandSegment] = field(default_factory=list)
    execution_mode: str = "parallel"  # "parallel" for "and", "sequential" for "then"
    original_text: str = ""
    is_compound: bool = False
    parse_errors: list[str] = field(default_factory=list)


__all__ = [
    "HATarget",
    "HAServiceCall",
    "CommandSegment",
    "ParsedCommand",
]
