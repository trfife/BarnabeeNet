"""Entity Query Service - Natural language queries about Home Assistant entity states.

Supports various query types:
- Single entity state: "is the office light on?"
- Area aggregation: "how many lights are on downstairs?"
- Domain listing: "which lights are on?"
- Attribute queries: "what batteries need changing?"
- Count queries: "how many devices do I have outside?"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
    from barnabeenet.services.homeassistant.topology import HATopologyService

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of entity queries."""

    SINGLE = "single"  # "is the office light on?"
    AREA_LIST = "area_list"  # "what lights are on downstairs?"
    DOMAIN_LIST = "domain_list"  # "which lights are on?"
    ATTRIBUTE = "attribute"  # "what batteries need changing?"
    COUNT = "count"  # "how many lights are in the kitchen?"
    UNKNOWN = "unknown"


# Map plural/common terms to HA domains
DOMAIN_MAPPING: dict[str, list[str]] = {
    "light": ["light"],
    "lights": ["light"],
    "lamp": ["light"],
    "lamps": ["light"],
    "switch": ["switch"],
    "switches": ["switch"],
    "fan": ["fan"],
    "fans": ["fan"],
    "door": ["lock", "binary_sensor"],
    "doors": ["lock", "binary_sensor"],
    "lock": ["lock"],
    "locks": ["lock"],
    "window": ["binary_sensor", "cover"],
    "windows": ["binary_sensor", "cover"],
    "sensor": ["sensor", "binary_sensor"],
    "sensors": ["sensor", "binary_sensor"],
    "cover": ["cover"],
    "covers": ["cover"],
    "blind": ["cover"],
    "blinds": ["cover"],
    "shade": ["cover"],
    "shades": ["cover"],
    "curtain": ["cover"],
    "curtains": ["cover"],
    "device": ["light", "switch", "fan", "lock", "cover", "climate", "media_player"],
    "devices": ["light", "switch", "fan", "lock", "cover", "climate", "media_player"],
    "climate": ["climate"],
    "thermostat": ["climate"],
    "media": ["media_player"],
    "speaker": ["media_player"],
    "tv": ["media_player"],
    "camera": ["camera"],
    "cameras": ["camera"],
    "battery": ["sensor"],
    "batteries": ["sensor"],
}

# Map state query terms to entity states
STATE_MAPPING: dict[str, list[str]] = {
    "on": ["on"],
    "off": ["off"],
    "open": ["open", "unlocked", "on"],
    "closed": ["closed", "locked", "off"],
    "locked": ["locked"],
    "unlocked": ["unlocked"],
}

# Floor/location terms
FLOOR_TERMS = {"downstairs", "upstairs", "first floor", "second floor", "ground floor", "basement", "outside", "outdoor", "outdoors"}


@dataclass
class EntityQuery:
    """Parsed entity query."""

    query_type: QueryType
    domain: str | None = None  # "light", "switch", etc.
    domains: list[str] | None = None  # For multi-domain queries like "devices"
    area: str | None = None  # "living room", "kitchen"
    floor: str | None = None  # "downstairs", "upstairs"
    state_filter: str | None = None  # "on", "off", "open", etc.
    attribute_filter: str | None = None  # "low_battery", "unavailable"
    entity_name: str | None = None  # For single entity queries
    raw_text: str = ""


# =============================================================================
# Query Patterns
# =============================================================================

# Single entity state: "is the office light on?"
SINGLE_ENTITY_PATTERNS = [
    re.compile(r"^is (?:the |my )?(.+?) (on|off|open|closed|locked|unlocked)\??$", re.IGNORECASE),
]

# Area/domain listing: "what lights are on downstairs?"
AREA_LIST_PATTERNS = [
    re.compile(r"^what (\w+) (?:are|is) (on|off|open|closed|locked|unlocked)(?: (?:in |on )?(?:the )?(.+))?$", re.IGNORECASE),
    re.compile(r"^which (\w+) (?:are|is) (on|off|open|closed|locked|unlocked)(?: (?:in |on )?(?:the )?(.+))?$", re.IGNORECASE),
    re.compile(r"^(?:list|show)(?: all)?(?: the)? (\w+) (?:that are )?(on|off|open|closed)(?: (?:in |on )?(?:the )?(.+))?$", re.IGNORECASE),
]

# Domain existence check: "are any lights on?"
DOMAIN_CHECK_PATTERNS = [
    re.compile(r"^(?:are|is) (?:there )?any (\w+) (on|off|open|closed|locked|unlocked)\??(?: (?:in |on )?(?:the )?(.+))?$", re.IGNORECASE),
]

# Count queries: "how many lights are on downstairs?"
COUNT_PATTERNS = [
    re.compile(r"^how many (\w+) (?:are )?(on|off|open|closed)\??(?: (?:in |on )?(?:the )?(.+))?$", re.IGNORECASE),
    re.compile(r"^how many (\w+) (?:do i have |are )?(?:in |on )?(?:the )?(.+)\??$", re.IGNORECASE),
]

# Attribute queries: "what batteries need changing?"
ATTRIBUTE_PATTERNS = [
    re.compile(r"^what (?:batteries|devices?) need (?:changing|replacing|charging)", re.IGNORECASE),
    re.compile(r"^(?:which|what) (?:devices?|sensors?|batteries?) (?:are |have )?(?:low|dead|dying)", re.IGNORECASE),
    re.compile(r"^(?:which|what) (?:devices?|entities?) (?:are )?unavailable", re.IGNORECASE),
]


def parse_entity_query(text: str) -> EntityQuery | None:
    """Parse natural language into an EntityQuery.

    Args:
        text: User's natural language query

    Returns:
        EntityQuery if recognized, None otherwise
    """
    text = text.strip()
    text_lower = text.lower()

    # Check attribute queries first (most specific)
    for pattern in ATTRIBUTE_PATTERNS:
        if pattern.match(text_lower):
            attr_filter = "low_battery"
            if "unavailable" in text_lower:
                attr_filter = "unavailable"
            return EntityQuery(
                query_type=QueryType.ATTRIBUTE,
                attribute_filter=attr_filter,
                raw_text=text,
            )

    # Check single entity state patterns
    for pattern in SINGLE_ENTITY_PATTERNS:
        match = pattern.match(text)
        if match:
            entity_name = match.group(1).strip()
            state = match.group(2).lower()

            # Check if entity_name contains a floor/area term
            area = None
            floor = None
            for term in FLOOR_TERMS:
                if term in entity_name.lower():
                    floor = term
                    entity_name = entity_name.lower().replace(term, "").strip()
                    break

            # Check if it's actually a domain query ("is any light on?")
            entity_lower = entity_name.lower()
            if entity_lower in DOMAIN_MAPPING:
                return EntityQuery(
                    query_type=QueryType.DOMAIN_LIST,
                    domains=DOMAIN_MAPPING[entity_lower],
                    state_filter=state,
                    floor=floor,
                    raw_text=text,
                )

            return EntityQuery(
                query_type=QueryType.SINGLE,
                entity_name=entity_name,
                state_filter=state,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check domain check patterns ("are any lights on?")
    for pattern in DOMAIN_CHECK_PATTERNS:
        match = pattern.match(text)
        if match:
            domain_term = match.group(1).lower()
            state = match.group(2).lower()
            location = match.group(3).strip() if match.lastindex and match.lastindex >= 3 and match.group(3) else None

            domains = DOMAIN_MAPPING.get(domain_term, [domain_term])
            area, floor = _parse_location(location)

            return EntityQuery(
                query_type=QueryType.DOMAIN_LIST,
                domains=domains,
                state_filter=state,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check area/domain list patterns
    for pattern in AREA_LIST_PATTERNS:
        match = pattern.match(text)
        if match:
            domain_term = match.group(1).lower()
            state = match.group(2).lower()
            location = match.group(3).strip() if match.lastindex and match.lastindex >= 3 and match.group(3) else None

            domains = DOMAIN_MAPPING.get(domain_term, [domain_term])
            area, floor = _parse_location(location)

            return EntityQuery(
                query_type=QueryType.AREA_LIST if (area or floor) else QueryType.DOMAIN_LIST,
                domains=domains,
                state_filter=state,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check count patterns
    for pattern in COUNT_PATTERNS:
        match = pattern.match(text)
        if match:
            domain_term = match.group(1).lower()
            # Group 2 might be state or location depending on pattern
            group2 = match.group(2).lower() if match.lastindex and match.lastindex >= 2 and match.group(2) else None
            group3 = match.group(3).strip() if match.lastindex and match.lastindex >= 3 and match.group(3) else None

            domains = DOMAIN_MAPPING.get(domain_term, [domain_term])

            # Determine if group2 is a state or location
            state_filter = None
            location = None
            if group2 in STATE_MAPPING:
                state_filter = group2
                location = group3
            else:
                location = group2

            area, floor = _parse_location(location)

            return EntityQuery(
                query_type=QueryType.COUNT,
                domains=domains,
                state_filter=state_filter,
                area=area,
                floor=floor,
                raw_text=text,
            )

    return None


def _parse_location(location: str | None) -> tuple[str | None, str | None]:
    """Parse a location string into area and floor components.

    Returns:
        Tuple of (area, floor) - one will be set, other None
    """
    if not location:
        return None, None

    location_lower = location.lower().strip()

    # Check if it's a floor term
    for term in FLOOR_TERMS:
        if term in location_lower or location_lower == term:
            return None, term

    # Otherwise treat as area
    return location, None


async def execute_entity_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute an entity query and return a natural language response.

    Args:
        query: Parsed EntityQuery
        ha_client: Home Assistant client
        topology_service: Optional topology service for floor resolution

    Returns:
        Natural language response string
    """
    try:
        if query.query_type == QueryType.SINGLE:
            return await _execute_single_query(query, ha_client)
        elif query.query_type == QueryType.DOMAIN_LIST:
            return await _execute_domain_list_query(query, ha_client, topology_service)
        elif query.query_type == QueryType.AREA_LIST:
            return await _execute_area_list_query(query, ha_client, topology_service)
        elif query.query_type == QueryType.COUNT:
            return await _execute_count_query(query, ha_client, topology_service)
        elif query.query_type == QueryType.ATTRIBUTE:
            return await _execute_attribute_query(query, ha_client)
        else:
            return "I'm not sure how to answer that question about your devices."
    except Exception as e:
        logger.error("Error executing entity query: %s", e, exc_info=True)
        return "I had trouble checking your devices. Please try again."


async def _execute_single_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a single entity state query."""
    if not query.entity_name:
        return "I'm not sure which device you're asking about."

    # Find the entity
    entity = ha_client._entity_registry.find_by_name(query.entity_name)
    if not entity:
        return f"I couldn't find a device called '{query.entity_name}'."

    # Get current state
    state = await ha_client.get_state(entity.entity_id)
    if not state:
        return f"I couldn't get the current state of {entity.friendly_name}."

    # Format response based on query state
    current_state = state.state.lower()
    friendly_name = entity.friendly_name

    if query.state_filter:
        expected_states = STATE_MAPPING.get(query.state_filter, [query.state_filter])
        is_match = current_state in expected_states

        if query.state_filter in ("on", "off"):
            if is_match:
                return f"Yes, {friendly_name} is {current_state}."
            else:
                return f"No, {friendly_name} is {current_state}."
        elif query.state_filter in ("open", "closed"):
            if is_match:
                return f"Yes, {friendly_name} is {current_state}."
            else:
                return f"No, {friendly_name} is {current_state}."
        elif query.state_filter in ("locked", "unlocked"):
            if is_match:
                return f"Yes, {friendly_name} is {current_state}."
            else:
                return f"No, {friendly_name} is {current_state}."

    return f"{friendly_name} is {current_state}."


async def _execute_domain_list_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute a domain listing query (e.g., "which lights are on?")."""
    domains = query.domains or []
    if not domains:
        return "I'm not sure which type of device you're asking about."

    # Get entities matching the domains
    entities = []
    for domain in domains:
        entities.extend(ha_client._entity_registry.get_by_domain(domain))

    # Filter by floor if specified
    if query.floor and topology_service:
        area_ids = topology_service.resolve_floor(query.floor)
        if area_ids:
            entities = [e for e in entities if e.area_id in area_ids]

    # Filter by area if specified
    if query.area:
        area = ha_client.find_area_by_name(query.area)
        if area:
            entities = [e for e in entities if e.area_id == area.id]

    if not entities:
        location_str = _format_location(query.area, query.floor)
        domain_str = _format_domain_plural(domains[0]) if domains else "devices"
        return f"I couldn't find any {domain_str}{location_str}."

    # Get current states and filter
    matching_entities = []
    for entity in entities:
        state = await ha_client.get_state(entity.entity_id)
        if state and query.state_filter:
            expected_states = STATE_MAPPING.get(query.state_filter, [query.state_filter])
            if state.state.lower() in expected_states:
                matching_entities.append((entity, state))

    location_str = _format_location(query.area, query.floor)
    domain_str = _format_domain_plural(domains[0]) if domains else "devices"

    if not matching_entities:
        if query.state_filter:
            return f"No {domain_str} are {query.state_filter}{location_str}."
        return f"I couldn't find any {domain_str}{location_str}."

    # Format response
    count = len(matching_entities)
    if count == 1:
        entity, state = matching_entities[0]
        return f"Yes, {entity.friendly_name} is {state.state}{location_str}."

    names = [e.friendly_name for e, _ in matching_entities[:5]]
    names_str = ", ".join(names)
    if count > 5:
        names_str += f" and {count - 5} more"

    return f"There are {count} {domain_str} {query.state_filter}{location_str}: {names_str}."


async def _execute_area_list_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute an area-based list query."""
    # This is essentially the same as domain_list with location filter
    return await _execute_domain_list_query(query, ha_client, topology_service)


async def _execute_count_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute a count query (e.g., "how many lights are on downstairs?")."""
    domains = query.domains or []
    if not domains:
        return "I'm not sure which type of device you're asking about."

    # Get entities matching the domains
    entities = []
    for domain in domains:
        entities.extend(ha_client._entity_registry.get_by_domain(domain))

    # Filter by floor if specified
    if query.floor and topology_service:
        area_ids = topology_service.resolve_floor(query.floor)
        if area_ids:
            entities = [e for e in entities if e.area_id in area_ids]

    # Filter by area if specified
    if query.area:
        area = ha_client.find_area_by_name(query.area)
        if area:
            entities = [e for e in entities if e.area_id == area.id]

    location_str = _format_location(query.area, query.floor)
    domain_str = _format_domain_plural(domains[0]) if domains else "devices"

    if not entities:
        return f"You don't have any {domain_str}{location_str}."

    # If no state filter, just count total
    if not query.state_filter:
        count = len(entities)
        return f"You have {count} {domain_str}{location_str}."

    # Get current states and filter
    matching_count = 0
    for entity in entities:
        state = await ha_client.get_state(entity.entity_id)
        if state and query.state_filter:
            expected_states = STATE_MAPPING.get(query.state_filter, [query.state_filter])
            if state.state.lower() in expected_states:
                matching_count += 1

    if matching_count == 0:
        return f"No {domain_str} are {query.state_filter}{location_str}."
    elif matching_count == 1:
        return f"1 {_format_domain_singular(domains[0])} is {query.state_filter}{location_str}."
    else:
        return f"{matching_count} {domain_str} are {query.state_filter}{location_str}."


async def _execute_attribute_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute an attribute query (e.g., "what batteries need changing?")."""
    if query.attribute_filter == "low_battery":
        return await _get_low_battery_devices(ha_client)
    elif query.attribute_filter == "unavailable":
        return await _get_unavailable_devices(ha_client)
    else:
        return "I'm not sure what device attribute you're asking about."


async def _get_low_battery_devices(ha_client: HomeAssistantClient, threshold: int = 20) -> str:
    """Get devices with low battery."""
    low_battery = []

    # Check all sensor entities for battery level
    sensors = ha_client._entity_registry.get_by_domain("sensor")
    for entity in sensors:
        # Look for battery sensors (device_class: battery or entity_id contains battery)
        if entity.device_class == "battery" or "battery" in entity.entity_id.lower():
            state = await ha_client.get_state(entity.entity_id)
            if state:
                try:
                    level = float(state.state)
                    if level < threshold:
                        low_battery.append((entity.friendly_name, int(level)))
                except (ValueError, TypeError):
                    pass

    # Also check attributes of other entities for battery_level
    for entity in ha_client._entity_registry:
        if entity.state and entity.state.attributes:
            battery_level = entity.state.attributes.get("battery_level")
            if battery_level is not None:
                try:
                    level = float(battery_level)
                    if level < threshold:
                        # Avoid duplicates
                        name = entity.friendly_name
                        if not any(n == name for n, _ in low_battery):
                            low_battery.append((name, int(level)))
                except (ValueError, TypeError):
                    pass

    if not low_battery:
        return "All your devices have good battery levels."

    # Sort by battery level (lowest first)
    low_battery.sort(key=lambda x: x[1])

    if len(low_battery) == 1:
        name, level = low_battery[0]
        return f"1 device has low battery: {name} ({level}%)."

    details = [f"{name} ({level}%)" for name, level in low_battery[:5]]
    details_str = ", ".join(details)
    if len(low_battery) > 5:
        details_str += f" and {len(low_battery) - 5} more"

    return f"{len(low_battery)} devices have low battery: {details_str}."


async def _get_unavailable_devices(ha_client: HomeAssistantClient) -> str:
    """Get unavailable devices."""
    unavailable = []

    for entity in ha_client._entity_registry:
        state = await ha_client.get_state(entity.entity_id)
        if state and state.is_unavailable:
            unavailable.append(entity.friendly_name)

    if not unavailable:
        return "All your devices are available."

    if len(unavailable) == 1:
        return f"1 device is unavailable: {unavailable[0]}."

    details_str = ", ".join(unavailable[:5])
    if len(unavailable) > 5:
        details_str += f" and {len(unavailable) - 5} more"

    return f"{len(unavailable)} devices are unavailable: {details_str}."


def _format_location(area: str | None, floor: str | None) -> str:
    """Format location string for responses."""
    if floor:
        return f" {floor}"
    if area:
        return f" in {area}"
    return ""


def _format_domain_plural(domain: str) -> str:
    """Get plural form of domain name."""
    plurals = {
        "light": "lights",
        "switch": "switches",
        "fan": "fans",
        "lock": "locks",
        "cover": "covers",
        "sensor": "sensors",
        "binary_sensor": "sensors",
        "climate": "climate devices",
        "media_player": "media players",
        "camera": "cameras",
    }
    return plurals.get(domain, f"{domain}s")


def _format_domain_singular(domain: str) -> str:
    """Get singular form of domain name."""
    singulars = {
        "light": "light",
        "switch": "switch",
        "fan": "fan",
        "lock": "lock",
        "cover": "cover",
        "sensor": "sensor",
        "binary_sensor": "sensor",
        "climate": "climate device",
        "media_player": "media player",
        "camera": "camera",
    }
    return singulars.get(domain, domain)
