# BarnabeeNet Override System Architecture

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Author:** Thom Fife  
**Purpose:** Comprehensive specification for per-user, per-room, and per-time behavioral overrides

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Override Hierarchy](#override-hierarchy)
3. [YAML Schema Definition](#yaml-schema-definition)
4. [Family Member Overrides](#family-member-overrides)
5. [Room Overrides](#room-overrides)
6. [Time Period Overrides](#time-period-overrides)
7. [Override Resolution Engine](#override-resolution-engine)
8. [Response Transformer](#response-transformer)
9. [Agent Integration](#agent-integration)
10. [Resolution Scenarios](#resolution-scenarios)
11. [Comparison to SkyrimNet](#comparison-to-skyrimnet)

---

## Executive Summary

The Override System allows BarnabeeNet to provide contextually appropriate responses based on **who is speaking**, **where they are**, and **when they're interacting**. This directly mirrors SkyrimNet's per-NPC/faction overrides (found in `config/Overrides/`) but adapts the concept for home automation with per-user, per-room, and per-time override dimensions.

### Why Overrides Matter

| Without Overrides | With Overrides |
|-------------------|----------------|
| Same response style for everyone | Technical for Thom, playful for kids |
| Voice responses always on | Silent in nursery at night |
| Adult content accessible to all | Age-appropriate filtering per child |
| Same LLM model always used | Fast local model at night, quality during day |
| One-size-fits-all proactivity | Urgent-only during work hours |

---

## Override Hierarchy

### Cascading Priority (Lowest to Highest)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                              OVERRIDE HIERARCHY                                              │
│                         (Later layers take precedence)                                       │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   Priority 0 (Lowest)           ┌─────────────────────────────────────────────┐             │
│   BASE DEFAULTS           ───▶  │ System-wide defaults for all contexts       │             │
│                                 └─────────────────────────────────────────────┘             │
│                                                  │                                           │
│   Priority 1                    ┌────────────────▼──────────────────────────────┐           │
│   TIME PERIOD             ───▶  │ night_mode, work_hours, weekend, etc.        │           │
│                                 └───────────────────────────────────────────────┘           │
│                                                  │                                           │
│   Priority 2                    ┌────────────────▼──────────────────────────────┐           │
│   ROOM                    ───▶  │ office, nursery, bedroom, kitchen, etc.      │           │
│                                 └───────────────────────────────────────────────┘           │
│                                                  │                                           │
│   Priority 3                    ┌────────────────▼──────────────────────────────┐           │
│   FAMILY GROUP            ───▶  │ adults, kids, guests                         │           │
│                                 └───────────────────────────────────────────────┘           │
│                                                  │                                           │
│   Priority 4 (Highest)          ┌────────────────▼──────────────────────────────┐           │
│   INDIVIDUAL              ───▶  │ thom, elizabeth, penelope, etc.              │           │
│                                 └───────────────────────────────────────────────┘           │
│                                                  │                                           │
│                                                  ▼                                           │
│                                 ┌───────────────────────────────────────────────┐           │
│                                 │       EFFECTIVE CONFIGURATION                 │           │
│                                 └───────────────────────────────────────────────┘           │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Merge Strategy

Following SkyrimNet's pattern, overrides use **deep merge with replacement**:

| Strategy | Behavior | Example |
|----------|----------|---------|
| **Scalar values** | Later wins | `temperature: 0.7` overwrites `0.5` |
| **Lists** | Later replaces entirely | `topics: ["a"]` replaces `["b", "c"]` |
| **Dicts** | Recursive deep merge | Nested keys merge independently |
| **Null values** | Explicitly removes key | `proactive_suggestions: null` disables |

### Conditional Override Application

Some overrides apply only when conditions are met (similar to SkyrimNet's eligibility checks):

```yaml
# Room override with time-based sub-condition
rooms:
  office:
    # Base room settings (always apply when in office)
    response_style: "professional"
    
    # Conditional overrides within room context
    conditions:
      during_work_hours:
        when: "{{ is_work_hours() }}"
        proactive_suggestions: false
        interruption_threshold: "urgent_only"
      after_hours:
        when: "{{ not is_work_hours() }}"
        proactive_suggestions: true
        response_style: "casual"
```

---

## YAML Schema Definition

### Master Override Configuration File

```yaml
# config/overrides/overrides.yaml
# Master override configuration for BarnabeeNet
# All overrides follow cascading priority: base → time → room → group → individual

schema_version: "1.0"
last_updated: "2026-01-17"

# ==============================================================================
# BASE DEFAULTS (Priority 0)
# These apply when no other override matches
# ==============================================================================
base_defaults:
  # Response Generation
  response_style: "friendly_helpful"  # friendly_helpful, technical_detailed, simple_playful, formal, casual
  llm_temperature: 0.7
  max_response_length: 150            # Words
  response_format: "natural"          # natural, structured, brief
  
  # Content Filtering
  content_restrictions: []            # age_appropriate, no_violence, no_profanity, etc.
  allowed_topics: "all"               # all, or list of allowed topics
  blocked_topics: []                  # Topics to never discuss
  
  # Proactive Behavior
  proactive_suggestions: true
  proactive_frequency: "normal"       # none, minimal, normal, frequent
  interruption_threshold: "normal"    # none, urgent_only, important, normal, any
  
  # Voice & Audio
  voice_responses: true
  voice_volume: "normal"              # quiet, normal, loud
  voice_speed: "normal"               # slow, normal, fast
  tts_voice: "default"                # Voice model identifier
  
  # Output Routing
  notifications: "all"                # all, visual_only, audio_only, none
  output_devices: "auto"              # auto, or list of specific devices
  
  # Model Selection
  use_model: "default"                # default, fast_local, quality_cloud
  model_fallback: true                # Fall back to local if cloud unavailable
  
  # Memory & Context
  include_memories: true
  memory_retrieval_count: 5
  include_calendar: true
  include_recent_events: true
  recent_events_count: 20
  
  # Confirmation Requirements
  require_confirmation: ["security", "purchase", "schedule"]
  high_risk_actions: ["lock", "alarm", "garage", "payment"]
```

### JSON Schema for Validation

```yaml
# config/schemas/override_schema.yaml
$schema: "http://json-schema.org/draft-07/schema#"
title: "BarnabeeNet Override Configuration Schema"
type: object

definitions:
  response_style:
    type: string
    enum:
      - "friendly_helpful"
      - "technical_detailed"
      - "simple_playful"
      - "formal"
      - "casual"
      - "brief"
      - "professional"
      - "encouraging_educational"

  vocabulary_level:
    type: string
    enum:
      - "advanced"
      - "normal"
      - "simple"
      - "age_appropriate"
      - "very_simple"
      - "toddler"

  content_restriction:
    type: string
    enum:
      - "age_appropriate"
      - "age_appropriate_12"
      - "age_appropriate_9"
      - "age_appropriate_6"
      - "toddler_safe"
      - "no_violence"
      - "no_profanity"
      - "family_friendly"
      - "educational_focus"
      - "no_personal_info"
      - "very_simple"

  interruption_threshold:
    type: string
    enum:
      - "none"
      - "urgent_only"
      - "important"
      - "normal"
      - "any"

  voice_volume:
    type: string
    enum:
      - "quiet"
      - "normal"
      - "loud"

  notification_mode:
    type: string
    enum:
      - "all"
      - "visual_only"
      - "audio_only"
      - "none"

  time_range:
    type: string
    pattern: "^([01]?[0-9]|2[0-3]):[0-5][0-9]-([01]?[0-9]|2[0-3]):[0-5][0-9]$"

  day_of_week:
    type: string
    enum:
      - "monday"
      - "tuesday"
      - "wednesday"
      - "thursday"
      - "friday"
      - "saturday"
      - "sunday"
```

---

## Family Member Overrides

### Family Groups (Priority 3)

```yaml
# ==============================================================================
# FAMILY MEMBER GROUP OVERRIDES (Priority 3)
# ==============================================================================
family_groups:
  adults:
    description: "Adult family members"
    members: ["thom", "elizabeth"]
    
    response_style: "friendly_helpful"
    content_restrictions: []
    max_response_length: 200
    include_memories: true
    
    # Adults can access everything
    allowed_actions: "all"
    require_confirmation: ["security", "purchase"]

  kids:
    description: "Children in the household"
    members: ["penelope", "xander", "zachary", "viola"]
    
    response_style: "simple_playful"
    content_restrictions: ["age_appropriate", "no_violence", "educational_focus"]
    max_response_length: 50
    llm_temperature: 0.5              # More predictable responses
    
    # Limited action permissions
    allowed_actions: ["lights", "music", "temperature_minor", "information"]
    blocked_actions: ["locks", "garage", "alarm", "purchases", "adult_content"]
    
    # Response transformations
    vocabulary_level: "simple"        # Use simple words
    avoid_concepts: ["death", "violence", "adult_themes"]
    
    # Proactive settings
    proactive_topics: ["homework_reminders", "bedtime", "chores", "encouragement"]

  guests:
    description: "Visitors to the home"
    members: []                       # Dynamically populated
    
    response_style: "formal"
    content_restrictions: ["family_friendly", "no_personal_info"]
    max_response_length: 100
    
    # Very limited permissions
    allowed_actions: ["lights", "temperature_minor", "information_public"]
    blocked_actions: ["locks", "garage", "cameras", "personal_calendars", "family_memories"]
    
    # Don't reveal family information
    include_memories: false
    include_calendar: false
    privacy_mode: true
```

### Individual Family Members (Priority 4 - Highest)

```yaml
# ==============================================================================
# INDIVIDUAL FAMILY MEMBER OVERRIDES (Priority 4 - Highest)
# ==============================================================================
family_members:
  thom:
    description: "Thom - Head of household, tech-oriented"
    speaker_id: "thom_fife"           # Maps to speaker recognition model
    person_entity: "person.thom"      # Home Assistant person entity
    
    # Personal preferences
    response_style: "technical_detailed"
    llm_temperature: 0.7
    topics_of_interest: ["woodworking", "technology", "home_automation", "ai", "smart_home"]
    
    # Full permissions
    allowed_actions: "all"
    is_admin: true
    can_modify_overrides: true
    
    # Context preferences
    include_memories: true
    memory_retrieval_count: 8         # More context for complex queries
    
    # Proactive preferences
    proactive_topics: ["calendar", "home_maintenance", "technology_news", "project_reminders"]
    
    # Output preferences
    preferred_output_device: "office_speaker"
    fallback_output: "nearest"

  elizabeth:
    description: "Elizabeth - Mom, detail-oriented"
    speaker_id: "elizabeth_fife"
    person_entity: "person.elizabeth"
    
    response_style: "friendly_helpful"
    llm_temperature: 0.6
    topics_of_interest: ["family", "cooking", "organization", "kids_activities", "health"]
    
    allowed_actions: "all"
    is_admin: true
    
    proactive_topics: ["family_calendar", "meal_planning", "kids_school", "appointments"]
    
    # Specific preferences
    calendar_detail_level: "high"     # Full event details
    include_kids_calendars: true

  penelope:
    description: "Penelope - Oldest child"
    speaker_id: "penelope_fife"
    person_entity: "person.penelope"
    age: 12
    
    response_style: "encouraging_educational"
    llm_temperature: 0.5
    topics_of_interest: ["books", "art", "music", "animals"]
    
    # Age-appropriate content
    content_restrictions: ["age_appropriate_12"]
    vocabulary_level: "age_appropriate"
    max_response_length: 75
    
    # Limited but expanded permissions for oldest
    allowed_actions: ["lights", "music", "temperature_minor", "information", "homework_help"]
    
    # Homework help settings
    homework_mode:
      enabled: true
      subjects: ["math", "science", "english", "history"]
      provide_answers: false          # Guide, don't give answers
      
    proactive_topics: ["homework_reminders", "reading_time", "activity_reminders"]

  xander:
    description: "Xander - Middle child"
    speaker_id: "xander_fife"
    person_entity: "person.xander"
    age: 9
    
    response_style: "simple_playful"
    llm_temperature: 0.5
    topics_of_interest: ["sports", "games", "dinosaurs", "space"]
    
    content_restrictions: ["age_appropriate_9"]
    vocabulary_level: "simple"
    max_response_length: 50
    
    allowed_actions: ["lights", "music_kids", "information_educational"]
    
    proactive_topics: ["homework", "bedtime", "chores"]

  zachary:
    description: "Zachary - Young child"
    speaker_id: "zachary_fife"
    person_entity: "person.zachary"
    age: 6
    
    response_style: "simple_playful"
    llm_temperature: 0.4              # Very predictable
    topics_of_interest: ["cartoons", "animals", "superheroes"]
    
    content_restrictions: ["age_appropriate_6", "very_simple"]
    vocabulary_level: "very_simple"
    max_response_length: 30
    
    allowed_actions: ["lights_own_room", "music_kids"]
    
    # Special handling
    always_confirm_before_action: true
    encourage_politeness: true        # Remind to say please/thank you

  viola:
    description: "Viola - Toddler"
    speaker_id: "viola_fife"
    person_entity: "person.viola"
    age: 2
    
    response_style: "simple_playful"
    llm_temperature: 0.3
    
    content_restrictions: ["toddler_safe"]
    vocabulary_level: "toddler"
    max_response_length: 15
    
    # Toddler can't really give commands, but might be recognized
    allowed_actions: []               # No actions for toddler
    
    # When toddler detected, likely need parent
    alert_parent_on_interaction: true
    interaction_response: "playful_acknowledgment"
```

---

## Room Overrides

### Room Configuration (Priority 2)

```yaml
# ==============================================================================
# ROOM OVERRIDES (Priority 2)
# ==============================================================================
rooms:
  office:
    description: "Thom's home office"
    entity_area: "office"             # Home Assistant area mapping
    
    # Base room settings
    response_style: "professional"
    include_calendar: true
    
    # Time-conditional sub-overrides
    conditions:
      during_work_hours:
        when: "{{ is_work_hours() and is_weekday() }}"
        proactive_suggestions: false
        interruption_threshold: "urgent_only"
        response_style: "technical_detailed"
      after_hours:
        when: "{{ not is_work_hours() or not is_weekday() }}"
        proactive_suggestions: true
        response_style: "casual"

  nursery:
    description: "Baby's room - always quiet"
    entity_area: "nursery"
    
    voice_volume: "quiet"
    notifications: "visual_only"
    proactive_suggestions: false
    voice_responses: false            # Use visual only in nursery
    
    # Context-aware exceptions
    conditions:
      baby_awake:
        when: "{{ states('binary_sensor.nursery_motion') == 'on' and is_daytime() }}"
        voice_responses: true
        voice_volume: "quiet"

  kids_bedroom:
    description: "Children's shared bedroom"
    entity_area: "kids_bedroom"
    
    response_style: "simple_playful"
    content_restrictions: ["age_appropriate"]
    max_response_length: 50
    
    conditions:
      bedtime:
        when: "{{ current_hour >= 20 or current_hour < 7 }}"
        voice_volume: "quiet"
        proactive_suggestions: false

  master_bedroom:
    description: "Parents' bedroom"
    entity_area: "master_bedroom"
    
    voice_volume: "quiet"
    proactive_suggestions: false
    
    conditions:
      sleep_time:
        when: "{{ current_hour >= 22 or current_hour < 6 }}"
        voice_responses: false
        notifications: "none"

  living_room:
    description: "Main family gathering space"
    entity_area: "living_room"
    
    response_style: "friendly_helpful"
    voice_volume: "normal"
    
    conditions:
      movie_mode:
        when: "{{ states('media_player.living_room_tv') == 'playing' }}"
        voice_volume: "quiet"
        proactive_suggestions: false
      guests_present:
        when: "{{ 'guest' in occupants() }}"
        response_style: "formal"
        content_restrictions: ["family_friendly"]

  kitchen:
    description: "Kitchen and cooking area"
    entity_area: "kitchen"
    
    response_style: "helpful_concise"
    proactive_suggestions: true
    
    # Kitchen-specific allowed proactive topics
    proactive_topics: ["timers", "recipes", "grocery", "meal_planning"]

  garage:
    description: "Garage and workshop"
    entity_area: "garage"
    
    voice_volume: "loud"              # May be noisy
    response_style: "brief"
    
    conditions:
      vehicle_running:
        when: "{{ states('binary_sensor.garage_car_presence') == 'on' }}"
        voice_responses: false        # Don't compete with engine noise

  bathroom_master:
    description: "Master bathroom - privacy zone"
    entity_area: "bathroom_master"
    privacy_zone: true
    
    voice_responses: false            # Privacy - no audio
    notifications: "none"
    proactive_suggestions: false

  bathroom_kids:
    description: "Kids' bathroom - safety focus"
    entity_area: "bathroom_kids"
    privacy_zone: true
    
    voice_responses: false
    notifications: "visual_only"
    
    # Exception for safety
    conditions:
      water_running_long:
        when: "{{ states('sensor.kids_bath_water_flow') == 'on' and state_duration('sensor.kids_bath_water_flow', 'on') > 900 }}"
        proactive_suggestions: true
        voice_responses: true         # Override for safety alert
```

---

## Time Period Overrides

### Time-Based Configuration (Priority 1)

```yaml
# ==============================================================================
# TIME PERIOD OVERRIDES (Priority 1)
# ==============================================================================
time_periods:
  night_mode:
    description: "Quiet hours for sleeping household"
    active_hours: "22:00-06:00"
    active_days: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    # Override values
    proactive_suggestions: false
    voice_responses: false
    notifications: "visual_only"
    voice_volume: "quiet"
    use_model: "fast_local"           # Minimize latency, avoid cloud
    interruption_threshold: "urgent_only"
    
    # Exceptions (urgent items bypass night_mode)
    exceptions:
      security_alerts: true
      smoke_fire_alerts: true
      medical_alerts: true

  early_morning:
    description: "Quiet transition period"
    active_hours: "06:00-07:30"
    active_days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    voice_volume: "quiet"
    proactive_suggestions: true
    proactive_frequency: "minimal"
    response_style: "brief"

  work_hours:
    description: "Business hours configuration"
    active_hours: "09:00-17:00"
    active_days: ["monday", "tuesday", "wednesday", "thursday", "friday"]
    
    response_style: "professional"
    proactive_frequency: "minimal"
    # Other settings inherit from base

  weekend_mode:
    description: "Relaxed weekend configuration"
    active_hours: "00:00-23:59"
    active_days: ["saturday", "sunday"]
    
    response_style: "casual"
    proactive_frequency: "normal"
    interruption_threshold: "normal"

  deep_focus:
    description: "Do not disturb mode - manually activated"
    manual_activation: true           # Not time-based, activated by command
    
    proactive_suggestions: false
    interruption_threshold: "urgent_only"
    notifications: "none"
    voice_responses: false
```

---

## Override Resolution Engine

### Core Data Structures

```python
# barnabeenet/core/overrides/models.py
"""Data models for the Override System."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Literal

class ResponseStyle(str, Enum):
    """Available response styles."""
    FRIENDLY_HELPFUL = "friendly_helpful"
    TECHNICAL_DETAILED = "technical_detailed"
    SIMPLE_PLAYFUL = "simple_playful"
    FORMAL = "formal"
    CASUAL = "casual"
    BRIEF = "brief"
    PROFESSIONAL = "professional"
    ENCOURAGING_EDUCATIONAL = "encouraging_educational"

class VocabularyLevel(str, Enum):
    """Vocabulary complexity levels."""
    ADVANCED = "advanced"
    NORMAL = "normal"
    SIMPLE = "simple"
    AGE_APPROPRIATE = "age_appropriate"
    VERY_SIMPLE = "very_simple"
    TODDLER = "toddler"

class InterruptionThreshold(str, Enum):
    """When to interrupt the user."""
    NONE = "none"
    URGENT_ONLY = "urgent_only"
    IMPORTANT = "important"
    NORMAL = "normal"
    ANY = "any"

class VoiceVolume(str, Enum):
    """Voice output volume levels."""
    QUIET = "quiet"
    NORMAL = "normal"
    LOUD = "loud"

class NotificationMode(str, Enum):
    """Notification delivery modes."""
    ALL = "all"
    VISUAL_ONLY = "visual_only"
    AUDIO_ONLY = "audio_only"
    NONE = "none"

@dataclass
class TimeRange:
    """Represents a time range (e.g., 22:00-06:00)."""
    start: time
    end: time
    
    @classmethod
    def from_string(cls, time_str: str) -> TimeRange:
        """Parse from 'HH:MM-HH:MM' format."""
        start_str, end_str = time_str.split("-")
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        return cls(start=start, end=end)
    
    def contains(self, check_time: time) -> bool:
        """Check if time falls within range (handles overnight spans)."""
        if self.start <= self.end:
            # Normal range (e.g., 09:00-17:00)
            return self.start <= check_time <= self.end
        else:
            # Overnight range (e.g., 22:00-06:00)
            return check_time >= self.start or check_time <= self.end

@dataclass
class EffectiveConfig:
    """The resolved configuration after applying all overrides."""
    # Response Generation
    response_style: ResponseStyle = ResponseStyle.FRIENDLY_HELPFUL
    llm_temperature: float = 0.7
    max_response_length: int = 150
    response_format: str = "natural"
    
    # Content Filtering
    content_restrictions: list[str] = field(default_factory=list)
    allowed_topics: str | list[str] = "all"
    blocked_topics: list[str] = field(default_factory=list)
    
    # Proactive Behavior
    proactive_suggestions: bool = True
    proactive_frequency: str = "normal"
    proactive_topics: list[str] = field(default_factory=list)
    interruption_threshold: InterruptionThreshold = InterruptionThreshold.NORMAL
    
    # Voice & Audio
    voice_responses: bool = True
    voice_volume: VoiceVolume = VoiceVolume.NORMAL
    voice_speed: str = "normal"
    tts_voice: str = "default"
    
    # Output Routing
    notifications: NotificationMode = NotificationMode.ALL
    output_devices: str | list[str] = "auto"
    preferred_output_device: str | None = None
    
    # Model Selection
    use_model: str = "default"
    model_fallback: bool = True
    
    # Memory & Context
    include_memories: bool = True
    memory_retrieval_count: int = 5
    include_calendar: bool = True
    include_recent_events: bool = True
    recent_events_count: int = 20
    
    # Permissions
    allowed_actions: str | list[str] = "all"
    blocked_actions: list[str] = field(default_factory=list)
    require_confirmation: list[str] = field(default_factory=list)
    
    # Response Transformation
    vocabulary_level: VocabularyLevel = VocabularyLevel.NORMAL
    avoid_concepts: list[str] = field(default_factory=list)
    
    # User Context
    topics_of_interest: list[str] = field(default_factory=list)
    is_admin: bool = False
    privacy_mode: bool = False
    
    # Resolution Metadata (for debugging/logging)
    applied_overrides: list[str] = field(default_factory=list)
    resolution_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ResolutionContext:
    """Context for resolving overrides."""
    speaker_id: str | None = None
    room_id: str | None = None
    current_time: datetime = field(default_factory=datetime.now)
    manual_modes: list[str] = field(default_factory=list)  # e.g., ["deep_focus"]
    home_state: dict[str, Any] = field(default_factory=dict)  # For Jinja2 conditions
```

### Override Resolution Engine

```python
# barnabeenet/core/overrides/resolver.py
"""Override Resolution Engine - merges configuration layers by priority."""

from __future__ import annotations

import copy
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, BaseLoader

from .models import (
    EffectiveConfig,
    ResolutionContext,
    TimeRange,
    ResponseStyle,
    VocabularyLevel,
    InterruptionThreshold,
    VoiceVolume,
    NotificationMode,
)

_LOGGER = logging.getLogger(__name__)

class OverrideResolver:
    """
    Resolves effective configuration by merging override layers.
    
    Priority order (lowest to highest):
    0. Base defaults
    1. Time periods
    2. Room overrides
    3. Family group overrides
    4. Individual family member overrides
    """
    
    def __init__(self, config_path: Path | str):
        """Initialize with path to overrides.yaml."""
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._jinja_env = Environment(loader=BaseLoader())
        self._load_config()
    
    def _load_config(self) -> None:
        """Load and parse the override configuration file."""
        with open(self.config_path) as f:
            self._config = yaml.safe_load(f)
        _LOGGER.info(f"Loaded override config v{self._config.get('schema_version')}")
    
    def reload_config(self) -> None:
        """Hot-reload configuration (called on file change)."""
        self._load_config()
        _LOGGER.info("Override configuration reloaded")
    
    def resolve(self, context: ResolutionContext) -> EffectiveConfig:
        """
        Resolve the effective configuration for the given context.
        
        Args:
            context: Resolution context containing speaker, room, time, etc.
            
        Returns:
            EffectiveConfig with all applicable overrides merged.
        """
        # Start with base defaults
        merged = self._get_base_defaults()
        applied = ["base_defaults"]
        
        # Layer 1: Time period overrides
        time_overrides = self._get_active_time_overrides(context)
        for name, override in time_overrides.items():
            merged = self._deep_merge(merged, override)
            applied.append(f"time:{name}")
        
        # Layer 2: Room overrides
        if context.room_id:
            room_override = self._get_room_override(context)
            if room_override:
                merged = self._deep_merge(merged, room_override)
                applied.append(f"room:{context.room_id}")
        
        # Layer 3: Family group overrides
        if context.speaker_id:
            group_override = self._get_group_override(context.speaker_id)
            if group_override:
                group_name, override = group_override
                merged = self._deep_merge(merged, override)
                applied.append(f"group:{group_name}")
        
        # Layer 4: Individual overrides (highest priority)
        if context.speaker_id:
            individual_override = self._get_individual_override(context.speaker_id)
            if individual_override:
                merged = self._deep_merge(merged, individual_override)
                applied.append(f"individual:{context.speaker_id}")
        
        # Convert merged dict to EffectiveConfig
        config = self._dict_to_config(merged)
        config.applied_overrides = applied
        config.resolution_timestamp = context.current_time
        
        _LOGGER.debug(
            f"Resolved config for speaker={context.speaker_id}, "
            f"room={context.room_id}: {applied}"
        )
        
        return config
    
    def _get_base_defaults(self) -> dict[str, Any]:
        """Get base default configuration."""
        return copy.deepcopy(self._config.get("base_defaults", {}))
    
    def _get_active_time_overrides(
        self, context: ResolutionContext
    ) -> dict[str, dict[str, Any]]:
        """Get all active time period overrides."""
        active = {}
        current_time = context.current_time.time()
        current_day = context.current_time.strftime("%A").lower()
        
        time_periods = self._config.get("time_periods", {})
        
        for name, period in time_periods.items():
            # Check manual activation modes
            if period.get("manual_activation"):
                if name in context.manual_modes:
                    active[name] = self._extract_override_values(period)
                continue
            
            # Check time range
            time_range = TimeRange.from_string(period["active_hours"])
            if not time_range.contains(current_time):
                continue
            
            # Check active days
            active_days = period.get("active_days", [
                "monday", "tuesday", "wednesday", 
                "thursday", "friday", "saturday", "sunday"
            ])
            if current_day not in active_days:
                continue
            
            active[name] = self._extract_override_values(period)
        
        return active
    
    def _get_room_override(self, context: ResolutionContext) -> dict[str, Any] | None:
        """Get room override with conditional sub-overrides evaluated."""
        rooms = self._config.get("rooms", {})
        room_config = rooms.get(context.room_id)
        
        if not room_config:
            return None
        
        # Start with base room settings
        override = self._extract_override_values(room_config)
        
        # Evaluate conditional sub-overrides
        conditions = room_config.get("conditions", {})
        for cond_name, cond_config in conditions.items():
            condition_expr = cond_config.get("when", "")
            if self._evaluate_condition(condition_expr, context):
                cond_override = self._extract_override_values(cond_config)
                override = self._deep_merge(override, cond_override)
                _LOGGER.debug(f"Room condition '{cond_name}' matched for {context.room_id}")
        
        return override
    
    def _get_group_override(
        self, speaker_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        """Get family group override for speaker."""
        groups = self._config.get("family_groups", {})
        
        for group_name, group_config in groups.items():
            members = group_config.get("members", [])
            # Check if speaker is in this group (by speaker_id or name)
            if speaker_id in members or self._speaker_in_group(speaker_id, members):
                return group_name, self._extract_override_values(group_config)
        
        return None
    
    def _speaker_in_group(self, speaker_id: str, members: list[str]) -> bool:
        """Check if speaker_id matches any member in the group."""
        # Look up speaker_id in family_members to get their name
        family_members = self._config.get("family_members", {})
        for member_name, member_config in family_members.items():
            if member_config.get("speaker_id") == speaker_id:
                return member_name in members
        return False
    
    def _get_individual_override(self, speaker_id: str) -> dict[str, Any] | None:
        """Get individual family member override."""
        family_members = self._config.get("family_members", {})
        
        # First try direct lookup by speaker_id
        for member_name, member_config in family_members.items():
            if member_config.get("speaker_id") == speaker_id:
                return self._extract_override_values(member_config)
        
        # Fall back to name lookup
        if speaker_id in family_members:
            return self._extract_override_values(family_members[speaker_id])
        
        return None
    
    def _extract_override_values(self, config: dict[str, Any]) -> dict[str, Any]:
        """Extract only the override values, excluding metadata."""
        excluded_keys = {
            "description", "active_hours", "active_days", "manual_activation",
            "exceptions", "members", "entity_area", "privacy_zone", "conditions",
            "when", "speaker_id", "person_entity", "age", "homework_mode"
        }
        return {k: v for k, v in config.items() if k not in excluded_keys}
    
    def _evaluate_condition(
        self, condition_expr: str, context: ResolutionContext
    ) -> bool:
        """Evaluate a Jinja2 condition expression."""
        if not condition_expr:
            return True
        
        try:
            # Build template context
            template_context = {
                "current_hour": context.current_time.hour,
                "current_minute": context.current_time.minute,
                "current_day": context.current_time.strftime("%A").lower(),
                "is_weekday": lambda: context.current_time.weekday() < 5,
                "is_weekend": lambda: context.current_time.weekday() >= 5,
                "is_daytime": lambda: 6 <= context.current_time.hour < 22,
                "is_work_hours": lambda: (
                    context.current_time.weekday() < 5 and
                    9 <= context.current_time.hour < 17
                ),
                "states": lambda entity: context.home_state.get(entity, "unknown"),
                "occupants": lambda: context.home_state.get("occupants", []),
                "state_duration": lambda entity, state: context.home_state.get(
                    f"{entity}_duration_{state}", 0
                ),
            }
            
            # Compile and render template
            template = self._jinja_env.from_string(f"{{{{ {condition_expr} }}}}")
            result = template.render(**template_context)
            
            return result.lower() in ("true", "1", "yes")
            
        except Exception as e:
            _LOGGER.warning(f"Failed to evaluate condition '{condition_expr}': {e}")
            return False
    
    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Rules:
        - Scalar values: override wins
        - Lists: override replaces entirely
        - Dicts: recursive merge
        - None/null: explicitly removes key
        """
        result = copy.deepcopy(base)
        
        for key, value in override.items():
            if value is None:
                # Explicit removal
                result.pop(key, None)
            elif isinstance(value, dict) and isinstance(result.get(key), dict):
                # Recursive merge for nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Direct replacement for scalars and lists
                result[key] = copy.deepcopy(value)
        
        return result
    
    def _dict_to_config(self, merged: dict[str, Any]) -> EffectiveConfig:
        """Convert merged dictionary to EffectiveConfig dataclass."""
        # Handle enum conversions
        if "response_style" in merged:
            try:
                merged["response_style"] = ResponseStyle(merged["response_style"])
            except ValueError:
                merged["response_style"] = ResponseStyle.FRIENDLY_HELPFUL
        
        if "vocabulary_level" in merged:
            try:
                merged["vocabulary_level"] = VocabularyLevel(merged["vocabulary_level"])
            except ValueError:
                merged["vocabulary_level"] = VocabularyLevel.NORMAL
        
        if "interruption_threshold" in merged:
            try:
                merged["interruption_threshold"] = InterruptionThreshold(
                    merged["interruption_threshold"]
                )
            except ValueError:
                merged["interruption_threshold"] = InterruptionThreshold.NORMAL
        
        if "voice_volume" in merged:
            try:
                merged["voice_volume"] = VoiceVolume(merged["voice_volume"])
            except ValueError:
                merged["voice_volume"] = VoiceVolume.NORMAL
        
        if "notifications" in merged:
            try:
                merged["notifications"] = NotificationMode(merged["notifications"])
            except ValueError:
                merged["notifications"] = NotificationMode.ALL
        
        # Create config with only valid fields
        valid_fields = {f.name for f in EffectiveConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in merged.items() if k in valid_fields}
        
        return EffectiveConfig(**filtered)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_family_member_by_speaker_id(self, speaker_id: str) -> str | None:
        """Look up family member name from speaker ID."""
        family_members = self._config.get("family_members", {})
        for name, config in family_members.items():
            if config.get("speaker_id") == speaker_id:
                return name
        return None
    
    def get_room_by_area(self, area: str) -> str | None:
        """Look up room name from Home Assistant area."""
        rooms = self._config.get("rooms", {})
        for name, config in rooms.items():
            if config.get("entity_area") == area:
                return name
        return None
    
    def is_privacy_zone(self, room_id: str) -> bool:
        """Check if a room is marked as a privacy zone."""
        rooms = self._config.get("rooms", {})
        room_config = rooms.get(room_id, {})
        return room_config.get("privacy_zone", False)
    
    def get_all_family_members(self) -> list[str]:
        """Get list of all configured family member IDs."""
        return list(self._config.get("family_members", {}).keys())
```

### File Watcher for Hot-Reload

```python
# barnabeenet/core/overrides/watcher.py
"""File watcher for hot-reloading override configuration."""

import asyncio
import logging
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

_LOGGER = logging.getLogger(__name__)

class OverrideConfigHandler(FileSystemEventHandler):
    """Handles file change events for override config."""
    
    def __init__(self, callback: Callable[[], None], debounce_seconds: float = 1.0):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_modified = 0.0
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification event."""
        if event.is_directory:
            return
        
        import time
        current_time = time.time()
        
        # Debounce rapid changes
        if current_time - self._last_modified < self.debounce_seconds:
            return
        
        self._last_modified = current_time
        
        _LOGGER.info(f"Override config modified: {event.src_path}")
        try:
            self.callback()
        except Exception as e:
            _LOGGER.error(f"Error reloading override config: {e}")

class OverrideConfigWatcher:
    """Watches override configuration files for changes."""
    
    def __init__(self, config_path: Path, reload_callback: Callable[[], None]):
        self.config_path = config_path
        self.reload_callback = reload_callback
        self._observer: Observer | None = None
    
    def start(self) -> None:
        """Start watching for config changes."""
        handler = OverrideConfigHandler(self.reload_callback)
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.config_path.parent),
            recursive=False
        )
        self._observer.start()
        _LOGGER.info(f"Started watching override config: {self.config_path}")
    
    def stop(self) -> None:
        """Stop watching for config changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            _LOGGER.info("Stopped override config watcher")
```

---

## Response Transformer

The Response Transformer adapts Barnabee's raw response based on the listener's profile.

```python
# barnabeenet/core/overrides/transformer.py
"""Response Transformer - adapts responses based on listener profile."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .models import EffectiveConfig, VocabularyLevel, ResponseStyle

_LOGGER = logging.getLogger(__name__)

# Word complexity mappings (simple alternatives for complex words)
VOCABULARY_SIMPLIFICATIONS = {
    VocabularyLevel.TODDLER: {
        "temperature": "how warm",
        "illuminate": "turn on lights",
        "activate": "turn on",
        "deactivate": "turn off",
        "approximately": "about",
        "subsequently": "then",
        "however": "but",
        "therefore": "so",
        "additionally": "also",
        "refrigerator": "fridge",
        "thermostat": "temperature thing",
        "humidity": "wetness",
        "schedule": "plan",
        "notification": "message",
        "configuration": "settings",
    },
    VocabularyLevel.VERY_SIMPLE: {
        "temperature": "how warm it is",
        "illuminate": "turn on",
        "activate": "turn on",
        "deactivate": "turn off",
        "approximately": "about",
        "subsequently": "then",
        "however": "but",
        "therefore": "so",
        "additionally": "and",
        "configuration": "settings",
    },
    VocabularyLevel.SIMPLE: {
        "illuminate": "turn on",
        "approximately": "about",
        "subsequently": "then",
        "configuration": "settings",
    },
}

# Response style templates
STYLE_ADJUSTMENTS = {
    ResponseStyle.SIMPLE_PLAYFUL: {
        "affirmations": ["Okay!", "Sure thing!", "You got it!", "Absolutely!"],
        "add_emoji": True,
        "use_exclamations": True,
    },
    ResponseStyle.TECHNICAL_DETAILED: {
        "affirmations": ["Acknowledged.", "Understood.", "Processing."],
        "add_emoji": False,
        "include_details": True,
    },
    ResponseStyle.FORMAL: {
        "affirmations": ["Certainly.", "Of course.", "Very well."],
        "add_emoji": False,
        "polite_phrasing": True,
    },
    ResponseStyle.BRIEF: {
        "affirmations": ["Done.", "OK.", "Got it."],
        "add_emoji": False,
        "minimize_words": True,
    },
    ResponseStyle.ENCOURAGING_EDUCATIONAL: {
        "affirmations": ["Great question!", "Let's figure this out!", "Wonderful!"],
        "add_emoji": True,
        "explain_why": True,
    },
}

# Content filtering patterns
CONTENT_FILTERS = {
    "age_appropriate": {
        "blocked_patterns": [
            r"\b(damn|hell|crap)\b",
            r"\b(kill|murder|death)\b",
            r"\b(stupid|idiot|dumb)\b",
        ],
        "replacements": {
            "died": "passed away",
            "dead": "no longer alive",
            "kill": "stop",
        },
    },
    "age_appropriate_6": {
        "blocked_patterns": [
            r"\b(scary|frightening|terrifying)\b",
            r"\b(monster|ghost|demon)\b",
        ],
        "replacements": {
            "scary": "surprising",
            "monster": "creature",
        },
    },
    "toddler_safe": {
        "blocked_patterns": [
            r"\b(no|don't|can't|won't|stop)\b",  # Reframe negatives
        ],
        "replacements": {},
    },
}

@dataclass
class TransformationResult:
    """Result of response transformation."""
    original: str
    transformed: str
    modifications: list[str]
    truncated: bool
    word_count: int

class ResponseTransformer:
    """
    Transforms responses based on effective configuration.
    
    Transformations applied:
    1. Vocabulary simplification
    2. Length enforcement
    3. Style adaptation
    4. Content filtering
    5. Concept avoidance
    """
    
    def transform(
        self, response: str, config: EffectiveConfig
    ) -> TransformationResult:
        """
        Transform a response based on the effective configuration.
        
        Args:
            response: Raw response from the LLM
            config: Effective configuration with transformations to apply
            
        Returns:
            TransformationResult with transformed text and metadata
        """
        modifications = []
        transformed = response
        
        # 1. Vocabulary simplification
        if config.vocabulary_level != VocabularyLevel.NORMAL:
            transformed, vocab_mods = self._simplify_vocabulary(
                transformed, config.vocabulary_level
            )
            modifications.extend(vocab_mods)
        
        # 2. Concept avoidance
        if config.avoid_concepts:
            transformed, avoid_mods = self._avoid_concepts(
                transformed, config.avoid_concepts
            )
            modifications.extend(avoid_mods)
        
        # 3. Content filtering
        if config.content_restrictions:
            transformed, filter_mods = self._apply_content_filters(
                transformed, config.content_restrictions
            )
            modifications.extend(filter_mods)
        
        # 4. Style adaptation
        transformed, style_mods = self._adapt_style(transformed, config.response_style)
        modifications.extend(style_mods)
        
        # 5. Length enforcement (last, after other transformations)
        truncated = False
        word_count = len(transformed.split())
        
        if word_count > config.max_response_length:
            transformed, truncated = self._enforce_length(
                transformed, config.max_response_length
            )
            if truncated:
                modifications.append(
                    f"truncated from {word_count} to {config.max_response_length} words"
                )
        
        return TransformationResult(
            original=response,
            transformed=transformed,
            modifications=modifications,
            truncated=truncated,
            word_count=len(transformed.split()),
        )
    
    def _simplify_vocabulary(
        self, text: str, level: VocabularyLevel
    ) -> tuple[str, list[str]]:
        """Replace complex words with simpler alternatives."""
        modifications = []
        result = text
        
        # Get all simplifications for this level and below
        simplifications = {}
        levels_to_apply = []
        
        if level == VocabularyLevel.TODDLER:
            levels_to_apply = [
                VocabularyLevel.SIMPLE,
                VocabularyLevel.VERY_SIMPLE,
                VocabularyLevel.TODDLER,
            ]
        elif level == VocabularyLevel.VERY_SIMPLE:
            levels_to_apply = [VocabularyLevel.SIMPLE, VocabularyLevel.VERY_SIMPLE]
        elif level == VocabularyLevel.SIMPLE:
            levels_to_apply = [VocabularyLevel.SIMPLE]
        
        for lvl in levels_to_apply:
            simplifications.update(VOCABULARY_SIMPLIFICATIONS.get(lvl, {}))
        
        # Apply simplifications
        for complex_word, simple_word in simplifications.items():
            pattern = re.compile(rf"\b{complex_word}\b", re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(simple_word, result)
                modifications.append(f"simplified '{complex_word}' → '{simple_word}'")
        
        return result, modifications
    
    def _avoid_concepts(
        self, text: str, concepts: list[str]
    ) -> tuple[str, list[str]]:
        """Remove or rephrase sentences containing avoided concepts."""
        modifications = []
        sentences = self._split_sentences(text)
        filtered_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            should_remove = False
            
            for concept in concepts:
                if concept.lower() in sentence_lower:
                    should_remove = True
                    modifications.append(f"removed sentence containing '{concept}'")
                    break
            
            if not should_remove:
                filtered_sentences.append(sentence)
        
        # Ensure we have at least something
        if not filtered_sentences and sentences:
            filtered_sentences = ["I'm here to help!"]
            modifications.append("replaced all content (concept avoidance)")
        
        return " ".join(filtered_sentences), modifications
    
    def _apply_content_filters(
        self, text: str, restrictions: list[str]
    ) -> tuple[str, list[str]]:
        """Apply content filtering based on restrictions."""
        modifications = []
        result = text
        
        for restriction in restrictions:
            filter_config = CONTENT_FILTERS.get(restriction, {})
            
            # Apply blocked patterns
            for pattern in filter_config.get("blocked_patterns", []):
                regex = re.compile(pattern, re.IGNORECASE)
                if regex.search(result):
                    result = regex.sub("***", result)
                    modifications.append(f"filtered content ({restriction})")
            
            # Apply replacements
            for old, new in filter_config.get("replacements", {}).items():
                pattern = re.compile(rf"\b{old}\b", re.IGNORECASE)
                if pattern.search(result):
                    result = pattern.sub(new, result)
                    modifications.append(f"replaced '{old}' with '{new}'")
        
        return result, modifications
    
    def _adapt_style(
        self, text: str, style: ResponseStyle
    ) -> tuple[str, list[str]]:
        """Adapt response style."""
        modifications = []
        result = text
        
        style_config = STYLE_ADJUSTMENTS.get(style, {})
        
        # Add exclamations for playful style
        if style_config.get("use_exclamations"):
            # Add exclamation to first sentence if it ends with period
            result = re.sub(r"^([^.!?]+)\.", r"\1!", result, count=1)
            modifications.append("added exclamation (playful style)")
        
        # Minimize words for brief style
        if style_config.get("minimize_words"):
            # Remove filler phrases
            fillers = [
                r"\bI think\b",
                r"\bperhaps\b",
                r"\bmaybe\b",
                r"\bactually\b",
                r"\bjust\b",
                r"\breally\b",
                r"\bbasically\b",
            ]
            for filler in fillers:
                result = re.sub(filler, "", result, flags=re.IGNORECASE)
            
            # Clean up extra spaces
            result = re.sub(r"\s+", " ", result).strip()
            modifications.append("minimized filler words (brief style)")
        
        return result, modifications
    
    def _enforce_length(
        self, text: str, max_words: int
    ) -> tuple[str, bool]:
        """Enforce maximum word count, trying to end at sentence boundary."""
        words = text.split()
        
        if len(words) <= max_words:
            return text, False
        
        # Take max_words, then find last sentence boundary
        truncated_words = words[:max_words]
        truncated_text = " ".join(truncated_words)
        
        # Find last sentence ending
        last_period = truncated_text.rfind(".")
        last_exclaim = truncated_text.rfind("!")
        last_question = truncated_text.rfind("?")
        
        last_boundary = max(last_period, last_exclaim, last_question)
        
        if last_boundary > len(truncated_text) // 2:
            # Found a reasonable boundary
            return truncated_text[:last_boundary + 1], True
        else:
            # No good boundary, just truncate and add ellipsis
            return truncated_text + "...", True
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]
```

---

## Agent Integration

### Base Agent with Override Support

```python
# barnabeenet/agents/base.py (additions)
"""Base agent with override integration."""

from barnabeenet.core.overrides.resolver import OverrideResolver
from barnabeenet.core.overrides.transformer import ResponseTransformationPipeline
from barnabeenet.core.overrides.models import EffectiveConfig, ResolutionContext

class BaseAgent:
    """Base class for all agents with override support."""
    
    def __init__(self, override_resolver: OverrideResolver):
        self.override_resolver = override_resolver
        self.transform_pipeline = ResponseTransformationPipeline(override_resolver)
    
    def get_effective_config(
        self,
        speaker_id: str | None = None,
        room_id: str | None = None,
    ) -> EffectiveConfig:
        """Get the effective configuration for this context."""
        context = ResolutionContext(
            speaker_id=speaker_id,
            room_id=room_id,
        )
        return self.override_resolver.resolve(context)
    
    async def should_respond_proactively(
        self,
        speaker_id: str | None,
        room_id: str | None,
        urgency: str = "normal",
    ) -> bool:
        """Check if proactive response is allowed."""
        config = self.get_effective_config(speaker_id, room_id)
        
        if not config.proactive_suggestions:
            return False
        
        # Check interruption threshold
        urgency_levels = {
            "none": 0,
            "any": 1,
            "normal": 2,
            "important": 3,
            "urgent_only": 4,
        }
        
        threshold = urgency_levels.get(config.interruption_threshold.value, 2)
        urgency_level = urgency_levels.get(urgency, 2)
        
        return urgency_level >= threshold
    
    async def get_llm_config(
        self,
        speaker_id: str | None = None,
        room_id: str | None = None,
    ) -> dict:
        """Get LLM configuration for this context."""
        config = self.get_effective_config(speaker_id, room_id)
        
        return {
            "model": config.use_model,
            "temperature": config.llm_temperature,
            "max_tokens": self._estimate_max_tokens(config.max_response_length),
        }
    
    def _estimate_max_tokens(self, max_words: int) -> int:
        """Estimate token count from word count (1.3 tokens per word avg)."""
        return int(max_words * 1.3) + 50  # Buffer for variance
```

---

## Resolution Scenarios

### Scenario 1: Kid at Night in Nursery

```
Context:
  speaker_id: "zachary_fife"
  room_id: "nursery"
  time: 21:30 (night_mode active)

Resolution:
  Priority 0 (base): response_style=friendly_helpful, voice_responses=true
  Priority 1 (night_mode): voice_responses=false, voice_volume=quiet
  Priority 2 (nursery): notifications=visual_only, proactive_suggestions=false
  Priority 3 (kids group): response_style=simple_playful, max_response_length=50
  Priority 4 (zachary): vocabulary_level=very_simple, max_response_length=30

Effective:
  response_style: simple_playful
  vocabulary_level: very_simple
  max_response_length: 30
  voice_responses: false (nursery wins over night_mode, same value)
  voice_volume: quiet
  notifications: visual_only
  proactive_suggestions: false
```

### Scenario 2: Thom in Office During Work Hours

```
Context:
  speaker_id: "thom_fife"
  room_id: "office"
  time: 10:30 (work_hours active)
  home_state: {is_work_hours: true}

Resolution:
  Priority 0 (base): proactive_suggestions=true
  Priority 1 (work_hours): response_style=professional
  Priority 2 (office): interruption_threshold=urgent_only (via condition)
  Priority 3 (adults): allowed_actions=all
  Priority 4 (thom): response_style=technical_detailed, topics_of_interest=[...]

Effective:
  response_style: technical_detailed (thom's preference)
  proactive_suggestions: false (office work_hours condition)
  interruption_threshold: urgent_only
  allowed_actions: all
  topics_of_interest: ["woodworking", "technology", ...]
```

### Scenario 3: Guest in Living Room

```
Context:
  speaker_id: "guest_unknown"
  room_id: "living_room"
  time: 19:00

Resolution:
  Priority 0 (base): all defaults
  Priority 1 (none active)
  Priority 2 (living_room): guests_present condition triggers
  Priority 3 (guests group): privacy_mode=true, include_memories=false
  Priority 4 (none - unknown guest)

Effective:
  response_style: formal
  privacy_mode: true
  include_memories: false
  include_calendar: false
  allowed_actions: ["lights", "temperature_minor", "information_public"]
```

---

## Comparison to SkyrimNet

| Aspect | SkyrimNet | BarnabeeNet |
|--------|-----------|-------------|
| **Override Dimensions** | Per-NPC, Per-Faction | Per-User, Per-Room, Per-Time, Per-Group |
| **Storage Location** | `config/Overrides/` (YAML files) | `config/overrides/overrides.yaml` |
| **Merge Strategy** | Deep merge, later wins | Same |
| **Conditional Overrides** | Via eligibility scripts | Via Jinja2 conditions |
| **Hot-Reload** | YAML file watching | Same |
| **Resolution Trigger** | Dialogue initiation | Request context |
| **Response Transformation** | None (LLM handles) | Dedicated transformer |
| **Privacy Zones** | N/A | Bathroom, bedroom flagging |

### Key Adaptations from SkyrimNet

1. **Multi-dimensional hierarchy**: SkyrimNet uses NPC → Faction. BarnabeeNet uses Time → Room → Group → Individual, providing more granular control.

2. **Conditional sub-overrides**: Room overrides in BarnabeeNet can have nested conditions (e.g., office during work hours vs. after hours), similar to how SkyrimNet's NPCs behave differently in combat vs. dialogue.

3. **Response transformation**: SkyrimNet relies on prompt engineering. BarnabeeNet adds a dedicated post-processing layer to handle vocabulary, length, and content filtering—essential for child safety.

4. **Privacy zones**: Unique to BarnabeeNet, certain rooms can be flagged to disable voice responses entirely.

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial Override System architecture document |

---

*This document specifies the Override System for BarnabeeNet. For core architecture, see BarnabeeNet_Technical_Architecture.md. For feature descriptions, see BarnabeeNet_Features_UseCases.md.*
