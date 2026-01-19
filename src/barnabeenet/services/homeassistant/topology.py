"""Home Assistant Topology Service.

Loads and caches Home Assistant's floor/area structure dynamically at startup.
Provides intelligent area and floor resolution from natural language.

Key features:
- Loads floor registry from HA's WebSocket API (config/floor_registry/list)
- Loads area registry with floor associations
- Supports natural language floor terms ("downstairs", "upstairs", "first floor")
- Bidirectional mappings for fast lookups
- Periodic refresh to stay in sync with HA
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


@dataclass
class Floor:
    """Home Assistant floor from floor registry."""

    floor_id: str
    name: str
    level: int | None = None  # Floor level (e.g., 0 = ground, 1 = second)
    aliases: list[str] = field(default_factory=list)
    icon: str | None = None

    def matches_name(self, query: str) -> bool:
        """Check if floor matches a name query (case-insensitive)."""
        query_lower = query.lower()
        if query_lower == self.name.lower():
            return True
        if query_lower == self.floor_id.lower():
            return True
        return any(alias.lower() == query_lower for alias in self.aliases)


# =============================================================================
# Common Floor Term Mappings
# =============================================================================

# Maps common natural language floor terms to potential floor names/IDs
# These are checked against the actual floors loaded from HA
FLOOR_TERM_MAPPINGS: dict[str, list[str]] = {
    # Ground/First floor terms
    "downstairs": [
        "first_floor",
        "first floor",
        "ground_floor",
        "ground floor",
        "main_floor",
        "main floor",
        "1st_floor",
        "1st floor",
        "floor_1",
        "level_0",
        "lower_level",
    ],
    "first floor": [
        "first_floor",
        "first floor",
        "ground_floor",
        "ground floor",
        "main_floor",
        "1st_floor",
        "floor_1",
    ],
    "ground floor": [
        "ground_floor",
        "ground floor",
        "first_floor",
        "first floor",
        "main_floor",
        "floor_0",
        "level_0",
    ],
    "main floor": [
        "main_floor",
        "main floor",
        "first_floor",
        "first floor",
        "ground_floor",
        "floor_1",
    ],
    "lower level": [
        "lower_level",
        "lower level",
        "first_floor",
        "basement",
        "ground_floor",
    ],
    # Second floor terms
    "upstairs": [
        "second_floor",
        "second floor",
        "upper_floor",
        "upper floor",
        "2nd_floor",
        "2nd floor",
        "floor_2",
        "level_1",
        "upper_level",
    ],
    "second floor": [
        "second_floor",
        "second floor",
        "2nd_floor",
        "2nd floor",
        "floor_2",
        "upper_floor",
    ],
    "upper floor": [
        "upper_floor",
        "upper floor",
        "second_floor",
        "second floor",
        "2nd_floor",
        "top_floor",
    ],
    "top floor": [
        "top_floor",
        "top floor",
        "upper_floor",
        "second_floor",
        "third_floor",
        "attic",
    ],
    # Basement terms
    "basement": [
        "basement",
        "lower_level",
        "lower level",
        "cellar",
        "floor_0",
        "level_-1",
    ],
    # Outside
    "outside": ["outside", "outdoor", "outdoors", "exterior", "yard", "patio"],
}


@dataclass
class HATopology:
    """Cached Home Assistant topology data."""

    floors: dict[str, Floor] = field(default_factory=dict)  # floor_id -> Floor
    area_to_floor: dict[str, str] = field(default_factory=dict)  # area_id -> floor_id
    floor_to_areas: dict[str, list[str]] = field(default_factory=dict)  # floor_id -> [area_ids]
    area_name_to_id: dict[str, str] = field(default_factory=dict)  # normalized name -> area_id
    last_refresh: datetime | None = None
    refresh_errors: list[str] = field(default_factory=list)


class HATopologyService:
    """Service for loading and caching HA topology (floors, areas).

    This service is responsible for:
    - Loading floor and area registries from Home Assistant
    - Building bidirectional mappings for efficient lookups
    - Resolving natural language location references to area_ids
    - Supporting floor-based targeting (e.g., "downstairs" → list of area_ids)

    Usage:
        topology_service = HATopologyService(ha_client)
        await topology_service.refresh()

        # Resolve "kitchen" to area_id
        area_id = topology_service.resolve_area("kitchen")

        # Resolve "downstairs" to list of area_ids
        area_ids = topology_service.resolve_floor("downstairs")
    """

    def __init__(self, ha_client: HomeAssistantClient) -> None:
        """Initialize the topology service.

        Args:
            ha_client: Connected Home Assistant client
        """
        self._ha = ha_client
        self._topology = HATopology()
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_interval: int = 300  # 5 minutes

    @property
    def topology(self) -> HATopology:
        """Get the current topology data."""
        return self._topology

    @property
    def floors(self) -> dict[str, Floor]:
        """Get the floor registry."""
        return self._topology.floors

    @property
    def last_refresh(self) -> datetime | None:
        """Get the last refresh timestamp."""
        return self._topology.last_refresh

    async def refresh(self) -> bool:
        """Refresh topology from Home Assistant.

        Loads:
        - Floor registry (via WebSocket: config/floor_registry/list)
        - Area registry (already in HA client, just needs floor mapping)

        Returns:
            True if refresh was successful, False otherwise.
        """
        logger.info("Refreshing HA topology...")
        self._topology.refresh_errors.clear()

        try:
            # Load floors from WebSocket API
            await self._load_floors()

            # Build area mappings from existing HA client data
            self._build_area_mappings()

            self._topology.last_refresh = datetime.now()
            logger.info(
                "HA topology refreshed: %d floors, %d areas mapped",
                len(self._topology.floors),
                len(self._topology.area_to_floor),
            )
            return True

        except Exception as e:
            error_msg = f"Failed to refresh topology: {e}"
            logger.error(error_msg)
            self._topology.refresh_errors.append(error_msg)
            return False

    async def _load_floors(self) -> None:
        """Load floor registry from Home Assistant via WebSocket."""
        try:
            floor_data = await self._ha._ws_command("config/floor_registry/list")
            if not floor_data:
                logger.warning("No floor data returned from HA")
                return

            self._topology.floors.clear()
            for entry in floor_data:
                floor_id = entry.get("floor_id", "")
                if not floor_id:
                    continue

                floor = Floor(
                    floor_id=floor_id,
                    name=entry.get("name", floor_id),
                    level=entry.get("level"),
                    aliases=entry.get("aliases", []),
                    icon=entry.get("icon"),
                )
                self._topology.floors[floor_id] = floor

            logger.debug("Loaded %d floors from HA", len(self._topology.floors))

        except Exception as e:
            error_msg = f"Failed to load floors: {e}"
            logger.warning(error_msg)
            self._topology.refresh_errors.append(error_msg)

    def _build_area_mappings(self) -> None:
        """Build area-to-floor and floor-to-areas mappings from HA client data."""
        self._topology.area_to_floor.clear()
        self._topology.floor_to_areas.clear()
        self._topology.area_name_to_id.clear()

        # Get areas from HA client
        for area_id, area in self._ha.areas.items():
            # Build name lookup (normalize for matching)
            normalized_name = area.name.lower().strip()
            self._topology.area_name_to_id[normalized_name] = area_id
            # Also add the ID itself
            self._topology.area_name_to_id[area_id.lower()] = area_id
            # Add aliases
            for alias in area.aliases:
                self._topology.area_name_to_id[alias.lower().strip()] = area_id

            # Map area to floor
            if area.floor_id:
                self._topology.area_to_floor[area_id] = area.floor_id
                if area.floor_id not in self._topology.floor_to_areas:
                    self._topology.floor_to_areas[area.floor_id] = []
                self._topology.floor_to_areas[area.floor_id].append(area_id)

        logger.debug(
            "Built mappings: %d area names, %d area-floor associations",
            len(self._topology.area_name_to_id),
            len(self._topology.area_to_floor),
        )

    def resolve_area(self, text: str) -> str | None:
        """Resolve natural language to an area_id.

        Tries multiple strategies:
        1. Exact match on area name or ID
        2. Match on area aliases
        3. Partial match (text contains area name or vice versa)

        Args:
            text: Natural language area reference (e.g., "kitchen", "living room")

        Returns:
            area_id if found, None otherwise
        """
        text_lower = text.lower().strip()

        # Direct lookup
        if text_lower in self._topology.area_name_to_id:
            return self._topology.area_name_to_id[text_lower]

        # Handle possessives: "girl's room" -> "girls room"
        normalized = text_lower.replace("'s", "s").replace("'", "")
        if normalized in self._topology.area_name_to_id:
            return self._topology.area_name_to_id[normalized]

        # Try partial matching
        for name, area_id in self._topology.area_name_to_id.items():
            # Check if query is contained in name or vice versa
            if text_lower in name or name in text_lower:
                return area_id
            if normalized in name or name in normalized:
                return area_id

        return None

    def resolve_floor(self, text: str) -> list[str]:
        """Resolve floor term to list of area_ids on that floor.

        Handles common floor terms like "downstairs", "upstairs", "first floor".
        Maps these to actual floor_ids in HA, then returns all areas on that floor.

        Args:
            text: Floor reference (e.g., "downstairs", "upstairs", "second floor")

        Returns:
            List of area_ids on the resolved floor, empty list if not found
        """
        text_lower = text.lower().strip()

        # First, try to match directly to a floor_id or name
        floor_id = self._resolve_floor_id(text_lower)
        if floor_id:
            return self._topology.floor_to_areas.get(floor_id, [])

        return []

    def _resolve_floor_id(self, text: str) -> str | None:
        """Resolve text to a floor_id.

        Args:
            text: Lowercase floor reference

        Returns:
            floor_id if found, None otherwise
        """
        # Check common floor terms
        if text in FLOOR_TERM_MAPPINGS:
            potential_matches = FLOOR_TERM_MAPPINGS[text]
            for potential in potential_matches:
                # Check if this matches any actual floor
                for floor_id, floor in self._topology.floors.items():
                    if floor_id.lower() == potential.lower():
                        return floor_id
                    if floor.name.lower() == potential.lower():
                        return floor_id
                    # Check floor aliases
                    for alias in floor.aliases:
                        if alias.lower() == potential.lower():
                            return floor_id

        # Direct floor lookup
        for floor_id, floor in self._topology.floors.items():
            if floor.matches_name(text):
                return floor_id

        # Try by floor level if text is a number
        try:
            level = int(text.replace("floor", "").replace("level", "").strip())
            for floor_id, floor in self._topology.floors.items():
                if floor.level == level:
                    return floor_id
        except ValueError:
            pass

        return None

    def get_areas_on_floor(self, floor_id: str) -> list[str]:
        """Get all area_ids on a specific floor.

        Args:
            floor_id: The floor ID

        Returns:
            List of area_ids on this floor
        """
        return self._topology.floor_to_areas.get(floor_id, [])

    def get_floor_for_area(self, area_id: str) -> str | None:
        """Get the floor_id for a specific area.

        Args:
            area_id: The area ID

        Returns:
            floor_id if the area is on a floor, None otherwise
        """
        return self._topology.area_to_floor.get(area_id)

    async def start_periodic_refresh(self, interval_seconds: int = 300) -> None:
        """Start periodic topology refresh.

        Args:
            interval_seconds: Refresh interval in seconds (default 5 minutes)
        """
        self._refresh_interval = interval_seconds
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._periodic_refresh_loop())
            logger.info(
                "Started periodic topology refresh every %d seconds",
                interval_seconds,
            )

    async def stop_periodic_refresh(self) -> None:
        """Stop periodic topology refresh."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            logger.info("Stopped periodic topology refresh")

    async def _periodic_refresh_loop(self) -> None:
        """Background loop for periodic topology refresh."""
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self.refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Periodic topology refresh failed: %s", e)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current topology.

        Returns:
            Dictionary with topology statistics
        """
        return {
            "floors": len(self._topology.floors),
            "areas_with_floors": len(self._topology.area_to_floor),
            "total_areas": len(self._topology.area_name_to_id),
            "last_refresh": self._topology.last_refresh.isoformat()
            if self._topology.last_refresh
            else None,
            "errors": self._topology.refresh_errors,
            "floor_details": [
                {
                    "floor_id": f.floor_id,
                    "name": f.name,
                    "level": f.level,
                    "area_count": len(self._topology.floor_to_areas.get(f.floor_id, [])),
                }
                for f in self._topology.floors.values()
            ],
        }


# =============================================================================
# Singleton Pattern
# =============================================================================

_topology_service: HATopologyService | None = None


async def get_topology_service(
    ha_client: HomeAssistantClient | None = None,
) -> HATopologyService | None:
    """Get or create the topology service singleton.

    Args:
        ha_client: HA client (required for first call)

    Returns:
        The topology service instance, or None if no HA client available
    """
    global _topology_service

    if _topology_service is not None:
        return _topology_service

    if ha_client is None:
        # Try to get from global HA client
        try:
            from barnabeenet.api.routes.homeassistant import get_ha_client

            ha_client = await get_ha_client()
        except Exception:
            return None

    if ha_client is None:
        return None

    _topology_service = HATopologyService(ha_client)
    await _topology_service.refresh()
    return _topology_service


def reset_topology_service() -> None:
    """Reset the topology service singleton (for testing)."""
    global _topology_service
    _topology_service = None


__all__ = [
    "Floor",
    "HATopology",
    "HATopologyService",
    "get_topology_service",
    "reset_topology_service",
]
