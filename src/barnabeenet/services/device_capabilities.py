"""Device Capabilities Database for BarnabeeNet.

Stores and manages device capabilities, features, and metadata for all Home Assistant
entities. This enables:
- Knowing what actions each device supports (dimmable, color, temperature, etc.)
- Preventing invalid commands (e.g., "dim" on an on/off-only switch)
- Tracking previous states for undo functionality
- Auto-discovery of new devices

The database is populated from Home Assistant entity attributes and can be
enhanced by the self-improvement agent with online research.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)

# Path to the capabilities database file
DATA_DIR = Path(__file__).parent.parent / "data"
CAPABILITIES_DB_PATH = DATA_DIR / "device_capabilities.json"


class DeviceFeature(str, Enum):
    """Features a device can support."""

    # Basic
    ON_OFF = "on_off"
    TOGGLE = "toggle"

    # Light features
    BRIGHTNESS = "brightness"
    COLOR_TEMP = "color_temp"
    RGB_COLOR = "rgb_color"
    HS_COLOR = "hs_color"
    XY_COLOR = "xy_color"
    RGBW_COLOR = "rgbw_color"
    RGBWW_COLOR = "rgbww_color"
    EFFECT = "effect"
    FLASH = "flash"
    TRANSITION = "transition"

    # Climate features
    TARGET_TEMPERATURE = "target_temperature"
    TARGET_HUMIDITY = "target_humidity"
    FAN_MODE = "fan_mode"
    HVAC_MODE = "hvac_mode"
    PRESET_MODE = "preset_mode"
    SWING_MODE = "swing_mode"
    AUX_HEAT = "aux_heat"

    # Cover features
    OPEN_CLOSE = "open_close"
    SET_POSITION = "set_position"
    TILT = "tilt"
    STOP = "stop"

    # Media player features
    PLAY_PAUSE = "play_pause"
    VOLUME = "volume"
    MUTE = "mute"
    SOURCE = "source"
    MEDIA_POSITION = "media_position"
    SHUFFLE = "shuffle"
    REPEAT = "repeat"

    # Lock features
    LOCK_UNLOCK = "lock_unlock"
    OPEN = "open"  # Some locks can open (like smart locks with motor)

    # Fan features
    SPEED = "speed"
    DIRECTION = "direction"
    OSCILLATE = "oscillate"

    # Timer features
    START_CANCEL = "start_cancel"
    PAUSE_RESUME = "pause_resume"


@dataclass
class DeviceCapability:
    """Capability information for a single device."""

    entity_id: str
    domain: str
    friendly_name: str
    features: list[str] = field(default_factory=list)

    # Domain-specific capabilities
    supported_color_modes: list[str] = field(default_factory=list)  # For lights
    min_color_temp_kelvin: int | None = None
    max_color_temp_kelvin: int | None = None
    effect_list: list[str] = field(default_factory=list)

    hvac_modes: list[str] = field(default_factory=list)  # For climate
    fan_modes: list[str] = field(default_factory=list)
    preset_modes: list[str] = field(default_factory=list)
    min_temp: float | None = None
    max_temp: float | None = None

    # Source list for media players
    source_list: list[str] = field(default_factory=list)

    # Metadata
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    area_name: str | None = None

    # Research notes from self-improvement agent
    research_notes: str | None = None
    last_updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceCapability:
        """Create from dictionary."""
        return cls(**data)

    def supports(self, feature: str | DeviceFeature) -> bool:
        """Check if device supports a feature."""
        feature_str = feature.value if isinstance(feature, DeviceFeature) else feature
        return feature_str in self.features

    def get_capability_summary(self) -> str:
        """Get a human-readable summary of capabilities."""
        parts = [f"{self.friendly_name} ({self.entity_id})"]

        if self.features:
            parts.append(f"Features: {', '.join(self.features)}")

        if self.supported_color_modes:
            parts.append(f"Color modes: {', '.join(self.supported_color_modes)}")

        if self.hvac_modes:
            parts.append(f"HVAC modes: {', '.join(self.hvac_modes)}")

        if self.manufacturer or self.model:
            parts.append(f"Device: {self.manufacturer or 'Unknown'} {self.model or ''}")

        return "\n".join(parts)


class DeviceCapabilitiesDB:
    """Database of device capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, DeviceCapability] = {}
        self._previous_states: dict[str, dict[str, Any]] = {}  # entity_id -> state snapshot
        self._load_from_file()

    def _load_from_file(self) -> None:
        """Load capabilities from JSON file."""
        if CAPABILITIES_DB_PATH.exists():
            try:
                with open(CAPABILITIES_DB_PATH, "r") as f:
                    data = json.load(f)
                    for entity_id, cap_data in data.get("capabilities", {}).items():
                        self._capabilities[entity_id] = DeviceCapability.from_dict(cap_data)
                logger.info(f"Loaded {len(self._capabilities)} device capabilities from file")
            except Exception as e:
                logger.warning(f"Failed to load capabilities file: {e}")

    def _save_to_file(self) -> None:
        """Save capabilities to JSON file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "capabilities": {
                    entity_id: cap.to_dict()
                    for entity_id, cap in self._capabilities.items()
                },
                "last_updated": datetime.now().isoformat(),
            }
            with open(CAPABILITIES_DB_PATH, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._capabilities)} device capabilities to file")
        except Exception as e:
            logger.warning(f"Failed to save capabilities file: {e}")

    def get(self, entity_id: str) -> DeviceCapability | None:
        """Get capabilities for an entity."""
        return self._capabilities.get(entity_id)

    def set(self, entity_id: str, capability: DeviceCapability) -> None:
        """Set capabilities for an entity."""
        self._capabilities[entity_id] = capability
        self._save_to_file()

    def get_all(self) -> dict[str, DeviceCapability]:
        """Get all capabilities."""
        return self._capabilities.copy()

    def supports_feature(self, entity_id: str, feature: str | DeviceFeature) -> bool:
        """Check if an entity supports a feature."""
        cap = self.get(entity_id)
        if not cap:
            return True  # Assume supported if we don't know
        return cap.supports(feature)

    def save_previous_state(self, entity_id: str, state: dict[str, Any]) -> None:
        """Save the current state of an entity before changing it (for undo)."""
        self._previous_states[entity_id] = {
            "state": state.get("state"),
            "attributes": state.get("attributes", {}),
            "timestamp": datetime.now().isoformat(),
        }
        logger.debug(f"Saved previous state for {entity_id}: {self._previous_states[entity_id]}")

    def get_previous_state(self, entity_id: str) -> dict[str, Any] | None:
        """Get the previous state of an entity (for undo)."""
        return self._previous_states.get(entity_id)

    def clear_previous_state(self, entity_id: str) -> None:
        """Clear the saved previous state after undo."""
        self._previous_states.pop(entity_id, None)

    async def sync_from_ha(self, ha_client: "HomeAssistantClient") -> int:
        """Sync capabilities from Home Assistant entities.

        Returns number of entities updated.
        """
        updated = 0

        # Domains to sync
        domains = ["light", "switch", "climate", "cover", "lock", "media_player", "fan", "timer"]

        for domain in domains:
            try:
                entities = await ha_client.get_entities(domain=domain)
                for entity in entities:
                    entity_id = entity.get("entity_id", "")
                    if not entity_id:
                        continue

                    cap = self._extract_capabilities(entity)
                    if cap:
                        self._capabilities[entity_id] = cap
                        updated += 1
            except Exception as e:
                logger.warning(f"Failed to sync {domain} entities: {e}")

        if updated > 0:
            self._save_to_file()
            logger.info(f"Synced {updated} device capabilities from Home Assistant")

        return updated

    def _extract_capabilities(self, entity: dict[str, Any]) -> DeviceCapability | None:
        """Extract capabilities from a Home Assistant entity."""
        entity_id = entity.get("entity_id", "")
        domain = entity.get("domain", entity_id.split(".")[0] if "." in entity_id else "")
        attributes = entity.get("attributes", {})

        cap = DeviceCapability(
            entity_id=entity_id,
            domain=domain,
            friendly_name=entity.get("friendly_name") or attributes.get("friendly_name", entity_id),
            area_id=entity.get("area_id"),
            area_name=entity.get("area_name"),
            last_updated=datetime.now().isoformat(),
        )

        # Extract features based on domain
        if domain == "light":
            cap.features = self._extract_light_features(attributes)
            cap.supported_color_modes = attributes.get("supported_color_modes", [])
            cap.min_color_temp_kelvin = attributes.get("min_color_temp_kelvin")
            cap.max_color_temp_kelvin = attributes.get("max_color_temp_kelvin")
            cap.effect_list = attributes.get("effect_list", [])

        elif domain == "switch":
            cap.features = [DeviceFeature.ON_OFF.value, DeviceFeature.TOGGLE.value]

        elif domain == "climate":
            cap.features = self._extract_climate_features(attributes)
            cap.hvac_modes = attributes.get("hvac_modes", [])
            cap.fan_modes = attributes.get("fan_modes", [])
            cap.preset_modes = attributes.get("preset_modes", [])
            cap.min_temp = attributes.get("min_temp")
            cap.max_temp = attributes.get("max_temp")

        elif domain == "cover":
            cap.features = self._extract_cover_features(attributes)

        elif domain == "lock":
            cap.features = [DeviceFeature.LOCK_UNLOCK.value]

        elif domain == "media_player":
            cap.features = self._extract_media_player_features(attributes)
            cap.source_list = attributes.get("source_list", [])

        elif domain == "fan":
            cap.features = self._extract_fan_features(attributes)

        elif domain == "timer":
            cap.features = [DeviceFeature.START_CANCEL.value, DeviceFeature.PAUSE_RESUME.value]

        return cap

    def _extract_light_features(self, attributes: dict[str, Any]) -> list[str]:
        """Extract light features from attributes."""
        features = [DeviceFeature.ON_OFF.value, DeviceFeature.TOGGLE.value]

        color_modes = attributes.get("supported_color_modes", [])

        if "brightness" in color_modes or attributes.get("brightness") is not None:
            features.append(DeviceFeature.BRIGHTNESS.value)

        if "color_temp" in color_modes:
            features.append(DeviceFeature.COLOR_TEMP.value)

        if "hs" in color_modes or "rgb" in color_modes:
            features.append(DeviceFeature.RGB_COLOR.value)
            features.append(DeviceFeature.HS_COLOR.value)

        if "rgbw" in color_modes:
            features.append(DeviceFeature.RGBW_COLOR.value)

        if "rgbww" in color_modes:
            features.append(DeviceFeature.RGBWW_COLOR.value)

        if "xy" in color_modes:
            features.append(DeviceFeature.XY_COLOR.value)

        if attributes.get("effect_list"):
            features.append(DeviceFeature.EFFECT.value)

        # Check supported_features bitmask
        supported = attributes.get("supported_features", 0)
        if supported & 4:  # SUPPORT_EFFECT
            if DeviceFeature.EFFECT.value not in features:
                features.append(DeviceFeature.EFFECT.value)
        if supported & 8:  # SUPPORT_FLASH
            features.append(DeviceFeature.FLASH.value)
        if supported & 32:  # SUPPORT_TRANSITION
            features.append(DeviceFeature.TRANSITION.value)

        return features

    def _extract_climate_features(self, attributes: dict[str, Any]) -> list[str]:
        """Extract climate features from attributes."""
        features = []

        if attributes.get("hvac_modes"):
            features.append(DeviceFeature.HVAC_MODE.value)

        if attributes.get("min_temp") is not None:
            features.append(DeviceFeature.TARGET_TEMPERATURE.value)

        if attributes.get("fan_modes"):
            features.append(DeviceFeature.FAN_MODE.value)

        if attributes.get("preset_modes"):
            features.append(DeviceFeature.PRESET_MODE.value)

        if attributes.get("swing_modes"):
            features.append(DeviceFeature.SWING_MODE.value)

        return features

    def _extract_cover_features(self, attributes: dict[str, Any]) -> list[str]:
        """Extract cover features from attributes."""
        features = [DeviceFeature.OPEN_CLOSE.value]

        supported = attributes.get("supported_features", 0)
        if supported & 4:  # SUPPORT_SET_POSITION
            features.append(DeviceFeature.SET_POSITION.value)
        if supported & 8:  # SUPPORT_STOP
            features.append(DeviceFeature.STOP.value)
        if supported & 128:  # SUPPORT_SET_TILT_POSITION
            features.append(DeviceFeature.TILT.value)

        return features

    def _extract_media_player_features(self, attributes: dict[str, Any]) -> list[str]:
        """Extract media player features from attributes."""
        features = [DeviceFeature.ON_OFF.value]

        supported = attributes.get("supported_features", 0)
        if supported & 1:  # SUPPORT_PAUSE
            features.append(DeviceFeature.PLAY_PAUSE.value)
        if supported & 4:  # SUPPORT_VOLUME_SET
            features.append(DeviceFeature.VOLUME.value)
        if supported & 8:  # SUPPORT_VOLUME_MUTE
            features.append(DeviceFeature.MUTE.value)
        if supported & 256:  # SUPPORT_SELECT_SOURCE
            features.append(DeviceFeature.SOURCE.value)
        if supported & 2048:  # SUPPORT_SHUFFLE_SET
            features.append(DeviceFeature.SHUFFLE.value)
        if supported & 4096:  # SUPPORT_REPEAT_SET
            features.append(DeviceFeature.REPEAT.value)

        return features

    def _extract_fan_features(self, attributes: dict[str, Any]) -> list[str]:
        """Extract fan features from attributes."""
        features = [DeviceFeature.ON_OFF.value, DeviceFeature.TOGGLE.value]

        supported = attributes.get("supported_features", 0)
        if supported & 1:  # SUPPORT_SET_SPEED
            features.append(DeviceFeature.SPEED.value)
        if supported & 2:  # SUPPORT_OSCILLATE
            features.append(DeviceFeature.OSCILLATE.value)
        if supported & 4:  # SUPPORT_DIRECTION
            features.append(DeviceFeature.DIRECTION.value)

        return features

    def add_research_notes(self, entity_id: str, notes: str) -> bool:
        """Add research notes from self-improvement agent."""
        cap = self.get(entity_id)
        if cap:
            cap.research_notes = notes
            cap.last_updated = datetime.now().isoformat()
            self._save_to_file()
            return True
        return False


# Global instance
_capabilities_db: DeviceCapabilitiesDB | None = None


def get_capabilities_db() -> DeviceCapabilitiesDB:
    """Get the global capabilities database instance."""
    global _capabilities_db
    if _capabilities_db is None:
        _capabilities_db = DeviceCapabilitiesDB()
    return _capabilities_db


async def sync_capabilities(ha_client: "HomeAssistantClient") -> int:
    """Sync device capabilities from Home Assistant."""
    db = get_capabilities_db()
    return await db.sync_from_ha(ha_client)
