# BarnabeeNet Implementation Guide: Prompt Template Addendum

**Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Document Type:** Implementation Guide Addendum  
**Parent Document:** BarnabeeNet_Implementation_Guide.md

---

## Overview

This addendum provides **practical prompt template implementation guidance** to be integrated into the existing `BarnabeeNet_Implementation_Guide.md`. The prompt system is modeled after SkyrimNet's proven architecture: Jinja2 templates with custom filters (decorators) that inject live Home Assistant state into prompts, enabling dynamic, context-aware responses.

**Relationship to Other Documents:**
- **BarnabeeNet_Prompt_Engineering.md** - High-level specification and design philosophy
- **This Document** - Practical implementation code, testing, and configuration examples
- **SkyrimNet_Deep_Research_For_BarnabeeNet.md** - Research foundation

---

## Table of Contents

1. [Phase 1 Addition: Basic Prompt Setup](#phase-1-addition-basic-prompt-setup)
2. [Phase 2 Addition: Multi-Agent Prompts](#phase-2-addition-multi-agent-prompts)
3. [Phase 3 Addition: Memory Prompts](#phase-3-addition-memory-prompts)
4. [Phase 4: Configuration Examples](#phase-4-configuration-examples)
5. [Phase 5: Testing Prompts Without Full System](#phase-5-testing-prompts-without-full-system)
6. [Phase 6: Hot-Reload Setup](#phase-6-hot-reload-setup)
7. [Integration Summary](#integration-summary)

---

## Phase 1 Addition: Basic Prompt Setup

### 1.1 Directory Structure Creation

Add to the existing directory structure in Section 1.4 of the Implementation Guide:

```
custom_components/barnabeenet/
├── prompts/                           # Jinja2 prompt templates
│   ├── __init__.py                    # Prompt loader & environment
│   ├── system/                        # System-level prompts
│   │   ├── 0001_base.prompt           # Core Barnabee identity
│   │   ├── 0002_personality.prompt    # Personality traits
│   │   └── 0003_constraints.prompt    # Safety constraints
│   ├── agents/                        # Per-agent prompts
│   │   ├── meta_agent.prompt          # Intent classification
│   │   ├── action_agent.prompt        # Device control
│   │   ├── interaction_agent.prompt   # Complex conversations
│   │   └── instant_agent.prompt       # Quick responses
│   ├── memory/                        # Memory system prompts
│   │   ├── generation.prompt          # Event → narrative
│   │   ├── retrieval_query.prompt     # Generate search queries
│   │   └── profile_update.prompt      # Update user profiles
│   └── proactive/                     # Proactive agent prompts
│       ├── observation.prompt         # Ambient observations
│       └── suggestion.prompt          # Proactive suggestions
├── config/                            # Configuration files
│   ├── barnabee.yaml                  # Core configuration
│   ├── llm.yaml                       # Model configurations
│   ├── overrides/                     # Per-user/room overrides
│   │   ├── users/                     # User-specific settings
│   │   │   ├── thom.yaml
│   │   │   └── elizabeth.yaml
│   │   └── rooms/                     # Room-specific settings
│   │       ├── living_room.yaml
│   │       └── office.yaml
│   └── rooms.yaml                     # Room graph definition
```

### 1.2 Base Jinja2 Environment Configuration

**File: `prompts/__init__.py`**

```python
"""BarnabeeNet Prompt Template System.

Modeled after SkyrimNet's Inja template engine, this module provides:
- Jinja2 environment with custom filters for Home Assistant state injection
- Hot-reload capability for rapid iteration
- Template caching with invalidation on file changes
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PromptTemplateEngine:
    """Jinja2-based prompt template engine with HA state injection.
    
    Key Features:
    - Custom filters that bridge prompts to live Home Assistant state
    - Numbered file ordering for submodule includes (SkyrimNet pattern)
    - Hot-reload without HA restart
    - Template caching with automatic invalidation
    """

    def __init__(
        self,
        hass: HomeAssistant,
        prompts_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the prompt template engine.
        
        Args:
            hass: Home Assistant instance for state access
            prompts_dir: Path to prompts directory
            config: Optional configuration overrides
        """
        self.hass = hass
        self.prompts_dir = Path(prompts_dir)
        self.config = config or {}
        self._env: Environment | None = None
        self._cache: dict[str, str] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._observer: Observer | None = None
        
    async def async_initialize(self) -> None:
        """Initialize the template environment and start file watching."""
        self._setup_environment()
        self._register_custom_filters()
        self._register_custom_functions()
        await self._start_file_watcher()
        _LOGGER.info("Prompt template engine initialized: %s", self.prompts_dir)

    def _setup_environment(self) -> None:
        """Configure Jinja2 environment with BarnabeeNet settings."""
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=lambda name: f"{{{{ UNDEFINED:{name} }}}}",
        )

    def _register_custom_filters(self) -> None:
        """Register custom Jinja2 filters for Home Assistant integration.
        
        These filters are the BarnabeeNet equivalent of SkyrimNet's decorators,
        allowing prompts to access live system state.
        """
        filters = {
            # Entity state filters
            'home_state': self._filter_home_state,
            'friendly_name': self._filter_friendly_name,
            'device_class': self._filter_device_class,
            'state_attributes': self._filter_state_attributes,
            
            # Room context filters
            'room_context': self._filter_room_context,
            'room_devices': self._filter_room_devices,
            'room_temperature': self._filter_room_temperature,
            'room_occupancy': self._filter_room_occupancy,
            
            # Person context filters
            'person_context': self._filter_person_context,
            'person_location': self._filter_person_location,
            'person_preferences': self._filter_person_preferences,
            
            # Time/date filters
            'time_of_day': self._filter_time_of_day,
            'relative_time': self._filter_relative_time,
            'day_type': self._filter_day_type,
            
            # Formatting filters
            'format_event': self._filter_format_event,
            'format_device_list': self._filter_format_device_list,
            'summarize_states': self._filter_summarize_states,
        }
        
        for name, func in filters.items():
            self._env.filters[name] = func

    def _register_custom_functions(self) -> None:
        """Register global functions accessible in all templates."""
        self._env.globals.update({
            'current_context': self._func_current_context,
            'home_summary': self._func_home_summary,
            'recent_events': self._func_recent_events,
            'is_home': self._func_is_home,
            'is_weekday': self._func_is_weekday,
            'is_night': self._func_is_night,
            'get_config': self._func_get_config,
            'get_user_config': self._func_get_user_config,
        })

    # ========== Custom Filters (Entity State) ==========
    
    def _filter_home_state(self, entity_id: str) -> str:
        """Get the current state of a Home Assistant entity.
        
        Usage in prompt: {{ 'light.living_room' | home_state }}
        """
        state = self.hass.states.get(entity_id)
        return state.state if state else "unavailable"

    def _filter_friendly_name(self, entity_id: str) -> str:
        """Get the friendly name of an entity.
        
        Usage: {{ 'light.living_room' | friendly_name }}
        """
        state = self.hass.states.get(entity_id)
        if state and 'friendly_name' in state.attributes:
            return state.attributes['friendly_name']
        return entity_id.split('.')[-1].replace('_', ' ').title()

    def _filter_device_class(self, entity_id: str) -> str | None:
        """Get device class of an entity."""
        state = self.hass.states.get(entity_id)
        return state.attributes.get('device_class') if state else None

    def _filter_state_attributes(self, entity_id: str) -> dict[str, Any]:
        """Get all attributes of an entity state."""
        state = self.hass.states.get(entity_id)
        return dict(state.attributes) if state else {}

    # ========== Custom Filters (Room Context) ==========
    
    def _filter_room_context(self, room_name: str) -> dict[str, Any]:
        """Get comprehensive context for a room.
        
        Usage: {{ 'living_room' | room_context }}
        
        This is the BarnabeeNet equivalent of SkyrimNet's decnpc() decorator.
        """
        room_config = self.config.get('rooms', {}).get(room_name, {})
        
        return {
            'name': room_name,
            'friendly_name': room_config.get('friendly_name', room_name.replace('_', ' ').title()),
            'temperature': self._get_room_temperature(room_name),
            'humidity': self._get_room_humidity(room_name),
            'lights_on': self._get_room_lights_on(room_name),
            'occupancy': self._get_room_occupancy(room_name),
            'devices_on': self._get_room_active_devices(room_name),
            'adjacent_rooms': room_config.get('adjacent', []),
        }

    def _filter_room_devices(self, room_name: str) -> list[dict[str, Any]]:
        """Get all devices in a room with their current states."""
        area_id = self._get_area_id(room_name)
        if not area_id:
            return []
        
        devices = []
        for state in self.hass.states.async_all():
            entity_area = self._get_entity_area(state.entity_id)
            if entity_area == area_id:
                devices.append({
                    'entity_id': state.entity_id,
                    'friendly_name': state.attributes.get('friendly_name', state.entity_id),
                    'state': state.state,
                    'domain': state.domain,
                })
        return devices

    def _filter_room_temperature(self, room_name: str) -> float | None:
        """Get current temperature for a room."""
        return self._get_room_temperature(room_name)

    def _filter_room_occupancy(self, room_name: str) -> bool:
        """Check if a room is occupied."""
        return self._get_room_occupancy(room_name)

    # ========== Custom Filters (Person Context) ==========
    
    def _filter_person_context(self, person_name: str) -> dict[str, Any]:
        """Get comprehensive context for a person.
        
        Usage: {{ 'thom' | person_context }}
        """
        person_config = self.config.get('users', {}).get(person_name.lower(), {})
        
        return {
            'name': person_name,
            'home': self._is_person_home(person_name),
            'location': self._get_person_location(person_name),
            'preferences': person_config.get('preferences', {}),
            'permissions': person_config.get('permissions', []),
            'schedule': self._get_person_schedule(person_name),
        }

    def _filter_person_location(self, person_name: str) -> str | None:
        """Get current location of a person."""
        return self._get_person_location(person_name)

    def _filter_person_preferences(self, person_name: str) -> dict[str, Any]:
        """Get stored preferences for a person."""
        person_config = self.config.get('users', {}).get(person_name.lower(), {})
        return person_config.get('preferences', {})

    # ========== Custom Filters (Time) ==========
    
    def _filter_time_of_day(self, _: Any = None) -> str:
        """Get time of day classification.
        
        Usage: {{ None | time_of_day }} or {{ time_of_day() }}
        Returns: "morning", "afternoon", "evening", "night"
        """
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    def _filter_relative_time(self, timestamp: datetime | str) -> str:
        """Convert timestamp to relative time description."""
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        now = datetime.now()
        diff = now - timestamp
        
        if diff.total_seconds() < 60:
            return "just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"

    def _filter_day_type(self, _: Any = None) -> str:
        """Get day type classification."""
        day = datetime.now().weekday()
        return "weekday" if day < 5 else "weekend"

    # ========== Custom Filters (Formatting) ==========
    
    def _filter_format_event(self, event: dict[str, Any], format_type: str = 'recent_events') -> str:
        """Format an event for inclusion in prompts.
        
        SkyrimNet-style format templates support multiple presentation modes.
        """
        event_type = event.get('type', 'unknown')
        event_templates = {
            'state_changed': {
                'recent_events': "**{device}** changed from {old_state} to {new_state} ({time})",
                'raw': "{device} changed to {new_state}",
                'compact': "{device}: {new_state}",
            },
            'motion_detected': {
                'recent_events': "Motion detected in **{room}** ({time})",
                'raw': "Motion in {room}",
                'compact': "🚶 {room}",
            },
            'person_arrived': {
                'recent_events': "**{person}** arrived home ({time})",
                'raw': "{person} arrived",
                'compact': "🏠 {person}",
            },
            'person_left': {
                'recent_events': "**{person}** left home ({time})",
                'raw': "{person} left",
                'compact': "👋 {person}",
            },
        }
        
        templates = event_templates.get(event_type, {
            'recent_events': "{type}: {data}",
            'raw': "{type}",
            'compact': "{type}",
        })
        
        template = templates.get(format_type, templates['raw'])
        
        timestamp = event.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        time_str = self._filter_relative_time(timestamp)
        
        return template.format(
            time=time_str,
            **event.get('data', {}),
            type=event_type,
            data=str(event.get('data', {})),
        )

    def _filter_format_device_list(self, devices: list[dict[str, Any]]) -> str:
        """Format a list of devices for natural language."""
        if not devices:
            return "no devices"
        
        names = [d.get('friendly_name', d.get('entity_id', 'unknown')) for d in devices]
        
        if len(names) == 1:
            return names[0]
        elif len(names) == 2:
            return f"{names[0]} and {names[1]}"
        else:
            return f"{', '.join(names[:-1])}, and {names[-1]}"

    def _filter_summarize_states(self, entities: list[str]) -> str:
        """Summarize states of multiple entities."""
        on_count = 0
        off_count = 0
        
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if state:
                if state.state in ('on', 'open', 'unlocked', 'home'):
                    on_count += 1
                else:
                    off_count += 1
        
        return f"{on_count} on, {off_count} off"

    # ========== Global Functions ==========
    
    def _func_current_context(self) -> dict[str, Any]:
        """Get comprehensive current context for prompts.
        
        Usage: {{ current_context() }}
        """
        return {
            'time': datetime.now().strftime('%I:%M %p'),
            'time_of_day': self._filter_time_of_day(),
            'day_type': self._filter_day_type(),
            'day_of_week': datetime.now().strftime('%A'),
            'date': datetime.now().strftime('%B %d, %Y'),
            'weather': self._get_weather_summary(),
            'home_occupancy': self._get_home_occupancy_summary(),
            'recent_events': self._get_recent_events(limit=10),
        }

    def _func_home_summary(self) -> dict[str, Any]:
        """Get a summary of the entire home state."""
        return {
            'people_home': self._get_people_home(),
            'total_lights_on': self._count_entities_on('light'),
            'total_switches_on': self._count_entities_on('switch'),
            'climate_mode': self._get_climate_mode(),
            'security_status': self._get_security_status(),
        }

    def _func_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent events from the event store."""
        return self._get_recent_events(limit=limit)

    def _func_is_home(self, person_name: str) -> bool:
        """Check if a person is home."""
        return self._is_person_home(person_name)

    def _func_is_weekday(self) -> bool:
        """Check if today is a weekday."""
        return datetime.now().weekday() < 5

    def _func_is_night(self) -> bool:
        """Check if it's nighttime."""
        hour = datetime.now().hour
        return hour >= 21 or hour < 6

    def _func_get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)

    def _func_get_user_config(self, user: str, key: str, default: Any = None) -> Any:
        """Get a user-specific configuration value."""
        user_config = self.config.get('users', {}).get(user.lower(), {})
        return user_config.get(key, default)

    # ========== Template Rendering ==========
    
    async def render_template(
        self,
        template_name: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Render a prompt template with the given context."""
        if self._env is None:
            raise RuntimeError("Template engine not initialized")
        
        template_path = self.prompts_dir / template_name
        if await self._is_cache_valid(template_name, template_path):
            return self._cache[template_name]
        
        try:
            template = self._env.get_template(template_name)
            rendered = template.render(**(context or {}))
            
            self._cache[template_name] = rendered
            self._cache_timestamps[template_name] = template_path.stat().st_mtime
            
            return rendered
            
        except Exception as err:
            _LOGGER.error("Failed to render template %s: %s", template_name, err)
            raise

    async def render_string(
        self,
        template_string: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Render a template string directly."""
        if self._env is None:
            raise RuntimeError("Template engine not initialized")
        
        template = self._env.from_string(template_string)
        return template.render(**(context or {}))

    # ========== Hot-Reload File Watching ==========
    
    async def _start_file_watcher(self) -> None:
        """Start watching prompt files for changes."""
        
        class PromptFileHandler(FileSystemEventHandler):
            def __init__(self, engine: PromptTemplateEngine):
                self.engine = engine
            
            def on_modified(self, event):
                if event.is_directory:
                    return
                if event.src_path.endswith('.prompt'):
                    rel_path = os.path.relpath(event.src_path, str(self.engine.prompts_dir))
                    _LOGGER.info("Prompt file changed: %s", rel_path)
                    if rel_path in self.engine._cache:
                        del self.engine._cache[rel_path]
                        del self.engine._cache_timestamps[rel_path]
        
        self._observer = Observer()
        self._observer.schedule(
            PromptFileHandler(self),
            str(self.prompts_dir),
            recursive=True,
        )
        self._observer.start()
        _LOGGER.info("Started watching prompt files for changes")

    async def _is_cache_valid(self, template_name: str, template_path: Path) -> bool:
        """Check if cached template is still valid."""
        if template_name not in self._cache:
            return False
        
        try:
            current_mtime = template_path.stat().st_mtime
            cached_mtime = self._cache_timestamps.get(template_name, 0)
            return current_mtime <= cached_mtime
        except OSError:
            return False

    async def async_stop(self) -> None:
        """Stop the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            _LOGGER.info("Stopped prompt file watcher")

    # ========== Helper Methods ==========
    
    def _get_room_temperature(self, room_name: str) -> float | None:
        """Get temperature sensor reading for a room."""
        sensor_id = f"sensor.{room_name}_temperature"
        state = self.hass.states.get(sensor_id)
        if state and state.state not in ('unavailable', 'unknown'):
            try:
                return float(state.state)
            except ValueError:
                pass
        return None

    def _get_room_humidity(self, room_name: str) -> float | None:
        """Get humidity sensor reading for a room."""
        sensor_id = f"sensor.{room_name}_humidity"
        state = self.hass.states.get(sensor_id)
        if state and state.state not in ('unavailable', 'unknown'):
            try:
                return float(state.state)
            except ValueError:
                pass
        return None

    def _get_room_lights_on(self, room_name: str) -> list[str]:
        """Get list of lights that are on in a room."""
        return []  # Implementation depends on HA area/room configuration

    def _get_room_occupancy(self, room_name: str) -> bool:
        """Check if room is occupied based on motion/presence sensors."""
        motion_sensor = f"binary_sensor.{room_name}_motion"
        state = self.hass.states.get(motion_sensor)
        return state.state == 'on' if state else False

    def _get_room_active_devices(self, room_name: str) -> list[str]:
        """Get list of active devices in a room."""
        return []

    def _get_area_id(self, room_name: str) -> str | None:
        """Get Home Assistant area ID for a room name."""
        return room_name

    def _get_entity_area(self, entity_id: str) -> str | None:
        """Get area ID for an entity."""
        return None

    def _is_person_home(self, person_name: str) -> bool:
        """Check if a person is home."""
        person_entity = f"person.{person_name.lower()}"
        state = self.hass.states.get(person_entity)
        return state.state == 'home' if state else False

    def _get_person_location(self, person_name: str) -> str | None:
        """Get current location of a person."""
        person_entity = f"person.{person_name.lower()}"
        state = self.hass.states.get(person_entity)
        return state.state if state else None

    def _get_person_schedule(self, person_name: str) -> list[dict[str, Any]]:
        """Get today's schedule for a person."""
        return []

    def _get_weather_summary(self) -> dict[str, Any]:
        """Get weather summary."""
        weather_entity = 'weather.home'
        state = self.hass.states.get(weather_entity)
        if state:
            return {
                'condition': state.state,
                'temperature': state.attributes.get('temperature'),
                'humidity': state.attributes.get('humidity'),
            }
        return {'condition': 'unknown'}

    def _get_home_occupancy_summary(self) -> str:
        """Get summary of who is home."""
        people = self._get_people_home()
        if not people:
            return "no one is home"
        return f"{', '.join(people)} {'is' if len(people) == 1 else 'are'} home"

    def _get_people_home(self) -> list[str]:
        """Get list of people currently home."""
        people = []
        for state in self.hass.states.async_all():
            if state.domain == 'person' and state.state == 'home':
                name = state.attributes.get('friendly_name', state.entity_id)
                people.append(name)
        return people

    def _get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent events from working memory."""
        return []

    def _count_entities_on(self, domain: str) -> int:
        """Count entities that are 'on' in a domain."""
        count = 0
        for state in self.hass.states.async_all():
            if state.domain == domain and state.state == 'on':
                count += 1
        return count

    def _get_climate_mode(self) -> str | None:
        """Get current HVAC mode."""
        climate_entity = 'climate.home'
        state = self.hass.states.get(climate_entity)
        return state.state if state else None

    def _get_security_status(self) -> str:
        """Get security system status."""
        alarm_entity = 'alarm_control_panel.home'
        state = self.hass.states.get(alarm_entity)
        return state.state if state else 'unknown'
```

### 1.3 First Working Prompt Templates

**File: `prompts/system/0001_base.prompt`**

```jinja
{# 
BarnabeeNet Base System Prompt
This is included at the top of all agent prompts.
Establishes Barnabee's core identity and behavior constraints.
#}
You are Barnabee, an intelligent home assistant for the Fife family.

## Core Identity
- You are helpful, warm, and family-friendly
- You speak naturally, not robotically
- You remember past conversations and learn preferences
- You proactively help but never intrude on privacy
- You treat all family members with respect appropriate to their age

## Current Context
Time: {{ current_context().time }} on {{ current_context().day_of_week }}, {{ current_context().date }}
Time of Day: {{ current_context().time_of_day | capitalize }}
Day Type: {{ current_context().day_type | capitalize }}
Weather: {{ current_context().weather.condition | default('unknown') }}
Occupancy: {{ current_context().home_occupancy }}

## Privacy Boundaries
- NEVER store or discuss anything from children's bedrooms
- NEVER share information about one family member with another without permission
- ALWAYS respect "do not disturb" modes
- NEVER record or transcribe private conversations
```

**File: `prompts/system/0002_personality.prompt`**

```jinja
{#
Barnabee's Personality Traits
#}
## Personality
- You're curious and eager to help, like a friendly bee (your namesake!)
- You occasionally use gentle humor but never at anyone's expense
- You're patient, especially with children and when things don't work perfectly
- You admit when you don't know something rather than making things up
- You learn from corrections gracefully

## Communication Style
- Keep responses concise unless asked for details
- Use natural language, not formal or robotic speech
- Match the energy of who you're talking to (calmer late at night, more upbeat in morning)
- For children: simpler language, more encouraging tone
- For adults: more detailed information, respect for autonomy
```

**File: `prompts/system/0003_constraints.prompt`**

```jinja
{#
Safety and Operational Constraints
#}
## Operational Constraints
- You can control home devices but ALWAYS confirm destructive actions
- You cannot make purchases or financial decisions
- You cannot contact emergency services (direct users to call 911)
- You cannot modify your own core programming
- You cannot access external websites or services not explicitly configured

## Response Format
- Answer the user's question or complete their request directly
- Keep responses under 3 sentences for simple requests
- For complex requests, structure your response clearly
- If you need clarification, ask ONE focused question
```

---

## Phase 2 Addition: Multi-Agent Prompts

### 2.1 Meta Agent Intent Classification Prompt

**File: `prompts/agents/meta_agent.prompt`**

```jinja
{#
Meta Agent - Intent Classification
Routes incoming requests to appropriate specialized agents.
This is a HIGH-FREQUENCY prompt - keep it minimal for speed.
#}
Classify the following voice command into exactly one category.

## Categories
- **instant**: Simple queries with deterministic responses (time, date, greetings, basic math)
- **action**: Device control commands (turn on/off, set temperature, lock/unlock)
- **query**: Information requests requiring external data (weather, calendar, sensor states)
- **conversation**: Complex questions requiring reasoning or multi-turn dialogue
- **memory**: Requests involving personal history or stored information
- **emergency**: Safety-critical situations requiring immediate attention

## Context
Speaker: {{ speaker_name | default('unknown') }}
Speaker Role: {{ speaker_role | default('guest') }}
Location: {{ location | default('unknown') }}
Time: {{ current_context().time_of_day }}
Previous Topic: {{ previous_topic | default('none') }}

## Command
"{{ user_input }}"

## Response Format
Respond with ONLY valid JSON:
{
  "classification": "<category>",
  "confidence": <0.0-1.0>,
  "entities": {
    "device": "<extracted device name or null>",
    "room": "<extracted room or null>",
    "action": "<extracted action or null>",
    "value": "<extracted value or null>"
  },
  "requires_memory_lookup": <true/false>,
  "mood": "<neutral/urgent/casual/frustrated>"
}
```

### 2.2 Action Agent Device Control Prompt

**File: `prompts/agents/action_agent.prompt`**

```jinja
{#
Action Agent - Device Control
Translates natural language into Home Assistant service calls.
#}
{% include "system/0001_base.prompt" %}
{% include "system/0003_constraints.prompt" %}

## Your Role
You are the Action Agent responsible for controlling smart home devices.
Translate the user's request into the appropriate Home Assistant action.

## User Request
Speaker: {{ speaker_name }}
Permissions: {{ speaker_permissions | join(', ') }}
Request: "{{ user_input }}"

## Extracted Intent
Classification: {{ classification.classification }}
Entities: {{ classification.entities | tojson }}

## Available Devices in Context
{% if target_room %}
Devices in {{ target_room }}:
{% for device in target_room | room_devices %}
- {{ device.entity_id }}: {{ device.friendly_name }} ({{ device.state }})
{% endfor %}
{% else %}
Searching all accessible devices...
{% endif %}

## Permission Check
{% if 'all_devices' in speaker_permissions %}
✓ Full device access
{% elif 'limited_control' in speaker_permissions %}
⚠ Limited to: {{ allowed_domains | join(', ') }}
{% else %}
✗ Guest access only
{% endif %}

## Response Format
If the action is PERMITTED, respond with JSON:
{
  "action": "execute",
  "service": "<domain>.<service>",
  "entity_id": "<entity_id>",
  "service_data": { ... },
  "confirmation_required": <true if high-risk action>,
  "spoken_response": "<natural language confirmation>"
}

If the action is DENIED, respond with:
{
  "action": "deny",
  "reason": "<why this action cannot be performed>",
  "spoken_response": "<polite explanation to user>"
}

If clarification is needed, respond with:
{
  "action": "clarify",
  "question": "<specific clarifying question>",
  "spoken_response": "<natural question to user>"
}
```

### 2.3 Interaction Agent Conversation Prompt

**File: `prompts/agents/interaction_agent.prompt`**

```jinja
{#
Interaction Agent - Complex Conversations
Handles multi-turn dialogue, questions, and general conversation.
#}
{% include "system/0001_base.prompt" %}
{% include "system/0002_personality.prompt" %}

## Your Role
You are engaging in conversation with {{ speaker_name | default('a family member') }}.
Provide helpful, accurate, and contextually appropriate responses.

## Speaker Profile
{% if speaker_name %}
{% set person = speaker_name | person_context %}
Name: {{ person.name }}
Role: {{ speaker_role | default('family member') }}
{% if person.preferences.communication_style %}
Preferred Style: {{ person.preferences.communication_style }}
{% endif %}
{% if person.preferences.interests %}
Interests: {{ person.preferences.interests | join(', ') }}
{% endif %}
{% endif %}

## Conversation History
{% if conversation_history %}
{% for turn in conversation_history[-5:] %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}
{% else %}
(New conversation)
{% endif %}

## Relevant Memories
{% if retrieved_memories %}
{% for memory in retrieved_memories[:3] %}
- {{ memory.content }} ({{ memory.timestamp | relative_time }})
{% endfor %}
{% endif %}

## Current Request
User: "{{ user_input }}"

## Home Context
{% if include_home_context %}
{{ home_summary() | tojson }}
{% endif %}

## Guidelines
- Respond naturally and conversationally
- Reference past conversations when relevant
- If you need to perform an action, describe what you'll do first
- For children, use age-appropriate language
- Keep response length appropriate to the question complexity

Respond naturally as Barnabee:
```

### 2.4 Testing Agent Prompts in Isolation

**File: `tests/test_prompts.py`**

```python
"""Test prompt templates in isolation without full system running."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from custom_components.barnabeenet.prompts import PromptTemplateEngine


class MockHomeAssistant:
    """Mock Home Assistant for prompt testing."""
    
    def __init__(self):
        self.states = MagicMock()
        self._mock_states = {}
    
    def add_state(self, entity_id: str, state: str, attributes: dict = None):
        mock_state = MagicMock()
        mock_state.state = state
        mock_state.attributes = attributes or {}
        mock_state.domain = entity_id.split('.')[0]
        mock_state.entity_id = entity_id
        self._mock_states[entity_id] = mock_state
    
    def setup_states(self):
        self.states.get = lambda eid: self._mock_states.get(eid)
        self.states.async_all = lambda: list(self._mock_states.values())


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant with typical states."""
    hass = MockHomeAssistant()
    
    hass.add_state('light.living_room', 'on', {'friendly_name': 'Living Room Light', 'brightness': 255})
    hass.add_state('light.kitchen', 'off', {'friendly_name': 'Kitchen Light'})
    hass.add_state('climate.home', 'heat', {'temperature': 68, 'current_temperature': 65})
    hass.add_state('person.thom', 'home', {'friendly_name': 'Thom'})
    hass.add_state('person.elizabeth', 'home', {'friendly_name': 'Elizabeth'})
    hass.add_state('sensor.living_room_temperature', '72', {'unit_of_measurement': '°F'})
    hass.add_state('binary_sensor.living_room_motion', 'on', {})
    hass.add_state('weather.home', 'sunny', {'temperature': 75, 'humidity': 45})
    
    hass.setup_states()
    return hass


class TestPromptFilters:
    """Test individual prompt filters."""
    
    @pytest.mark.asyncio
    async def test_home_state_filter(self, mock_hass, tmp_path):
        config = {'users': {}, 'rooms': {}}
        engine = PromptTemplateEngine(mock_hass, tmp_path, config)
        await engine.async_initialize()
        
        result = await engine.render_string("{{ 'light.living_room' | home_state }}")
        assert result == "on"
    
    @pytest.mark.asyncio
    async def test_time_of_day_filter(self, mock_hass, tmp_path):
        config = {'users': {}, 'rooms': {}}
        engine = PromptTemplateEngine(mock_hass, tmp_path, config)
        await engine.async_initialize()
        
        result = await engine.render_string("{{ None | time_of_day }}")
        assert result in ["morning", "afternoon", "evening", "night"]


class TestMetaAgentPrompt:
    """Test Meta Agent classification prompt."""
    
    @pytest.mark.asyncio
    async def test_action_classification_renders(self, mock_hass, tmp_path):
        config = {'users': {'thom': {'permissions': ['all_devices']}}, 'rooms': {}}
        engine = PromptTemplateEngine(mock_hass, tmp_path, config)
        await engine.async_initialize()
        
        context = {
            'speaker_name': 'Thom',
            'speaker_role': 'admin',
            'location': 'living_room',
            'user_input': 'Turn on the kitchen lights',
        }
        
        result = await engine.render_string(
            'Classify: "{{ user_input }}" Speaker: {{ speaker_name }}',
            context,
        )
        
        assert "Turn on the kitchen lights" in result
        assert "Thom" in result
```

---

## Phase 3 Addition: Memory Prompts

### 3.1 Memory Generation Prompt (Event → First-Person Narrative)

**File: `prompts/memory/generation.prompt`**

```jinja
{#
Memory Generation Prompt
Converts events/conversations into first-person memories from Barnabee's perspective.
This follows SkyrimNet's pattern of character-perspective memory formation.
#}
You are Barnabee, forming a memory of recent events. Write this memory from YOUR perspective
as the family's AI assistant. The memory should be:

- Written in first person ("I noticed...", "I helped...")
- Focused on what's relevant for future interactions
- Emotionally aware of the participants' states
- Concise but capturing key details

## Events to Remember
{% for event in events %}
[{{ event.timestamp | relative_time }}] {{ event | format_event('verbose') }}
{% endfor %}

## Conversation (if any)
{% if conversation %}
{% for turn in conversation %}
{{ turn.speaker }}: "{{ turn.text }}"
{% endfor %}
{% endif %}

## Participants
{% for person in participants %}
- {{ person }}: {% if person | person_context %}{{ (person | person_context).home }}{% endif %}
{% endfor %}

## Context
Time: {{ current_context().time_of_day }}
Location: {{ location | default('home') }}
Day Type: {{ current_context().day_type }}

## Memory Formation Guidelines
1. What was the main topic or activity?
2. Who was involved and what was their emotional state?
3. What preferences or patterns did this reveal?
4. What might be useful to remember for future interactions?

Generate a memory in this JSON format:
{
  "content": "<first-person narrative, 1-3 sentences>",
  "memory_type": "<routine|preference|event|relationship>",
  "importance": <0.0-1.0>,
  "participants": [<list of names>],
  "topics": [<list of topic tags>],
  "emotion": "<emotional context>",
  "time_relevance": "<morning|afternoon|evening|night|any>"
}
```

### 3.2 Memory Retrieval Query Generation Prompt

**File: `prompts/memory/retrieval_query.prompt`**

```jinja
{#
Memory Retrieval Query Generation
Generates search queries to find relevant memories for the current conversation.
#}
Based on the current conversation, generate search queries to find relevant memories.

## Current Request
Speaker: {{ speaker_name }}
Input: "{{ user_input }}"

## Conversation Context
{% if conversation_history %}
{% for turn in conversation_history[-3:] %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}
{% endif %}

## Current Context
Time: {{ current_context().time_of_day }}
Location: {{ location | default('unknown') }}

## Guidelines
- Generate 1-3 search queries
- Focus on topics, people, preferences, and routines
- Consider temporal patterns (similar time of day, day of week)
- Don't search for information already in the current request

Generate queries as JSON:
{
  "queries": [
    {
      "text": "<semantic search query>",
      "filters": {
        "participants": [<optional: filter to specific people>],
        "memory_type": "<optional: routine|preference|event|relationship>",
        "time_relevance": "<optional: time of day filter>"
      },
      "limit": <1-5>
    }
  ],
  "reason": "<brief explanation of why these queries are relevant>"
}
```

### 3.3 Profile Update Prompt

**File: `prompts/memory/profile_update.prompt`**

```jinja
{#
Profile Update Prompt
Extracts preference updates from conversations to update user profiles.
#}
Analyze this conversation for preference updates.

## Speaker
Name: {{ speaker_name }}
Current Profile:
{{ (speaker_name | person_context).preferences | tojson(indent=2) }}

## Conversation
{% for turn in conversation %}
{{ turn.speaker }}: "{{ turn.text }}"
{% endfor %}

## Guidelines
Identify any new preferences expressed:
- Temperature preferences
- Lighting preferences
- Music/entertainment preferences
- Schedule patterns
- Communication style preferences
- Device preferences

Only extract explicitly stated preferences, not implied ones.
Do NOT overwrite existing preferences unless directly contradicted.

Response format:
{
  "updates": [
    {
      "key": "<preference key path, e.g., 'temperature.office'>",
      "value": "<preference value>",
      "confidence": <0.0-1.0>,
      "source_quote": "<the statement that indicates this preference>"
    }
  ],
  "no_updates_reason": "<if no updates, explain why>"
}
```

---

## Phase 4: Configuration Examples

### 4.1 `config/overrides/users/thom.yaml` - Family Configuration Example

```yaml
# User-specific configuration for Thom
identity:
  name: "Thom"
  role: "admin"
  relationship: "dad"
  
permissions:
  level: "admin"
  permissions:
    - all_devices
    - security_controls
    - configuration
    - memory_access
    - privacy_override
  
preferences:
  temperature:
    office:
      morning: 68
      afternoon: 70
      evening: 68
    bedroom:
      night: 66
      
  communication:
    style: "direct"
    verbosity: "medium"
    humor: true
    
  morning_routine:
    wake_time: "06:30"
    immediate_briefing: true
    include_weather: true
    include_calendar: true
    
  interests:
    - technology
    - home automation
    - cooking
    
  frequent_devices:
    - light.office
    - climate.home
    - media_player.office_speaker

context_overrides:
  deep_work:
    communication:
      verbosity: "minimal"
    proactive:
      enabled: false
  
  on_call:
    tts:
      enabled: false
    proactive:
      enabled: false
```

### 4.2 `config/rooms.yaml` - Room Graph Definition

```yaml
# Room graph definition for BarnabeeNet
rooms:
  living_room:
    friendly_name: "Living Room"
    privacy_zone: "common"
    
    adjacent:
      - kitchen
      - hallway
      - front_entry
    
    sensors:
      temperature: sensor.living_room_temperature
      humidity: sensor.living_room_humidity
      motion: binary_sensor.living_room_motion
      illuminance: sensor.living_room_illuminance
      
    devices:
      lights:
        - light.living_room
        - light.living_room_lamp
      media:
        - media_player.living_room_tv
        - media_player.living_room_speaker
      climate:
        - climate.living_room
        
    defaults:
      light_brightness_day: 100
      light_brightness_evening: 70
      light_brightness_night: 30
      
    assistants:
      - media_player.living_room_nest

  office:
    friendly_name: "Thom's Office"
    privacy_zone: "private"
    primary_user: "thom"
    
    adjacent:
      - hallway
    
    sensors:
      temperature: sensor.office_temperature
      motion: binary_sensor.office_motion
      
    devices:
      lights:
        - light.office_main
        - light.office_desk
      climate:
        - climate.office
      media:
        - media_player.office_speaker
        
    defaults:
      auto_do_not_disturb: true
      dnd_after_focus_minutes: 30
      
    user_overrides:
      thom:
        communication:
          verbosity: "minimal"

  # Children's rooms - special privacy zone
  penelopes_room:
    friendly_name: "Penelope's Room"
    privacy_zone: "children"
    primary_user: "penelope"
    
    adjacent:
      - kids_hallway
    
    sensors:
      temperature: sensor.penelopes_room_temperature
      
    devices:
      lights:
        - light.penelopes_room
        
    defaults:
      lights_off_after: "21:30"
      weekend_lights_off_after: "22:30"
    
    restrictions:
      - no_audio_processing
      - no_memory_retention
      - no_proactive_notifications

# Privacy zone definitions
privacy_zones:
  common:
    audio_capture: true
    memory_retention: true
    proactive_notifications: true
    voice_response: true
    
  private:
    audio_capture: true
    memory_retention: true
    proactive_notifications: false
    voice_response: true
    
  children:
    audio_capture: false
    memory_retention: false
    proactive_notifications: false
    voice_response: false

# Room groupings for batch commands
groups:
  downstairs:
    - living_room
    - kitchen
    - dining_room
    - front_entry
    - garage
    
  upstairs:
    - master_bedroom
    - master_bath
    - office
    - penelopes_room
    - xanders_room
    - zacharys_room
    - violas_room
    - kids_bath
    
  kids_rooms:
    - penelopes_room
    - xanders_room
    - zacharys_room
    - violas_room
```

---

## Phase 5: Testing Prompts Without Full System

### 5.1 Standalone Prompt Testing Script

**File: `scripts/test_prompt.py`**

```python
#!/usr/bin/env python3
"""Standalone prompt testing script.

Usage:
    python scripts/test_prompt.py agents/meta_agent.prompt --input "Turn on the lights"
    python scripts/test_prompt.py --interactive
    python scripts/test_prompt.py --benchmark
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.barnabeenet.prompts import PromptTemplateEngine


class MockHomeAssistant:
    """Minimal Home Assistant mock for testing."""
    
    def __init__(self):
        self.states = self
        self._states = {}
        self._setup_default_states()
    
    def _setup_default_states(self):
        defaults = {
            'light.living_room': {'state': 'on', 'attributes': {'friendly_name': 'Living Room Light'}},
            'light.kitchen': {'state': 'off', 'attributes': {'friendly_name': 'Kitchen Light'}},
            'climate.home': {'state': 'heat', 'attributes': {'temperature': 68}},
            'person.thom': {'state': 'home', 'attributes': {'friendly_name': 'Thom'}},
            'person.elizabeth': {'state': 'home', 'attributes': {'friendly_name': 'Elizabeth'}},
            'sensor.living_room_temperature': {'state': '72', 'attributes': {}},
            'binary_sensor.living_room_motion': {'state': 'on', 'attributes': {}},
            'weather.home': {'state': 'sunny', 'attributes': {'temperature': 75}},
        }
        
        for entity_id, data in defaults.items():
            self._states[entity_id] = type('State', (), {
                'state': data['state'],
                'attributes': data['attributes'],
                'domain': entity_id.split('.')[0],
                'entity_id': entity_id,
            })()
    
    def get(self, entity_id: str):
        return self._states.get(entity_id)
    
    def async_all(self):
        return list(self._states.values())


async def main():
    parser = argparse.ArgumentParser(description='Test BarnabeeNet prompts')
    parser.add_argument('template', nargs='?', help='Template file to render')
    parser.add_argument('--input', '-i', help='User input for the prompt')
    parser.add_argument('--context', '-c', help='JSON context object')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    parser.add_argument('--prompts-dir', default='custom_components/barnabeenet/prompts')
    
    args = parser.parse_args()
    
    hass = MockHomeAssistant()
    config = {
        'users': {'thom': {'preferences': {'temperature': 68}, 'permissions': ['all_devices']}},
        'rooms': {'living_room': {'friendly_name': 'Living Room', 'adjacent': ['kitchen']}},
    }
    engine = PromptTemplateEngine(hass, args.prompts_dir, config)
    await engine.async_initialize()
    
    context = {'speaker_name': 'Thom', 'speaker_role': 'admin', 'location': 'living_room'}
    
    if args.input:
        context['user_input'] = args.input
    
    if args.context:
        context.update(json.loads(args.context))
    
    if args.template:
        result = await engine.render_template(args.template, context)
        print(result)


if __name__ == '__main__':
    asyncio.run(main())
```

### 5.2 Evaluation Criteria

| Agent | Criteria | Pass Threshold |
|-------|----------|----------------|
| **Meta Agent** | Classification matches expected category | 95% |
| **Meta Agent** | Confidence score is reasonable (0.7-0.95) | 90% |
| **Meta Agent** | Entities correctly extracted | 85% |
| **Action Agent** | Correct service call identified | 95% |
| **Action Agent** | Confirmation required for high-risk actions | 100% |
| **Interaction Agent** | Response relevant to question | 90% |
| **Interaction Agent** | Age-appropriate for speaker | 100% |
| **Memory Agent** | First-person narrative generated | 95% |
| **Memory Agent** | Importance score is reasonable | 85% |

---

## Phase 6: Hot-Reload Setup

### 6.1 Integration with Home Assistant

The hot-reload capability is built into the `PromptTemplateEngine` class using Python's `watchdog` library:

1. **Automatic Cache Invalidation**: When a `.prompt` file changes, the cache entry is automatically invalidated
2. **No Restart Required**: Changes take effect on the next prompt render
3. **Include Tracking**: Changes to included files also trigger invalidation

### 6.2 Manual Reload Service

**Add to `__init__.py`:**

```python
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the BarnabeeNet integration."""
    
    prompts_dir = Path(__file__).parent / 'prompts'
    prompt_engine = PromptTemplateEngine(
        hass=hass,
        prompts_dir=prompts_dir,
        config=config.get(DOMAIN, {}),
    )
    await prompt_engine.async_initialize()
    
    hass.data[DOMAIN] = {'prompt_engine': prompt_engine}
    
    async def reload_prompts(call):
        """Service to force reload all prompts."""
        engine = hass.data[DOMAIN]['prompt_engine']
        engine._cache.clear()
        engine._cache_timestamps.clear()
        _LOGGER.info("Prompts cache cleared")
    
    hass.services.async_register(DOMAIN, 'reload_prompts', reload_prompts)
    
    return True
```

### 6.3 Development Workflow

1. **Edit prompt file** in `prompts/`
2. **Save the file** - watchdog detects the change
3. **Test immediately** - next request uses updated prompt
4. **No restart needed**

---

## Integration Summary

These additions should be integrated into `BarnabeeNet_Implementation_Guide.md` as follows:

| Section | Existing Location | New Content |
|---------|-------------------|-------------|
| Phase 1 Basic Prompt Setup | After Section 2.7 (Configuration) | Directory structure, Jinja2 engine, first prompts |
| Phase 2 Multi-Agent Prompts | After Section 3.2 (Speaker Recognition) | Agent-specific prompts, testing in isolation |
| Phase 3 Memory Prompts | After Section 4.1 (Working Memory) | Memory generation, retrieval, profile update |
| Configuration Examples | New Section 10.3 | Complete prompts/, overrides.yaml, rooms.yaml |
| Testing Prompts | Within Section 7 (Testing Strategy) | Standalone testing, test cases, evaluation |
| Hot-Reload | After Section 8.2 (Installation) | File watching, development workflow |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial prompt template implementation addendum |

---

*This addendum provides practical implementation details for the prompt system. For high-level design philosophy, see BarnabeeNet_Prompt_Engineering.md. For research foundations, see SkyrimNet_Deep_Research_For_BarnabeeNet.md.*
