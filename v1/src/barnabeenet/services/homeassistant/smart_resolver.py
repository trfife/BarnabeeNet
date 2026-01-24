"""Smart entity resolver for natural language device commands.

Provides intelligent entity resolution including:
- Area/room matching with aliases (downstairs, upstairs, kids rooms)
- Floor-based entity groups
- Batch operations (all lights in X, all blinds)
- Device type synonyms
- Cross-domain matching (switches that control lights)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
    from barnabeenet.services.homeassistant.entities import Entity
    from barnabeenet.services.homeassistant.models import Area

logger = logging.getLogger(__name__)


# =============================================================================
# Area and Floor Aliases
# =============================================================================

# Common aliases for areas - maps user terms to area IDs
AREA_ALIASES: dict[str, list[str]] = {
    # Rooms
    "living_room": ["living room", "lounge", "family room", "front room"],
    "kitchen": ["kitchen", "kitchens"],
    "dining_room": ["dining room", "dining", "eat-in"],
    "office": ["office", "study", "home office", "work room"],
    "den": ["den", "tv room", "media room"],
    "entry": ["entry", "entryway", "foyer", "front door", "mudroom"],
    # Bathrooms
    "guest_bath": [
        "guest bath",
        "guest bathroom",
        "powder room",
        "half bath",
        "downstairs bathroom",
    ],
    "kids_bath": ["kids bath", "kids bathroom", "children's bathroom", "upstairs bathroom"],
    "parents_bath": ["parents bath", "master bath", "master bathroom", "main bath"],
    # Bedrooms
    "boys_room": ["boys room", "boy's room", "son's room", "boy bedroom"],
    "girls_room": ["girls room", "girl's room", "daughter's room", "girl bedroom"],
    "parents_room": ["parents room", "master bedroom", "master", "main bedroom"],
    "playroom": ["playroom", "play room", "game room", "toy room"],
    "landing": ["landing", "upstairs hall", "hallway", "upper hall"],
    # Outside
    "outside": ["outside", "outdoors", "yard", "patio", "deck"],
    "greenhouse": ["greenhouse", "green house", "plant room"],
}

# Floor aliases - maps user terms to floor IDs
FLOOR_ALIASES: dict[str, list[str]] = {
    "first_floor": [
        "downstairs",
        "first floor",
        "ground floor",
        "main floor",
        "main level",
        "lower level",
        "1st floor",
    ],
    "second_floor": [
        "upstairs",
        "second floor",
        "upper floor",
        "upper level",
        "2nd floor",
        "top floor",
    ],
    "outside": ["outside", "outdoor", "outdoors", "exterior"],
}

# Area groups - virtual collections of areas
AREA_GROUPS: dict[str, list[str]] = {
    "kids_rooms": ["boys_room", "girls_room", "playroom"],
    "bedrooms": ["boys_room", "girls_room", "parents_room", "playroom"],
    "bathrooms": ["guest_bath", "kids_bath", "parents_bath"],
    "common_areas": ["living_room", "kitchen", "dining_room", "den"],
}


# =============================================================================
# Device Type Synonyms
# =============================================================================

# Maps user terms to HA domains
DEVICE_TYPE_SYNONYMS: dict[str, str] = {
    # Lighting
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "bulb": "light",
    "bulbs": "light",
    # Switches (often control lights)
    "switch": "switch",
    "switches": "switch",
    "outlet": "switch",
    "outlets": "switch",
    "plug": "switch",
    "plugs": "switch",
    # Covers (blinds, shades, curtains)
    "blind": "cover",
    "blinds": "cover",
    "shade": "cover",
    "shades": "cover",
    "curtain": "cover",
    "curtains": "cover",
    "cover": "cover",
    "covers": "cover",
    "window": "cover",
    "windows": "cover",
    # Climate
    "thermostat": "climate",
    "ac": "climate",
    "heater": "climate",
    "hvac": "climate",
    # Fans
    "fan": "fan",
    "fans": "fan",
    # Locks
    "lock": "lock",
    "locks": "lock",
    "door": "lock",
    "doors": "lock",
    # Media
    "tv": "media_player",
    "television": "media_player",
    "speaker": "media_player",
    "speakers": "media_player",
}

# Domains that can substitute for each other (for "light" commands)
# Key is requested domain, value is list of alternative domains to search
DOMAIN_ALTERNATIVES: dict[str, list[str]] = {
    "light": ["switch", "input_boolean"],  # Switches often control lights
    "switch": ["light", "input_boolean"],
    "cover": ["switch"],  # Some covers have switch controls
}


# =============================================================================
# Batch Command Patterns
# =============================================================================

# Patterns that indicate a batch/group operation
BATCH_PATTERNS = [
    r"all\s+(?:the\s+)?(\w+)(?:\s+in\s+(?:the\s+)?(.+))?",  # "all lights in living room"
    r"every\s+(\w+)(?:\s+in\s+(?:the\s+)?(.+))?",  # "every light in kitchen"
    r"(\w+)\s+in\s+(?:the\s+)?(.+)",  # "lights in office" (implicit all)
]


@dataclass
class ResolvedTarget:
    """Result of entity resolution."""

    entities: list[Entity] = field(default_factory=list)
    area: Area | None = None
    domain: str | None = None
    is_batch: bool = False
    confidence: float = 0.0
    resolution_method: str = ""
    error: str | None = None


class SmartEntityResolver:
    """Intelligent entity resolver for natural language commands.

    Handles:
    - Single entity resolution with fuzzy matching
    - Area-based batch operations
    - Floor-based batch operations
    - Device type synonyms
    - Cross-domain matching
    """

    def __init__(self, ha_client: HomeAssistantClient) -> None:
        self._ha = ha_client
        self._area_lookup: dict[str, str] = {}  # alias -> area_id
        self._floor_lookup: dict[str, str] = {}  # alias -> floor_id
        self._init_lookups()

    def _init_lookups(self) -> None:
        """Initialize alias lookup tables."""
        # Build area alias lookup
        for area_id, aliases in AREA_ALIASES.items():
            for alias in aliases:
                self._area_lookup[alias.lower()] = area_id

        # Build floor alias lookup
        for floor_id, aliases in FLOOR_ALIASES.items():
            for alias in aliases:
                self._floor_lookup[alias.lower()] = floor_id

    def resolve_area(self, text: str) -> Area | None:
        """Resolve a text phrase to an area.

        Tries:
        1. Exact area name match
        2. Area alias match
        3. Fuzzy area name match
        """
        text_lower = text.lower().strip()

        # Check HA areas directly
        area = self._ha.find_area_by_name(text)
        if area:
            return area

        # Check aliases
        area_id = self._area_lookup.get(text_lower)
        if area_id:
            return self._ha.get_area(area_id)

        # Try partial matching - "girls room" in "girls_room"
        for area in self._ha.areas.values():
            if text_lower in area.name.lower() or text_lower in area.id.lower():
                return area
            # Handle possessive forms: "girl's" -> "girls"
            normalized = text_lower.replace("'s", "s").replace("'", "")
            if normalized in area.name.lower() or normalized in area.id.lower():
                return area

        return None

    def resolve_floor(self, text: str) -> str | None:
        """Resolve a text phrase to a floor ID."""
        text_lower = text.lower().strip()
        return self._floor_lookup.get(text_lower)

    def get_areas_on_floor(self, floor_id: str) -> list[Area]:
        """Get all areas on a specific floor."""
        return [a for a in self._ha.areas.values() if a.floor_id == floor_id]

    def get_area_group(self, group_name: str) -> list[str]:
        """Get area IDs for a named group."""
        return AREA_GROUPS.get(group_name.lower().replace(" ", "_"), [])

    def normalize_device_type(self, text: str) -> str | None:
        """Normalize a device type phrase to HA domain."""
        text_lower = text.lower().strip()
        return DEVICE_TYPE_SYNONYMS.get(text_lower)

    def get_alternative_domains(self, domain: str) -> list[str]:
        """Get alternative domains that might contain matching entities."""
        return DOMAIN_ALTERNATIVES.get(domain, [])

    def resolve(
        self,
        entity_name: str,
        domain: str | None = None,
        area_hint: str | None = None,
    ) -> ResolvedTarget:
        """Resolve a natural language entity reference.

        Args:
            entity_name: The entity reference (e.g., "office light", "all blinds in living room")
            domain: Optional domain hint
            area_hint: Optional area hint from context

        Returns:
            ResolvedTarget with matched entities
        """
        entity_name = entity_name.strip()

        # Check for batch patterns first
        batch_result = self._try_batch_resolution(entity_name, domain)
        if batch_result.entities:
            return batch_result

        # Try single entity resolution
        return self._resolve_single(entity_name, domain, area_hint)

    def _try_batch_resolution(
        self,
        text: str,
        domain: str | None = None,
    ) -> ResolvedTarget:
        """Try to resolve as a batch operation.

        Handles patterns like:
        - "all lights in living room"
        - "blinds in the kitchen"
        - "lights downstairs"
        - "all the blinds"
        """
        text_lower = text.lower()

        # Pattern: "all (device_type) [in/on] (location)"
        # e.g., "all lights in living room", "all blinds downstairs"
        all_match = re.match(
            r"^all\s+(?:the\s+)?(\w+)(?:\s+(?:in|on)\s+(?:the\s+)?(.+))?$",
            text_lower,
        )
        if all_match:
            device_type = all_match.group(1)
            location = all_match.group(2) if all_match.group(2) else None
            return self._resolve_batch(device_type, location, domain)

        # Pattern: "(device_type) in/on (location)" - implicit batch
        # e.g., "lights in the kitchen", "blinds in office"
        location_match = re.match(
            r"^(?:the\s+)?(\w+)\s+(?:in|on)\s+(?:the\s+)?(.+)$",
            text_lower,
        )
        if location_match:
            device_type = location_match.group(1)
            location = location_match.group(2)
            # Only treat as batch if device_type is plural or matches a type
            if device_type.endswith("s") or device_type in DEVICE_TYPE_SYNONYMS:
                return self._resolve_batch(device_type, location, domain)

        # Pattern: "(device_type) (floor_alias)" - floor-based batch
        # e.g., "lights downstairs", "blinds upstairs"
        for word in text_lower.split():
            if word in self._floor_lookup:
                # Found a floor reference
                remaining = text_lower.replace(word, "").strip()
                device_type = remaining.strip()
                if device_type in DEVICE_TYPE_SYNONYMS:
                    return self._resolve_batch(device_type, word, domain)

        return ResolvedTarget()  # Empty result = not a batch

    def _resolve_batch(
        self,
        device_type: str,
        location: str | None,
        domain_hint: str | None,
    ) -> ResolvedTarget:
        """Resolve a batch operation targeting multiple entities."""
        result = ResolvedTarget(is_batch=True, resolution_method="batch")

        # Determine the target domain
        domain = domain_hint or self.normalize_device_type(device_type)
        if not domain:
            # Try singular form
            singular = device_type.rstrip("s")
            domain = self.normalize_device_type(singular)

        if not domain:
            result.error = f"Unknown device type: {device_type}"
            return result

        result.domain = domain

        # Determine target areas
        target_area_ids: list[str] = []

        if location:
            # Check if it's a floor reference
            floor_id = self.resolve_floor(location)
            if floor_id:
                areas = self.get_areas_on_floor(floor_id)
                target_area_ids = [a.id for a in areas]
                logger.debug("Resolved floor '%s' to areas: %s", location, target_area_ids)
            else:
                # Check if it's an area group
                group_areas = self.get_area_group(location)
                if group_areas:
                    target_area_ids = group_areas
                    logger.debug("Resolved group '%s' to areas: %s", location, target_area_ids)
                else:
                    # Try single area
                    area = self.resolve_area(location)
                    if area:
                        target_area_ids = [area.id]
                        result.area = area
                        logger.debug("Resolved area: %s", area.id)
                    else:
                        # Last try: look in entity names
                        logger.debug(
                            "Could not resolve location '%s', searching entity names", location
                        )

        # Get entities
        all_domains = [domain] + self.get_alternative_domains(domain)

        # Build list of search terms for entity name matching
        # When searching by floor, we need the actual area names, not "downstairs"
        name_search_terms: list[str] = []
        if target_area_ids:
            # Get actual area names for searching entity names/IDs
            for area_id in target_area_ids:
                name_search_terms.append(area_id)  # e.g., "living_room"
                # Also add space version
                name_search_terms.append(area_id.replace("_", " "))  # e.g., "living room"

        # Helper to check if entity matches device type (used for alternative domains)
        def entity_matches_device_type(
            entity: Entity, device_type: str, target_domain: str
        ) -> bool:
            """Check if entity likely represents the requested device type.

            For primary domains (light, cover, etc.), we trust the domain.
            For alternative domains (switch instead of light), we require
            the device type word to appear in the entity name.
            """
            if target_domain == domain:
                # Primary domain - always match
                return True
            # Alternative domain - check if device type appears in name
            # e.g., "switch.office_switch_light" contains "light"
            name_lower = entity.friendly_name.lower()
            id_lower = entity.entity_id.lower()
            type_lower = device_type.lower()
            # Also check singular form
            singular = type_lower.rstrip("s")
            return (
                type_lower in name_lower
                or type_lower in id_lower
                or singular in name_lower
                or singular in id_lower
            )

        def score_entity_for_device_type(
            entity: Entity, device_type: str, target_domain: str
        ) -> float:
            """Score how well an entity matches the requested device type.

            Higher scores indicate better matches:
            - 1.0: Device type word appears in entity name (strongest match)
            - 0.5: Entity is in the primary domain but type word not in name
            - 0.0: Alternative domain without type word in name (won't be included)
            """
            name_lower = entity.friendly_name.lower()
            id_lower = entity.entity_id.lower()
            type_lower = device_type.lower()
            singular = type_lower.rstrip("s")

            # Check if device type appears in name
            has_type_in_name = (
                type_lower in name_lower
                or type_lower in id_lower
                or singular in name_lower
                or singular in id_lower
            )

            if has_type_in_name:
                # Best match - device type word is in the name
                return 1.0
            elif target_domain == domain:
                # Primary domain but no type word in name
                return 0.5
            else:
                # Alternative domain without type word - shouldn't happen
                # (filtered out by entity_matches_device_type)
                return 0.0

        # Helper to check if a term appears as a whole word or phrase in text
        def term_matches_in_text(term: str, text: str) -> bool:
            """Check if term appears as a whole word/phrase in text.

            Prevents false positives like "house" matching "greenhouse".
            Uses word boundaries: start/end of string, spaces, underscores, hyphens.
            """
            import re

            term_lower = term.lower()
            text_lower = text.lower()
            # Escape any regex special characters in the term
            escaped_term = re.escape(term_lower)
            # Match term with word boundaries (space, underscore, hyphen, or string boundary)
            pattern = rf"(?:^|[\s_\-])({escaped_term})(?:$|[\s_\-])"
            return bool(re.search(pattern, text_lower))

        for dom in all_domains:
            # Track entities found for THIS domain via area_id
            found_for_domain_by_area_id = False

            if target_area_ids:
                # First try: Get entities by area_id
                for area_id in target_area_ids:
                    entities = self._ha.entities.get_by_area(area_id)
                    for entity in entities:
                        if entity.domain == dom:
                            if entity_matches_device_type(entity, device_type, dom):
                                if entity not in result.entities:
                                    result.entities.append(entity)
                                    found_for_domain_by_area_id = True

                # If no entities found by area_id FOR THIS DOMAIN, fall back to name matching
                # Many entities have area in their name but area_id not set
                if not found_for_domain_by_area_id and name_search_terms:
                    entities = self._ha.entities.get_by_domain(dom)
                    for entity in entities:
                        # Skip if doesn't match device type (for alternative domains)
                        if not entity_matches_device_type(entity, device_type, dom):
                            continue
                        name_lower = entity.friendly_name.lower()
                        id_lower = entity.entity_id.lower()
                        # Check if any area name appears in name or id as a whole word
                        for term in name_search_terms:
                            if term_matches_in_text(term, name_lower) or term_matches_in_text(
                                term, id_lower
                            ):
                                if entity not in result.entities:
                                    result.entities.append(entity)
                                break  # Found a match, no need to check other terms
            else:
                # No specific area - get all entities of domain
                # But check if location appears in entity name
                entities = self._ha.entities.get_by_domain(dom)
                if location:
                    # Filter by location in name
                    location_lower = location.lower()
                    entities = [
                        e
                        for e in entities
                        if location_lower in e.friendly_name.lower()
                        or location_lower in e.entity_id.lower()
                    ]
                for entity in entities:
                    # For alternative domains, check device type match
                    if not entity_matches_device_type(entity, device_type, dom):
                        continue
                    if entity not in result.entities:
                        result.entities.append(entity)

        if result.entities:
            # Sort entities by how well they match the device type
            # Entities with the device type word in their name rank higher
            # This ensures switch.office_switch_light beats light.office_door_status_light
            # when looking for "office light"
            result.entities.sort(
                key=lambda e: score_entity_for_device_type(
                    e, device_type, e.entity_id.split(".")[0]
                ),
                reverse=True,
            )
            result.confidence = 0.8
            logger.info(
                "Batch resolved %d %s entities%s (best: %s)",
                len(result.entities),
                domain,
                f" in {location}" if location else "",
                result.entities[0].entity_id if result.entities else "none",
            )
        else:
            result.error = f"No {device_type} found" + (f" in {location}" if location else "")

        return result

    def _resolve_single(
        self,
        entity_name: str,
        domain: str | None,
        area_hint: str | None,
    ) -> ResolvedTarget:
        """Resolve a single entity reference."""
        result = ResolvedTarget(resolution_method="single")

        # Collect candidates from all relevant domains
        candidates: list[tuple[float, Entity]] = []

        domains_to_search = [domain] if domain else list(DEVICE_TYPE_SYNONYMS.values())
        domains_to_search = list(set(domains_to_search))  # Dedupe

        # Add alternative domains
        if domain:
            domains_to_search.extend(self.get_alternative_domains(domain))

        for dom in domains_to_search:
            if not dom:
                continue
            entity = self._ha.resolve_entity(entity_name, dom)
            if entity:
                score = entity.match_score(entity_name)
                # Boost score if area matches hint
                if area_hint and entity.area_id:
                    area = self._ha.get_area(entity.area_id)
                    if area and area_hint.lower() in area.name.lower():
                        score += 0.1
                candidates.append((score, entity))

        if not candidates:
            # Try without domain restriction
            entity = self._ha.resolve_entity(entity_name, None)
            if entity:
                candidates.append((entity.match_score(entity_name), entity))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_entity = candidates[0][1]
            result.entities = [best_entity]
            result.confidence = candidates[0][0]
            result.domain = best_entity.domain
            logger.debug(
                "Single entity resolved: %s (score=%.2f)",
                best_entity.entity_id,
                result.confidence,
            )
        else:
            result.error = f"Could not find entity: {entity_name}"

        return result

    def resolve_multiple(
        self,
        targets: list[str],
        domain: str | None = None,
    ) -> list[ResolvedTarget]:
        """Resolve multiple entity targets.

        Handles comma-separated lists like:
        "living room, kitchen, and office blinds"
        """
        results = []
        for target in targets:
            target = target.strip()
            if target:
                results.append(self.resolve(target, domain))
        return results
