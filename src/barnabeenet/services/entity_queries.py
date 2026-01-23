"""Entity Query Service - Natural language queries about Home Assistant entity states.

Supports various query types:
- Single entity state: "is the office light on?"
- Area aggregation: "how many lights are on downstairs?"
- Domain listing: "which lights are on?"
- Attribute queries: "what batteries need changing?"
- Count queries: "how many devices do I have outside?"
- Sensor values: "what's the temperature in the living room?"
- Climate queries: "what's the thermostat set to?"
- Security queries: "are all the doors locked?"
- Presence queries: "is anyone home?"
- Media queries: "what's playing on the TV?"
- Cover queries: "are the blinds open?"
- Last changed: "when was the front door last opened?"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
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
    SENSOR_VALUE = "sensor_value"  # "what's the temperature?"
    CLIMATE = "climate"  # "what's the thermostat set to?"
    SECURITY = "security"  # "are all the doors locked?"
    PRESENCE = "presence"  # "is anyone home?"
    MEDIA = "media"  # "what's playing?"
    COVER = "cover"  # "are the blinds open?"
    LAST_CHANGED = "last_changed"  # "when was X last opened?"
    BRIGHTNESS = "brightness"  # "how bright is the light?"
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
    "garage": ["cover"],
    "garage door": ["cover"],
    "device": ["light", "switch", "fan", "lock", "cover", "climate", "media_player"],
    "devices": ["light", "switch", "fan", "lock", "cover", "climate", "media_player"],
    "climate": ["climate"],
    "thermostat": ["climate"],
    "thermostats": ["climate"],
    "ac": ["climate"],
    "air conditioning": ["climate"],
    "heating": ["climate"],
    "hvac": ["climate"],
    "media": ["media_player"],
    "media player": ["media_player"],
    "speaker": ["media_player"],
    "speakers": ["media_player"],
    "tv": ["media_player"],
    "television": ["media_player"],
    "camera": ["camera"],
    "cameras": ["camera"],
    "battery": ["sensor"],
    "batteries": ["sensor"],
    "motion": ["binary_sensor"],
    "motion sensor": ["binary_sensor"],
    "person": ["person"],
    "people": ["person"],
    "vacuum": ["vacuum"],
    "robot": ["vacuum"],
    "alarm": ["alarm_control_panel"],
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

# Sensor value queries: "what's the temperature in the living room?"
SENSOR_VALUE_PATTERNS = [
    re.compile(r"^what(?:'s| is) the (temperature|humidity|power|energy|pressure|illuminance|lux)(?: (?:in |of )?(?:the )?(.+))?\??$", re.IGNORECASE),
    re.compile(r"^(?:what's|what is) the (.+?) (temperature|humidity)\??$", re.IGNORECASE),
    re.compile(r"^how (?:hot|cold|warm|humid) is (?:it )?(in )?(?:the )?(.+)?\??$", re.IGNORECASE),
    re.compile(r"^(?:what's|what is) the current (temperature|humidity|power usage|energy)\??$", re.IGNORECASE),
]

# Climate/thermostat queries: "what's the thermostat set to?"
CLIMATE_PATTERNS = [
    re.compile(r"^what(?:'s| is) the (?:thermostat|ac|heating|climate|hvac)(?: (?:set )?(?:to|at))?\??$", re.IGNORECASE),
    re.compile(r"^what(?:'s| is) the (.+?) (?:thermostat|ac|climate)(?: (?:set )?(?:to|at))?\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the (?:heating|cooling|ac|air conditioning) (on|off|running)\??$", re.IGNORECASE),
    re.compile(r"^what mode is the (?:thermostat|ac|hvac|climate)(?: (?:set )?(?:to|on))?\??$", re.IGNORECASE),
    re.compile(r"^what(?:'s| is) the (?:target |set )?temperature\??$", re.IGNORECASE),
]

# Security queries: "are all the doors locked?"
SECURITY_PATTERNS = [
    re.compile(r"^(?:are|is) (?:all )?(?:the )?doors? (?:all )?locked\??$", re.IGNORECASE),
    re.compile(r"^(?:are|is) (?:all )?(?:the )?windows? (?:all )?closed\??$", re.IGNORECASE),
    re.compile(r"^(?:are|is) (?:any|the) doors? (?:unlocked|open)\??$", re.IGNORECASE),
    re.compile(r"^(?:are|is) (?:any|the) windows? open\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the (?:house|home) (?:secure|locked|safe)\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the (?:alarm|security)(?: system)? (?:armed|on|set)\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the garage(?: door)? (?:open|closed)\??$", re.IGNORECASE),
    re.compile(r"^security status\??$", re.IGNORECASE),
]

# Presence queries: "is anyone home?"
PRESENCE_PATTERNS = [
    re.compile(r"^(?:is|are) (?:anyone|anybody|someone|somebody) (?:home|here|in)\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) (?:everyone|everybody) (?:home|here|out|away|gone)\??$", re.IGNORECASE),
    re.compile(r"^who(?:'s| is) (?:home|here|away|out)\??$", re.IGNORECASE),
    re.compile(r"^(?:is|where is|where's) (\w+) (?:home|here|away|at)?\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the (?:house|home) (?:empty|occupied)\??$", re.IGNORECASE),
    re.compile(r"^how many (?:people|persons?) (?:are )?(?:home|here)\??$", re.IGNORECASE),
]

# Media queries: "what's playing on the TV?"
MEDIA_PATTERNS = [
    re.compile(r"^what(?:'s| is) (?:playing|on)(?: (?:on |the )?(?:the )?(.+))?\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) (?:any )?(?:music|something|anything) playing\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) the (?:tv|television|speaker|music|media)(?: player)? (?:on|playing)\??$", re.IGNORECASE),
    re.compile(r"^what(?:'s| is) the volume(?: (?:on |of |at )?(?:the )?(.+))?\??$", re.IGNORECASE),
    re.compile(r"^(?:is|are) (?:the )?(.+?) (?:playing|on|paused)\??$", re.IGNORECASE),
]

# Cover/blind queries: "are the blinds open?"
COVER_PATTERNS = [
    re.compile(r"^(?:are|is) (?:the )?(?:blinds?|shades?|curtains?|covers?) (?:open|closed|up|down)(?: (?:in |on )?(?:the )?(.+))?\??$", re.IGNORECASE),
    re.compile(r"^what(?:'s| is) the (?:position|status) of (?:the )?(?:blinds?|shades?|curtains?|covers?)(?: (?:in |on )?(?:the )?(.+))?\??$", re.IGNORECASE),
    re.compile(r"^(?:are|is) the (.+?) (?:blinds?|shades?|curtains?) (?:open|closed|up|down)\??$", re.IGNORECASE),
]

# Last changed queries: "when was the front door last opened?"
LAST_CHANGED_PATTERNS = [
    re.compile(r"^when (?:was|did) (?:the )?(.+?) (?:last )?(?:opened|closed|changed|turned on|turned off|unlocked|locked)\??$", re.IGNORECASE),
    re.compile(r"^how long (?:has|have) (?:the )?(.+?) been (on|off|open|closed|locked|unlocked)\??$", re.IGNORECASE),
    re.compile(r"^when did (?:the )?(.+?) (?:turn |go )?(on|off|open|close)\??$", re.IGNORECASE),
    re.compile(r"^(?:what|when) was the last (?:time |)?(?:the )?(.+?) (?:was )?(opened|closed|used|activated)\??$", re.IGNORECASE),
]

# Brightness queries: "how bright is the light?"
BRIGHTNESS_PATTERNS = [
    re.compile(r"^how bright (?:is|are) (?:the )?(.+)\??$", re.IGNORECASE),
    re.compile(r"^what(?:'s| is) the brightness(?: of)? (?:the )?(.+)\??$", re.IGNORECASE),
    re.compile(r"^(?:what's|what is) (?:the )?(.+?) (?:brightness|level|dim level)\??$", re.IGNORECASE),
    re.compile(r"^(?:at )?what (?:level|percentage|percent) (?:is|are) (?:the )?(.+?)(?: set| at| on)?\??$", re.IGNORECASE),
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

    # Check sensor value patterns
    for pattern in SENSOR_VALUE_PATTERNS:
        match = pattern.match(text)
        if match:
            sensor_type = match.group(1).lower() if match.group(1) else None
            location = match.group(2).strip() if match.lastindex and match.lastindex >= 2 and match.group(2) else None
            area, floor = _parse_location(location)
            return EntityQuery(
                query_type=QueryType.SENSOR_VALUE,
                attribute_filter=sensor_type,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check climate patterns
    for pattern in CLIMATE_PATTERNS:
        match = pattern.match(text)
        if match:
            location = match.group(1).strip() if match.lastindex and match.lastindex >= 1 and match.group(1) else None
            area, floor = _parse_location(location)
            return EntityQuery(
                query_type=QueryType.CLIMATE,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check security patterns
    for pattern in SECURITY_PATTERNS:
        if pattern.match(text):
            return EntityQuery(
                query_type=QueryType.SECURITY,
                raw_text=text,
            )

    # Check presence patterns
    for pattern in PRESENCE_PATTERNS:
        match = pattern.match(text)
        if match:
            person_name = match.group(1) if match.lastindex and match.lastindex >= 1 and match.group(1) else None
            return EntityQuery(
                query_type=QueryType.PRESENCE,
                entity_name=person_name,
                raw_text=text,
            )

    # Check media patterns
    for pattern in MEDIA_PATTERNS:
        match = pattern.match(text)
        if match:
            device_name = match.group(1).strip() if match.lastindex and match.lastindex >= 1 and match.group(1) else None
            return EntityQuery(
                query_type=QueryType.MEDIA,
                entity_name=device_name,
                raw_text=text,
            )

    # Check cover patterns
    for pattern in COVER_PATTERNS:
        match = pattern.match(text)
        if match:
            location = match.group(1).strip() if match.lastindex and match.lastindex >= 1 and match.group(1) else None
            area, floor = _parse_location(location)
            return EntityQuery(
                query_type=QueryType.COVER,
                area=area,
                floor=floor,
                raw_text=text,
            )

    # Check last changed patterns
    for pattern in LAST_CHANGED_PATTERNS:
        match = pattern.match(text)
        if match:
            entity_name = match.group(1).strip() if match.group(1) else None
            return EntityQuery(
                query_type=QueryType.LAST_CHANGED,
                entity_name=entity_name,
                raw_text=text,
            )

    # Check brightness patterns
    for pattern in BRIGHTNESS_PATTERNS:
        match = pattern.match(text)
        if match:
            entity_name = match.group(1).strip() if match.group(1) else None
            return EntityQuery(
                query_type=QueryType.BRIGHTNESS,
                entity_name=entity_name,
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
        elif query.query_type == QueryType.SENSOR_VALUE:
            return await _execute_sensor_value_query(query, ha_client, topology_service)
        elif query.query_type == QueryType.CLIMATE:
            return await _execute_climate_query(query, ha_client)
        elif query.query_type == QueryType.SECURITY:
            return await _execute_security_query(query, ha_client)
        elif query.query_type == QueryType.PRESENCE:
            return await _execute_presence_query(query, ha_client)
        elif query.query_type == QueryType.MEDIA:
            return await _execute_media_query(query, ha_client)
        elif query.query_type == QueryType.COVER:
            return await _execute_cover_query(query, ha_client, topology_service)
        elif query.query_type == QueryType.LAST_CHANGED:
            return await _execute_last_changed_query(query, ha_client)
        elif query.query_type == QueryType.BRIGHTNESS:
            return await _execute_brightness_query(query, ha_client)
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
    for entity in ha_client._entity_registry.all():
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

    for entity in ha_client._entity_registry.all():
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


# =============================================================================
# New Query Executors
# =============================================================================

async def _execute_sensor_value_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute a sensor value query (temperature, humidity, etc.)."""
    sensor_type = query.attribute_filter or "temperature"

    # Map sensor types to device classes
    type_to_device_class = {
        "temperature": "temperature",
        "humidity": "humidity",
        "power": "power",
        "energy": "energy",
        "pressure": "pressure",
        "illuminance": "illuminance",
        "lux": "illuminance",
    }
    device_class = type_to_device_class.get(sensor_type, sensor_type)

    # Find matching sensors
    sensors = ha_client._entity_registry.get_by_domain("sensor")
    matching = []

    for entity in sensors:
        if entity.device_class == device_class:
            # Filter by area if specified
            if query.area:
                area = ha_client.find_area_by_name(query.area)
                if area and entity.area_id != area.id:
                    continue
            if query.floor and topology_service:
                area_ids = topology_service.resolve_floor(query.floor)
                if area_ids and entity.area_id not in area_ids:
                    continue

            state = await ha_client.get_state(entity.entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                unit = state.attributes.get("unit_of_measurement", "")
                matching.append((entity.friendly_name, state.state, unit))

    if not matching:
        location_str = _format_location(query.area, query.floor)
        return f"I couldn't find any {sensor_type} sensors{location_str}."

    if len(matching) == 1:
        name, value, unit = matching[0]
        return f"The {sensor_type} at {name} is {value}{unit}."

    # Multiple sensors - list them
    responses = [f"{name}: {value}{unit}" for name, value, unit in matching[:5]]
    if len(matching) > 5:
        responses.append(f"and {len(matching) - 5} more")
    return f"{sensor_type.title()} readings: " + ", ".join(responses) + "."


async def _execute_climate_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a climate/thermostat query."""
    climate_entities = ha_client._entity_registry.get_by_domain("climate")

    if not climate_entities:
        return "I couldn't find any thermostats or climate devices."

    # Filter by area if specified
    if query.area:
        area = ha_client.find_area_by_name(query.area)
        if area:
            climate_entities = [e for e in climate_entities if e.area_id == area.id]

    if not climate_entities:
        return f"I couldn't find any thermostats in {query.area}."

    results = []
    for entity in climate_entities[:3]:  # Limit to 3
        state = await ha_client.get_state(entity.entity_id)
        if state:
            current_temp = state.attributes.get("current_temperature")
            target_temp = state.attributes.get("temperature")
            hvac_mode = state.state
            unit = state.attributes.get("temperature_unit", "°")

            parts = [entity.friendly_name]
            if current_temp:
                parts.append(f"currently {current_temp}{unit}")
            if target_temp:
                parts.append(f"set to {target_temp}{unit}")
            if hvac_mode and hvac_mode not in ("unknown", "unavailable"):
                parts.append(f"mode: {hvac_mode}")

            results.append(" - ".join(parts[1:]) if len(parts) > 1 else f"{entity.friendly_name}: {hvac_mode}")

    if len(results) == 1:
        entity = climate_entities[0]
        state = await ha_client.get_state(entity.entity_id)
        if state:
            current_temp = state.attributes.get("current_temperature")
            target_temp = state.attributes.get("temperature")
            hvac_mode = state.state
            unit = state.attributes.get("temperature_unit", "°")

            if target_temp and current_temp:
                return f"{entity.friendly_name} is set to {target_temp}{unit} (currently {current_temp}{unit}, mode: {hvac_mode})."
            elif target_temp:
                return f"{entity.friendly_name} is set to {target_temp}{unit} ({hvac_mode})."
            else:
                return f"{entity.friendly_name} is in {hvac_mode} mode."

    return "Climate status: " + "; ".join(results)


async def _execute_security_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a security status query (doors, locks, windows)."""
    text_lower = query.raw_text.lower()

    # Determine what to check based on the query
    if "door" in text_lower and "lock" in text_lower:
        return await _check_locks(ha_client)
    elif "door" in text_lower:
        return await _check_doors(ha_client)
    elif "window" in text_lower:
        return await _check_windows(ha_client)
    elif "garage" in text_lower:
        return await _check_garage(ha_client)
    elif "alarm" in text_lower or "security" in text_lower:
        return await _check_alarm(ha_client)
    elif "secure" in text_lower or "safe" in text_lower:
        # Full security check
        locks = await _check_locks(ha_client)
        doors = await _check_doors(ha_client)
        windows = await _check_windows(ha_client)
        return f"{locks} {doors} {windows}"
    else:
        return await _check_locks(ha_client)


async def _check_locks(ha_client: HomeAssistantClient) -> str:
    """Check status of all locks."""
    locks = ha_client._entity_registry.get_by_domain("lock")
    if not locks:
        return "No locks found."

    unlocked = []
    for entity in locks:
        state = await ha_client.get_state(entity.entity_id)
        if state and state.state == "unlocked":
            unlocked.append(entity.friendly_name)

    if not unlocked:
        return f"All {len(locks)} door(s) are locked."
    elif len(unlocked) == 1:
        return f"{unlocked[0]} is unlocked."
    else:
        return f"{len(unlocked)} doors are unlocked: {', '.join(unlocked)}."


async def _check_doors(ha_client: HomeAssistantClient) -> str:
    """Check status of door sensors."""
    sensors = ha_client._entity_registry.get_by_domain("binary_sensor")
    door_sensors = [e for e in sensors if e.device_class == "door" or "door" in e.entity_id.lower()]

    if not door_sensors:
        return "No door sensors found."

    open_doors = []
    for entity in door_sensors:
        state = await ha_client.get_state(entity.entity_id)
        if state and state.state == "on":  # on = open for door sensors
            open_doors.append(entity.friendly_name)

    if not open_doors:
        return f"All {len(door_sensors)} doors are closed."
    elif len(open_doors) == 1:
        return f"{open_doors[0]} is open."
    else:
        return f"{len(open_doors)} doors are open: {', '.join(open_doors)}."


async def _check_windows(ha_client: HomeAssistantClient) -> str:
    """Check status of window sensors."""
    sensors = ha_client._entity_registry.get_by_domain("binary_sensor")
    window_sensors = [e for e in sensors if e.device_class == "window" or "window" in e.entity_id.lower()]

    if not window_sensors:
        return "No window sensors found."

    open_windows = []
    for entity in window_sensors:
        state = await ha_client.get_state(entity.entity_id)
        if state and state.state == "on":  # on = open for window sensors
            open_windows.append(entity.friendly_name)

    if not open_windows:
        return f"All {len(window_sensors)} windows are closed."
    elif len(open_windows) == 1:
        return f"{open_windows[0]} is open."
    else:
        return f"{len(open_windows)} windows are open: {', '.join(open_windows)}."


async def _check_garage(ha_client: HomeAssistantClient) -> str:
    """Check garage door status."""
    covers = ha_client._entity_registry.get_by_domain("cover")
    garage_doors = [e for e in covers if "garage" in e.entity_id.lower() or "garage" in e.friendly_name.lower()]

    if not garage_doors:
        return "No garage doors found."

    results = []
    for entity in garage_doors:
        state = await ha_client.get_state(entity.entity_id)
        if state:
            results.append(f"{entity.friendly_name} is {state.state}.")

    return " ".join(results)


async def _check_alarm(ha_client: HomeAssistantClient) -> str:
    """Check alarm/security panel status."""
    alarms = ha_client._entity_registry.get_by_domain("alarm_control_panel")

    if not alarms:
        return "No alarm system found."

    results = []
    for entity in alarms:
        state = await ha_client.get_state(entity.entity_id)
        if state:
            mode = state.state.replace("_", " ")
            results.append(f"{entity.friendly_name} is {mode}.")

    return " ".join(results)


async def _execute_presence_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a presence query (who's home)."""
    persons = ha_client._entity_registry.get_by_domain("person")

    if not persons:
        # Fallback to device_tracker
        trackers = ha_client._entity_registry.get_by_domain("device_tracker")
        if not trackers:
            return "No presence tracking configured."
        persons = trackers

    home_people = []
    away_people = []

    for entity in persons:
        state = await ha_client.get_state(entity.entity_id)
        if state:
            # Extract just the name from the entity
            name = entity.friendly_name
            if state.state.lower() in ("home", "on"):
                home_people.append(name)
            elif state.state.lower() in ("away", "not_home", "off"):
                away_people.append(name)

    # Check for specific person query
    if query.entity_name:
        person_name = query.entity_name.lower()
        for entity in persons:
            if person_name in entity.friendly_name.lower():
                state = await ha_client.get_state(entity.entity_id)
                if state:
                    if state.state.lower() in ("home", "on"):
                        return f"Yes, {entity.friendly_name} is home."
                    else:
                        return f"No, {entity.friendly_name} is {state.state}."
        return f"I don't have presence information for {query.entity_name}."

    # General presence query
    if "everyone" in query.raw_text.lower():
        if not away_people:
            return f"Yes, everyone is home ({len(home_people)} people)."
        else:
            return f"No, {', '.join(away_people)} {'is' if len(away_people) == 1 else 'are'} away."

    if not home_people:
        return "Nobody is home."
    elif len(home_people) == 1:
        return f"{home_people[0]} is home."
    else:
        return f"{len(home_people)} people are home: {', '.join(home_people)}."


async def _execute_media_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a media status query."""
    media_players = ha_client._entity_registry.get_by_domain("media_player")

    if not media_players:
        return "No media players found."

    # If specific device requested
    if query.entity_name:
        for entity in media_players:
            if query.entity_name.lower() in entity.friendly_name.lower():
                state = await ha_client.get_state(entity.entity_id)
                if state:
                    return _format_media_status(entity.friendly_name, state)
        return f"I couldn't find a media player called '{query.entity_name}'."

    # Check what's playing on all media players
    playing = []
    for entity in media_players:
        state = await ha_client.get_state(entity.entity_id)
        if state and state.state == "playing":
            playing.append((entity.friendly_name, state))

    if not playing:
        return "Nothing is currently playing."

    responses = []
    for name, state in playing[:3]:
        media_title = state.attributes.get("media_title", "")
        media_artist = state.attributes.get("media_artist", "")
        if media_title and media_artist:
            responses.append(f"{name}: {media_artist} - {media_title}")
        elif media_title:
            responses.append(f"{name}: {media_title}")
        else:
            responses.append(f"{name} is playing")

    return "; ".join(responses) + "."


def _format_media_status(name: str, state: Any) -> str:
    """Format media player status."""
    if state.state in ("off", "unavailable", "unknown"):
        return f"{name} is {state.state}."

    media_title = state.attributes.get("media_title", "")
    media_artist = state.attributes.get("media_artist", "")
    volume = state.attributes.get("volume_level")

    parts = [f"{name} is {state.state}"]
    if media_title and media_artist:
        parts.append(f"playing {media_artist} - {media_title}")
    elif media_title:
        parts.append(f"playing {media_title}")
    if volume is not None:
        parts.append(f"volume at {int(volume * 100)}%")

    return ", ".join(parts) + "."


async def _execute_cover_query(
    query: EntityQuery,
    ha_client: HomeAssistantClient,
    topology_service: HATopologyService | None = None,
) -> str:
    """Execute a cover/blind status query."""
    covers = ha_client._entity_registry.get_by_domain("cover")

    if not covers:
        return "No blinds or covers found."

    # Filter by area if specified
    if query.area:
        area = ha_client.find_area_by_name(query.area)
        if area:
            covers = [e for e in covers if e.area_id == area.id]
    if query.floor and topology_service:
        area_ids = topology_service.resolve_floor(query.floor)
        if area_ids:
            covers = [e for e in covers if e.area_id in area_ids]

    if not covers:
        location_str = _format_location(query.area, query.floor)
        return f"No blinds or covers found{location_str}."

    open_covers = []
    closed_covers = []

    for entity in covers:
        state = await ha_client.get_state(entity.entity_id)
        if state:
            position = state.attributes.get("current_position")
            if state.state == "open" or (position and position > 0):
                open_covers.append((entity.friendly_name, position))
            else:
                closed_covers.append(entity.friendly_name)

    location_str = _format_location(query.area, query.floor)

    if not open_covers and not closed_covers:
        return f"I couldn't get the status of the covers{location_str}."

    if not open_covers:
        return f"All {len(closed_covers)} covers are closed{location_str}."
    elif not closed_covers:
        if len(open_covers) == 1:
            name, pos = open_covers[0]
            pos_str = f" ({pos}%)" if pos else ""
            return f"{name} is open{pos_str}."
        return f"All {len(open_covers)} covers are open{location_str}."
    else:
        open_names = [f"{name} ({pos}%)" if pos else name for name, pos in open_covers]
        return f"{len(open_covers)} covers are open{location_str}: {', '.join(open_names[:3])}."


async def _execute_last_changed_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a last changed query."""
    if not query.entity_name:
        return "Which device do you want to know about?"

    entity = ha_client._entity_registry.find_by_name(query.entity_name)
    if not entity:
        return f"I couldn't find a device called '{query.entity_name}'."

    state = await ha_client.get_state(entity.entity_id)
    if not state or not state.last_changed:
        return f"I don't have change history for {entity.friendly_name}."

    try:
        # Parse the ISO timestamp
        last_changed = datetime.fromisoformat(state.last_changed.replace("Z", "+00:00"))
        now = datetime.now(last_changed.tzinfo)
        diff = now - last_changed

        # Format the time difference
        if diff.total_seconds() < 60:
            time_ago = "just now"
        elif diff.total_seconds() < 3600:
            mins = int(diff.total_seconds() / 60)
            time_ago = f"{mins} minute{'s' if mins != 1 else ''} ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(diff.total_seconds() / 86400)
            time_ago = f"{days} day{'s' if days != 1 else ''} ago"

        return f"{entity.friendly_name} was last changed {time_ago} (currently {state.state})."
    except Exception:
        return f"{entity.friendly_name} is currently {state.state}."


async def _execute_brightness_query(query: EntityQuery, ha_client: HomeAssistantClient) -> str:
    """Execute a brightness level query."""
    if not query.entity_name:
        return "Which light do you want to know the brightness of?"

    entity = ha_client._entity_registry.find_by_name(query.entity_name)
    if not entity:
        return f"I couldn't find a light called '{query.entity_name}'."

    state = await ha_client.get_state(entity.entity_id)
    if not state:
        return f"I couldn't get the status of {entity.friendly_name}."

    if state.state == "off":
        return f"{entity.friendly_name} is off."

    brightness = state.attributes.get("brightness")
    if brightness is not None:
        # Convert from 0-255 to percentage
        percent = int((brightness / 255) * 100)
        return f"{entity.friendly_name} is at {percent}% brightness."

    return f"{entity.friendly_name} is {state.state}."
