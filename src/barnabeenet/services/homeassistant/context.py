"""Home Assistant Context Service - Lightweight entity metadata for intent classification.

This service provides just-in-time HA context to agents:
- Meta Agent: Entity names/domains for better intent classification (no states)
- Action Agent: Entity states only when needed for device control
- Interaction Agent: Entity info only when user asks about devices

Design principles:
- Cache entity names/domains (lightweight, changes infrequently)
- Don't cache entity states (heavy, changes frequently)
- Load states only when needed (just-in-time)
- Refresh entity metadata periodically (every 5 minutes)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


@dataclass
class EntityMetadata:
    """Lightweight entity metadata (name, domain, area) - no state."""

    entity_id: str
    domain: str
    friendly_name: str
    area_id: str | None = None
    device_id: str | None = None
    aliases: list[str] = field(default_factory=list)  # Alternative names


@dataclass
class HAContext:
    """Context data for agents - only what they need."""

    # For Meta Agent (intent classification)
    entity_names: list[str] = field(default_factory=list)  # All friendly names
    entity_domains: dict[str, list[str]] = field(
        default_factory=dict
    )  # domain -> [entity_ids]
    area_names: list[str] = field(default_factory=list)  # All area names

    # For Action Agent (device control) - loaded just-in-time
    entity_states: dict[str, Any] = field(default_factory=dict)  # entity_id -> state

    # For Interaction Agent (conversation) - loaded just-in-time
    entity_details: dict[str, EntityMetadata] = field(
        default_factory=dict
    )  # entity_id -> metadata


class HAContextService:
    """Lightweight service for providing HA context to agents.

    Caches entity metadata (names, domains, areas) but NOT states.
    States are loaded just-in-time when agents need them.
    """

    def __init__(self, ha_client: HomeAssistantClient | None = None):
        """Initialize the context service.

        Args:
            ha_client: Home Assistant client (optional, will be fetched if needed)
        """
        self._ha_client = ha_client
        self._entity_metadata: dict[str, EntityMetadata] = {}  # entity_id -> metadata
        self._area_names: list[str] = []
        self._last_refresh: datetime | None = None
        self._refresh_interval = timedelta(minutes=5)  # Refresh metadata every 5 min
        self._refresh_lock = asyncio.Lock()

    async def get_ha_client(self) -> HomeAssistantClient | None:
        """Get or fetch HA client."""
        if self._ha_client is not None:
            return self._ha_client

        try:
            from barnabeenet.api.routes.homeassistant import get_ha_client

            self._ha_client = await get_ha_client()
            return self._ha_client
        except Exception as e:
            logger.warning("Could not get HA client: %s", e)
            return None

    async def refresh_metadata(self, force: bool = False) -> int:
        """Refresh entity metadata (names, domains, areas) - lightweight.

        Does NOT load entity states - those are loaded just-in-time.

        Args:
            force: Force refresh even if recently refreshed

        Returns:
            Number of entities loaded
        """
        async with self._refresh_lock:
            # Check if refresh is needed
            if (
                not force
                and self._last_refresh
                and datetime.now() - self._last_refresh < self._refresh_interval
            ):
                return len(self._entity_metadata)

            ha_client = await self.get_ha_client()
            if not ha_client:
                return 0

            try:
                # Connect if needed
                if not ha_client.connected:
                    await ha_client.connect()

                # Get entity registry via WebSocket (lightweight, no states)
                entity_registry_data = await ha_client._ws_command("config/entity_registry/list")
                if not entity_registry_data:
                    logger.warning("No entity registry data from HA")
                    return 0

                # Get area registry
                area_registry_data = await ha_client._ws_command("config/area_registry/list")
                area_map: dict[str, str] = {}
                if area_registry_data:
                    for area in area_registry_data:
                        area_id = area.get("area_id")
                        name = area.get("name")
                        if area_id and name:
                            area_map[area_id] = name

                # Build metadata cache (no states!)
                self._entity_metadata.clear()
                for entry in entity_registry_data:
                    entity_id = entry.get("entity_id")
                    if not entity_id:
                        continue

                    domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
                    friendly_name = entry.get("name") or entity_id
                    area_id = entry.get("area_id")
                    device_id = entry.get("device_id")
                    aliases = entry.get("aliases", [])

                    self._entity_metadata[entity_id] = EntityMetadata(
                        entity_id=entity_id,
                        domain=domain,
                        friendly_name=friendly_name,
                        area_id=area_id,
                        device_id=device_id,
                        aliases=aliases,
                    )

                # Also populate HA client's EntityRegistry with metadata (for resolve_entity compatibility)
                # This allows existing code to work, but without loading states
                if ha_client and ha_client._entity_registry:
                    from barnabeenet.services.homeassistant.entities import Entity, EntityState

                    # Clear existing registry
                    ha_client._entity_registry.clear()

                    # Add entities with metadata only (no state)
                    for meta in self._entity_metadata.values():
                        entity = Entity(
                            entity_id=meta.entity_id,
                            domain=meta.domain,
                            friendly_name=meta.friendly_name,
                            area_id=meta.area_id,
                            device_id=meta.device_id,
                            state=EntityState(state="unknown"),  # Placeholder - state loaded just-in-time
                        )
                        ha_client._entity_registry.add(entity)

                # Build area names list
                self._area_names = list(area_map.values())

                self._last_refresh = datetime.now()
                logger.info(
                    "Refreshed HA metadata: %d entities, %d areas",
                    len(self._entity_metadata),
                    len(self._area_names),
                )

                return len(self._entity_metadata)

            except Exception as e:
                logger.error("Failed to refresh HA metadata: %s", e)
                return 0

    async def get_context_for_meta_agent(self) -> HAContext:
        """Get lightweight context for Meta Agent (intent classification).

        Returns only entity names, domains, and areas - no states.
        This helps Meta Agent understand if a request is about devices.
        """
        await self.refresh_metadata()

        # Build entity names list
        entity_names = [meta.friendly_name for meta in self._entity_metadata.values()]

        # Build domain -> entity_ids mapping
        entity_domains: dict[str, list[str]] = {}
        for entity_id, meta in self._entity_metadata.items():
            domain = meta.domain
            if domain not in entity_domains:
                entity_domains[domain] = []
            entity_domains[domain].append(entity_id)

        return HAContext(
            entity_names=entity_names,
            entity_domains=entity_domains,
            area_names=self._area_names,
        )

    async def get_context_for_action_agent(
        self, entity_ids: list[str] | None = None
    ) -> HAContext:
        """Get context for Action Agent (device control).

        Loads entity states just-in-time for the specified entities.
        If entity_ids is None, loads states for all entities (fallback).

        Args:
            entity_ids: Specific entities to load states for (None = all)

        Returns:
            HAContext with entity states loaded
        """
        await self.refresh_metadata()

        ha_client = await self.get_ha_client()
        if not ha_client:
            return HAContext()

        try:
            # Connect if needed
            if not ha_client.connected:
                await ha_client.connect()

            # Load states just-in-time for requested entities
            entity_states: dict[str, Any] = {}

            if entity_ids:
                # Load states for specific entities only (just-in-time)
                for entity_id in entity_ids:
                    try:
                        if not ha_client._client:
                            continue
                        response = await ha_client._client.get(f"/api/states/{entity_id}")
                        if response.status_code == 200:
                            state_data = response.json()
                            entity_states[entity_id] = {
                                "state": state_data.get("state"),
                                "attributes": state_data.get("attributes", {}),
                            }
                    except Exception as e:
                        logger.debug("Failed to load state for %s: %s", entity_id, e)
            # Note: We don't load all states as fallback - that defeats the purpose of just-in-time loading

            # Build entity details from metadata
            entity_details: dict[str, EntityMetadata] = {}
            if entity_ids:
                for entity_id in entity_ids:
                    if entity_id in self._entity_metadata:
                        entity_details[entity_id] = self._entity_metadata[entity_id]
            else:
                entity_details = self._entity_metadata.copy()

            return HAContext(
                entity_names=[meta.friendly_name for meta in self._entity_metadata.values()],
                entity_domains={
                    domain: [
                        eid
                        for eid, meta in self._entity_metadata.items()
                        if meta.domain == domain
                    ]
                    for domain in set(meta.domain for meta in self._entity_metadata.values())
                },
                area_names=self._area_names,
                entity_states=entity_states,
                entity_details=entity_details,
            )

        except Exception as e:
            logger.error("Failed to get context for Action Agent: %s", e)
            return HAContext()

    async def get_context_for_interaction_agent(
        self, query: str | None = None
    ) -> HAContext:
        """Get context for Interaction Agent (conversation).

        Loads entity info just-in-time based on the query.
        If query mentions entities, loads only those entities' details.

        Args:
            query: User query to extract entity mentions from

        Returns:
            HAContext with relevant entity details
        """
        await self.refresh_metadata()

        # Extract entity mentions from query (simple keyword matching)
        mentioned_entities: list[str] = []
        if query:
            query_lower = query.lower()
            for entity_id, meta in self._entity_metadata.items():
                # Check if friendly name or alias is mentioned
                if meta.friendly_name.lower() in query_lower:
                    mentioned_entities.append(entity_id)
                elif any(alias.lower() in query_lower for alias in meta.aliases):
                    mentioned_entities.append(entity_id)

        # Load states just-in-time for mentioned entities
        entity_states: dict[str, Any] = {}
        entity_details: dict[str, EntityMetadata] = {}

        if mentioned_entities:
            ha_client = await self.get_ha_client()
            if ha_client and ha_client.connected:
                for entity_id in mentioned_entities:
                    if entity_id in self._entity_metadata:
                        entity_details[entity_id] = self._entity_metadata[entity_id]

                        # Load state just-in-time
                        try:
                            if ha_client._client:
                                response = await ha_client._client.get(f"/api/states/{entity_id}")
                                if response.status_code == 200:
                                    state_data = response.json()
                                    entity_states[entity_id] = {
                                        "state": state_data.get("state"),
                                        "attributes": state_data.get("attributes", {}),
                                    }
                        except Exception:
                            pass

        return HAContext(
            entity_names=[meta.friendly_name for meta in self._entity_metadata.values()],
            entity_domains={
                domain: [
                    eid
                    for eid, meta in self._entity_metadata.items()
                    if meta.domain == domain
                ]
                for domain in set(meta.domain for meta in self._entity_metadata.values())
            },
            area_names=self._area_names,
            entity_states=entity_states,
            entity_details=entity_details,
        )

    def get_entity_metadata(self, entity_id: str) -> EntityMetadata | None:
        """Get metadata for a specific entity (from cache, no API call)."""
        return self._entity_metadata.get(entity_id)

    def find_entities_by_name(self, name: str, domain: str | None = None) -> list[EntityMetadata]:
        """Find entities by name (fuzzy matching, from cache)."""
        results: list[EntityMetadata] = []
        name_lower = name.lower()

        for meta in self._entity_metadata.values():
            if domain and meta.domain != domain:
                continue

            # Check friendly name
            if name_lower in meta.friendly_name.lower():
                results.append(meta)
            # Check aliases
            elif any(name_lower in alias.lower() for alias in meta.aliases):
                results.append(meta)

        return results

    async def resolve_entity_with_state(
        self, name: str, domain: str | None = None
    ) -> dict[str, Any] | None:
        """Resolve entity by name and load its state just-in-time.

        Returns entity metadata + current state, or None if not found.
        """
        await self.refresh_metadata()

        # Find matching entities
        matches = self.find_entities_by_name(name, domain)
        if not matches:
            return None

        # Use best match (first one)
        meta = matches[0]

        # Load state just-in-time
        ha_client = await self.get_ha_client()
        state_data = None
        if ha_client and ha_client._client:
            try:
                response = await ha_client._client.get(f"/api/states/{meta.entity_id}")
                if response.status_code == 200:
                    state_data = response.json()
            except Exception:
                pass

        return {
            "entity_id": meta.entity_id,
            "domain": meta.domain,
            "friendly_name": meta.friendly_name,
            "area_id": meta.area_id,
            "device_id": meta.device_id,
            "state": state_data.get("state") if state_data else None,
            "attributes": state_data.get("attributes", {}) if state_data else {},
        }


# =============================================================================
# Singleton Pattern
# =============================================================================

_context_service: HAContextService | None = None


async def get_ha_context_service(
    ha_client: HomeAssistantClient | None = None,
) -> HAContextService:
    """Get or create the HA context service singleton.

    Args:
        ha_client: Optional HA client (will be fetched if not provided)

    Returns:
        The context service instance
    """
    global _context_service

    if _context_service is None:
        _context_service = HAContextService(ha_client)
        # Do initial refresh in background
        asyncio.create_task(_context_service.refresh_metadata())

    elif ha_client and _context_service._ha_client is None:
        _context_service._ha_client = ha_client

    return _context_service


def reset_context_service() -> None:
    """Reset the context service singleton (for testing)."""
    global _context_service
    _context_service = None
