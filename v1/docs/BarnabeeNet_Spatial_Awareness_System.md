# BarnabeeNet Spatial Awareness System

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Technical specification for room-based event propagation and notification routing

---

## Table of Contents

1. [Overview](#overview)
2. [Room Graph Definition](#room-graph-definition)
3. [Event Propagation Rules](#event-propagation-rules)
4. [Spatial Awareness Class](#spatial-awareness-class)
5. [Integration with Proactive Agent](#integration-with-proactive-agent)
6. [Configuration Schema](#configuration-schema)
7. [Implementation Recommendations](#implementation-recommendations)

---

## Overview

### Background: SkyrimNet Inspiration

SkyrimNet achieves realistic NPC behavior through distance thresholds (typically 1000 game units for dragon events) and line-of-sight calculations. BarnabeeNet needs an equivalent system adapted for home topology: a **Room Graph** that models physical space as nodes (rooms) and edges (adjacencies/connections), enabling intelligent event propagation, notification routing, and speaker selection.

### System Benefits

This system directly enhances:
- **Proactive Agent**: Knows which rooms should receive alerts
- **Action Agent**: Selects appropriate speakers for TTS output
- **Privacy Architecture**: Enforces spatial boundaries for sensitive events
- **Memory System**: Adds location context to memories

---

## Room Graph Definition

### Data Structure Design

The room graph is an **undirected weighted graph** where:
- **Nodes** = Rooms (identified by Home Assistant area IDs)
- **Edges** = Physical connections (doors, archways, open passages)
- **Edge Weights** = Acoustic attenuation factors (affects sound propagation)

**Design Rationale:**

| Design Choice | Rationale |
|---------------|-----------|
| **Undirected Graph** | Sound and events propagate bidirectionally |
| **Weighted Edges** | Different barriers have different acoustic properties (open archway vs closed door) |
| **Node Metadata** | Store privacy level, output devices, room type for routing decisions |
| **Edge Metadata** | Store barrier type, current state (door open/closed), acoustic factor |

### Core Data Structures

```python
# core/spatial.py
"""Spatial Awareness System - Room Graph Data Structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class RoomType(Enum):
    """Types of rooms in the home."""
    COMMON = "common"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    OFFICE = "office"
    UTILITY = "utility"


class PrivacyLevel(Enum):
    """Privacy levels for rooms."""
    PUBLIC = "public"
    SEMI_PRIVATE = "semi_private"
    PRIVATE = "private"


class BarrierType(Enum):
    """Types of barriers between rooms."""
    OPEN = "open"              # No barrier, open passage
    ARCHWAY = "archway"        # Architectural opening, no door
    DOOR = "door"              # Standard interior door
    POCKET_DOOR = "pocket_door"
    DOUBLE_DOOR = "double_door"
    SOLID_WALL = "solid_wall"  # No connection (for reference only)


class PropagationType(Enum):
    """Event propagation types."""
    WHISPER = "whisper"
    NORMAL_SPEECH = "normal_speech"
    RAISED_VOICE = "raised_voice"
    LOUD_EVENT = "loud_event"
    VISUAL_ONLY = "visual_only"
    BROADCAST = "broadcast"


@dataclass
class RoomNode:
    """Represents a room in the home."""
    room_id: str
    name: str
    room_type: RoomType
    privacy_level: PrivacyLevel
    ha_area_id: str
    output_devices: list[str] = field(default_factory=list)
    input_devices: list[str] = field(default_factory=list)
    occupancy_sensor: str | None = None


@dataclass
class RoomConnection:
    """Represents a connection between two rooms."""
    from_room: str
    to_room: str
    barrier_type: BarrierType
    base_acoustic_factor: float  # 0.0 = soundproof, 1.0 = fully open
    barrier_state_entity: str | None = None  # HA entity for door state
    open_bonus: float = 0.5  # Added to base when door is open


@dataclass
class PathResult:
    """Result of a path calculation between rooms."""
    path: list[str]
    hop_count: int
    cumulative_acoustic_factor: float
    barriers: list[tuple[str, str, BarrierType]]  # (from, to, barrier)


@dataclass
class RoomPerceptionResult:
    """Result indicating if/how a room perceives an event."""
    room_id: str
    hop_count: int
    cumulative_acoustic_factor: float
    path: list[str]
    output_devices: list[str]
    is_privacy_blocked: bool = False


@dataclass
class PropagationConfig:
    """Configuration for an event propagation type."""
    propagation_type: PropagationType
    description: str
    max_hops: int
    acoustic_threshold: float | None  # None for same-room only
    respect_privacy: bool
    output_modalities: list[str]
```

### Typical Home Layout Example

```
Layout Topology (Fife Household):

                                    ┌─────────────┐
                                    │   GARAGE    │
                                    │  (utility)  │
                                    └──────┬──────┘
                                           │ door
                                    ┌──────▼──────┐
                     ┌─────────────┤   KITCHEN   ├─────────────┐
                     │   archway   │  (common)   │   archway   │
              ┌──────▼──────┐      └──────┬──────┘      ┌──────▼──────┐
              │LIVING ROOM  │             │             │   OFFICE    │
              │  (common)   │             │ open        │  (common)   │
              └──────┬──────┘      ┌──────▼──────┐      └─────────────┘
                     │ hallway     │   HALLWAY   │
                     └─────────────┤  (common)   ├─────────────┐
                                   └──────┬──────┘             │
                     ┌─────────────────┬──┴──┬─────────────────┤
                     │ door            │door │ door            │ door
              ┌──────▼──────┐   ┌──────▼────┐┌▼─────────┐┌─────▼──────┐
              │ MASTER BED  │   │KIDS BATH  ││ PENELOPE ││  XANDER    │
              │  (private)  │   │ (private) ││(private) ││ (private)  │
              └──────┬──────┘   └───────────┘└──────────┘└────────────┘
                     │ door                   ┌──────────┐┌────────────┐
              ┌──────▼──────┐                 │ ZACHARY  ││   VIOLA    │
              │MASTER BATH  │                 │(private) ││ (private)  │
              │  (private)  │                 └──────────┘└────────────┘
              └─────────────┘
```

**Graph Representation:**

| Room | Adjacent To | Barrier | Base Acoustic Factor |
|------|-------------|---------|---------------------|
| living_room | kitchen | archway (open) | 0.9 |
| living_room | hallway | open passage | 0.85 |
| kitchen | garage | interior door | 0.3 |
| kitchen | office | archway (open) | 0.9 |
| kitchen | hallway | open passage | 0.85 |
| hallway | master_bedroom | door | 0.3 |
| hallway | kids_bathroom | door | 0.3 |
| hallway | bedroom.penelope | door | 0.3 |
| hallway | bedroom.xander | door | 0.3 |
| hallway | bedroom.zachary | door | 0.3 |
| hallway | bedroom.viola | door | 0.3 |
| master_bedroom | master_bathroom | door | 0.3 |

### Door/Barrier State Awareness

Acoustic propagation changes based on door state. A closed door reduces transmission; an open door increases it.

**Dynamic Acoustic Factor Calculation:**

```python
def calculate_effective_acoustic_factor(connection: RoomConnection, door_is_open: bool) -> float:
    """
    Calculate effective acoustic factor based on door state.
    
    Formula: effective = base + (is_open × open_bonus)
    
    Examples:
        Closed door: 0.3 + (0 × 0.5) = 0.3
        Open door:   0.3 + (1 × 0.5) = 0.8
    """
    if connection.barrier_state_entity is None:
        # No state tracking (archway, open passage)
        return connection.base_acoustic_factor
    
    state_modifier = 1.0 if door_is_open else 0.0
    return connection.base_acoustic_factor + (state_modifier * connection.open_bonus)
```

---

## Event Propagation Rules

### Propagation Types Definition

Drawing from SkyrimNet's distance-based thresholds, BarnabeeNet translates this to hop-based propagation in a discrete room graph:

| Propagation Type | Max Hops | Acoustic Threshold | Use Cases |
|------------------|----------|-------------------|-----------|
| `whisper` | 0 | N/A (same room only) | Private mode, personal notifications, watch-only |
| `normal_speech` | 1 | >0.3 cumulative | Standard voice responses, conversation |
| `raised_voice` | 2 | >0.2 cumulative | Important announcements, calling someone |
| `loud_event` | 3 | >0.1 cumulative | Smoke alarm, doorbell, glass break, security |
| `visual_only` | 0 | N/A | Watch haptic, AR overlay, no audio component |
| `broadcast` | ∞ | None | Emergency alerts (fire, CO, intruder) |

### Acoustic Threshold Mechanics

**Cumulative Acoustic Factor:** As sound travels through multiple rooms, the acoustic factor compounds multiplicatively.

```
Path: kitchen → hallway → bedroom
Factors: 0.85 (open) × 0.3 (closed door) = 0.255 cumulative

If event requires >0.3 threshold, bedroom does NOT perceive it.
If event requires >0.2 threshold, bedroom DOES perceive it.
```

**Real-World Reasoning:**
- Normal conversation (~60dB) drops ~20dB through a closed door
- A smoke alarm (~85dB) remains audible (~65dB) through a closed door
- Whispered conversation (~30dB) is inaudible beyond the same room

### Event Type Registry

| Event Type | Propagation | Priority | Source Examples |
|------------|-------------|----------|-----------------|
| `voice_response` | normal_speech | medium | TTS responses |
| `proactive_notification` | normal_speech | low | Calendar reminders, package arrival |
| `safety_alert` | loud_event | high | Door open too long, unusual motion |
| `security_alert` | broadcast | critical | Smoke, CO, water leak, intruder |
| `doorbell` | loud_event | medium | Someone at door |
| `glass_break` | loud_event | critical | Security sensor |
| `private_notification` | whisper | low | Personal calendar, private messages |
| `timer_alarm` | raised_voice | medium | Kitchen timer, reminder alarm |
| `music_announcement` | normal_speech | low | "Now playing..." |

### Privacy Zone Interaction

**Critical Constraint:** Propagation rules must respect privacy zones.

```
Privacy Zone Rules:
- children_rooms: No audio propagation INTO these rooms (proactive_notifications: false)
- bathrooms: No audio IN or OUT (audio_capture: false, privacy: maximum)
- common_areas: Full bidirectional propagation allowed
```

**Propagation Matrix:**

| From \ To | common | office | kids_room | bathroom |
|-----------|--------|--------|-----------|----------|
| **common** | ✅ | ✅ | ⚠️ safety only | ❌ |
| **office** | ✅ | ✅ | ⚠️ safety only | ❌ |
| **kids_room** | ✅ out | ✅ out | ❌ between | ❌ |
| **bathroom** | ❌ | ❌ | ❌ | ❌ |

**Exception:** `broadcast` events (fire, CO, intruder) override privacy zones because safety supersedes privacy.

---

## Spatial Awareness Class

### Complete Implementation

```python
# core/spatial.py
"""Spatial Awareness System for BarnabeeNet."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SpatialAwareness:
    """
    Room graph-based spatial awareness for event propagation.
    
    Provides methods for:
    - Determining which rooms perceive events
    - Calculating shortest paths between rooms
    - Selecting appropriate speakers for output
    - Respecting privacy zones and context rules
    """

    # Default propagation configurations
    PROPAGATION_CONFIGS: dict[PropagationType, PropagationConfig] = {
        PropagationType.WHISPER: PropagationConfig(
            propagation_type=PropagationType.WHISPER,
            description="Same room only, private mode",
            max_hops=0,
            acoustic_threshold=None,
            respect_privacy=True,
            output_modalities=["audio", "ar"],
        ),
        PropagationType.NORMAL_SPEECH: PropagationConfig(
            propagation_type=PropagationType.NORMAL_SPEECH,
            description="Standard voice responses and conversation",
            max_hops=1,
            acoustic_threshold=0.3,
            respect_privacy=True,
            output_modalities=["audio", "ar", "watch"],
        ),
        PropagationType.RAISED_VOICE: PropagationConfig(
            propagation_type=PropagationType.RAISED_VOICE,
            description="Important announcements, calling someone",
            max_hops=2,
            acoustic_threshold=0.2,
            respect_privacy=True,
            output_modalities=["audio", "ar", "watch"],
        ),
        PropagationType.LOUD_EVENT: PropagationConfig(
            propagation_type=PropagationType.LOUD_EVENT,
            description="Smoke alarm, doorbell, glass break, security",
            max_hops=3,
            acoustic_threshold=0.1,
            respect_privacy=True,
            output_modalities=["audio", "ar", "watch"],
        ),
        PropagationType.VISUAL_ONLY: PropagationConfig(
            propagation_type=PropagationType.VISUAL_ONLY,
            description="Watch/AR notification, no audio",
            max_hops=0,
            acoustic_threshold=None,
            respect_privacy=True,
            output_modalities=["ar", "watch"],
        ),
        PropagationType.BROADCAST: PropagationConfig(
            propagation_type=PropagationType.BROADCAST,
            description="Emergency - all rooms regardless of privacy",
            max_hops=999,
            acoustic_threshold=0.0,
            respect_privacy=False,
            output_modalities=["audio", "ar", "watch"],
        ),
    }

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize spatial awareness system."""
        self.hass = hass
        self.config = config
        self._rooms: dict[str, RoomNode] = {}
        self._adjacencies: dict[str, list[RoomConnection]] = {}
        self._door_states: dict[str, bool] = {}  # entity_id -> is_open
        self._path_cache: dict[tuple[str, str], PathResult | None] = {}
        self._cache_valid = False
        self._unsubscribe_listeners: list = []

    async def async_initialize(self) -> None:
        """Initialize the spatial awareness system."""
        _LOGGER.info("Initializing Spatial Awareness System...")
        
        # Load configuration
        await self._load_configuration()
        
        # Subscribe to door state changes
        await self._setup_door_listeners()
        
        # Precompute paths
        self._precompute_all_paths()
        
        _LOGGER.info(
            f"Spatial Awareness initialized: {len(self._rooms)} rooms, "
            f"{sum(len(adj) for adj in self._adjacencies.values()) // 2} connections"
        )

    async def _load_configuration(self) -> None:
        """Load room graph from configuration."""
        spatial_config = self.config.get("spatial_awareness", {})
        
        # Load rooms
        for room_id, room_data in spatial_config.get("rooms", {}).items():
            self._rooms[room_id] = RoomNode(
                room_id=room_id,
                name=room_data.get("name", room_id),
                room_type=RoomType(room_data.get("type", "common")),
                privacy_level=PrivacyLevel(room_data.get("privacy_level", "public")),
                ha_area_id=room_data.get("ha_area_id", room_id),
                output_devices=room_data.get("output_devices", []),
                input_devices=room_data.get("input_devices", []),
                occupancy_sensor=room_data.get("occupancy_sensor"),
            )
        
        # Load connections
        for conn_data in spatial_config.get("connections", []):
            connection = RoomConnection(
                from_room=conn_data["from"],
                to_room=conn_data["to"],
                barrier_type=BarrierType(conn_data["barrier"]["type"]),
                base_acoustic_factor=conn_data["barrier"]["base_acoustic_factor"],
                barrier_state_entity=conn_data["barrier"].get("state_entity"),
                open_bonus=conn_data["barrier"].get("open_bonus", 0.5),
            )
            
            # Add bidirectional connections
            if connection.from_room not in self._adjacencies:
                self._adjacencies[connection.from_room] = []
            if connection.to_room not in self._adjacencies:
                self._adjacencies[connection.to_room] = []
            
            self._adjacencies[connection.from_room].append(connection)
            # Create reverse connection
            reverse_connection = RoomConnection(
                from_room=connection.to_room,
                to_room=connection.from_room,
                barrier_type=connection.barrier_type,
                base_acoustic_factor=connection.base_acoustic_factor,
                barrier_state_entity=connection.barrier_state_entity,
                open_bonus=connection.open_bonus,
            )
            self._adjacencies[connection.to_room].append(reverse_connection)

    async def _setup_door_listeners(self) -> None:
        """Subscribe to door state changes in Home Assistant."""
        # Collect all door entities
        door_entities = set()
        for connections in self._adjacencies.values():
            for conn in connections:
                if conn.barrier_state_entity:
                    door_entities.add(conn.barrier_state_entity)
        
        # Subscribe to state changes
        for entity_id in door_entities:
            # Get initial state
            state = self.hass.states.get(entity_id)
            if state:
                self._door_states[entity_id] = state.state == "on"
            
            # Subscribe to changes
            unsub = self.hass.helpers.event.async_track_state_change_event(
                entity_id,
                self._handle_door_state_change,
            )
            self._unsubscribe_listeners.append(unsub)
        
        _LOGGER.debug(f"Subscribed to {len(door_entities)} door sensors")

    async def _handle_door_state_change(self, event) -> None:
        """Handle door state change events."""
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        
        if new_state:
            is_open = new_state.state == "on"
            old_state = self._door_states.get(entity_id)
            
            if old_state != is_open:
                self._door_states[entity_id] = is_open
                self._invalidate_cache()
                _LOGGER.debug(
                    f"Door state changed: {entity_id} -> {'open' if is_open else 'closed'}"
                )

    def _invalidate_cache(self) -> None:
        """Invalidate the path cache."""
        self._path_cache.clear()
        self._cache_valid = False
        _LOGGER.debug("Path cache invalidated")

    def _precompute_all_paths(self) -> None:
        """Precompute shortest paths between all room pairs."""
        room_ids = list(self._rooms.keys())
        
        for i, room_a in enumerate(room_ids):
            for room_b in room_ids[i:]:
                if room_a != room_b:
                    path = self._calculate_path(room_a, room_b)
                    self._path_cache[(room_a, room_b)] = path
                    self._path_cache[(room_b, room_a)] = path
        
        self._cache_valid = True
        _LOGGER.debug(f"Precomputed {len(self._path_cache)} paths")

    def _get_effective_acoustic_factor(self, connection: RoomConnection) -> float:
        """Get effective acoustic factor considering door state."""
        if connection.barrier_state_entity is None:
            return connection.base_acoustic_factor
        
        is_open = self._door_states.get(connection.barrier_state_entity, False)
        if is_open:
            return min(1.0, connection.base_acoustic_factor + connection.open_bonus)
        return connection.base_acoustic_factor

    def _calculate_path(self, room_a: str, room_b: str) -> PathResult | None:
        """Calculate shortest path between two rooms using BFS."""
        if room_a == room_b:
            return PathResult(
                path=[room_a],
                hop_count=0,
                cumulative_acoustic_factor=1.0,
                barriers=[],
            )
        
        if room_a not in self._rooms or room_b not in self._rooms:
            return None
        
        # BFS for shortest path
        queue = deque([(room_a, [room_a], 1.0, [])])
        visited = {room_a}
        
        while queue:
            current, path, acoustic, barriers = queue.popleft()
            
            for connection in self._adjacencies.get(current, []):
                neighbor = connection.to_room
                
                if neighbor in visited:
                    continue
                
                new_acoustic = acoustic * self._get_effective_acoustic_factor(connection)
                new_path = path + [neighbor]
                new_barriers = barriers + [
                    (connection.from_room, connection.to_room, connection.barrier_type)
                ]
                
                if neighbor == room_b:
                    return PathResult(
                        path=new_path,
                        hop_count=len(new_path) - 1,
                        cumulative_acoustic_factor=new_acoustic,
                        barriers=new_barriers,
                    )
                
                visited.add(neighbor)
                queue.append((neighbor, new_path, new_acoustic, new_barriers))
        
        return None  # No path found

    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================

    def can_room_perceive_event(
        self,
        event_room: str,
        observer_room: str,
        event_type: PropagationType,
    ) -> bool:
        """
        Determine if a specific room should perceive an event.
        
        Args:
            event_room: Room where the event originated
            observer_room: Room to check for perception
            event_type: Type of event (affects propagation rules)
            
        Returns:
            True if observer_room should perceive the event
        """
        # Same room always perceives
        if event_room == observer_room:
            return True
        
        # Get propagation config
        config = self.PROPAGATION_CONFIGS.get(event_type)
        if not config:
            _LOGGER.warning(f"Unknown propagation type: {event_type}")
            return False
        
        # Whisper and visual_only are same-room only
        if config.max_hops == 0:
            return False
        
        # Check privacy
        if config.respect_privacy:
            if not self._check_privacy_allowed(event_room, observer_room, event_type):
                return False
        
        # Get path
        path = self.get_shortest_path(event_room, observer_room)
        if path is None:
            return False
        
        # Check hop count
        if path.hop_count > config.max_hops:
            return False
        
        # Check acoustic threshold
        if config.acoustic_threshold is not None:
            if path.cumulative_acoustic_factor < config.acoustic_threshold:
                return False
        
        return True

    def get_rooms_perceiving_event(
        self,
        event_room: str,
        event_type: PropagationType,
    ) -> list[RoomPerceptionResult]:
        """
        Get all rooms that should perceive an event, with details.
        
        Args:
            event_room: Room where the event originated
            event_type: Type of event
            
        Returns:
            List of RoomPerceptionResult sorted by hop count (nearest first)
        """
        config = self.PROPAGATION_CONFIGS.get(event_type)
        if not config:
            return []
        
        results = []
        
        for room_id, room in self._rooms.items():
            if room_id == event_room:
                # Event room always perceives
                results.append(RoomPerceptionResult(
                    room_id=room_id,
                    hop_count=0,
                    cumulative_acoustic_factor=1.0,
                    path=[room_id],
                    output_devices=room.output_devices,
                    is_privacy_blocked=False,
                ))
                continue
            
            # Check privacy first
            is_privacy_blocked = (
                config.respect_privacy and 
                not self._check_privacy_allowed(event_room, room_id, event_type)
            )
            
            # Get path
            path = self.get_shortest_path(event_room, room_id)
            if path is None:
                continue
            
            # Check hop count
            if path.hop_count > config.max_hops:
                continue
            
            # Check acoustic threshold
            if config.acoustic_threshold is not None:
                if path.cumulative_acoustic_factor < config.acoustic_threshold:
                    continue
            
            results.append(RoomPerceptionResult(
                room_id=room_id,
                hop_count=path.hop_count,
                cumulative_acoustic_factor=path.cumulative_acoustic_factor,
                path=path.path,
                output_devices=room.output_devices,
                is_privacy_blocked=is_privacy_blocked,
            ))
        
        # Filter out privacy-blocked rooms (unless broadcast)
        if config.respect_privacy:
            results = [r for r in results if not r.is_privacy_blocked]
        
        # Sort by hop count
        results.sort(key=lambda r: (r.hop_count, -r.cumulative_acoustic_factor))
        
        return results

    def get_shortest_path(self, room_a: str, room_b: str) -> PathResult | None:
        """
        Calculate shortest path and acoustic properties between two rooms.
        
        Args:
            room_a: Starting room
            room_b: Destination room
            
        Returns:
            PathResult with path details, or None if no path exists
        """
        # Check cache first
        cache_key = (room_a, room_b)
        if self._cache_valid and cache_key in self._path_cache:
            cached = self._path_cache[cache_key]
            if cached:
                # Recalculate acoustic factor with current door states
                return self._recalculate_path_acoustic(cached)
            return None
        
        # Calculate fresh
        path = self._calculate_path(room_a, room_b)
        self._path_cache[cache_key] = path
        return path

    def _recalculate_path_acoustic(self, path: PathResult) -> PathResult:
        """Recalculate acoustic factor for a cached path with current door states."""
        if path.hop_count == 0:
            return path
        
        acoustic = 1.0
        for from_room, to_room, _ in path.barriers:
            for conn in self._adjacencies.get(from_room, []):
                if conn.to_room == to_room:
                    acoustic *= self._get_effective_acoustic_factor(conn)
                    break
        
        return PathResult(
            path=path.path,
            hop_count=path.hop_count,
            cumulative_acoustic_factor=acoustic,
            barriers=path.barriers,
        )

    def is_private_space(self, room_id: str) -> bool:
        """
        Quick check for privacy zone status.
        
        Args:
            room_id: Room to check
            
        Returns:
            True if room is a private space (bathroom, bedroom)
        """
        room = self._rooms.get(room_id)
        if not room:
            return False
        
        return (
            room.privacy_level in (PrivacyLevel.PRIVATE, PrivacyLevel.SEMI_PRIVATE) or
            room.room_type in (RoomType.BATHROOM, RoomType.BEDROOM)
        )

    def _check_privacy_allowed(
        self,
        from_room: str,
        to_room: str,
        event_type: PropagationType,
    ) -> bool:
        """Check if propagation is allowed based on privacy rules."""
        to_room_node = self._rooms.get(to_room)
        if not to_room_node:
            return False
        
        # Bathrooms never receive non-broadcast audio
        if to_room_node.room_type == RoomType.BATHROOM:
            return event_type == PropagationType.BROADCAST
        
        # Children's rooms only receive safety alerts and broadcasts
        if to_room_node.room_type == RoomType.BEDROOM and to_room_node.privacy_level == PrivacyLevel.PRIVATE:
            # Check if it's a child's room (not master)
            if "master" not in to_room.lower():
                return event_type in (
                    PropagationType.LOUD_EVENT,
                    PropagationType.BROADCAST,
                )
        
        return True

    def get_best_speaker_for_user(
        self,
        user_location: str | None,
        fallback_room: str = "living_room",
    ) -> str | None:
        """
        Select optimal speaker for TTS output based on user location.
        
        Args:
            user_location: Room where user is located (or None if unknown)
            fallback_room: Room to use if location unknown
            
        Returns:
            Entity ID of best speaker, or None if no speaker available
        """
        # If user in room with speaker, use that
        if user_location:
            room = self._rooms.get(user_location)
            if room and room.output_devices and not self.is_private_space(user_location):
                return room.output_devices[0]
        
        # Try fallback room
        fallback = self._rooms.get(fallback_room)
        if fallback and fallback.output_devices:
            return fallback.output_devices[0]
        
        # Find nearest room with speaker
        for room in self._rooms.values():
            if room.output_devices and not self.is_private_space(room.room_id):
                return room.output_devices[0]
        
        return None

    def get_speakers_for_event(
        self,
        event_room: str,
        event_type: PropagationType,
    ) -> list[str]:
        """
        Get all speakers that should play an event.
        
        Args:
            event_room: Room where event originated
            event_type: Type of event
            
        Returns:
            List of speaker entity IDs
        """
        perceiving_rooms = self.get_rooms_perceiving_event(event_room, event_type)
        
        speakers = []
        for room_result in perceiving_rooms:
            speakers.extend(room_result.output_devices)
        
        return list(set(speakers))  # Deduplicate

    async def async_shutdown(self) -> None:
        """Shutdown spatial awareness system."""
        for unsub in self._unsubscribe_listeners:
            unsub()
        self._unsubscribe_listeners.clear()
        self._path_cache.clear()
        _LOGGER.info("Spatial Awareness System shut down")
```

---

## Integration with Proactive Agent

### Notification Routing Flow

```
Proactive Agent Decision Flow:

┌─────────────────────────────────────────────────────────────────┐
│                     PROACTIVE EVENT TRIGGERED                   │
│                  (e.g., "Package arrived at door")              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              DETERMINE EVENT ORIGIN ROOM                        │
│           (front_door → entryway/living_room)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│         SPATIAL AWARENESS: get_rooms_perceiving_event()         │
│    event_room="living_room", event_type="proactive_notification"│
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FILTER BY OCCUPANCY                           │
│     Only include rooms where family members are present         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 APPLY CONTEXT RULES                             │
│   - Is user in "work mode"? (office during work hours)          │
│   - Is user in "do not disturb" mode?                           │
│   - Rate limiting per room                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               SELECT OUTPUT MODALITY                            │
│   - Audio (TTS to speakers in perceiving rooms)                 │
│   - Visual (AR overlay if wearing glasses)                      │
│   - Haptic (watch notification)                                 │
│   - Combination based on urgency                                │
└─────────────────────────────────────────────────────────────────┘
```

### Work Hours Context Example

**Scenario:** Someone in office shouldn't hear kitchen conversations during work hours.

```python
# agents/proactive_agent.py (enhanced)

async def _should_notify_room(
    self,
    event: ProactiveEvent,
    target_room: str,
    user_context: UserContext,
) -> bool:
    """Determine if a room should receive notification."""
    # Base spatial check
    if not self.spatial.can_room_perceive_event(
        event.origin_room,
        target_room,
        event.propagation_type,
    ):
        return False
    
    # Context-based filtering for office during work hours
    if target_room == "office" and user_context.work_mode_active:
        if event.priority < Priority.MEDIUM:
            return False  # Suppress low-priority during work
        if event.propagation_type in [
            PropagationType.NORMAL_SPEECH,
            PropagationType.VISUAL_ONLY,
        ]:
            return False  # No casual interruptions
    
    return True
```

### Speaker Selection Strategy

**Priority Order for TTS Output:**

1. **Same room as user** (if user location known)
2. **Nearest occupied room** (by hop count)
3. **Room where event originated** (for context)
4. **Fallback room** (configured default, e.g., living_room)

### Multi-Room Announcement

For `loud_event` and `broadcast` types:

```python
async def _announce_to_all_perceiving_rooms(
    self,
    message: str,
    event_room: str,
    event_type: PropagationType,
) -> None:
    """Announce on all speakers that should perceive the event."""
    speakers = self.spatial.get_speakers_for_event(event_room, event_type)
    
    if not speakers:
        _LOGGER.warning(f"No speakers available for event in {event_room}")
        return
    
    # Generate TTS audio
    tts_url = await self.tts.async_get_url(message)
    
    # Play on all speakers simultaneously
    await self.hass.services.async_call(
        "media_player",
        "play_media",
        target={"entity_id": speakers},
        service_data={
            "media_content_id": tts_url,
            "media_content_type": "music",
        },
    )
```

### Notification Delivery Matrix

| Event Priority | Modality Selection | Spatial Scope |
|----------------|-------------------|---------------|
| **Critical** (fire, CO) | Audio (all rooms) + AR + Watch vibrate | broadcast (all) |
| **High** (security) | Audio (perceiving rooms) + Watch | loud_event (3 hops) |
| **Medium** (doorbell) | Audio (perceiving) OR Watch | loud_event (3 hops) |
| **Low** (package) | Watch only, OR audio if idle | normal_speech (1 hop) |
| **Informational** | Watch/AR only | whisper (same room) |

---

## Configuration Schema

### Complete YAML Configuration

**File Location:** `config/spatial_awareness.yaml`

```yaml
# BarnabeeNet Spatial Awareness Configuration
# Version: 1.0

spatial_awareness:
  enabled: true
  
  cache:
    enabled: true
    ttl_seconds: 3600
    invalidate_on_door_change: true

  defaults:
    acoustic_threshold: 0.3
    max_hops: 2
    respect_privacy_zones: true

# Room definitions
rooms:
  living_room:
    name: "Living Room"
    type: common
    privacy_level: public
    ha_area_id: "living_room"
    output_devices:
      - media_player.living_room_speaker
      - media_player.living_room_tv
    input_devices:
      - binary_sensor.living_room_alexa
    occupancy_sensor: binary_sensor.living_room_motion

  kitchen:
    name: "Kitchen"
    type: common
    privacy_level: public
    ha_area_id: "kitchen"
    output_devices:
      - media_player.kitchen_speaker
    input_devices:
      - binary_sensor.kitchen_alexa
    occupancy_sensor: binary_sensor.kitchen_motion

  office:
    name: "Home Office"
    type: office
    privacy_level: semi_private
    ha_area_id: "office"
    output_devices:
      - media_player.office_speaker
    input_devices:
      - binary_sensor.office_thinksmart
    occupancy_sensor: binary_sensor.office_motion
    context_rules:
      work_mode:
        schedule: "09:00-17:00"
        days: [monday, tuesday, wednesday, thursday, friday]
        suppress_types: [normal_speech, proactive_notification]
        allow_types: [safety_alert, security_alert, raised_voice, broadcast]

  garage:
    name: "Garage"
    type: utility
    privacy_level: public
    ha_area_id: "garage"
    output_devices:
      - media_player.garage_speaker
    occupancy_sensor: binary_sensor.garage_motion

  hallway:
    name: "Main Hallway"
    type: common
    privacy_level: public
    ha_area_id: "hallway"
    output_devices: []
    occupancy_sensor: binary_sensor.hallway_motion

  master_bedroom:
    name: "Master Bedroom"
    type: bedroom
    privacy_level: private
    ha_area_id: "master_bedroom"
    output_devices:
      - media_player.master_bedroom_speaker
    occupancy_sensor: binary_sensor.master_bedroom_motion

  master_bathroom:
    name: "Master Bathroom"
    type: bathroom
    privacy_level: private
    ha_area_id: "bathroom_master"
    output_devices: []
    occupancy_sensor: binary_sensor.master_bathroom_motion

  bedroom_penelope:
    name: "Penelope's Room"
    type: bedroom
    privacy_level: private
    ha_area_id: "bedroom_penelope"
    output_devices: []
    occupancy_sensor: binary_sensor.penelope_room_motion

  bedroom_xander:
    name: "Xander's Room"
    type: bedroom
    privacy_level: private
    ha_area_id: "bedroom_xander"
    output_devices: []
    occupancy_sensor: binary_sensor.xander_room_motion

  bedroom_zachary:
    name: "Zachary's Room"
    type: bedroom
    privacy_level: private
    ha_area_id: "bedroom_zachary"
    output_devices: []
    occupancy_sensor: binary_sensor.zachary_room_motion

  bedroom_viola:
    name: "Viola's Room"
    type: bedroom
    privacy_level: private
    ha_area_id: "bedroom_viola"
    output_devices: []
    occupancy_sensor: binary_sensor.viola_room_motion

  kids_bathroom:
    name: "Kids Bathroom"
    type: bathroom
    privacy_level: private
    ha_area_id: "bathroom_kids"
    output_devices: []
    occupancy_sensor: binary_sensor.kids_bathroom_motion

# Room connections
connections:
  - from: living_room
    to: kitchen
    barrier:
      type: archway
      base_acoustic_factor: 0.9
      state_entity: null

  - from: living_room
    to: hallway
    barrier:
      type: open
      base_acoustic_factor: 0.85
      state_entity: null

  - from: kitchen
    to: garage
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.kitchen_garage_door
      open_bonus: 0.5

  - from: kitchen
    to: office
    barrier:
      type: archway
      base_acoustic_factor: 0.9
      state_entity: null

  - from: kitchen
    to: hallway
    barrier:
      type: open
      base_acoustic_factor: 0.85
      state_entity: null

  - from: hallway
    to: master_bedroom
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.master_bedroom_door
      open_bonus: 0.5

  - from: hallway
    to: kids_bathroom
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.kids_bathroom_door
      open_bonus: 0.4

  - from: hallway
    to: bedroom_penelope
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.penelope_room_door
      open_bonus: 0.5

  - from: hallway
    to: bedroom_xander
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.xander_room_door
      open_bonus: 0.5

  - from: hallway
    to: bedroom_zachary
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.zachary_room_door
      open_bonus: 0.5

  - from: hallway
    to: bedroom_viola
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.viola_room_door
      open_bonus: 0.5

  - from: master_bedroom
    to: master_bathroom
    barrier:
      type: door
      base_acoustic_factor: 0.3
      state_entity: binary_sensor.master_bathroom_door
      open_bonus: 0.4

# Event propagation rules
propagation_rules:
  whisper:
    description: "Same room only, private mode"
    max_hops: 0
    acoustic_threshold: null
    respect_privacy: true
    output_modalities: [audio, ar]

  normal_speech:
    description: "Standard voice responses"
    max_hops: 1
    acoustic_threshold: 0.3
    respect_privacy: true
    output_modalities: [audio, ar, watch]

  raised_voice:
    description: "Important announcements"
    max_hops: 2
    acoustic_threshold: 0.2
    respect_privacy: true
    output_modalities: [audio, ar, watch]

  loud_event:
    description: "Alarms and alerts"
    max_hops: 3
    acoustic_threshold: 0.1
    respect_privacy: true
    output_modalities: [audio, ar, watch]

  visual_only:
    description: "Silent notifications"
    max_hops: 0
    acoustic_threshold: null
    respect_privacy: true
    output_modalities: [ar, watch]

  broadcast:
    description: "Emergency - all rooms"
    max_hops: 999
    acoustic_threshold: 0.0
    respect_privacy: false
    output_modalities: [audio, ar, watch]

# Event type mappings
event_types:
  voice_response:
    propagation: normal_speech
    priority: medium

  proactive_notification:
    propagation: normal_speech
    priority: low

  timer_alarm:
    propagation: raised_voice
    priority: medium

  doorbell:
    propagation: loud_event
    priority: medium

  safety_alert:
    propagation: loud_event
    priority: high

  security_alert:
    propagation: broadcast
    priority: critical

  smoke_alarm:
    propagation: broadcast
    priority: critical

  co_alarm:
    propagation: broadcast
    priority: critical

  water_leak:
    propagation: broadcast
    priority: critical

  private_notification:
    propagation: whisper
    priority: low

# Privacy overrides
privacy_overrides:
  children_rooms:
    allow_inbound: [broadcast]
    block_inbound: [normal_speech, raised_voice, loud_event, proactive_notification]
    allow_outbound: all

  bathrooms:
    allow_inbound: [broadcast]
    block_inbound: [normal_speech, raised_voice, loud_event, proactive_notification, whisper]
    allow_outbound: none

# Fallback settings
fallback:
  default_speaker: media_player.living_room_speaker
  unknown_location_room: living_room
  announcement_delay_ms: 0
```

---

## Implementation Recommendations

### Phasing

| Phase | Scope | Dependencies |
|-------|-------|--------------|
| **Phase 1** | Basic room graph, static connections, `can_room_perceive_event()` | None |
| **Phase 2** | Dynamic door state integration, cache invalidation | Door sensors configured |
| **Phase 3** | Proactive agent integration, speaker selection | Phase 2 complete |
| **Phase 4** | Context rules (work mode, quiet hours), occupancy-aware routing | Phase 3 complete |
| **Phase 5** | Multi-room announcement, acoustic factor tuning | Phase 4 complete |

### Performance Targets

| Operation | Target Latency | Strategy |
|-----------|----------------|----------|
| `can_room_perceive_event` | <1ms | Cached paths, precomputed adjacency |
| `get_rooms_perceiving_event` | <5ms | BFS with early termination |
| `get_shortest_path` | <2ms | Cached results, invalidate on change |
| Graph update (door change) | <10ms | Incremental update, selective cache clear |

### Testing Strategy

**Unit Tests:**
- Graph construction from YAML
- BFS/path calculation correctness
- Acoustic factor multiplication
- Privacy zone filtering

**Integration Tests:**
- Door state change → cache invalidation
- Event propagation with real HA entities
- Speaker selection with occupancy

**Manual Testing:**
- Fire alarm should reach ALL rooms
- Normal notification should NOT reach office during work hours
- Bathroom should never receive audio (except broadcast)
- Kids' rooms should only receive safety alerts

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial spatial awareness system specification |

---

*This document specifies the Spatial Awareness System for BarnabeeNet. For core architecture, see BarnabeeNet_Technical_Architecture.md. For feature descriptions, see BarnabeeNet_Features_UseCases.md.*
