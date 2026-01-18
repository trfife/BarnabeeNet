"""Entity registry and state models for Home Assistant integration.

Provides:
- Entity model for device representation
- EntityState for current state and attributes
- EntityRegistry for entity lookup by name/domain/area
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EntityState:
    """Current state of a Home Assistant entity."""

    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None

    @property
    def is_on(self) -> bool:
        """Check if entity is in 'on' state."""
        return self.state.lower() == "on"

    @property
    def is_off(self) -> bool:
        """Check if entity is in 'off' state."""
        return self.state.lower() == "off"

    @property
    def is_unavailable(self) -> bool:
        """Check if entity is unavailable."""
        return self.state.lower() in ("unavailable", "unknown")


@dataclass
class Entity:
    """Representation of a Home Assistant entity."""

    entity_id: str
    domain: str
    friendly_name: str
    device_class: str | None = None
    area_id: str | None = None
    device_id: str | None = None
    state: EntityState | None = None

    @property
    def name(self) -> str:
        """Get the best display name for the entity."""
        return self.friendly_name or self.entity_id

    def matches_name(self, query: str) -> bool:
        """Check if the entity matches a name query.

        Supports:
        - Exact entity_id match
        - Exact friendly_name match (case-insensitive)
        - Partial friendly_name match
        - Word boundary matching

        Args:
            query: The search query

        Returns:
            True if entity matches the query.
        """
        query_lower = query.lower().strip()

        # Exact entity_id match
        if query_lower == self.entity_id.lower():
            return True

        # Exact friendly_name match
        if query_lower == self.friendly_name.lower():
            return True

        # Partial match in friendly_name (as whole words)
        name_lower = self.friendly_name.lower()
        if query_lower in name_lower:
            # Check if it's a word boundary match
            pattern = rf"\b{re.escape(query_lower)}\b"
            if re.search(pattern, name_lower):
                return True
            # Also accept if query is a significant portion of the name
            if len(query_lower) >= 3 and len(query_lower) >= len(name_lower) * 0.4:
                return True

        return False

    def match_score(self, query: str) -> float:
        """Calculate a match score for ranking results.

        Higher score = better match.

        Args:
            query: The search query

        Returns:
            Match score from 0.0 to 1.0
        """
        query_lower = query.lower().strip()
        name_lower = self.friendly_name.lower()
        entity_id_lower = self.entity_id.lower()

        # Exact match = perfect score
        if query_lower == name_lower or query_lower == entity_id_lower:
            return 1.0

        # Name starts with query = high score
        if name_lower.startswith(query_lower):
            return 0.9

        # Query is a whole word in name = good score
        pattern = rf"\b{re.escape(query_lower)}\b"
        if re.search(pattern, name_lower):
            return 0.8

        # Query appears in name = moderate score
        if query_lower in name_lower:
            return 0.5 + (len(query_lower) / len(name_lower)) * 0.3

        # Check if all query words appear in name (allows words in between)
        # "office light" matches "Office Switch Light" because both words present
        query_words = query_lower.split()
        if len(query_words) > 1:
            name_words = name_lower.split()
            name_words_set = set(name_words)
            matching_words = sum(1 for w in query_words if w in name_words_set)
            if matching_words == len(query_words):
                # All words match - score based on name conciseness
                # Prefer "Office Switch Light" (3 words) over "Office Door Status Light" (4 words)
                # when matching "office light" (2 words)
                base_score = 0.7
                # Bonus for shorter names (fewer extra words)
                name_word_count = len(name_words)
                extra_words = name_word_count - len(query_words)
                # Penalize extra words: 0 extra = +0.15, 1 extra = +0.1, 2+ extra = +0.05
                conciseness_bonus = max(0.05, 0.15 - extra_words * 0.05)
                return min(0.85, base_score + conciseness_bonus)
            elif matching_words >= len(query_words) - 1:
                # Most words match - moderate score
                return 0.4 + (matching_words / len(query_words)) * 0.2

        # Check entity_id for matches (e.g., switch.office_switch_light)
        entity_name_part = entity_id_lower.split(".")[-1] if "." in entity_id_lower else entity_id_lower
        if query_lower in entity_name_part:
            return 0.4 + (len(query_lower) / len(entity_name_part)) * 0.2

        # Check if query words appear in entity_id
        if len(query_words) > 1:
            entity_words = set(entity_name_part.replace("_", " ").split())
            matching_words = sum(1 for w in query_words if w in entity_words)
            if matching_words == len(query_words):
                return 0.6
            elif matching_words > 0:
                return 0.3 + (matching_words / len(query_words)) * 0.2

        return 0.0


class EntityRegistry:
    """Registry for managing and searching Home Assistant entities.

    Provides efficient lookup by:
    - entity_id
    - friendly name (fuzzy matching)
    - domain
    - area/room
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._by_domain: dict[str, list[str]] = {}
        self._by_area: dict[str, list[str]] = {}

    def __len__(self) -> int:
        return len(self._entities)

    def add(self, entity: Entity) -> None:
        """Add an entity to the registry."""
        self._entities[entity.entity_id] = entity

        # Index by domain
        if entity.domain not in self._by_domain:
            self._by_domain[entity.domain] = []
        if entity.entity_id not in self._by_domain[entity.domain]:
            self._by_domain[entity.domain].append(entity.entity_id)

        # Index by area
        if entity.area_id:
            if entity.area_id not in self._by_area:
                self._by_area[entity.area_id] = []
            if entity.entity_id not in self._by_area[entity.area_id]:
                self._by_area[entity.area_id].append(entity.entity_id)

    def remove(self, entity_id: str) -> bool:
        """Remove an entity from the registry.

        Returns:
            True if entity was removed, False if not found.
        """
        if entity_id not in self._entities:
            return False

        entity = self._entities.pop(entity_id)

        # Remove from domain index
        if entity.domain in self._by_domain:
            self._by_domain[entity.domain] = [
                eid for eid in self._by_domain[entity.domain] if eid != entity_id
            ]

        # Remove from area index
        if entity.area_id and entity.area_id in self._by_area:
            self._by_area[entity.area_id] = [
                eid for eid in self._by_area[entity.area_id] if eid != entity_id
            ]

        return True

    def clear(self) -> None:
        """Clear all entities from the registry."""
        self._entities.clear()
        self._by_domain.clear()
        self._by_area.clear()

    def get(self, entity_id: str) -> Entity | None:
        """Get entity by exact entity_id."""
        return self._entities.get(entity_id)

    def all(self) -> Iterator[Entity]:
        """Iterate over all entities."""
        return iter(self._entities.values())

    def get_by_domain(self, domain: str) -> list[Entity]:
        """Get all entities in a domain."""
        entity_ids = self._by_domain.get(domain, [])
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]

    def get_by_area(self, area_id: str) -> list[Entity]:
        """Get all entities in an area."""
        entity_ids = self._by_area.get(area_id, [])
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]

    def find_by_name(self, name: str, domain: str | None = None) -> Entity | None:
        """Find best matching entity by name.

        Args:
            name: Friendly name or entity_id to search for
            domain: Optional domain to filter search

        Returns:
            Best matching Entity or None if no match found.
        """
        # First try exact entity_id match
        if name in self._entities:
            return self._entities[name]

        # Search for best match
        candidates = self.get_by_domain(domain) if domain else list(self._entities.values())

        best_match: Entity | None = None
        best_score = 0.0

        for entity in candidates:
            score = entity.match_score(name)
            if score > best_score:
                best_score = score
                best_match = entity

        # Require minimum score to avoid false positives
        if best_score >= 0.5:
            return best_match

        return None

    def search(
        self,
        query: str,
        domain: str | None = None,
        area: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Search entities by query.

        Args:
            query: Search query
            domain: Optional domain filter
            area: Optional area filter
            limit: Maximum results to return

        Returns:
            List of matching entities, sorted by relevance.
        """
        # Start with all entities or domain-filtered
        if domain:
            candidates = self.get_by_domain(domain)
        elif area:
            candidates = self.get_by_area(area)
        else:
            candidates = list(self._entities.values())

        # Apply area filter if domain was used
        if domain and area:
            candidates = [e for e in candidates if e.area_id == area]

        # Score and sort
        scored: list[tuple[float, Entity]] = []
        for entity in candidates:
            score = entity.match_score(query)
            if score > 0.0:
                scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in scored[:limit]]

    @property
    def domains(self) -> list[str]:
        """Get list of all domains in registry."""
        return list(self._by_domain.keys())

    @property
    def areas(self) -> list[str]:
        """Get list of all areas in registry."""
        return list(self._by_area.keys())
