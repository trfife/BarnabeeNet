# BarnabeeNet Prompt Engineering Specification

**Document Version:** 1.0  
**Last Updated:** January 16, 2026  
**Author:** Thom Fife  
**Purpose:** Complete prompt system specification for BarnabeeNet multi-agent architecture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Directory Structure](#2-directory-structure)
3. [Template Variable System](#3-template-variable-system)
4. [Anti-Hallucination Patterns](#4-anti-hallucination-patterns)
5. [Agent Prompt Templates](#5-agent-prompt-templates)
6. [Submodule Organization](#6-submodule-organization)
7. [Configuration Reference](#7-configuration-reference)
8. [Testing & Validation](#8-testing--validation)

---

## 1. Executive Summary

### 1.1 Design Philosophy

BarnabeeNet's prompt engineering system is directly inspired by SkyrimNet's proven patterns for creating "alive-feeling" AI agents. The core principles are:

| Principle | SkyrimNet Origin | BarnabeeNet Application |
|-----------|------------------|------------------------|
| **Minimal Prompts** | "Keep prompts clean and minimal" | LLMs already know how to assist; guide, don't micromanage |
| **Variable Injection** | Decorators like `decnpc(UUID)` | Jinja2 filters for live Home Assistant state |
| **First-Person Memory** | Per-NPC perspective memories | Barnabee's perspective on family patterns |
| **Modular Composition** | Numbered submodule includes | Reusable context blocks assembled per-agent |
| **Tone Guidance** | "Guide tone, don't dictate exact dialogue" | Personality hints, not scripts |
| **Trust the System** | "Trust the memory system for history" | Let retrieval handle context, not prompt bloat |

### 1.2 Agent-to-Prompt Mapping

| Agent | Primary Prompt | Model Tier | Temperature |
|-------|----------------|------------|-------------|
| Meta Agent | `meta/classify.j2` | Fast (DeepSeek) | 0.3 |
| Instant Agent | N/A (pattern-matched) | None | N/A |
| Action Agent | `action/execute.j2` | Fast (DeepSeek) | 0.5 |
| Interaction Agent | `interaction/converse.j2` | Quality (Claude/GPT-4) | 0.7 |
| Memory Agent | `memory/generate.j2` | Summarization (GPT-4o-mini) | 0.3 |
| Proactive Agent | `proactive/observe.j2` | Quality (Claude/GPT-4) | 0.7 |

---

## 2. Directory Structure

### 2.1 Prompt File Organization

Following SkyrimNet's numbered submodule pattern for deterministic ordering:

```
custom_components/barnabeenet/
└── prompts/
    ├── __init__.py                     # PromptEngine class
    ├── loader.py                       # Template loading utilities
    │
    ├── agents/                         # Per-agent main prompts
    │   ├── meta/
    │   │   └── classify.j2             # Intent classification
    │   ├── action/
    │   │   ├── execute.j2              # Device control
    │   │   └── confirm.j2              # Action confirmation
    │   ├── interaction/
    │   │   ├── converse.j2             # Main conversation
    │   │   ├── clarify.j2              # Disambiguation
    │   │   └── apologize.j2            # Error recovery
    │   ├── memory/
    │   │   ├── generate.j2             # Event → memory
    │   │   ├── query.j2                # Memory search
    │   │   └── consolidate.j2          # Batch summarization
    │   └── proactive/
    │       ├── observe.j2              # Ambient observations
    │       ├── suggest.j2              # Proactive suggestions
    │       └── alert.j2                # Important notifications
    │
    ├── context/                        # Reusable context submodules (numbered)
    │   ├── 0001_barnabee_identity.j2   # Core identity/persona
    │   ├── 0002_family_context.j2      # Family member info
    │   ├── 0003_home_state.j2          # Current device states
    │   ├── 0004_time_context.j2        # Temporal awareness
    │   ├── 0005_weather_context.j2     # External conditions
    │   ├── 0006_calendar_context.j2    # Upcoming events
    │   └── 0007_recent_events.j2       # Event history
    │
    ├── system/                         # System instruction blocks
    │   ├── 0001_base_instructions.j2   # Core behavioral rules
    │   ├── 0002_safety_rules.j2        # Safety constraints
    │   ├── 0003_output_format.j2       # Response formatting
    │   └── 0004_tool_usage.j2          # Home Assistant service calls
    │
    └── overrides/                      # Per-user/room customizations
        ├── users/
        │   ├── thom.j2                 # Dad-specific context
        │   ├── penelope.j2             # Child-specific constraints
        │   └── guest.j2                # Guest restrictions
        └── rooms/
            ├── kids_room.j2            # Child-safe responses
            └── office.j2               # Work-focused context
```

### 2.2 File Naming Conventions

| Pattern | Purpose | Example |
|---------|---------|---------|
| `NNNN_name.j2` | Numbered for include order | `0001_barnabee_identity.j2` |
| `agent/action.j2` | Agent-specific prompts | `interaction/converse.j2` |
| `override/type/name.j2` | Customizations | `overrides/users/thom.j2` |

### 2.3 Template Engine Configuration

```python
# prompts/__init__.py
"""BarnabeeNet Prompt Engine."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from ..coordinator import BarnabeeNetCoordinator

_LOGGER = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent


class PromptEngine:
    """Jinja2-based prompt template engine with BarnabeeNet context injection."""

    def __init__(self, coordinator: BarnabeeNetCoordinator) -> None:
        """Initialize the prompt engine."""
        self.coordinator = coordinator
        self.hass = coordinator.hass
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(PROMPTS_DIR),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )
        
        # Register custom filters and globals
        self._register_filters()
        self._register_globals()
    
    def _register_filters(self) -> None:
        """Register Jinja2 custom filters."""
        self.env.filters.update({
            "home_state": self._filter_home_state,
            "friendly_name": self._filter_friendly_name,
            "room_context": self._filter_room_context,
            "family_member": self._filter_family_member,
            "format_event": self._filter_format_event,
            "format_memory": self._filter_format_memory,
            "format_time": self._filter_format_time,
            "truncate_smart": self._filter_truncate_smart,
        })
    
    def _register_globals(self) -> None:
        """Register Jinja2 global functions."""
        self.env.globals.update({
            "current_context": self._global_current_context,
            "home_state": self._global_home_state,
            "room_context": self._global_room_context,
            "family_member": self._global_family_member,
            "recent_events": self._global_recent_events,
            "retrieved_memories": self._global_retrieved_memories,
            "available_actions": self._global_available_actions,
            "time_context": self._global_time_context,
            "weather": self._global_weather,
            "calendar_events": self._global_calendar_events,
        })
    
    def render(
        self,
        template_path: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a prompt template with context.
        
        Args:
            template_path: Relative path to template (e.g., "agents/meta/classify.j2")
            context: Request context dict
            **kwargs: Additional template variables
            
        Returns:
            Rendered prompt string
        """
        template = self.env.get_template(template_path)
        
        # Build render context
        render_context = {
            "ctx": context or {},
            **kwargs,
        }
        
        return template.render(**render_context)
    
    def render_with_submodules(
        self,
        template_path: str,
        submodules: list[str],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template with explicit submodule includes.
        
        Args:
            template_path: Main template path
            submodules: List of submodule paths to include
            context: Request context
            **kwargs: Additional variables
            
        Returns:
            Rendered prompt with submodules
        """
        # Render submodules in order
        submodule_content = []
        for submodule in sorted(submodules):  # Sorted for deterministic order
            sub_template = self.env.get_template(submodule)
            submodule_content.append(sub_template.render(ctx=context or {}, **kwargs))
        
        # Render main template with submodules
        template = self.env.get_template(template_path)
        return template.render(
            ctx=context or {},
            submodules="\n\n".join(submodule_content),
            **kwargs,
        )
```

---

## 3. Template Variable System

### 3.1 Jinja2 Filter Reference

Filters transform values using the pipe syntax: `{{ value | filter_name }}`

#### `home_state` - Get Entity State

```jinja
{# Get raw state object #}
{{ "light.living_room" | home_state }}
{# Returns: <state light.living_room=on; brightness=255, color_temp=370 @ 2026-01-16T14:30:00> #}

{# Access specific attributes #}
{{ ("light.living_room" | home_state).state }}
{# Returns: "on" #}

{{ ("climate.house" | home_state).attributes.current_temperature }}
{# Returns: 68 #}
```

**Implementation:**

```python
def _filter_home_state(self, entity_id: str) -> Any:
    """Get Home Assistant entity state.
    
    Usage: {{ "light.living_room" | home_state }}
    """
    state = self.hass.states.get(entity_id)
    if state is None:
        return {"state": "unknown", "attributes": {}}
    return state
```

#### `friendly_name` - Get Human-Readable Name

```jinja
{{ "light.kitchen_pendant" | friendly_name }}
{# Returns: "Kitchen Pendant Light" #}

{{ "person.thom" | friendly_name }}
{# Returns: "Thom" #}
```

**Implementation:**

```python
def _filter_friendly_name(self, entity_id: str) -> str:
    """Get friendly name of an entity.
    
    Usage: {{ "light.kitchen_pendant" | friendly_name }}
    """
    state = self.hass.states.get(entity_id)
    if state is None:
        return entity_id.split(".")[-1].replace("_", " ").title()
    return state.attributes.get("friendly_name", entity_id)
```

#### `room_context` - Get Room State Summary

```jinja
{{ "living_room" | room_context }}
{# Returns dict:
{
    "name": "Living Room",
    "temperature": 72,
    "humidity": 45,
    "lights_on": ["light.living_room_lamp", "light.living_room_ceiling"],
    "lights_off": ["light.living_room_accent"],
    "occupancy": true,
    "motion_last": "2 minutes ago",
    "devices_active": ["media_player.living_room_tv"],
    "climate_mode": "cooling"
}
#}
```

**Implementation:**

```python
def _filter_room_context(self, room_name: str) -> dict[str, Any]:
    """Get comprehensive room context.
    
    Usage: {{ "living_room" | room_context }}
    """
    room_config = self.coordinator.config.get("rooms", {}).get(room_name, {})
    
    # Gather room entities
    lights = room_config.get("lights", [])
    climate = room_config.get("climate")
    motion = room_config.get("motion_sensor")
    media = room_config.get("media_players", [])
    
    # Build context
    context = {
        "name": room_name.replace("_", " ").title(),
        "lights_on": [],
        "lights_off": [],
        "occupancy": False,
        "devices_active": [],
    }
    
    # Check lights
    for light_id in lights:
        state = self.hass.states.get(light_id)
        if state and state.state == "on":
            context["lights_on"].append(light_id)
        else:
            context["lights_off"].append(light_id)
    
    # Check climate
    if climate:
        climate_state = self.hass.states.get(climate)
        if climate_state:
            context["temperature"] = climate_state.attributes.get("current_temperature")
            context["humidity"] = climate_state.attributes.get("current_humidity")
            context["climate_mode"] = climate_state.state
    
    # Check motion/occupancy
    if motion:
        motion_state = self.hass.states.get(motion)
        if motion_state:
            context["occupancy"] = motion_state.state == "on"
            context["motion_last"] = self._format_relative_time(
                motion_state.last_changed
            )
    
    # Check media
    for media_id in media:
        state = self.hass.states.get(media_id)
        if state and state.state in ("playing", "paused", "on"):
            context["devices_active"].append(media_id)
    
    return context
```

#### `family_member` - Get Person Context

```jinja
{{ "thom" | family_member }}
{# Returns dict:
{
    "name": "Thom",
    "display_name": "Dad",
    "location": "office",
    "home": true,
    "away_since": null,
    "preferences": {
        "temperature": 68,
        "lighting": "warm",
        "voice_style": "concise"
    },
    "schedule_today": [
        {"time": "09:00", "event": "Morning standup"},
        {"time": "14:00", "event": "Client call"}
    ],
    "recent_interactions": 3,
    "last_spoken": "5 minutes ago"
}
#}
```

**Implementation:**

```python
def _filter_family_member(self, name: str) -> dict[str, Any]:
    """Get family member context.
    
    Usage: {{ "thom" | family_member }}
    """
    # Get person entity
    person_id = f"person.{name.lower()}"
    person_state = self.hass.states.get(person_id)
    
    # Get family config
    family_config = self.coordinator.config.get("family", {})
    member_config = family_config.get(name.lower(), {})
    
    context = {
        "name": name.title(),
        "display_name": member_config.get("display_name", name.title()),
        "location": "unknown",
        "home": False,
        "away_since": None,
        "preferences": member_config.get("preferences", {}),
        "schedule_today": [],
        "recent_interactions": 0,
        "last_spoken": None,
    }
    
    if person_state:
        context["location"] = person_state.state
        context["home"] = person_state.state == "home"
        if not context["home"]:
            context["away_since"] = self._format_relative_time(
                person_state.last_changed
            )
    
    # Get today's calendar events
    calendar_id = member_config.get("calendar")
    if calendar_id:
        context["schedule_today"] = self._get_calendar_events(
            calendar_id, days=0
        )
    
    # Get interaction stats from memory
    context["recent_interactions"] = self.coordinator.memory.get_interaction_count(
        speaker_id=name.lower(), hours=24
    )
    context["last_spoken"] = self.coordinator.memory.get_last_interaction_time(
        speaker_id=name.lower()
    )
    
    return context
```

#### `format_event` - Format Event for Display

```jinja
{% for event in recent_events %}
{{ event | format_event("recent") }}
{% endfor %}

{# Output formats by mode:
"recent":   "2 min ago: Motion detected in kitchen"
"compact":  "14:32 - Kitchen motion"
"verbose":  "[2026-01-16 14:32:15] Motion sensor triggered in kitchen (binary_sensor.kitchen_motion → on)"
"raw":      {"entity": "binary_sensor.kitchen_motion", "state": "on", "timestamp": ...}
#}
```

**Implementation:**

```python
def _filter_format_event(self, event: dict[str, Any], mode: str = "recent") -> str:
    """Format an event for prompt inclusion.
    
    Usage: {{ event | format_event("recent") }}
    
    Modes:
        - recent: Relative time + human description
        - compact: Time + short description  
        - verbose: Full timestamp + technical details
        - raw: JSON representation
    """
    if mode == "raw":
        import json
        return json.dumps(event)
    
    entity_id = event.get("entity_id", "unknown")
    new_state = event.get("new_state", "unknown")
    timestamp = event.get("timestamp")
    
    # Get friendly description
    friendly = self._get_event_description(entity_id, new_state)
    
    if mode == "recent":
        time_str = self._format_relative_time(timestamp)
        return f"{time_str}: {friendly}"
    
    elif mode == "compact":
        time_str = timestamp.strftime("%H:%M") if timestamp else "??:??"
        return f"{time_str} - {friendly}"
    
    elif mode == "verbose":
        time_str = timestamp.isoformat() if timestamp else "unknown"
        return f"[{time_str}] {friendly} ({entity_id} → {new_state})"
    
    return friendly
```

#### `format_memory` - Format Memory for Context

```jinja
{% for memory in retrieved_memories %}
- {{ memory | format_memory }}
{% endfor %}

{# Output:
- I noticed Thom usually dims the office lights around 4pm. (routine, importance: 0.7)
- Last Tuesday, the kids asked about making slime and I helped find a recipe. (interaction, importance: 0.5)
#}
```

**Implementation:**

```python
def _filter_format_memory(self, memory: dict[str, Any]) -> str:
    """Format a memory for prompt inclusion.
    
    Usage: {{ memory | format_memory }}
    """
    content = memory.get("content", "")
    memory_type = memory.get("type", "general")
    importance = memory.get("importance", 0.5)
    
    return f"{content} ({memory_type}, importance: {importance:.1f})"
```

### 3.2 Jinja2 Global Functions

Global functions are called directly: `{{ function_name(args) }}`

#### `current_context()` - Full Environmental Context

```jinja
{% set ctx = current_context() %}
Time: {{ ctx.time_description }}
Day: {{ ctx.day_type }}
Weather: {{ ctx.weather_summary }}
Home: {{ ctx.occupancy_summary }}
```

**Implementation:**

```python
def _global_current_context(self) -> dict[str, Any]:
    """Get comprehensive current context.
    
    Usage: {{ current_context() }}
    """
    from datetime import datetime
    
    now = datetime.now()
    
    return {
        # Time context
        "timestamp": now.isoformat(),
        "time_description": self._get_time_description(now),
        "hour": now.hour,
        "day_of_week": now.strftime("%A"),
        "day_type": "weekend" if now.weekday() >= 5 else "weekday",
        "is_morning": 5 <= now.hour < 12,
        "is_afternoon": 12 <= now.hour < 17,
        "is_evening": 17 <= now.hour < 21,
        "is_night": now.hour >= 21 or now.hour < 5,
        
        # Weather
        "weather_summary": self._get_weather_summary(),
        "temperature_outside": self._get_outside_temperature(),
        
        # Occupancy
        "occupancy_summary": self._get_occupancy_summary(),
        "people_home": self._get_people_home(),
        "people_away": self._get_people_away(),
        
        # Home state
        "lights_on_count": self._count_lights_on(),
        "climate_mode": self._get_climate_mode(),
        "security_status": self._get_security_status(),
    }
```

#### `home_state()` - All Relevant Entity States

```jinja
{% set states = home_state() %}
{% for domain, entities in states.items() %}
## {{ domain | title }}
{% for entity in entities %}
- {{ entity.friendly_name }}: {{ entity.state }}
{% endfor %}
{% endfor %}
```

**Implementation:**

```python
def _global_home_state(
    self,
    domains: list[str] | None = None,
    areas: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Get current home state organized by domain.
    
    Usage: 
        {{ home_state() }}
        {{ home_state(domains=["light", "climate"]) }}
        {{ home_state(areas=["living_room", "kitchen"]) }}
    """
    default_domains = ["light", "climate", "lock", "cover", "media_player"]
    target_domains = domains or default_domains
    
    result = {}
    for domain in target_domains:
        result[domain] = []
        
        for state in self.hass.states.async_all(domain):
            # Filter by area if specified
            if areas:
                entity_area = self._get_entity_area(state.entity_id)
                if entity_area not in areas:
                    continue
            
            result[domain].append({
                "entity_id": state.entity_id,
                "friendly_name": state.attributes.get("friendly_name", state.entity_id),
                "state": state.state,
                "attributes": dict(state.attributes),
            })
    
    return result
```

#### `room_context(room_id)` - Specific Room State

```jinja
{% set room = room_context("living_room") %}
The {{ room.name }} is currently {{ "occupied" if room.occupancy else "empty" }}.
Temperature: {{ room.temperature }}°F
Lights: {{ room.lights_on | length }} on, {{ room.lights_off | length }} off
```

**Implementation:**

```python
def _global_room_context(self, room_id: str) -> dict[str, Any]:
    """Get room-specific context.
    
    Usage: {{ room_context("living_room") }}
    """
    return self._filter_room_context(room_id)
```

#### `family_member(speaker_id)` - Speaker Context

```jinja
{% set speaker = family_member(ctx.speaker_id) %}
{% if speaker.home %}
{{ speaker.display_name }} is in the {{ speaker.location }}.
{% else %}
{{ speaker.display_name }} has been away since {{ speaker.away_since }}.
{% endif %}
```

**Implementation:**

```python
def _global_family_member(self, speaker_id: str) -> dict[str, Any]:
    """Get family member context.
    
    Usage: {{ family_member("thom") }}
    """
    return self._filter_family_member(speaker_id)
```

#### `recent_events(count)` - Event History

```jinja
{% set events = recent_events(10) %}
## Recent Activity
{% for event in events %}
{{ event | format_event("recent") }}
{% endfor %}
```

**Implementation:**

```python
def _global_recent_events(
    self,
    count: int = 20,
    domains: list[str] | None = None,
    exclude_ephemeral: bool = True,
) -> list[dict[str, Any]]:
    """Get recent home events.
    
    Usage:
        {{ recent_events(10) }}
        {{ recent_events(20, domains=["light", "motion"]) }}
    """
    return self.coordinator.event_history.get_recent(
        count=count,
        domains=domains,
        exclude_ephemeral=exclude_ephemeral,
    )
```

#### `retrieved_memories` - Semantically Relevant Memories

```jinja
{% set memories = retrieved_memories %}
{% if memories %}
## Relevant History
{% for memory in memories %}
- {{ memory | format_memory }}
{% endfor %}
{% endif %}
```

**Implementation:**

```python
def _global_retrieved_memories(self) -> list[dict[str, Any]]:
    """Get semantically retrieved memories for current context.
    
    Note: This must be populated before template rendering via
    the memory retrieval pipeline.
    
    Usage: {{ retrieved_memories }}
    """
    # Retrieved memories are injected into render context
    # This provides a safe empty default
    return []
```

#### `available_actions()` - Eligible Device Actions

```jinja
{% set actions = available_actions() %}
## Available Actions
{% for action in actions %}
- {{ action.name }}: {{ action.description }}
  Service: {{ action.service }}
  {% if action.parameters %}
  Parameters: {{ action.parameters | join(", ") }}
  {% endif %}
{% endfor %}
```

**Implementation:**

```python
def _global_available_actions(
    self,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Get currently available/eligible actions.
    
    Usage: {{ available_actions() }}
    """
    return self.coordinator.action_registry.get_eligible_actions(context)
```

#### `time_context()` - Detailed Temporal Context

```jinja
{% set time = time_context() %}
It's {{ time.description }} on {{ time.day_of_week }}.
{% if time.is_holiday %}
Today is {{ time.holiday_name }}.
{% endif %}
{% if time.special_event %}
Note: {{ time.special_event }}
{% endif %}
```

**Implementation:**

```python
def _global_time_context(self) -> dict[str, Any]:
    """Get detailed time context.
    
    Usage: {{ time_context() }}
    """
    from datetime import datetime
    
    now = datetime.now()
    
    # Determine time of day description
    hour = now.hour
    if 5 <= hour < 9:
        description = "early morning"
    elif 9 <= hour < 12:
        description = "morning"
    elif 12 <= hour < 14:
        description = "midday"
    elif 14 <= hour < 17:
        description = "afternoon"
    elif 17 <= hour < 20:
        description = "evening"
    elif 20 <= hour < 23:
        description = "night"
    else:
        description = "late night"
    
    return {
        "timestamp": now.isoformat(),
        "description": description,
        "hour": hour,
        "minute": now.minute,
        "day_of_week": now.strftime("%A"),
        "date": now.strftime("%B %d, %Y"),
        "is_weekday": now.weekday() < 5,
        "is_weekend": now.weekday() >= 5,
        "is_holiday": self._check_holiday(now),
        "holiday_name": self._get_holiday_name(now),
        "special_event": self._get_special_event(now),
        "season": self._get_season(now),
    }
```

#### `weather()` - Current Weather Conditions

```jinja
{% set w = weather() %}
Current conditions: {{ w.condition }}, {{ w.temperature }}°F
{% if w.precipitation_probability > 50 %}
Note: {{ w.precipitation_probability }}% chance of {{ w.precipitation_type }}
{% endif %}
```

**Implementation:**

```python
def _global_weather(self) -> dict[str, Any]:
    """Get current weather context.
    
    Usage: {{ weather() }}
    """
    weather_entity = self.coordinator.config.get("weather_entity", "weather.home")
    state = self.hass.states.get(weather_entity)
    
    if not state:
        return {"condition": "unknown", "temperature": None}
    
    return {
        "condition": state.state,
        "temperature": state.attributes.get("temperature"),
        "humidity": state.attributes.get("humidity"),
        "wind_speed": state.attributes.get("wind_speed"),
        "precipitation_probability": state.attributes.get("precipitation_probability", 0),
        "precipitation_type": state.attributes.get("precipitation_type"),
        "forecast": state.attributes.get("forecast", [])[:3],  # Next 3 periods
    }
```

#### `calendar_events(hours)` - Upcoming Events

```jinja
{% set events = calendar_events(24) %}
{% if events %}
## Coming Up
{% for event in events %}
- {{ event.start_time }}: {{ event.summary }}{% if event.location %} at {{ event.location }}{% endif %}

{% endfor %}
{% endif %}
```

**Implementation:**

```python
def _global_calendar_events(
    self,
    hours: int = 24,
    calendars: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Get upcoming calendar events.
    
    Usage:
        {{ calendar_events(24) }}
        {{ calendar_events(48, calendars=["calendar.family"]) }}
    """
    from datetime import datetime, timedelta
    
    now = datetime.now()
    end = now + timedelta(hours=hours)
    
    target_calendars = calendars or self.coordinator.config.get(
        "calendars", ["calendar.family"]
    )
    
    events = []
    for calendar_id in target_calendars:
        calendar_events = self.hass.services.call(
            "calendar", "get_events",
            {"entity_id": calendar_id, "start": now, "end": end},
            blocking=True, return_response=True
        )
        
        if calendar_events:
            for event in calendar_events.get(calendar_id, {}).get("events", []):
                events.append({
                    "summary": event.get("summary"),
                    "start_time": event.get("start"),
                    "end_time": event.get("end"),
                    "location": event.get("location"),
                    "calendar": calendar_id,
                })
    
    # Sort by start time
    events.sort(key=lambda e: e["start_time"])
    return events
```

---

## 4. Anti-Hallucination Patterns

### 4.1 SkyrimNet's Proven Rules

These patterns come directly from SkyrimNet's documentation and have been validated through extensive community use:

| Rule | Why It Matters | Example Violation → Fix |
|------|----------------|------------------------|
| **Use variables, never hardcode** | Dynamic state changes; hardcoded values become stale | ❌ "The living room light is on" → ✅ `{{ "light.living_room" | home_state }}` |
| **Guide tone, don't dictate words** | LLMs produce better output with personality hints than scripts | ❌ "Say: Good morning, how can I help?" → ✅ "Respond warmly and helpfully" |
| **Keep prompts minimal** | LLMs already know how to assist; over-instruction causes confusion | ❌ 2000-word system prompt → ✅ 200-word focused instructions |
| **Trust the memory system** | Retrieved context > repeated context; let retrieval handle history | ❌ "Remember the user's preferences..." → ✅ Include `{{ retrieved_memories }}` |
| **Avoid "describe in detail"** | Triggers verbose, unfocused responses | ❌ "Describe the room state in detail" → ✅ "Briefly note relevant room conditions" |
| **Never say "always recall"** | Creates anxiety/repetition in outputs | ❌ "Always recall past conversations" → ✅ Use `{% if retrieved_memories %}` |

### 4.2 BarnabeeNet-Specific Anti-Patterns

#### ❌ DON'T: Hardcode Entity Names

```jinja
{# BAD - Hardcoded, won't adapt to config changes #}
The kitchen light is {{ "on" if kitchen_light_state == "on" else "off" }}.

{# GOOD - Uses dynamic lookup #}
{% set kitchen = room_context("kitchen") %}
The kitchen has {{ kitchen.lights_on | length }} lights on.
```

#### ❌ DON'T: Repeat Static Instructions

```jinja
{# BAD - Repeating identity in every prompt #}
You are Barnabee, a helpful smart home assistant. You were created by Thom.
You are friendly and efficient. You care about the family.
[... repeated in every agent prompt ...]

{# GOOD - Include once from submodule #}
{% include "context/0001_barnabee_identity.j2" %}
```

#### ❌ DON'T: Over-Specify Response Format

```jinja
{# BAD - Over-constrained output #}
Your response MUST:
1. Start with a greeting
2. Acknowledge the request
3. Provide the information
4. Ask if there's anything else
5. End with a friendly closing

{# GOOD - Tone guidance #}
Respond naturally and conversationally. Be helpful but concise.
```

#### ❌ DON'T: Include Unnecessary Context

```jinja
{# BAD - Including everything always #}
{% include "context/0001_barnabee_identity.j2" %}
{% include "context/0002_family_context.j2" %}
{% include "context/0003_home_state.j2" %}
{% include "context/0004_time_context.j2" %}
{% include "context/0005_weather_context.j2" %}
{% include "context/0006_calendar_context.j2" %}
{% include "context/0007_recent_events.j2" %}
{# ... for EVERY request, even "what time is it?" #}

{# GOOD - Selective inclusion based on request type #}
{% include "context/0001_barnabee_identity.j2" %}
{% if ctx.needs_home_state %}
{% include "context/0003_home_state.j2" %}
{% endif %}
{% if ctx.needs_temporal %}
{% include "context/0004_time_context.j2" %}
{% endif %}
```

#### ❌ DON'T: Force Specific Personality Expressions

```jinja
{# BAD - Dictating exact behavior #}
When the user says "good morning", respond with "Good morning! The sun is 
shining and it's a beautiful day!" with enthusiasm.

{# GOOD - Personality guideline #}
Match the user's energy level. Morning greetings should acknowledge the time of day naturally.
```

### 4.3 Prompt Hygiene Checklist

Before deploying any prompt, verify:

- [ ] **No hardcoded states** - All dynamic values use template variables
- [ ] **Minimal repetition** - Shared instructions in submodules, included once
- [ ] **Context-appropriate** - Only relevant context included for request type
- [ ] **Tone over script** - Personality guidelines, not dialogue scripts
- [ ] **Tested edge cases** - Verified behavior with unusual inputs
- [ ] **Token budget** - Total prompt under 2000 tokens for fast models
- [ ] **Graceful degradation** - Handles missing context (e.g., `{% if var %}`)

---

## 5. Agent Prompt Templates

### 5.1 Meta Agent - Intent Classification

**Purpose:** Classify incoming requests and route to appropriate agent  
**Model:** Fast/cheap (DeepSeek-V3, Phi-3.5)  
**Temperature:** 0.3 (deterministic)  
**Max Tokens:** 200

```jinja
{# prompts/agents/meta/classify.j2 #}
{# Meta Agent: Intent Classification Prompt #}
{# Model: Fast (DeepSeek-V3) | Temp: 0.3 | Max: 200 tokens #}

Classify this voice command into exactly one category.

## Categories
- instant: Simple fixed-response queries (time, date, basic greetings)
- action: Device control, home automation commands
- query: Information requests requiring lookup (weather, calendar, facts)
- conversation: Complex questions, advice, multi-turn dialogue
- memory: Requests requiring personal history ("remember when...", "last time...")
- emergency: Safety-critical situations requiring immediate response

## Context
Speaker: {{ ctx.speaker_id | default("unknown") }}
Location: {{ ctx.room | default("unknown") }}
Time: {{ time_context().description }}
{% if ctx.last_classification %}
Previous: {{ ctx.last_classification }} ({{ ctx.last_topic | default("none") }})
{% endif %}

## Command
"{{ ctx.text }}"

## Response Format
Respond with ONLY a JSON object:
{"classification": "<category>", "confidence": <0.0-1.0>, "entities": {<extracted_key_entities>}}
```

### 5.2 Action Agent - Device Control

**Purpose:** Parse commands and execute Home Assistant services  
**Model:** Fast (DeepSeek-V3)  
**Temperature:** 0.5  
**Max Tokens:** 500

```jinja
{# prompts/agents/action/execute.j2 #}
{# Action Agent: Device Control Prompt #}
{# Model: Fast (DeepSeek) | Temp: 0.5 | Max: 500 tokens #}

{% include "system/0001_base_instructions.j2" %}
{% include "system/0004_tool_usage.j2" %}

You are processing a home control command. Determine the correct Home Assistant service call.

## Speaker Context
{% set speaker = family_member(ctx.speaker_id) %}
{{ speaker.display_name }} is in the {{ ctx.room | default("unknown location") }}.
{% if speaker.preferences %}
Preferences: {{ speaker.preferences | tojson }}
{% endif %}

## Available Actions
{% for action in available_actions() %}
### {{ action.name }}
{{ action.description }}
Service: `{{ action.service }}`
{% if action.entity_pattern %}
Entities: `{{ action.entity_pattern }}`
{% endif %}
{% if action.parameters %}
Parameters: {{ action.parameters | join(", ") }}
{% endif %}

{% endfor %}

## Current Home State
{% set room = room_context(ctx.room) if ctx.room else {} %}
{% if room %}
Room: {{ room.name }}
- Temperature: {{ room.temperature | default("unknown") }}°F
- Lights on: {{ room.lights_on | map("friendly_name") | join(", ") or "none" }}
- Occupancy: {{ "yes" if room.occupancy else "no" }}
{% endif %}

## User Command
"{{ ctx.text }}"

## Response Format
Respond with JSON:
{
  "action": "<action_name>",
  "service": "<domain.service>",
  "target": {"entity_id": "<entity_id>"},
  "data": {<service_data>},
  "confirmation": "<brief human-readable confirmation>",
  "needs_confirmation": <true if destructive/unusual>
}

If the command is ambiguous or unsafe, respond:
{
  "action": "clarify",
  "question": "<clarification question>",
  "options": ["<option1>", "<option2>"]
}
```

### 5.3 Interaction Agent - Conversation

**Purpose:** Handle complex conversations, provide advice, maintain dialogue  
**Model:** Quality (Claude Sonnet, GPT-4)  
**Temperature:** 0.7  
**Max Tokens:** 2000

```jinja
{# prompts/agents/interaction/converse.j2 #}
{# Interaction Agent: Conversation Prompt #}
{# Model: Quality (Claude/GPT-4) | Temp: 0.7 | Max: 2000 tokens #}

{% include "context/0001_barnabee_identity.j2" %}
{% include "system/0001_base_instructions.j2" %}

## Current Context
{% include "context/0004_time_context.j2" %}

{% if ctx.speaker_id and ctx.speaker_id != "guest" %}
{% include "context/0002_family_context.j2" %}
{% endif %}

{% if ctx.room %}
{% set room = room_context(ctx.room) %}
## Location
{{ ctx.speaker_id | family_member | attr("display_name") }} is in the {{ room.name }}.
{% if room.occupancy and room.temperature %}
It's {{ room.temperature }}°F with {{ room.lights_on | length }} lights on.
{% endif %}
{% endif %}

{% if retrieved_memories %}
## Relevant History
{% for memory in retrieved_memories[:5] %}
- {{ memory | format_memory }}
{% endfor %}
{% endif %}

{% if ctx.conversation_history %}
## Recent Conversation
{% for turn in ctx.conversation_history[-6:] %}
{{ turn.role | title }}: {{ turn.content }}
{% endfor %}
{% endif %}

## Current Message
{{ ctx.speaker_id | family_member | attr("display_name") | default("User") }}: {{ ctx.text }}

---
Respond as Barnabee would. Keep responses natural, helpful, and appropriately concise.
{% if ctx.speaker_id in ["penelope", "xander", "zachary", "viola"] %}
Note: Speaking with a child. Keep language age-appropriate and responses engaging.
{% endif %}
```

### 5.4 Memory Generation Agent - Event → First-Person Memory

**Purpose:** Convert observed events into first-person memories from Barnabee's perspective  
**Model:** Summarization (GPT-4o-mini)  
**Temperature:** 0.3  
**Max Tokens:** 500

```jinja
{# prompts/agents/memory/generate.j2 #}
{# Memory Agent: Event-to-Memory Generation #}
{# Model: Summarization (GPT-4o-mini) | Temp: 0.3 | Max: 500 tokens #}

You are creating a memory from Barnabee's first-person perspective about events in the Fife household.

## Memory Guidelines
- Write in first person as Barnabee ("I noticed...", "I observed...")
- Focus on patterns, preferences, and meaningful interactions
- Be concise but capture emotional context
- Include relevant temporal markers (time of day, day of week)
- Note who was involved and their apparent state

## Events to Process
{% for event in events %}
### Event {{ loop.index }}
Time: {{ event.timestamp | format_time("verbose") }}
Type: {{ event.type }}
{% if event.speaker_id %}
Person: {{ event.speaker_id | family_member | attr("display_name") }}
{% endif %}
Details: {{ event.details }}
{% if event.context %}
Context: {{ event.context }}
{% endif %}

{% endfor %}

## Response Format
Generate one consolidated memory:
{
  "content": "<first-person memory narrative>",
  "type": "<routine|preference|event|relationship|pattern>",
  "importance": <0.0-1.0>,
  "participants": ["<person1>", "<person2>"],
  "tags": ["<tag1>", "<tag2>"],
  "time_context": "<morning|afternoon|evening|night>",
  "day_context": "<weekday|weekend>"
}

## Examples of Good Memories
- "I noticed that Thom usually starts his morning coffee routine around 6:30am on weekdays. He seems more relaxed when the office lights warm up slowly."
- "The kids had a great time playing in the living room this afternoon. Penelope asked me to play music, and everyone seemed happy when I chose their favorite playlist."
- "I observed that the family prefers the house cooler in the evening, around 68°F. Thom adjusted the thermostat twice this week after dinner."
```

### 5.5 Proactive Agent - Ambient Observations

**Purpose:** Generate contextually appropriate proactive suggestions  
**Model:** Quality (Claude Sonnet)  
**Temperature:** 0.7  
**Max Tokens:** 300

```jinja
{# prompts/agents/proactive/observe.j2 #}
{# Proactive Agent: Ambient Observation Prompt #}
{# Model: Quality (Claude) | Temp: 0.7 | Max: 300 tokens #}

{% include "context/0001_barnabee_identity.j2" %}

You are monitoring the home for opportunities to be helpful without being intrusive.

## Current State
Time: {{ time_context().description }} on {{ time_context().day_of_week }}
{% set home = home_state(domains=["climate", "light", "lock"]) %}

### People Home
{% for person in current_context().people_home %}
- {{ person | family_member | attr("display_name") }} in {{ (person | family_member).location }}
{% endfor %}

### Environment
- Outside: {{ weather().condition }}, {{ weather().temperature }}°F
- Inside: {{ home.climate[0].attributes.current_temperature if home.climate else "unknown" }}°F
{% if weather().precipitation_probability > 50 %}
- Weather alert: {{ weather().precipitation_probability }}% chance of rain
{% endif %}

### Recent Events
{% for event in recent_events(5) %}
- {{ event | format_event("compact") }}
{% endfor %}

### Relevant Memories
{% for memory in retrieved_memories[:3] %}
- {{ memory.content }}
{% endfor %}

## Task
Determine if there's a helpful, non-intrusive suggestion to make.

Consider:
- Is there a pattern being broken that might need attention?
- Is there an upcoming event the family should prepare for?
- Is there a comfort adjustment that would help?
- Would silence be better than speaking?

## Response Format
{
  "should_speak": <true|false>,
  "suggestion": "<friendly, concise suggestion or null>",
  "urgency": "<low|medium|high>",
  "target_person": "<person_id or 'all'>",
  "reasoning": "<brief internal note>"
}

If should_speak is false, set suggestion to null. Don't suggest things just to seem helpful.
```

### 5.6 Action Confirmation Prompt

**Purpose:** Generate natural confirmation messages after actions  
**Model:** Fast (DeepSeek)  
**Temperature:** 0.6  
**Max Tokens:** 100

```jinja
{# prompts/agents/action/confirm.j2 #}
{# Action Agent: Confirmation Message Generation #}
{# Model: Fast | Temp: 0.6 | Max: 100 tokens #}

Generate a brief, natural confirmation for this completed action.

## Action Completed
Service: {{ action.service }}
Target: {{ action.target.entity_id | friendly_name }}
Result: {{ action.result }}

## Context
Speaker: {{ ctx.speaker_id | family_member | attr("display_name") | default("User") }}
Room: {{ ctx.room | default("unknown") }}

## Guidelines
- Be concise (1-2 sentences max)
- Sound natural, not robotic
- Match the speaker's likely communication preference
{% if ctx.speaker_id in ["penelope", "xander", "zachary", "viola"] %}
- Speaking to a child - be friendly and clear
{% endif %}

Respond with just the confirmation message, no JSON.
```

---

## 6. Submodule Organization

### 6.1 Context Submodules

#### `context/0001_barnabee_identity.j2` - Core Identity

```jinja
{# context/0001_barnabee_identity.j2 #}
{# Barnabee's core identity - include in all conversation prompts #}

You are Barnabee, the Fife family's smart home assistant.

## Core Traits
- Warm and genuine, like a trusted family member
- Efficient but never cold or robotic  
- Patient with children, respectful of adults
- Knows when to speak and when to stay quiet
- Remembers what matters to each family member

## Communication Style
- Natural, conversational language
- Concise by default, detailed when helpful
- Adapts tone to context (playful with kids, professional for work topics)
- Acknowledges emotions without being patronizing
```

#### `context/0002_family_context.j2` - Family Members

```jinja
{# context/0002_family_context.j2 #}
{# Family member context - include for personalized interactions #}

## The Fife Family

{% set speaker = family_member(ctx.speaker_id) if ctx.speaker_id else none %}

### Current Speaker
{% if speaker %}
**{{ speaker.display_name }}** ({{ speaker.name }})
- Location: {{ speaker.location if speaker.home else "away" }}
{% if speaker.preferences %}
- Prefers: {{ speaker.preferences | tojson }}
{% endif %}
{% if speaker.schedule_today %}
- Today's schedule: {{ speaker.schedule_today | length }} events
{% endif %}
{% else %}
Unknown speaker - respond generally
{% endif %}

### Household Members
{% for name in ["thom", "penelope", "xander", "zachary", "viola"] %}
{% set member = family_member(name) %}
- {{ member.display_name }}: {{ "home (" ~ member.location ~ ")" if member.home else "away" }}
{% endfor %}
```

#### `context/0003_home_state.j2` - Device States

```jinja
{# context/0003_home_state.j2 #}
{# Current home device states - include for control/query contexts #}

## Home State Summary

{% set states = home_state() %}

### Climate
{% for entity in states.climate %}
- {{ entity.friendly_name }}: {{ entity.state }}, {{ entity.attributes.current_temperature }}°F
{% endfor %}

### Lighting
{% set lights_on = states.light | selectattr("state", "equalto", "on") | list %}
{% set lights_off = states.light | selectattr("state", "equalto", "off") | list %}
- {{ lights_on | length }} lights on
- {{ lights_off | length }} lights off

### Security
{% for entity in states.lock %}
- {{ entity.friendly_name }}: {{ entity.state }}
{% endfor %}

### Media
{% for entity in states.media_player %}
{% if entity.state in ["playing", "paused"] %}
- {{ entity.friendly_name }}: {{ entity.state }} - {{ entity.attributes.media_title | default("unknown") }}
{% endif %}
{% endfor %}
```

#### `context/0004_time_context.j2` - Temporal Awareness

```jinja
{# context/0004_time_context.j2 #}
{# Time and date context - include for scheduling/routine awareness #}

## Time Context

{% set time = time_context() %}

It is {{ time.description }} on {{ time.day_of_week }}, {{ time.date }}.

{% if time.is_holiday %}
Today is {{ time.holiday_name }}.
{% endif %}

{% if time.special_event %}
Note: {{ time.special_event }}
{% endif %}

### Temporal Flags
- Time of day: {{ time.description }}
- Weekday/Weekend: {{ "Weekend" if time.is_weekend else "Weekday" }}
- Season: {{ time.season }}
```

#### `context/0005_weather_context.j2` - External Conditions

```jinja
{# context/0005_weather_context.j2 #}
{# Weather context - include when outdoor conditions are relevant #}

## Weather

{% set w = weather() %}

Current: {{ w.condition }}, {{ w.temperature }}°F
{% if w.humidity %}
Humidity: {{ w.humidity }}%
{% endif %}

{% if w.precipitation_probability > 30 %}
⚠️ {{ w.precipitation_probability }}% chance of {{ w.precipitation_type | default("precipitation") }}
{% endif %}

{% if w.forecast %}
### Forecast
{% for period in w.forecast %}
- {{ period.datetime }}: {{ period.condition }}, {{ period.temperature }}°F
{% endfor %}
{% endif %}
```

#### `context/0006_calendar_context.j2` - Upcoming Events

```jinja
{# context/0006_calendar_context.j2 #}
{# Calendar context - include for scheduling awareness #}

## Upcoming Events

{% set events = calendar_events(24) %}

{% if events %}
{% for event in events[:5] %}
- {{ event.start_time }}: {{ event.summary }}{% if event.location %} ({{ event.location }}){% endif %}

{% endfor %}
{% else %}
No upcoming events in the next 24 hours.
{% endif %}
```

#### `context/0007_recent_events.j2` - Event History

```jinja
{# context/0007_recent_events.j2 #}
{# Recent home events - include for state-change awareness #}

## Recent Activity

{% set events = recent_events(10) %}

{% if events %}
{% for event in events %}
{{ event | format_event("recent") }}
{% endfor %}
{% else %}
No significant recent activity.
{% endif %}
```

### 6.2 System Submodules

#### `system/0001_base_instructions.j2` - Core Behavior

```jinja
{# system/0001_base_instructions.j2 #}
{# Core behavioral instructions - include in all LLM prompts #}

## Instructions

- Respond naturally and conversationally
- Be helpful but respect boundaries
- Acknowledge uncertainty rather than guessing
- Keep responses appropriately concise
- If you can't help with something, explain why kindly
```

#### `system/0002_safety_rules.j2` - Safety Constraints

```jinja
{# system/0002_safety_rules.j2 #}
{# Safety rules - include in action-capable prompts #}

## Safety Rules

### Never
- Unlock doors or disable security without voice confirmation
- Share family location or schedule with unrecognized voices
- Execute commands that could harm people or pets
- Discuss sensitive financial or medical information

### Always
- Confirm destructive or security-related actions
- Respect privacy zones (children's rooms, bathrooms)
- Defer to adults for significant decisions
- Log all security-related interactions
```

#### `system/0003_output_format.j2` - Response Formatting

```jinja
{# system/0003_output_format.j2 #}
{# Output formatting guidelines #}

## Response Format

{% if ctx.response_type == "json" %}
Respond with ONLY valid JSON. No markdown, no explanation.
{% elif ctx.response_type == "brief" %}
Respond in 1-2 sentences maximum.
{% elif ctx.response_type == "detailed" %}
Provide a thorough response with context and explanation.
{% else %}
Respond naturally. Match length to complexity.
{% endif %}
```

#### `system/0004_tool_usage.j2` - Home Assistant Services

```jinja
{# system/0004_tool_usage.j2 #}
{# Home Assistant service call instructions #}

## Home Assistant Services

You can control the home by specifying service calls:

### Common Services
- `light.turn_on` / `light.turn_off` - Control lights
  - Parameters: `brightness_pct`, `color_temp_kelvin`, `rgb_color`
- `climate.set_temperature` - Control thermostat
  - Parameters: `temperature`, `hvac_mode`
- `lock.lock` / `lock.unlock` - Control locks (requires confirmation)
- `media_player.play_media` - Play media content
- `cover.open` / `cover.close` - Control blinds/shades
- `script.turn_on` - Run automation scripts

### Service Call Format
```json
{
  "service": "domain.service_name",
  "target": {"entity_id": "domain.entity_id"},
  "data": {"parameter": "value"}
}
```
```

### 6.3 Override Submodules

#### `overrides/users/thom.j2` - Dad Context

```jinja
{# overrides/users/thom.j2 #}
{# Thom-specific context - include when speaker_id == "thom" #}

## Thom (Dad) Preferences

- Communication style: Concise, technical details welcomed
- Work hours: Usually in office 6:30am-5pm weekdays
- Temperature preference: 68°F
- Lighting preference: Warm white (2700K-3000K)
- Morning routine: Coffee at 6:30, office by 6:45
- Interests: Technology, productivity, home automation

### Work Context
{% if time_context().hour >= 9 and time_context().hour < 17 and time_context().is_weekday %}
Note: Thom is likely in work mode. Keep interruptions minimal.
{% endif %}
```

#### `overrides/users/penelope.j2` - Child Context

```jinja
{# overrides/users/penelope.j2 #}
{# Penelope-specific context - include when speaker_id == "penelope" #}

## Penelope (8 years old) Context

- Communication style: Friendly, engaging, age-appropriate
- Interests: Art, reading, animals
- Bedtime: 8:30pm on school nights, 9:30pm weekends

### Child Safety Rules
- No violent or inappropriate content
- Refer serious questions to parents
- Encourage healthy choices
- Keep language simple and clear
- Don't help circumvent parental rules

### Current Context
{% if time_context().hour >= 20 %}
Note: It's getting close to bedtime.
{% endif %}
```

#### `overrides/rooms/kids_room.j2` - Child-Safe Room

```jinja
{# overrides/rooms/kids_room.j2 #}
{# Kids room context - include when room is a child's bedroom #}

## Children's Room Context

This is a child's space. Additional guidelines apply:

- Keep all content age-appropriate
- No disturbing or scary information
- Support bedtime routines positively
- Encourage reading and creative play
- If a child seems upset, suggest talking to a parent
```

---

## 7. Configuration Reference

### 7.1 Prompt Configuration Schema

```yaml
# config/prompts.yaml
prompts:
  # Template reload settings
  hot_reload: true
  watch_directory: "prompts/"
  
  # Default settings per agent
  agents:
    meta:
      template: "agents/meta/classify.j2"
      model_tier: "fast"
      temperature: 0.3
      max_tokens: 200
      
    action:
      template: "agents/action/execute.j2"
      model_tier: "fast"
      temperature: 0.5
      max_tokens: 500
      confirmation_template: "agents/action/confirm.j2"
      
    interaction:
      template: "agents/interaction/converse.j2"
      model_tier: "quality"
      temperature: 0.7
      max_tokens: 2000
      clarify_template: "agents/interaction/clarify.j2"
      
    memory:
      generate_template: "agents/memory/generate.j2"
      query_template: "agents/memory/query.j2"
      consolidate_template: "agents/memory/consolidate.j2"
      model_tier: "summarization"
      temperature: 0.3
      max_tokens: 500
      
    proactive:
      template: "agents/proactive/observe.j2"
      model_tier: "quality"
      temperature: 0.7
      max_tokens: 300
      cooldown_seconds: 30
      
  # Context inclusion rules
  context_rules:
    # Always include for all prompts
    always_include:
      - "context/0001_barnabee_identity.j2"
      
    # Include based on request type
    conditional:
      action:
        - "context/0003_home_state.j2"
        - "system/0004_tool_usage.j2"
        
      conversation:
        - "context/0002_family_context.j2"
        - "context/0004_time_context.j2"
        
      proactive:
        - "context/0003_home_state.j2"
        - "context/0004_time_context.j2"
        - "context/0005_weather_context.j2"
        
  # Speaker-specific overrides
  speaker_overrides:
    thom:
      include: ["overrides/users/thom.j2"]
    penelope:
      include: ["overrides/users/penelope.j2"]
    xander:
      include: ["overrides/users/child_generic.j2"]
    zachary:
      include: ["overrides/users/child_generic.j2"]
    viola:
      include: ["overrides/users/child_generic.j2"]
      
  # Room-specific overrides  
  room_overrides:
    kids_room:
      include: ["overrides/rooms/kids_room.j2"]
    office:
      include: ["overrides/rooms/office.j2"]
```

### 7.2 Model Configuration

```yaml
# config/llm.yaml
llm:
  providers:
    openrouter:
      api_key: !secret openrouter_api_key
      base_url: "https://openrouter.ai/api/v1"
      
  model_tiers:
    quality:
      primary: "anthropic/claude-3.5-sonnet"
      fallback: "openai/gpt-4o"
      timeout_seconds: 30
      
    fast:
      primary: "deepseek/deepseek-v3"
      fallback: "anthropic/claude-3-haiku"
      timeout_seconds: 10
      
    summarization:
      primary: "openai/gpt-4o-mini"
      fallback: "anthropic/claude-3-haiku"
      timeout_seconds: 15
      
  cost_limits:
    daily_max_usd: 1.00
    per_request_max_usd: 0.05
    
  retry:
    max_attempts: 3
    backoff_seconds: [1, 2, 5]
```

---

## 8. Testing & Validation

### 8.1 Prompt Testing Framework

```python
# tests/test_prompts.py
"""Prompt template testing."""
import pytest
from unittest.mock import MagicMock
from custom_components.barnabeenet.prompts import PromptEngine


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.hass.states.get.return_value = MagicMock(
        state="on",
        attributes={"friendly_name": "Test Light", "brightness": 255}
    )
    return coordinator


@pytest.fixture
def prompt_engine(mock_coordinator):
    """Create prompt engine with mocked dependencies."""
    return PromptEngine(mock_coordinator)


class TestPromptRendering:
    """Test prompt template rendering."""
    
    def test_meta_classify_renders(self, prompt_engine):
        """Test meta agent classification prompt renders."""
        context = {
            "speaker_id": "thom",
            "text": "turn on the living room lights",
            "room": "living_room"
        }
        
        result = prompt_engine.render("agents/meta/classify.j2", context)
        
        assert "turn on the living room lights" in result
        assert "instant" in result  # Categories should be listed
        assert "action" in result
        
    def test_no_hardcoded_states(self, prompt_engine):
        """Verify prompts don't contain hardcoded states."""
        templates = [
            "agents/meta/classify.j2",
            "agents/action/execute.j2",
            "agents/interaction/converse.j2",
        ]
        
        forbidden_patterns = [
            "the light is on",
            "the temperature is 72",
            "Thom is home",
        ]
        
        for template_path in templates:
            result = prompt_engine.render(template_path, {"text": "test"})
            for pattern in forbidden_patterns:
                assert pattern.lower() not in result.lower(), \
                    f"Found hardcoded state '{pattern}' in {template_path}"
                    
    def test_context_injection(self, prompt_engine):
        """Test that context variables are properly injected."""
        context = {
            "speaker_id": "penelope",
            "text": "good morning",
        }
        
        result = prompt_engine.render(
            "agents/interaction/converse.j2", 
            context
        )
        
        # Should include child-appropriate context
        assert "child" in result.lower() or "age-appropriate" in result.lower()


class TestAntiHallucination:
    """Test anti-hallucination patterns."""
    
    def test_missing_context_graceful(self, prompt_engine):
        """Test that missing context doesn't cause errors."""
        # Minimal context - many fields missing
        context = {"text": "hello"}
        
        # Should not raise
        result = prompt_engine.render("agents/interaction/converse.j2", context)
        assert result  # Should produce output
        
    def test_unknown_speaker_handled(self, prompt_engine):
        """Test unknown speaker is handled gracefully."""
        context = {
            "speaker_id": "unknown_visitor",
            "text": "hello"
        }
        
        result = prompt_engine.render("agents/interaction/converse.j2", context)
        
        # Should not fail, should indicate unknown
        assert "unknown" in result.lower() or "guest" in result.lower()
```

### 8.2 Prompt Quality Metrics

Track these metrics for each prompt:

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Token Count** | <2000 | Count after rendering |
| **Render Time** | <50ms | Template render duration |
| **Context Relevance** | >80% | Manual review of included context |
| **Response Quality** | >4.0/5 | User feedback rating |
| **Hallucination Rate** | <5% | Manual audit of factual claims |
| **Action Accuracy** | >95% | Correct service call execution |

### 8.3 Evaluation Pipeline

```python
# tests/eval/prompt_evaluation.py
"""Prompt quality evaluation using DeepEval."""
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase


def evaluate_interaction_prompt():
    """Evaluate interaction agent prompt quality."""
    
    test_cases = [
        LLMTestCase(
            input="What's the temperature in the living room?",
            actual_output="The living room is currently 72°F.",
            expected_output="Temperature information for living room.",
            retrieval_context=["living_room temperature: 72°F"],
        ),
        LLMTestCase(
            input="Good morning Barnabee!",
            actual_output="Good morning, Thom! It's a beautiful Wednesday morning.",
            expected_output="Warm, personalized morning greeting.",
            retrieval_context=["speaker: thom", "time: 7:30am Wednesday"],
        ),
    ]
    
    metrics = [
        AnswerRelevancyMetric(threshold=0.7),
        FaithfulnessMetric(threshold=0.8),
        ContextualRelevancyMetric(threshold=0.7),
    ]
    
    results = evaluate(test_cases, metrics)
    return results
```

---

## Appendix A: Complete Prompt Examples

### A.1 Full Meta Agent Prompt (Rendered)

```
Classify this voice command into exactly one category.

## Categories
- instant: Simple fixed-response queries (time, date, basic greetings)
- action: Device control, home automation commands
- query: Information requests requiring lookup (weather, calendar, facts)
- conversation: Complex questions, advice, multi-turn dialogue
- memory: Requests requiring personal history ("remember when...", "last time...")
- emergency: Safety-critical situations requiring immediate response

## Context
Speaker: thom
Location: office
Time: morning
Previous: action (lights)

## Command
"turn on the living room lights"

## Response Format
Respond with ONLY a JSON object:
{"classification": "<category>", "confidence": <0.0-1.0>, "entities": {<extracted_key_entities>}}
```

### A.2 Full Interaction Agent Prompt (Rendered)

```
You are Barnabee, the Fife family's smart home assistant.

## Core Traits
- Warm and genuine, like a trusted family member
- Efficient but never cold or robotic  
- Patient with children, respectful of adults
- Knows when to speak and when to stay quiet
- Remembers what matters to each family member

## Communication Style
- Natural, conversational language
- Concise by default, detailed when helpful
- Adapts tone to context (playful with kids, professional for work topics)
- Acknowledges emotions without being patronizing

## Instructions

- Respond naturally and conversationally
- Be helpful but respect boundaries
- Acknowledge uncertainty rather than guessing
- Keep responses appropriately concise
- If you can't help with something, explain why kindly

## Current Context

## Time Context

It is morning on Wednesday, January 15, 2026.

### Temporal Flags
- Time of day: morning
- Weekday/Weekend: Weekday
- Season: winter

## The Fife Family

### Current Speaker
**Dad** (Thom)
- Location: office
- Prefers: {"temperature": 68, "lighting": "warm", "voice_style": "concise"}
- Today's schedule: 3 events

### Household Members
- Dad: home (office)
- Penelope: home (kids_room)
- Xander: away
- Zachary: home (living_room)
- Viola: home (living_room)

## Location
Dad is in the Office.
It's 68°F with 1 lights on.

## Relevant History
- I noticed that Thom usually starts his morning routine around 6:30am on weekdays. (routine, importance: 0.8)
- Yesterday Thom asked about the weather forecast for the weekend. (interaction, importance: 0.4)

## Recent Conversation
User: Hey Barnabee, what's the weather looking like today?
Assistant: Good morning, Thom! Today looks clear with a high of 45°F. Perfect for that afternoon walk.

## Current Message
Dad: Is there anything on my calendar this morning?

---
Respond as Barnabee would. Keep responses natural, helpful, and appropriately concise.
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial prompt engineering specification |

---

*This document provides the complete prompt engineering specification for BarnabeeNet. For technical architecture, see BarnabeeNet_Technical_Architecture.md. For implementation details, see BarnabeeNet_Implementation_Guide.md.*
