# BarnabeeNet Timer System - Complete Implementation Guide

**Purpose:** Comprehensive implementation guide for building BarnabeeNet's timer, sequence, and escalation system  
**Target:** AI coding agents (Copilot, Claude Code) and developers  
**Last Updated:** January 2026

---

## Table of Contents

1. [Overview & Goals](#overview--goals)
2. [Architecture](#architecture)
3. [Home Assistant Prerequisites](#home-assistant-prerequisites)
4. [Data Models](#data-models)
5. [Core Services](#core-services)
   - [Timer Pool Manager](#1-timer-pool-manager)
   - [Duration Parser](#2-duration-parser)
   - [Sequence Parser](#3-sequence-parser)
   - [Sequence Executor](#4-sequence-executor)
   - [Escalation Engine](#5-escalation-engine)
   - [Notification Service](#6-notification-service)
6. [Integration Points](#integration-points)
7. [Voice Command Patterns](#voice-command-patterns)
8. [Testing Scenarios](#testing-scenarios)
9. [File Structure](#file-structure)

---

## Overview & Goals

BarnabeeNet's timer system replaces Amazon Echo timer functionality with enhanced capabilities:

### Core Requirements

1. **Simple Timers** - "Set a timer for 10 minutes" → alarm with escalating notifications
2. **Named Timers** - "Set a pizza timer for 15 minutes" → labeled, queryable
3. **Device Duration** - "Turn on the porch light for 10 minutes" → auto turn-off
4. **Delayed Actions** - "In 5 minutes turn off the fan" → scheduled command
5. **Complex Sequences** - "Wait 5 minutes, notify me, then 3 minutes later turn off the light"
6. **Escalating Alerts** - Room → All rooms → Phone notifications until acknowledged

### Design Principles

- **Hybrid Architecture**: HA timer helpers for countdown (survives restarts), BarnabeeNet for orchestration
- **Progressive Escalation**: Don't let timers go unnoticed like Echo sometimes does
- **Sequence Support**: Chain multiple timed actions together
- **Robust Parsing**: Handle "five minutes" and "5 minutes" equally
- **Full Observability**: Track timer state for dashboard display

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BarnabeeNet Timer System                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Voice Input                                                                 │
│  "wait 5 min, notify me, then 3 min later turn off office light"            │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Timer Intent Classifier                         │    │
│  │  (Part of Meta Agent - detects timer-related commands)               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Sequence Parser                               │    │
│  │  - Splits compound commands on "then", "after", etc.                 │    │
│  │  - Extracts delays and actions from each segment                     │    │
│  │  - Resolves targets to HA entities/areas                             │    │
│  │  - Handles word numbers ("five" → 5)                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Sequence Executor                               │    │
│  │  - Manages ActionSequence lifecycle                                  │    │
│  │  - Allocates timers from pool for each step                          │    │
│  │  - Executes actions when timers complete                             │    │
│  │  - Advances to next step or completes sequence                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Timer Pool Manager                               │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐            │    │
│  │  │ timer.    │ │ timer.    │ │ timer.    │ │ timer.    │  ...×10    │    │
│  │  │ barnabee_1│ │ barnabee_2│ │ barnabee_3│ │ barnabee_4│            │    │
│  │  └─────┬─────┘ └───────────┘ └───────────┘ └───────────┘            │    │
│  │        │                                                             │    │
│  │        │ timer.finished event (via HA state change)                  │    │
│  │        ▼                                                             │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │              Completion Handler                              │    │    │
│  │  │  1. Look up ActiveTimer by entity_id                         │    │    │
│  │  │  2. Execute on_complete action                               │    │    │
│  │  │  3. If sequence → notify Sequence Executor                   │    │    │
│  │  │  4. If alarm type → trigger Escalation Engine                │    │    │
│  │  │  5. Release timer entity back to pool                        │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                      │
│       ▼ (for alarm-type timers)                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Escalation Engine                               │    │
│  │                                                                      │    │
│  │  Stage 1: Announce in originating room                              │    │
│  │     ├─► TTS: "Your [label] timer is done"                           │    │
│  │     ├─► Play chime sound                                            │    │
│  │     └─► Wait 30s for wake word acknowledgment                       │    │
│  │                                                                      │    │
│  │  Stage 2: Announce in all common areas                              │    │
│  │     ├─► TTS in kitchen, living room, etc.                           │    │
│  │     └─► Wait 30s for acknowledgment                                 │    │
│  │                                                                      │    │
│  │  Stage 3: Push to phones                                            │    │
│  │     ├─► Android: TTS with alarm_stream_max                          │    │
│  │     └─► iOS: Critical alert                                         │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Home Assistant Prerequisites

### Timer Helper Entities

Create 10 timer helper entities in Home Assistant. These form the pool that BarnabeeNet allocates from.

**Option A: Via UI**
1. Settings → Devices & Services → Helpers → Create Helper → Timer
2. Create timers named: `barnabee_1`, `barnabee_2`, ... `barnabee_10`
3. Enable "Restore" option for each (survives HA restarts)

**Option B: Via configuration.yaml**
```yaml
timer:
  barnabee_1:
    name: "BarnabeeNet Timer 1"
    restore: true
  barnabee_2:
    name: "BarnabeeNet Timer 2"
    restore: true
  barnabee_3:
    name: "BarnabeeNet Timer 3"
    restore: true
  barnabee_4:
    name: "BarnabeeNet Timer 4"
    restore: true
  barnabee_5:
    name: "BarnabeeNet Timer 5"
    restore: true
  barnabee_6:
    name: "BarnabeeNet Timer 6"
    restore: true
  barnabee_7:
    name: "BarnabeeNet Timer 7"
    restore: true
  barnabee_8:
    name: "BarnabeeNet Timer 8"
    restore: true
  barnabee_9:
    name: "BarnabeeNet Timer 9"
    restore: true
  barnabee_10:
    name: "BarnabeeNet Timer 10"
    restore: true
```

### Timer Entity States & Attributes

Understanding HA timer behavior:

```
States: idle, active, paused
Attributes when active:
  - duration: "0:05:00" (original duration)
  - remaining: "0:04:32" (time left)
  - finishes_at: "2026-01-22T15:30:00+00:00"

Events fired:
  - timer.started
  - timer.finished
  - timer.cancelled
  - timer.paused
  - timer.restarted
```

### Service Calls

```python
# Start a timer
await ha_client.call_service(
    "timer.start",
    entity_id="timer.barnabee_1",
    duration="300"  # seconds, or "00:05:00"
)

# Cancel a timer
await ha_client.call_service(
    "timer.cancel",
    entity_id="timer.barnabee_1"
)

# Pause a timer
await ha_client.call_service(
    "timer.pause",
    entity_id="timer.barnabee_1"
)

# Resume a paused timer
await ha_client.call_service(
    "timer.start",  # Yes, start resumes a paused timer
    entity_id="timer.barnabee_1"
)

# Add time to running timer
await ha_client.call_service(
    "timer.change",
    entity_id="timer.barnabee_1",
    duration="60"  # Add 60 seconds
)
```

---

## Data Models

Create file: `src/barnabeenet/services/timers/models.py`

```python
"""Data models for BarnabeeNet timer system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


# =============================================================================
# Enums
# =============================================================================

class TimerType(str, Enum):
    """Types of timers."""
    ALARM = "alarm"                    # Basic countdown with announcement
    DEVICE_DURATION = "device_duration"  # Turn device on, then off after duration
    DELAYED_ACTION = "delayed_action"   # Execute action after delay
    SEQUENCE_STEP = "sequence_step"     # Part of a multi-step sequence


class ActionType(str, Enum):
    """Types of actions that can be executed."""
    HA_SERVICE = "ha_service"          # Call any Home Assistant service
    TTS_ANNOUNCE = "tts_announce"      # Speak message on satellite/speaker
    NOTIFICATION = "notification"       # Push notification to phone
    CHIME = "chime"                    # Play sound file


class EscalationStage(str, Enum):
    """Stages of timer escalation."""
    NOT_STARTED = "not_started"
    ROOM = "room"                      # Originating room only
    COMMON_AREAS = "common_areas"      # Kitchen, living room, etc.
    PHONES = "phones"                  # Mobile notifications
    COMPLETED = "completed"            # Acknowledged or timed out


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"              # Bypasses DND/silent mode


class Platform(str, Enum):
    """Mobile platform types."""
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


# =============================================================================
# Action Models
# =============================================================================

@dataclass
class TimedAction:
    """A single action with optional delay.
    
    This is the atomic unit of work in the timer system. It can represent
    turning off a light, sending a notification, or announcing via TTS.
    """
    
    action_type: ActionType
    
    # Delay before executing this action (relative to previous step)
    delay: timedelta = field(default_factory=lambda: timedelta(0))
    
    # For ActionType.HA_SERVICE
    service: str | None = None           # e.g., "light.turn_off", "fan.turn_on"
    entity_id: str | None = None         # e.g., "light.office_ceiling"
    area_id: str | None = None           # e.g., "office" (preferred over entity_id)
    service_data: dict[str, Any] = field(default_factory=dict)
    
    # For ActionType.TTS_ANNOUNCE
    message: str | None = None
    target_room: str | None = None       # None = use originating room
    
    # For ActionType.NOTIFICATION
    notification_title: str | None = None
    notification_message: str | None = None
    notification_target: str | None = None  # "thom", "penelope", or "all"
    bypass_silent: bool = True           # Use alarm_stream_max / critical alerts
    
    # For ActionType.CHIME
    chime_sound: str | None = None       # Path to sound file, or "default"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_type": self.action_type.value,
            "delay_seconds": self.delay.total_seconds(),
            "service": self.service,
            "entity_id": self.entity_id,
            "area_id": self.area_id,
            "service_data": self.service_data,
            "message": self.message,
            "target_room": self.target_room,
            "notification_title": self.notification_title,
            "notification_message": self.notification_message,
            "notification_target": self.notification_target,
            "bypass_silent": self.bypass_silent,
            "chime_sound": self.chime_sound,
        }
    
    @classmethod
    def ha_service(
        cls,
        service: str,
        entity_id: str | None = None,
        area_id: str | None = None,
        delay: timedelta | None = None,
        **service_data
    ) -> "TimedAction":
        """Factory for HA service call actions."""
        return cls(
            action_type=ActionType.HA_SERVICE,
            service=service,
            entity_id=entity_id,
            area_id=area_id,
            delay=delay or timedelta(0),
            service_data=service_data
        )
    
    @classmethod
    def tts(
        cls,
        message: str,
        room: str | None = None,
        delay: timedelta | None = None
    ) -> "TimedAction":
        """Factory for TTS announcement actions."""
        return cls(
            action_type=ActionType.TTS_ANNOUNCE,
            message=message,
            target_room=room,
            delay=delay or timedelta(0)
        )
    
    @classmethod
    def notification(
        cls,
        message: str,
        title: str = "BarnabeeNet",
        target: str = "all",
        delay: timedelta | None = None,
        bypass_silent: bool = True
    ) -> "TimedAction":
        """Factory for push notification actions."""
        return cls(
            action_type=ActionType.NOTIFICATION,
            notification_title=title,
            notification_message=message,
            notification_target=target,
            delay=delay or timedelta(0),
            bypass_silent=bypass_silent
        )


# =============================================================================
# Sequence Models
# =============================================================================

@dataclass
class ActionSequence:
    """A sequence of timed actions to execute in order.
    
    Sequences allow chaining multiple actions with delays between them.
    Example: "Wait 5 min, notify me, then 3 min later turn off the light"
    """
    
    id: str                              # UUID for this sequence
    steps: list[TimedAction]             # Ordered list of actions
    current_step_index: int = 0          # Which step we're on (or waiting for)
    
    # Context - who/where created this sequence
    created_by: str | None = None        # Speaker who created it
    created_in_room: str | None = None   # Room where created
    created_at: datetime | None = None
    
    # For display and voice queries
    label: str = "sequence"              # Human-friendly name
    
    # State
    is_active: bool = True
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    
    @property
    def current_step(self) -> TimedAction | None:
        """Get the current step, or None if sequence is complete."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if all steps have been executed."""
        return self.current_step_index >= len(self.steps)
    
    @property
    def remaining_steps(self) -> int:
        """Number of steps remaining."""
        return max(0, len(self.steps) - self.current_step_index)
    
    def advance(self) -> TimedAction | None:
        """Advance to next step and return it, or None if complete."""
        self.current_step_index += 1
        return self.current_step
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "label": self.label,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "remaining_steps": self.remaining_steps,
            "is_complete": self.is_complete,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_in_room": self.created_in_room,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# Escalation Models
# =============================================================================

@dataclass
class EscalationConfig:
    """Configuration for escalation behavior.
    
    Can be customized per-household or per-timer.
    """
    
    # Delays between stages (in seconds)
    stage_delays: list[int] = field(
        default_factory=lambda: [0, 30, 60]  # Immediate, 30s, 60s
    )
    
    # Rooms to announce in for each stage
    # "originating_room" is replaced with actual room at runtime
    stage_room_targets: list[list[str]] = field(
        default_factory=lambda: [
            ["originating_room"],
            ["kitchen", "living_room", "master_bedroom"],
            []  # Stage 3 uses phones, not rooms
        ]
    )
    
    # Phone targets for final stage
    phone_targets: list[str] = field(
        default_factory=lambda: ["all"]  # or specific users: ["thom", "penelope"]
    )
    
    # Maximum time to wait for acknowledgment before giving up (seconds)
    max_escalation_duration: int = 300  # 5 minutes
    
    # Sound to play with announcements
    chime_sound: str = "/local/sounds/timer-chime.mp3"
    
    # Whether to repeat announcements within a stage
    repeat_announcements: bool = True
    repeat_interval: int = 10  # seconds between repeats


@dataclass
class EscalationState:
    """Runtime state for an active escalation."""
    
    timer_id: str
    config: EscalationConfig = field(default_factory=EscalationConfig)
    
    # Current state
    stage: EscalationStage = EscalationStage.NOT_STARTED
    stage_index: int = 0
    
    # Timing
    started_at: datetime | None = None
    stage_started_at: datetime | None = None
    
    # Resolution
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None  # Room or device that acknowledged
    timed_out: bool = False
    
    @property
    def is_active(self) -> bool:
        """Check if escalation is still running."""
        return (
            self.stage not in (EscalationStage.NOT_STARTED, EscalationStage.COMPLETED)
            and not self.acknowledged
            and not self.timed_out
        )
    
    def advance_stage(self) -> EscalationStage:
        """Move to next escalation stage."""
        stages = [
            EscalationStage.ROOM,
            EscalationStage.COMMON_AREAS,
            EscalationStage.PHONES,
            EscalationStage.COMPLETED
        ]
        
        self.stage_index = min(self.stage_index + 1, len(stages) - 1)
        self.stage = stages[self.stage_index]
        self.stage_started_at = datetime.now()
        
        return self.stage


# =============================================================================
# Active Timer Model
# =============================================================================

@dataclass
class ActiveTimer:
    """An active timer managed by BarnabeeNet.
    
    Links a Home Assistant timer entity to BarnabeeNet's orchestration.
    """
    
    id: str                              # BarnabeeNet timer ID (UUID)
    ha_timer_entity: str                 # e.g., "timer.barnabee_1"
    timer_type: TimerType
    
    # Timing
    duration: timedelta
    started_at: datetime
    ends_at: datetime
    
    # What to do when timer finishes
    on_complete: TimedAction | None = None
    
    # If this timer is part of a sequence
    sequence_id: str | None = None
    sequence_step_index: int | None = None
    
    # For alarm-type timers with escalation
    escalation: EscalationState | None = None
    
    # Context
    label: str = "timer"
    created_by: str | None = None        # Speaker
    created_in_room: str | None = None
    
    # State
    is_paused: bool = False
    paused_at: datetime | None = None
    
    @property
    def remaining(self) -> timedelta:
        """Get remaining time on the timer."""
        if self.is_paused:
            # When paused, remaining is frozen
            # This requires tracking pause state properly
            return self.ends_at - (self.paused_at or datetime.now())
        
        now = datetime.now()
        if now >= self.ends_at:
            return timedelta(0)
        return self.ends_at - now
    
    @property
    def remaining_seconds(self) -> int:
        """Get remaining time in seconds."""
        return max(0, int(self.remaining.total_seconds()))
    
    @property
    def is_expired(self) -> bool:
        """Check if timer has expired."""
        return not self.is_paused and datetime.now() >= self.ends_at
    
    @property
    def progress_percent(self) -> float:
        """Get completion percentage (0-100)."""
        total = self.duration.total_seconds()
        remaining = self.remaining.total_seconds()
        if total <= 0:
            return 100.0
        return ((total - remaining) / total) * 100
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "ha_timer_entity": self.ha_timer_entity,
            "timer_type": self.timer_type.value,
            "label": self.label,
            "duration_seconds": self.duration.total_seconds(),
            "remaining_seconds": self.remaining_seconds,
            "progress_percent": self.progress_percent,
            "started_at": self.started_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "is_paused": self.is_paused,
            "created_by": self.created_by,
            "created_in_room": self.created_in_room,
            "sequence_id": self.sequence_id,
            "has_escalation": self.escalation is not None,
            "on_complete": self.on_complete.to_dict() if self.on_complete else None,
        }


# =============================================================================
# Timer Pool Models
# =============================================================================

@dataclass
class TimerPoolConfig:
    """Configuration for the timer entity pool."""
    
    # Pattern for HA timer entities
    entity_prefix: str = "timer.barnabee_"
    
    # Number of timer entities in the pool
    pool_size: int = 10
    
    @property
    def entity_ids(self) -> list[str]:
        """Get list of all timer entity IDs."""
        return [f"{self.entity_prefix}{i}" for i in range(1, self.pool_size + 1)]


@dataclass
class TimerPool:
    """Pool of HA timer entities for allocation."""
    
    config: TimerPoolConfig = field(default_factory=TimerPoolConfig)
    
    # Available entities (not currently in use)
    available: list[str] = field(default_factory=list)
    
    # Mapping: timer_id -> entity_id
    in_use: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize available pool from config."""
        if not self.available:
            self.available = list(self.config.entity_ids)
    
    def allocate(self, timer_id: str) -> str | None:
        """Allocate a timer entity from the pool.
        
        Args:
            timer_id: BarnabeeNet timer ID to associate
            
        Returns:
            Entity ID if available, None if pool exhausted
        """
        if not self.available:
            return None
        
        entity_id = self.available.pop(0)
        self.in_use[timer_id] = entity_id
        return entity_id
    
    def release(self, timer_id: str) -> str | None:
        """Return a timer entity to the pool.
        
        Args:
            timer_id: BarnabeeNet timer ID
            
        Returns:
            Released entity ID, or None if not found
        """
        entity_id = self.in_use.pop(timer_id, None)
        if entity_id and entity_id not in self.available:
            self.available.append(entity_id)
        return entity_id
    
    def get_entity(self, timer_id: str) -> str | None:
        """Get the HA entity for a timer ID."""
        return self.in_use.get(timer_id)
    
    def get_timer_id(self, entity_id: str) -> str | None:
        """Get the timer ID for an HA entity."""
        for tid, eid in self.in_use.items():
            if eid == entity_id:
                return tid
        return None
    
    @property
    def available_count(self) -> int:
        """Number of available timers."""
        return len(self.available)
    
    @property
    def in_use_count(self) -> int:
        """Number of timers currently in use."""
        return len(self.in_use)


# =============================================================================
# User Device Models (for notifications)
# =============================================================================

@dataclass
class UserDevice:
    """A user's registered mobile device."""
    
    user_name: str                       # e.g., "thom"
    device_id: str                       # HA device ID for notify service
    platform: Platform
    
    @property
    def notify_service(self) -> str:
        """Get the HA notify service name."""
        return f"notify.mobile_app_{self.device_id}"


@dataclass  
class RoomSpeaker:
    """A room's speaker/satellite for announcements."""
    
    room: str                            # e.g., "kitchen"
    media_player_entity: str             # e.g., "media_player.kitchen_speaker"
    satellite_entity: str | None = None  # e.g., "assist_satellite.kitchen"
    tts_engine: str = "tts.piper"        # or "tts.kokoro"
```

---

## Core Services

### 1. Timer Pool Manager

Create file: `src/barnabeenet/services/timers/pool_manager.py`

```python
"""Timer Pool Manager - Manages allocation of HA timer entities."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable
import uuid

from .models import (
    ActiveTimer,
    ActionType,
    EscalationConfig,
    EscalationState,
    TimedAction,
    TimerPool,
    TimerPoolConfig,
    TimerType,
)

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


class TimerPoolManager:
    """Manages BarnabeeNet timers using HA timer helper entities.
    
    Responsibilities:
    - Allocate/release timer entities from pool
    - Start/cancel/pause timers via HA service calls
    - Track active timers and their metadata
    - Handle timer.finished events
    - Trigger callbacks when timers complete
    """
    
    def __init__(
        self,
        ha_client: HomeAssistantClient,
        config: TimerPoolConfig | None = None,
        on_timer_finished: Callable[[ActiveTimer], None] | None = None,
    ):
        self._ha = ha_client
        self._config = config or TimerPoolConfig()
        self._pool = TimerPool(config=self._config)
        self._active_timers: dict[str, ActiveTimer] = {}
        self._on_timer_finished = on_timer_finished
        
        # Subscribe to HA state changes for timer entities
        self._ha.subscribe_state_change(self._on_state_change)
    
    async def initialize(self) -> None:
        """Initialize the timer pool.
        
        Verifies timer entities exist in HA and recovers any active timers
        after a restart.
        """
        logger.info("Initializing timer pool with %d entities", self._config.pool_size)
        
        # Check which entities exist and their current state
        for entity_id in self._config.entity_ids:
            state = await self._ha.get_state(entity_id)
            
            if state is None:
                logger.warning(
                    "Timer entity %s not found in HA. "
                    "Create it via Helpers or configuration.yaml",
                    entity_id
                )
                # Remove from available pool
                if entity_id in self._pool.available:
                    self._pool.available.remove(entity_id)
            elif state.state == "active":
                # Timer was running - could be from before restart
                # For now, cancel it to clean state
                logger.info("Cancelling orphaned active timer: %s", entity_id)
                await self._ha.call_service("timer.cancel", entity_id=entity_id)
        
        logger.info(
            "Timer pool ready: %d available, %d missing",
            self._pool.available_count,
            self._config.pool_size - self._pool.available_count
        )
    
    async def create_timer(
        self,
        timer_type: TimerType,
        duration: timedelta,
        label: str | None = None,
        created_by: str | None = None,
        created_in_room: str | None = None,
        on_complete: TimedAction | None = None,
        sequence_id: str | None = None,
        sequence_step_index: int | None = None,
        escalation_config: EscalationConfig | None = None,
    ) -> ActiveTimer | None:
        """Create and start a new timer.
        
        Args:
            timer_type: Type of timer (alarm, device_duration, etc.)
            duration: How long the timer should run
            label: Human-friendly name for the timer
            created_by: Who created it (speaker name)
            created_in_room: Where it was created
            on_complete: Action to execute when timer finishes
            sequence_id: If part of a sequence, the sequence ID
            sequence_step_index: Index within the sequence
            escalation_config: For alarm timers, escalation behavior
            
        Returns:
            ActiveTimer if created successfully, None if pool exhausted
        """
        # Generate timer ID
        timer_id = str(uuid.uuid4())[:8]
        
        # Allocate entity from pool
        entity_id = self._pool.allocate(timer_id)
        if not entity_id:
            logger.warning("No timer entities available in pool")
            return None
        
        # Calculate timing
        now = datetime.now()
        ends_at = now + duration
        
        # Create escalation state for alarm timers
        escalation = None
        if timer_type == TimerType.ALARM and escalation_config:
            escalation = EscalationState(
                timer_id=timer_id,
                config=escalation_config
            )
        
        # Create timer record
        timer = ActiveTimer(
            id=timer_id,
            ha_timer_entity=entity_id,
            timer_type=timer_type,
            duration=duration,
            started_at=now,
            ends_at=ends_at,
            label=label or f"timer_{timer_id}",
            created_by=created_by,
            created_in_room=created_in_room,
            on_complete=on_complete,
            sequence_id=sequence_id,
            sequence_step_index=sequence_step_index,
            escalation=escalation,
        )
        
        # Start the HA timer
        try:
            duration_seconds = int(duration.total_seconds())
            result = await self._ha.call_service(
                "timer.start",
                entity_id=entity_id,
                duration=str(duration_seconds)
            )
            
            if not result.success:
                logger.error("Failed to start HA timer %s: %s", entity_id, result.message)
                self._pool.release(timer_id)
                return None
                
        except Exception as e:
            logger.exception("Error starting HA timer %s", entity_id)
            self._pool.release(timer_id)
            return None
        
        # Register timer
        self._active_timers[timer_id] = timer
        
        logger.info(
            "Created %s timer '%s' for %s (entity: %s, id: %s)",
            timer_type.value,
            timer.label,
            self._format_duration(duration),
            entity_id,
            timer_id
        )
        
        return timer
    
    async def cancel_timer(self, timer_id: str) -> bool:
        """Cancel an active timer.
        
        Args:
            timer_id: Timer ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False
        
        # Cancel HA timer
        try:
            await self._ha.call_service(
                "timer.cancel",
                entity_id=timer.ha_timer_entity
            )
        except Exception as e:
            logger.warning("Error cancelling HA timer: %s", e)
        
        # Cleanup
        del self._active_timers[timer_id]
        self._pool.release(timer_id)
        
        logger.info("Cancelled timer '%s' (id: %s)", timer.label, timer_id)
        return True
    
    async def cancel_by_label(self, label: str) -> bool:
        """Cancel a timer by its label.
        
        Args:
            label: Timer label to match (case-insensitive)
            
        Returns:
            True if found and cancelled
        """
        label_lower = label.lower()
        for timer_id, timer in self._active_timers.items():
            if timer.label.lower() == label_lower:
                return await self.cancel_timer(timer_id)
        return False
    
    async def cancel_all(self) -> int:
        """Cancel all active timers.
        
        Returns:
            Number of timers cancelled
        """
        timer_ids = list(self._active_timers.keys())
        count = 0
        for timer_id in timer_ids:
            if await self.cancel_timer(timer_id):
                count += 1
        return count
    
    async def pause_timer(self, timer_id: str) -> bool:
        """Pause an active timer.
        
        Args:
            timer_id: Timer ID to pause
            
        Returns:
            True if paused, False if not found or already paused
        """
        timer = self._active_timers.get(timer_id)
        if not timer or timer.is_paused:
            return False
        
        try:
            await self._ha.call_service(
                "timer.pause",
                entity_id=timer.ha_timer_entity
            )
            timer.is_paused = True
            timer.paused_at = datetime.now()
            return True
        except Exception as e:
            logger.warning("Error pausing timer: %s", e)
            return False
    
    async def resume_timer(self, timer_id: str) -> bool:
        """Resume a paused timer.
        
        Args:
            timer_id: Timer ID to resume
            
        Returns:
            True if resumed, False if not found or not paused
        """
        timer = self._active_timers.get(timer_id)
        if not timer or not timer.is_paused:
            return False
        
        try:
            await self._ha.call_service(
                "timer.start",  # start resumes a paused timer
                entity_id=timer.ha_timer_entity
            )
            # Update ends_at based on remaining time
            if timer.paused_at:
                pause_duration = datetime.now() - timer.paused_at
                timer.ends_at = timer.ends_at + pause_duration
            timer.is_paused = False
            timer.paused_at = None
            return True
        except Exception as e:
            logger.warning("Error resuming timer: %s", e)
            return False
    
    async def add_time(self, timer_id: str, additional: timedelta) -> bool:
        """Add time to a running timer.
        
        Args:
            timer_id: Timer ID
            additional: Time to add
            
        Returns:
            True if time added, False if not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False
        
        try:
            await self._ha.call_service(
                "timer.change",
                entity_id=timer.ha_timer_entity,
                duration=str(int(additional.total_seconds()))
            )
            timer.ends_at = timer.ends_at + additional
            timer.duration = timer.duration + additional
            return True
        except Exception as e:
            logger.warning("Error adding time to timer: %s", e)
            return False
    
    def get_timer(self, timer_id: str) -> ActiveTimer | None:
        """Get a timer by ID."""
        return self._active_timers.get(timer_id)
    
    def get_by_label(self, label: str) -> ActiveTimer | None:
        """Get a timer by label (case-insensitive)."""
        label_lower = label.lower()
        for timer in self._active_timers.values():
            if timer.label.lower() == label_lower:
                return timer
        return None
    
    def get_active_timers(self) -> list[ActiveTimer]:
        """Get all active timers."""
        return list(self._active_timers.values())
    
    def get_timers_for_sequence(self, sequence_id: str) -> list[ActiveTimer]:
        """Get all timers associated with a sequence."""
        return [
            t for t in self._active_timers.values()
            if t.sequence_id == sequence_id
        ]
    
    def _on_state_change(self, event: dict) -> None:
        """Handle HA state change events.
        
        Looks for timer transitions to 'idle' (finished) state.
        """
        entity_id = event.get("entity_id", "")
        
        # Only process our timer entities
        if not entity_id.startswith(self._config.entity_prefix):
            return
        
        old_state = event.get("old_state", {}).get("state")
        new_state = event.get("new_state", {}).get("state")
        
        # Timer finished: active -> idle
        if old_state == "active" and new_state == "idle":
            timer_id = self._pool.get_timer_id(entity_id)
            if timer_id:
                asyncio.create_task(self._handle_timer_finished(timer_id))
    
    async def _handle_timer_finished(self, timer_id: str) -> None:
        """Handle a timer that has finished."""
        timer = self._active_timers.get(timer_id)
        if not timer:
            return
        
        logger.info("Timer finished: '%s' (id: %s)", timer.label, timer_id)
        
        # Remove from active timers
        del self._active_timers[timer_id]
        
        # Release entity back to pool
        self._pool.release(timer_id)
        
        # Trigger callback
        if self._on_timer_finished:
            try:
                await self._on_timer_finished(timer)
            except Exception as e:
                logger.exception("Error in timer finished callback")
    
    @staticmethod
    def _format_duration(td: timedelta) -> str:
        """Format duration for logging."""
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        if minutes < 60:
            return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m"
```

---

### 2. Duration Parser

Create file: `src/barnabeenet/services/timers/duration_parser.py`

```python
"""Duration Parser - Converts natural language to timedelta.

Handles:
- Numeric: "5 minutes", "30 seconds", "2 hours"
- Word numbers: "five minutes", "thirty seconds"
- Compound: "1 hour and 30 minutes", "5 minutes 30 seconds"
- Fractions: "half an hour", "quarter hour", "1.5 hours"
- Casual: "a minute", "an hour", "a few minutes"
"""

from __future__ import annotations

import re
from datetime import timedelta


# Word to number mapping (covers 0-60 plus common larger numbers)
WORD_NUMBERS: dict[str, int] = {
    "zero": 0,
    "one": 1, "a": 1, "an": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "ninety": 90,
    # Compound numbers handled separately
}

# Compound word numbers (twenty-one, thirty-five, etc.)
COMPOUND_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
COMPOUND_ONES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

# Casual expressions
CASUAL_DURATIONS: dict[str, timedelta] = {
    "a moment": timedelta(seconds=30),
    "a second": timedelta(seconds=1),
    "a minute": timedelta(minutes=1),
    "an hour": timedelta(hours=1),
    "a few seconds": timedelta(seconds=15),
    "a few minutes": timedelta(minutes=3),
    "a couple minutes": timedelta(minutes=2),
    "a couple of minutes": timedelta(minutes=2),
    "half a minute": timedelta(seconds=30),
    "half an hour": timedelta(minutes=30),
    "half hour": timedelta(minutes=30),
    "quarter hour": timedelta(minutes=15),
    "quarter of an hour": timedelta(minutes=15),
}


def normalize_word_numbers(text: str) -> str:
    """Convert word numbers to digits in text.
    
    Args:
        text: Text potentially containing word numbers
        
    Returns:
        Text with word numbers converted to digits
        
    Examples:
        "five minutes" -> "5 minutes"
        "twenty-five seconds" -> "25 seconds"
        "one hour thirty minutes" -> "1 hour 30 minutes"
    """
    text = text.lower().strip()
    
    # Handle compound numbers first (twenty-five, thirty-two, etc.)
    for tens in COMPOUND_TENS:
        for ones in COMPOUND_ONES:
            compound = f"{tens}-{ones}"
            compound_alt = f"{tens} {ones}"
            value = WORD_NUMBERS[tens] + WORD_NUMBERS[ones]
            text = text.replace(compound, str(value))
            text = text.replace(compound_alt, str(value))
    
    # Handle simple word numbers
    words = text.split()
    result = []
    for word in words:
        # Strip punctuation for matching
        clean_word = word.rstrip(".,;:!?")
        if clean_word in WORD_NUMBERS:
            result.append(str(WORD_NUMBERS[clean_word]))
        else:
            result.append(word)
    
    return " ".join(result)


def parse_duration(text: str) -> timedelta | None:
    """Parse a duration string into a timedelta.
    
    Args:
        text: Natural language duration string
        
    Returns:
        timedelta if successfully parsed, None otherwise
        
    Examples:
        "5 minutes" -> timedelta(minutes=5)
        "five minutes" -> timedelta(minutes=5)
        "30 seconds" -> timedelta(seconds=30)
        "1 hour 30 minutes" -> timedelta(hours=1, minutes=30)
        "1.5 hours" -> timedelta(hours=1, minutes=30)
        "half an hour" -> timedelta(minutes=30)
        "an hour and a half" -> timedelta(minutes=90)
    """
    if not text:
        return None
    
    text = text.lower().strip()
    
    # Check casual expressions first
    for phrase, duration in CASUAL_DURATIONS.items():
        if phrase in text:
            return duration
    
    # Handle "and a half" suffix
    half_suffix = False
    if "and a half" in text:
        text = text.replace("and a half", "").strip()
        half_suffix = True
    
    # Normalize word numbers to digits
    text = normalize_word_numbers(text)
    
    # Patterns for extracting duration components
    patterns = [
        # Hours (including decimals)
        (r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", "hours"),
        # Minutes
        (r"(\d+)\s*(?:minutes?|mins?|m)\b", "minutes"),
        # Seconds
        (r"(\d+)\s*(?:seconds?|secs?|s)\b", "seconds"),
    ]
    
    hours = 0.0
    minutes = 0
    seconds = 0
    matched_any = False
    
    for pattern, unit in patterns:
        match = re.search(pattern, text)
        if match:
            matched_any = True
            value = match.group(1)
            if unit == "hours":
                hours = float(value)
            elif unit == "minutes":
                minutes = int(value)
            elif unit == "seconds":
                seconds = int(value)
    
    if not matched_any:
        return None
    
    # Apply "and a half" suffix to the largest unit
    if half_suffix:
        if hours > 0:
            minutes += 30
        elif minutes > 0:
            seconds += 30
    
    # Convert fractional hours to minutes
    if hours != int(hours):
        fractional_minutes = (hours - int(hours)) * 60
        minutes += int(fractional_minutes)
        hours = int(hours)
    
    return timedelta(hours=int(hours), minutes=minutes, seconds=seconds)


def format_duration(td: timedelta) -> str:
    """Format a timedelta as natural language.
    
    Args:
        td: timedelta to format
        
    Returns:
        Human-readable duration string
        
    Examples:
        timedelta(minutes=5) -> "5 minutes"
        timedelta(seconds=30) -> "30 seconds"
        timedelta(hours=1, minutes=30) -> "1 hour 30 minutes"
    """
    total_seconds = int(td.total_seconds())
    
    if total_seconds == 0:
        return "0 seconds"
    
    if total_seconds < 60:
        return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"
    
    total_minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60
    
    if total_minutes < 60:
        parts = [f"{total_minutes} minute{'s' if total_minutes != 1 else ''}"]
        if remaining_seconds > 0:
            parts.append(f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}")
        return " ".join(parts)
    
    hours = total_minutes // 60
    remaining_minutes = total_minutes % 60
    
    parts = [f"{hours} hour{'s' if hours != 1 else ''}"]
    if remaining_minutes > 0:
        parts.append(f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}")
    
    return " ".join(parts)


def format_duration_short(td: timedelta) -> str:
    """Format a timedelta in short form for display.
    
    Args:
        td: timedelta to format
        
    Returns:
        Short format like "5m", "1h 30m", "45s"
    """
    total_seconds = int(td.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    
    total_minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60
    
    if total_minutes < 60:
        if remaining_seconds > 0:
            return f"{total_minutes}m {remaining_seconds}s"
        return f"{total_minutes}m"
    
    hours = total_minutes // 60
    remaining_minutes = total_minutes % 60
    
    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"
```

---

### 3. Sequence Parser

Create file: `src/barnabeenet/services/timers/sequence_parser.py`

```python
"""Sequence Parser - Converts voice commands to ActionSequences.

Parses complex commands like:
- "Wait 5 minutes then notify me to check the oven"
- "In 10 minutes turn off the office light"
- "Wait 5 minutes, send me a notification, then 3 minutes later turn off the light"
- "Turn on the porch light for 10 minutes"
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .duration_parser import parse_duration
from .models import (
    ActionSequence,
    ActionType,
    ActiveTimer,
    EscalationConfig,
    TimedAction,
    TimerType,
)

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.topology import HATopologyService

logger = logging.getLogger(__name__)


# =============================================================================
# Pattern Definitions
# =============================================================================

# Patterns that indicate a timer/sequence command
TIMER_INDICATORS = [
    r"\btimer\b",
    r"\bremind\b",
    r"\balarm\b",
    r"\bwait\b",
    r"\bin\s+\d+\s*(minutes?|seconds?|hours?)",
    r"\bafter\s+\d+\s*(minutes?|seconds?|hours?)",
    r"\bfor\s+\d+\s*(minutes?|seconds?|hours?)",
    r"\d+\s*(minutes?|seconds?|hours?)\s+later",
]

# Patterns for splitting multi-step sequences
SEQUENCE_SPLITTERS = [
    r",?\s*then\s+",
    r",?\s*and\s+then\s+",
    r",?\s*after\s+that\s+",
    r",?\s*next\s+",
    r";\s*",
]

# Patterns for extracting delay from segment start
DELAY_PREFIX_PATTERNS = [
    # "in 5 minutes send..."
    (r"^in\s+(.+?)\s+(send|turn|notify|say|announce|play)", 2),
    # "after 5 minutes turn..."
    (r"^after\s+(.+?)\s+(turn|send|notify|say|announce|play)", 2),
    # "wait 5 minutes and send..."
    (r"^wait\s+(.+?)\s+(?:and\s+)?(send|turn|notify|say|announce|play)", 2),
    # "5 minutes later turn..."
    (r"^(.+?)\s+later\s+(turn|send|notify|say|announce|play)", 2),
]

# Patterns for delayed action at end of command
DELAY_SUFFIX_PATTERNS = [
    # "turn off the light in 5 minutes"
    r"(.+?)\s+in\s+(\d+\s*(?:minutes?|seconds?|hours?|mins?|secs?|hrs?))$",
    # "turn off the light after 5 minutes"
    r"(.+?)\s+after\s+(\d+\s*(?:minutes?|seconds?|hours?|mins?|secs?|hrs?))$",
]

# Patterns for device duration ("turn on X for Y")
DEVICE_DURATION_PATTERNS = [
    # "turn on the porch light for 10 minutes"
    r"(turn\s+on|switch\s+on)\s+(?:the\s+)?(.+?)\s+for\s+(.+)",
    # "porch light on for 10 minutes"
    r"(.+?)\s+on\s+for\s+(.+)",
]

# Patterns for simple alarms ("set a timer for X")
ALARM_PATTERNS = [
    # "set a timer for 5 minutes"
    r"set\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)",
    # "set a pizza timer for 10 minutes"
    r"set\s+(?:a\s+)?(.+?)\s+timer\s+(?:for\s+)?(.+)",
    # "5 minute timer"
    r"^(\d+\s*(?:minutes?|seconds?|hours?|mins?|secs?|hrs?))\s+timer$",
    # "start a timer for 5 minutes"
    r"start\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)",
]

# Action patterns
NOTIFICATION_PATTERNS = [
    # "send a notification saying X"
    r"send\s+(?:a\s+)?(?:push\s+)?notification\s+(?:that\s+says?|saying)\s+[\"']?(.+?)[\"']?$",
    # "notify me that X" / "notify me to X"
    r"notify\s+(?:me|us)\s+(?:that|to)\s+[\"']?(.+?)[\"']?$",
    # "send me a message saying X"
    r"send\s+(?:me|us)\s+(?:a\s+)?message\s+(?:that\s+says?|saying)\s+[\"']?(.+?)[\"']?$",
    # "remind me to X"
    r"remind\s+(?:me|us)\s+(?:to\s+)?[\"']?(.+?)[\"']?$",
]

TTS_PATTERNS = [
    # "say X"
    r"^say\s+[\"']?(.+?)[\"']?$",
    # "announce X"
    r"^announce\s+[\"']?(.+?)[\"']?$",
    # "tell me X"
    r"^tell\s+(?:me|us)\s+[\"']?(.+?)[\"']?$",
]

# HA service action patterns
TURN_OFF_PATTERN = r"turn\s+off\s+(?:the\s+)?(.+)"
TURN_ON_PATTERN = r"turn\s+on\s+(?:the\s+)?(.+)"
TOGGLE_PATTERN = r"toggle\s+(?:the\s+)?(.+)"

# Domain inference from target names
DOMAIN_KEYWORDS = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "fan": "fan",
    "switch": "switch",
    "plug": "switch",
    "outlet": "switch",
    "tv": "media_player",
    "television": "media_player",
    "speaker": "media_player",
    "cover": "cover",
    "blind": "cover",
    "curtain": "cover",
    "lock": "lock",
    "thermostat": "climate",
    "ac": "climate",
    "heater": "climate",
}


# =============================================================================
# Sequence Parser
# =============================================================================

class SequenceParser:
    """Parses voice commands into action sequences."""
    
    def __init__(self, topology: HATopologyService | None = None):
        """Initialize parser.
        
        Args:
            topology: HA topology service for resolving areas/entities
        """
        self._topology = topology
    
    def is_timer_command(self, text: str) -> bool:
        """Check if text appears to be a timer-related command.
        
        Args:
            text: Voice command text
            
        Returns:
            True if this looks like a timer command
        """
        text_lower = text.lower()
        for pattern in TIMER_INDICATORS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def parse(
        self,
        text: str,
        speaker: str | None = None,
        room: str | None = None,
    ) -> ActionSequence | None:
        """Parse a voice command into an action sequence.
        
        Args:
            text: Voice command text
            speaker: Who issued the command
            room: Where the command was issued
            
        Returns:
            ActionSequence if parseable, None otherwise
        """
        text = text.strip()
        if not text:
            return None
        
        # Try parsing as different command types
        
        # 1. Simple alarm timer ("set a timer for 5 minutes")
        result = self._parse_alarm_timer(text)
        if result:
            return self._create_sequence(
                steps=result,
                label=self._extract_timer_label(text) or "timer",
                speaker=speaker,
                room=room,
            )
        
        # 2. Device duration ("turn on the light for 10 minutes")
        result = self._parse_device_duration(text)
        if result:
            return self._create_sequence(
                steps=result,
                label=self._generate_label(result),
                speaker=speaker,
                room=room,
            )
        
        # 3. Multi-step sequence ("wait 5 min, notify me, then turn off light")
        result = self._parse_multi_step(text)
        if result:
            return self._create_sequence(
                steps=result,
                label=self._generate_label(result),
                speaker=speaker,
                room=room,
            )
        
        # 4. Single delayed action ("in 5 minutes turn off the fan")
        result = self._parse_delayed_action(text)
        if result:
            return self._create_sequence(
                steps=result,
                label=self._generate_label(result),
                speaker=speaker,
                room=room,
            )
        
        return None
    
    def _parse_alarm_timer(self, text: str) -> list[TimedAction] | None:
        """Parse simple alarm timer commands."""
        text_lower = text.lower()
        
        for pattern in ALARM_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 1:
                    # "set a timer for 5 minutes"
                    duration = parse_duration(groups[0])
                    if duration:
                        # Alarm timer: just the delay, escalation handled separately
                        return [
                            TimedAction(
                                action_type=ActionType.TTS_ANNOUNCE,
                                delay=duration,
                                message="Your timer is done"
                            )
                        ]
                
                elif len(groups) == 2:
                    # "set a pizza timer for 10 minutes"
                    label = groups[0]
                    duration = parse_duration(groups[1])
                    if duration:
                        return [
                            TimedAction(
                                action_type=ActionType.TTS_ANNOUNCE,
                                delay=duration,
                                message=f"Your {label} timer is done"
                            )
                        ]
        
        return None
    
    def _parse_device_duration(self, text: str) -> list[TimedAction] | None:
        """Parse device duration commands ("turn on X for Y minutes")."""
        text_lower = text.lower()
        
        for pattern in DEVICE_DURATION_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 3:
                    # "turn on the porch light for 10 minutes"
                    target = groups[1].strip()
                    duration = parse_duration(groups[2])
                    
                    if duration:
                        domain = self._infer_domain(target)
                        entity_id, area_id = self._resolve_target(target)
                        
                        return [
                            # Step 1: Turn on immediately
                            TimedAction.ha_service(
                                service=f"{domain}.turn_on",
                                entity_id=entity_id,
                                area_id=area_id,
                                delay=timedelta(0)
                            ),
                            # Step 2: Turn off after duration
                            TimedAction.ha_service(
                                service=f"{domain}.turn_off",
                                entity_id=entity_id,
                                area_id=area_id,
                                delay=duration
                            )
                        ]
                
                elif len(groups) == 2:
                    # "porch light on for 10 minutes"
                    target = groups[0].strip()
                    duration = parse_duration(groups[1])
                    
                    if duration:
                        domain = self._infer_domain(target)
                        entity_id, area_id = self._resolve_target(target)
                        
                        return [
                            TimedAction.ha_service(
                                service=f"{domain}.turn_on",
                                entity_id=entity_id,
                                area_id=area_id,
                                delay=timedelta(0)
                            ),
                            TimedAction.ha_service(
                                service=f"{domain}.turn_off",
                                entity_id=entity_id,
                                area_id=area_id,
                                delay=duration
                            )
                        ]
        
        return None
    
    def _parse_delayed_action(self, text: str) -> list[TimedAction] | None:
        """Parse single delayed action commands."""
        text_lower = text.lower()
        
        # Check prefix patterns ("in 5 minutes turn off...")
        for pattern, action_group in DELAY_PREFIX_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                duration_text = match.group(1)
                # Get the action part after the duration
                action_start = match.start(action_group)
                action_text = text_lower[action_start:]
                
                duration = parse_duration(duration_text)
                if duration:
                    action = self._parse_action(action_text)
                    if action:
                        action.delay = duration
                        return [action]
        
        # Check suffix patterns ("turn off the light in 5 minutes")
        for pattern in DELAY_SUFFIX_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                action_text = match.group(1)
                duration_text = match.group(2)
                
                duration = parse_duration(duration_text)
                if duration:
                    action = self._parse_action(action_text)
                    if action:
                        action.delay = duration
                        return [action]
        
        return None
    
    def _parse_multi_step(self, text: str) -> list[TimedAction] | None:
        """Parse multi-step sequence commands."""
        # Split on sequence markers
        pattern = "|".join(SEQUENCE_SPLITTERS)
        segments = re.split(pattern, text, flags=re.IGNORECASE)
        segments = [s.strip() for s in segments if s.strip()]
        
        if len(segments) < 2:
            return None
        
        steps = []
        
        for segment in segments:
            # Try to extract delay from segment
            delay, action_text = self._extract_delay_from_segment(segment)
            
            if action_text:
                action = self._parse_action(action_text)
                if action:
                    if delay:
                        action.delay = delay
                    steps.append(action)
            elif delay:
                # Just a delay with no action - could be "wait 5 minutes"
                # This becomes a TTS announcement
                steps.append(TimedAction(
                    action_type=ActionType.TTS_ANNOUNCE,
                    delay=delay,
                    message="Timer checkpoint"
                ))
        
        return steps if steps else None
    
    def _extract_delay_from_segment(self, segment: str) -> tuple[timedelta | None, str]:
        """Extract delay from the start of a segment.
        
        Returns:
            (delay, remaining_text)
        """
        segment_lower = segment.lower().strip()
        
        # Pattern: "wait X" or "after X" at start
        wait_match = re.match(r"^(?:wait|after)\s+(.+?)(?:\s+(?:and\s+)?(.+))?$", segment_lower)
        if wait_match:
            duration_text = wait_match.group(1)
            action_text = wait_match.group(2) or ""
            duration = parse_duration(duration_text)
            if duration:
                return duration, action_text
        
        # Pattern: "X later" at start
        later_match = re.match(r"^(.+?)\s+later(?:\s+(.+))?$", segment_lower)
        if later_match:
            duration_text = later_match.group(1)
            action_text = later_match.group(2) or ""
            duration = parse_duration(duration_text)
            if duration:
                return duration, action_text
        
        # Pattern: "in X" at start
        in_match = re.match(r"^in\s+(.+?)\s+(.+)$", segment_lower)
        if in_match:
            duration_text = in_match.group(1)
            action_text = in_match.group(2)
            duration = parse_duration(duration_text)
            if duration:
                return duration, action_text
        
        return None, segment
    
    def _parse_action(self, text: str) -> TimedAction | None:
        """Parse an action phrase into a TimedAction."""
        text = text.strip()
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Check notification patterns
        for pattern in NOTIFICATION_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                message = match.group(1)
                return TimedAction.notification(message=message)
        
        # Check TTS patterns
        for pattern in TTS_PATTERNS:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                message = match.group(1)
                return TimedAction.tts(message=message)
        
        # Check turn off
        match = re.match(TURN_OFF_PATTERN, text_lower, re.IGNORECASE)
        if match:
            target = match.group(1)
            domain = self._infer_domain(target)
            entity_id, area_id = self._resolve_target(target)
            return TimedAction.ha_service(
                service=f"{domain}.turn_off",
                entity_id=entity_id,
                area_id=area_id
            )
        
        # Check turn on
        match = re.match(TURN_ON_PATTERN, text_lower, re.IGNORECASE)
        if match:
            target = match.group(1)
            domain = self._infer_domain(target)
            entity_id, area_id = self._resolve_target(target)
            return TimedAction.ha_service(
                service=f"{domain}.turn_on",
                entity_id=entity_id,
                area_id=area_id
            )
        
        # Check toggle
        match = re.match(TOGGLE_PATTERN, text_lower, re.IGNORECASE)
        if match:
            target = match.group(1)
            domain = self._infer_domain(target)
            entity_id, area_id = self._resolve_target(target)
            return TimedAction.ha_service(
                service=f"{domain}.toggle",
                entity_id=entity_id,
                area_id=area_id
            )
        
        return None
    
    def _infer_domain(self, target: str) -> str:
        """Infer HA domain from target name."""
        target_lower = target.lower()
        for keyword, domain in DOMAIN_KEYWORDS.items():
            if keyword in target_lower:
                return domain
        return "light"  # Default
    
    def _resolve_target(self, target: str) -> tuple[str | None, str | None]:
        """Resolve target to entity_id and/or area_id.
        
        Returns:
            (entity_id, area_id) - one or both may be set
        """
        if self._topology:
            # Try to resolve via topology service
            area_id = self._topology.resolve_area(target)
            if area_id:
                return None, area_id
        
        # Fall back to constructing entity_id from target name
        # "office light" -> "light.office", "porch fan" -> "fan.porch"
        domain = self._infer_domain(target)
        
        # Extract the location part
        target_clean = target.lower()
        for keyword in DOMAIN_KEYWORDS.keys():
            target_clean = target_clean.replace(keyword, "").strip()
        
        if target_clean:
            entity_id = f"{domain}.{target_clean.replace(' ', '_')}"
            return entity_id, None
        
        return None, None
    
    def _extract_timer_label(self, text: str) -> str | None:
        """Extract label from timer command."""
        # "set a pizza timer for 10 minutes" -> "pizza"
        match = re.search(r"(?:a|the)\s+(\w+)\s+timer", text.lower())
        if match:
            label = match.group(1)
            if label not in ("new", "quick", "short", "long"):
                return label
        return None
    
    def _generate_label(self, steps: list[TimedAction]) -> str:
        """Generate a label from action steps."""
        for step in steps:
            if step.action_type == ActionType.HA_SERVICE and step.service:
                # "light.turn_off" -> "turn off light"
                parts = step.service.split(".")
                if len(parts) == 2:
                    domain, action = parts
                    return f"{action.replace('_', ' ')} {domain}"
            elif step.action_type == ActionType.NOTIFICATION:
                return "reminder"
            elif step.action_type == ActionType.TTS_ANNOUNCE:
                return "announcement"
        return "timer"
    
    def _create_sequence(
        self,
        steps: list[TimedAction],
        label: str,
        speaker: str | None,
        room: str | None,
    ) -> ActionSequence:
        """Create an ActionSequence from parsed steps."""
        return ActionSequence(
            id=str(uuid.uuid4())[:8],
            steps=steps,
            label=label,
            created_by=speaker,
            created_in_room=room,
            created_at=datetime.now(),
        )
```

---

### 4. Sequence Executor

Create file: `src/barnabeenet/services/timers/sequence_executor.py`

```python
"""Sequence Executor - Orchestrates multi-step action sequences."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

from .models import (
    ActionSequence,
    ActionType,
    ActiveTimer,
    EscalationConfig,
    TimedAction,
    TimerType,
)

if TYPE_CHECKING:
    from .pool_manager import TimerPoolManager
    from .escalation import EscalationEngine
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
    from barnabeenet.services.notifications import NotificationService

logger = logging.getLogger(__name__)


class SequenceExecutor:
    """Executes multi-step action sequences using timer pool.
    
    Manages the lifecycle of sequences:
    1. Execute immediate actions (delay=0)
    2. Schedule delayed actions via timer pool
    3. On timer completion, execute action and advance sequence
    4. For alarm-type, trigger escalation engine
    """
    
    def __init__(
        self,
        timer_pool: TimerPoolManager,
        ha_client: HomeAssistantClient,
        notification_service: NotificationService,
        escalation_engine: EscalationEngine,
        tts_callback: Callable[[str, str | None], None] | None = None,
    ):
        """Initialize executor.
        
        Args:
            timer_pool: Timer pool manager
            ha_client: Home Assistant client
            notification_service: For sending notifications
            escalation_engine: For alarm escalation
            tts_callback: Callback for TTS announcements (message, room)
        """
        self._pool = timer_pool
        self._ha = ha_client
        self._notifications = notification_service
        self._escalation = escalation_engine
        self._tts_callback = tts_callback
        
        # Track active sequences
        self._active_sequences: dict[str, ActionSequence] = {}
        
        # Register as timer completion handler
        self._pool._on_timer_finished = self._on_timer_finished
    
    async def execute(self, sequence: ActionSequence) -> bool:
        """Start executing a sequence.
        
        Args:
            sequence: Sequence to execute
            
        Returns:
            True if started successfully
        """
        if not sequence.steps:
            logger.warning("Cannot execute empty sequence")
            return False
        
        logger.info(
            "Starting sequence '%s' with %d steps (id: %s)",
            sequence.label,
            len(sequence.steps),
            sequence.id
        )
        
        # Register sequence
        self._active_sequences[sequence.id] = sequence
        
        # Process first step
        return await self._process_current_step(sequence)
    
    async def cancel_sequence(self, sequence_id: str) -> bool:
        """Cancel an active sequence.
        
        Args:
            sequence_id: Sequence ID
            
        Returns:
            True if cancelled
        """
        sequence = self._active_sequences.get(sequence_id)
        if not sequence:
            return False
        
        # Cancel any pending timers for this sequence
        timers = self._pool.get_timers_for_sequence(sequence_id)
        for timer in timers:
            await self._pool.cancel_timer(timer.id)
        
        # Mark sequence as cancelled
        sequence.is_active = False
        sequence.cancelled_at = datetime.now()
        
        del self._active_sequences[sequence_id]
        logger.info("Cancelled sequence '%s' (id: %s)", sequence.label, sequence_id)
        
        return True
    
    async def cancel_all_sequences(self) -> int:
        """Cancel all active sequences.
        
        Returns:
            Number cancelled
        """
        sequence_ids = list(self._active_sequences.keys())
        count = 0
        for seq_id in sequence_ids:
            if await self.cancel_sequence(seq_id):
                count += 1
        return count
    
    def get_active_sequences(self) -> list[ActionSequence]:
        """Get all active sequences."""
        return list(self._active_sequences.values())
    
    async def _process_current_step(self, sequence: ActionSequence) -> bool:
        """Process the current step of a sequence.
        
        If step has no delay, execute immediately and advance.
        If step has delay, create timer and wait.
        """
        step = sequence.current_step
        if not step:
            # Sequence complete
            await self._complete_sequence(sequence)
            return True
        
        logger.debug(
            "Processing step %d of sequence '%s': %s (delay: %s)",
            sequence.current_step_index + 1,
            sequence.label,
            step.action_type.value,
            step.delay
        )
        
        if step.delay.total_seconds() <= 0:
            # Execute immediately
            await self._execute_action(step, sequence)
            
            # Advance to next step
            sequence.advance()
            return await self._process_current_step(sequence)
        else:
            # Create timer for delayed execution
            timer = await self._pool.create_timer(
                timer_type=TimerType.SEQUENCE_STEP,
                duration=step.delay,
                label=sequence.label,
                created_by=sequence.created_by,
                created_in_room=sequence.created_in_room,
                on_complete=step,
                sequence_id=sequence.id,
                sequence_step_index=sequence.current_step_index,
            )
            
            if not timer:
                logger.error("Failed to create timer for sequence step")
                return False
            
            return True
    
    async def _on_timer_finished(self, timer: ActiveTimer) -> None:
        """Handle timer completion.
        
        Called by TimerPoolManager when a timer finishes.
        """
        # If part of a sequence, handle that
        if timer.sequence_id:
            await self._handle_sequence_timer(timer)
        # If alarm type with escalation, trigger that
        elif timer.timer_type == TimerType.ALARM and timer.escalation:
            await self._handle_alarm_timer(timer)
        # If has on_complete action, execute it
        elif timer.on_complete:
            await self._execute_action(timer.on_complete, context_room=timer.created_in_room)
    
    async def _handle_sequence_timer(self, timer: ActiveTimer) -> None:
        """Handle timer completion for a sequence step."""
        sequence = self._active_sequences.get(timer.sequence_id)
        if not sequence:
            logger.warning("Timer for unknown sequence: %s", timer.sequence_id)
            return
        
        # Execute the action
        if timer.on_complete:
            await self._execute_action(timer.on_complete, sequence)
        
        # Advance sequence
        sequence.advance()
        
        # Process next step
        await self._process_current_step(sequence)
    
    async def _handle_alarm_timer(self, timer: ActiveTimer) -> None:
        """Handle alarm timer completion - trigger escalation."""
        logger.info("Alarm timer finished: '%s'", timer.label)
        
        if self._escalation and timer.escalation:
            await self._escalation.start_escalation(timer)
    
    async def _execute_action(
        self,
        action: TimedAction,
        sequence: ActionSequence | None = None,
        context_room: str | None = None,
    ) -> bool:
        """Execute a single action.
        
        Args:
            action: Action to execute
            sequence: Parent sequence (for context)
            context_room: Room context if not from sequence
            
        Returns:
            True if executed successfully
        """
        room = action.target_room or (sequence.created_in_room if sequence else context_room)
        
        try:
            if action.action_type == ActionType.HA_SERVICE:
                return await self._execute_ha_service(action)
            
            elif action.action_type == ActionType.TTS_ANNOUNCE:
                return await self._execute_tts(action, room)
            
            elif action.action_type == ActionType.NOTIFICATION:
                return await self._execute_notification(action)
            
            elif action.action_type == ActionType.CHIME:
                return await self._execute_chime(action, room)
            
            else:
                logger.warning("Unknown action type: %s", action.action_type)
                return False
                
        except Exception as e:
            logger.exception("Error executing action %s", action.action_type)
            return False
    
    async def _execute_ha_service(self, action: TimedAction) -> bool:
        """Execute a Home Assistant service call."""
        if not action.service:
            return False
        
        # Build service call
        kwargs = dict(action.service_data) if action.service_data else {}
        
        if action.entity_id:
            kwargs["entity_id"] = action.entity_id
        elif action.area_id:
            kwargs["area_id"] = action.area_id
        
        logger.info(
            "Executing HA service: %s (target: %s)",
            action.service,
            action.entity_id or action.area_id
        )
        
        result = await self._ha.call_service(action.service, **kwargs)
        return result.success
    
    async def _execute_tts(self, action: TimedAction, room: str | None) -> bool:
        """Execute TTS announcement."""
        if not action.message:
            return False
        
        logger.info("TTS in %s: '%s'", room or "default", action.message)
        
        if self._tts_callback:
            await self._tts_callback(action.message, room)
            return True
        
        # Fallback: use HA TTS service directly
        # This requires knowing the media_player entity for the room
        return True  # TODO: Implement fallback
    
    async def _execute_notification(self, action: TimedAction) -> bool:
        """Execute push notification."""
        if not action.notification_message:
            return False
        
        logger.info(
            "Notification to %s: '%s'",
            action.notification_target or "all",
            action.notification_message
        )
        
        return await self._notifications.send_push_notification(
            user_name=action.notification_target,
            title=action.notification_title or "BarnabeeNet",
            message=action.notification_message,
            priority="critical" if action.bypass_silent else "normal"
        )
    
    async def _execute_chime(self, action: TimedAction, room: str | None) -> bool:
        """Play a chime sound."""
        # TODO: Implement via media_player.play_media
        return True
    
    async def _complete_sequence(self, sequence: ActionSequence) -> None:
        """Mark a sequence as complete."""
        sequence.is_active = False
        sequence.completed_at = datetime.now()
        
        if sequence.id in self._active_sequences:
            del self._active_sequences[sequence.id]
        
        logger.info(
            "Sequence complete: '%s' (id: %s)",
            sequence.label,
            sequence.id
        )
```

---

### 5. Escalation Engine

Create file: `src/barnabeenet/services/timers/escalation.py`

```python
"""Escalation Engine - Progressive notification for timer alerts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from .models import (
    ActiveTimer,
    EscalationConfig,
    EscalationStage,
    EscalationState,
    NotificationPriority,
)

if TYPE_CHECKING:
    from barnabeenet.services.notifications import NotificationService

logger = logging.getLogger(__name__)


class EscalationEngine:
    """Manages progressive notification escalation for timer alerts.
    
    When an alarm timer finishes, this engine:
    1. Announces in the originating room
    2. Waits for acknowledgment (wake word detection)
    3. If not acknowledged, expands to more rooms
    4. Finally sends push notifications to phones
    
    Acknowledgment can come from:
    - Wake word detection ("OK Barnabee" to stop alarm)
    - Explicit voice command ("stop the alarm")
    - Dashboard interaction
    """
    
    def __init__(
        self,
        notification_service: NotificationService,
        tts_callback: Callable[[str, str, bool], None] | None = None,
        wake_word_callback: Callable[[], asyncio.Event] | None = None,
    ):
        """Initialize escalation engine.
        
        Args:
            notification_service: For sending phone notifications
            tts_callback: Callback for TTS (message, room, repeat)
            wake_word_callback: Callback that returns event triggered on wake word
        """
        self._notifications = notification_service
        self._tts_callback = tts_callback
        self._wake_word_callback = wake_word_callback
        
        # Active escalations
        self._active: dict[str, EscalationState] = {}
        self._ack_events: dict[str, asyncio.Event] = {}
        
        # Tasks for active escalations
        self._tasks: dict[str, asyncio.Task] = {}
    
    async def start_escalation(self, timer: ActiveTimer) -> None:
        """Begin escalation for a finished timer.
        
        Args:
            timer: The timer that finished
        """
        if not timer.escalation:
            logger.warning("Timer has no escalation config")
            return
        
        state = timer.escalation
        state.started_at = datetime.now()
        
        # Create acknowledgment event
        ack_event = asyncio.Event()
        self._ack_events[timer.id] = ack_event
        self._active[timer.id] = state
        
        # Start escalation task
        task = asyncio.create_task(self._run_escalation(timer, state, ack_event))
        self._tasks[timer.id] = task
        
        logger.info(
            "Started escalation for timer '%s' (id: %s)",
            timer.label,
            timer.id
        )
    
    async def acknowledge(self, timer_id: str, source: str | None = None) -> bool:
        """Acknowledge an escalating timer.
        
        Args:
            timer_id: Timer ID to acknowledge
            source: Where the acknowledgment came from (room, device, etc.)
            
        Returns:
            True if acknowledged, False if not found
        """
        ack_event = self._ack_events.get(timer_id)
        state = self._active.get(timer_id)
        
        if not ack_event or not state:
            return False
        
        state.acknowledged = True
        state.acknowledged_at = datetime.now()
        state.acknowledged_by = source
        ack_event.set()
        
        logger.info("Timer '%s' acknowledged by %s", timer_id, source or "unknown")
        return True
    
    async def acknowledge_all(self, source: str | None = None) -> int:
        """Acknowledge all escalating timers.
        
        Args:
            source: Acknowledgment source
            
        Returns:
            Number acknowledged
        """
        count = 0
        for timer_id in list(self._ack_events.keys()):
            if await self.acknowledge(timer_id, source):
                count += 1
        return count
    
    def get_active_escalations(self) -> list[tuple[str, EscalationState]]:
        """Get all active escalations."""
        return [(tid, state) for tid, state in self._active.items() if state.is_active]
    
    async def _run_escalation(
        self,
        timer: ActiveTimer,
        state: EscalationState,
        ack_event: asyncio.Event
    ) -> None:
        """Run the escalation sequence.
        
        Progresses through stages until acknowledged or timed out.
        """
        config = state.config
        message = f"Your {timer.label} timer is done"
        originating_room = timer.created_in_room
        
        try:
            # Stage 1: Originating room
            state.stage = EscalationStage.ROOM
            state.stage_started_at = datetime.now()
            
            rooms = self._resolve_room_targets(
                config.stage_room_targets[0] if config.stage_room_targets else ["originating_room"],
                originating_room
            )
            
            await self._announce_in_rooms(message, rooms, config.chime_sound, config.repeat_announcements)
            
            # Wait for acknowledgment or timeout
            if await self._wait_for_ack(ack_event, config.stage_delays[0] if config.stage_delays else 30):
                await self._cleanup(timer.id)
                return
            
            # Stage 2: Common areas
            if len(config.stage_room_targets) > 1:
                state.stage = EscalationStage.COMMON_AREAS
                state.stage_started_at = datetime.now()
                
                rooms = self._resolve_room_targets(config.stage_room_targets[1], originating_room)
                await self._announce_in_rooms(message, rooms, config.chime_sound, config.repeat_announcements)
                
                delay = config.stage_delays[1] if len(config.stage_delays) > 1 else 60
                if await self._wait_for_ack(ack_event, delay):
                    await self._cleanup(timer.id)
                    return
            
            # Stage 3: Phone notifications
            state.stage = EscalationStage.PHONES
            state.stage_started_at = datetime.now()
            
            await self._send_phone_notifications(message, config.phone_targets)
            
            # Wait for final acknowledgment
            delay = config.stage_delays[2] if len(config.stage_delays) > 2 else 120
            await self._wait_for_ack(ack_event, min(delay, config.max_escalation_duration))
            
            # Complete
            if not state.acknowledged:
                state.timed_out = True
                logger.warning("Escalation timed out for timer '%s'", timer.label)
            
            state.stage = EscalationStage.COMPLETED
            
        except asyncio.CancelledError:
            logger.info("Escalation cancelled for timer '%s'", timer.label)
        except Exception as e:
            logger.exception("Error in escalation for timer '%s'", timer.label)
        finally:
            await self._cleanup(timer.id)
    
    async def _wait_for_ack(self, event: asyncio.Event, timeout: float) -> bool:
        """Wait for acknowledgment event with timeout.
        
        Returns:
            True if acknowledged, False if timed out
        """
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    async def _announce_in_rooms(
        self,
        message: str,
        rooms: list[str],
        chime: str | None,
        repeat: bool
    ) -> None:
        """Announce message in specified rooms."""
        if not self._tts_callback:
            logger.warning("No TTS callback configured")
            return
        
        for room in rooms:
            try:
                await self._tts_callback(message, room, repeat)
            except Exception as e:
                logger.warning("Error announcing in %s: %s", room, e)
    
    async def _send_phone_notifications(
        self,
        message: str,
        targets: list[str]
    ) -> None:
        """Send push notifications to phones."""
        for target in targets:
            if target == "all":
                # Send to all registered users
                await self._notifications.send_to_all(
                    title="⏱️ Timer Alert",
                    message=message,
                    priority=NotificationPriority.CRITICAL
                )
            else:
                await self._notifications.send_push_notification(
                    user_name=target,
                    title="⏱️ Timer Alert",
                    message=message,
                    priority=NotificationPriority.CRITICAL
                )
    
    def _resolve_room_targets(
        self,
        targets: list[str],
        originating_room: str | None
    ) -> list[str]:
        """Resolve room target placeholders."""
        rooms = []
        for target in targets:
            if target == "originating_room":
                if originating_room:
                    rooms.append(originating_room)
            else:
                rooms.append(target)
        return rooms
    
    async def _cleanup(self, timer_id: str) -> None:
        """Cleanup after escalation completes."""
        self._ack_events.pop(timer_id, None)
        self._active.pop(timer_id, None)
        self._tasks.pop(timer_id, None)
```

---

### 6. Notification Service

Create file: `src/barnabeenet/services/notifications.py`

```python
"""Notification Service - Sends notifications to mobile devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from barnabeenet.services.timers.models import (
    NotificationPriority,
    Platform,
    UserDevice,
)

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


class NotificationService:
    """Manages notification delivery to mobile devices.
    
    Supports:
    - Android: TTS via companion app, push notifications
    - iOS: Push notifications with critical alerts
    """
    
    def __init__(self, ha_client: HomeAssistantClient):
        self._ha = ha_client
        self._users: dict[str, UserDevice] = {}
    
    def register_user(
        self,
        user_name: str,
        device_id: str,
        platform: Platform
    ) -> None:
        """Register a user's device.
        
        Args:
            user_name: User name (e.g., "thom")
            device_id: HA device ID for notify service
            platform: android or ios
        """
        self._users[user_name.lower()] = UserDevice(
            user_name=user_name,
            device_id=device_id,
            platform=platform
        )
        logger.info("Registered device for %s: %s (%s)", user_name, device_id, platform.value)
    
    def get_user_device(self, user_name: str) -> UserDevice | None:
        """Get device for a user."""
        return self._users.get(user_name.lower())
    
    async def send_tts_notification(
        self,
        user_name: str | None,
        message: str,
        priority: NotificationPriority | str = NotificationPriority.HIGH
    ) -> bool:
        """Send TTS notification to user's phone.
        
        On Android, this speaks the message aloud.
        On iOS, this sends a push notification (no background TTS support).
        
        Args:
            user_name: Target user (None for all)
            message: Message to speak/send
            priority: Notification priority
            
        Returns:
            True if sent successfully
        """
        if isinstance(priority, str):
            priority = NotificationPriority(priority)
        
        if user_name is None:
            return await self.send_to_all_tts(message, priority)
        
        device = self._users.get(user_name.lower())
        if not device:
            logger.warning("No device registered for user: %s", user_name)
            return False
        
        try:
            if device.platform == Platform.ANDROID:
                return await self._send_android_tts(device, message, priority)
            else:
                # iOS doesn't support background TTS
                return await self._send_ios_notification(
                    device,
                    "BarnabeeNet",
                    message,
                    priority
                )
        except Exception as e:
            logger.exception("Error sending TTS to %s", user_name)
            return False
    
    async def send_push_notification(
        self,
        user_name: str | None,
        title: str,
        message: str,
        priority: NotificationPriority | str = NotificationPriority.NORMAL
    ) -> bool:
        """Send push notification to user's phone.
        
        Args:
            user_name: Target user (None for all)
            title: Notification title
            message: Notification body
            priority: Notification priority
            
        Returns:
            True if sent successfully
        """
        if isinstance(priority, str):
            priority = NotificationPriority(priority)
        
        if user_name is None:
            return await self.send_to_all(title, message, priority)
        
        device = self._users.get(user_name.lower())
        if not device:
            logger.warning("No device registered for user: %s", user_name)
            return False
        
        try:
            if device.platform == Platform.ANDROID:
                return await self._send_android_notification(device, title, message, priority)
            else:
                return await self._send_ios_notification(device, title, message, priority)
        except Exception as e:
            logger.exception("Error sending notification to %s", user_name)
            return False
    
    async def send_to_all(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send push notification to all registered users."""
        success = True
        for user_name in self._users:
            if not await self.send_push_notification(user_name, title, message, priority):
                success = False
        return success
    
    async def send_to_all_tts(
        self,
        message: str,
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> bool:
        """Send TTS notification to all registered users."""
        success = True
        for user_name in self._users:
            if not await self.send_tts_notification(user_name, message, priority):
                success = False
        return success
    
    async def _send_android_tts(
        self,
        device: UserDevice,
        message: str,
        priority: NotificationPriority
    ) -> bool:
        """Send TTS to Android device."""
        data: dict[str, Any] = {"tts_text": message}
        
        # Use alarm stream to bypass silent mode for high/critical priority
        if priority in (NotificationPriority.HIGH, NotificationPriority.CRITICAL):
            data["media_stream"] = "alarm_stream_max"
        
        result = await self._ha.call_service(
            device.notify_service,
            message="TTS",
            data=data
        )
        
        return result.success
    
    async def _send_android_notification(
        self,
        device: UserDevice,
        title: str,
        message: str,
        priority: NotificationPriority
    ) -> bool:
        """Send push notification to Android device."""
        data: dict[str, Any] = {
            "ttl": 0,
            "priority": "high" if priority != NotificationPriority.LOW else "normal",
            "channel": "barnabee_timers",
        }
        
        if priority == NotificationPriority.CRITICAL:
            data["importance"] = "max"
            data["vibrationPattern"] = "100, 200, 100, 200, 100"
        
        result = await self._ha.call_service(
            device.notify_service,
            title=title,
            message=message,
            data=data
        )
        
        return result.success
    
    async def _send_ios_notification(
        self,
        device: UserDevice,
        title: str,
        message: str,
        priority: NotificationPriority
    ) -> bool:
        """Send push notification to iOS device."""
        data: dict[str, Any] = {}
        
        # Critical alerts bypass DND and silent mode
        if priority == NotificationPriority.CRITICAL:
            data["push"] = {
                "sound": {
                    "name": "default",
                    "critical": 1,
                    "volume": 0.8
                }
            }
        elif priority == NotificationPriority.HIGH:
            data["push"] = {
                "interruption-level": "time-sensitive"
            }
        
        result = await self._ha.call_service(
            device.notify_service,
            title=title,
            message=message,
            data=data
        )
        
        return result.success
```

---

## Integration Points

### Timer Service Facade

Create file: `src/barnabeenet/services/timers/service.py`

```python
"""Timer Service - Main facade for timer functionality."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from .models import (
    ActionSequence,
    ActiveTimer,
    EscalationConfig,
    TimerType,
)
from .duration_parser import parse_duration, format_duration
from .sequence_parser import SequenceParser
from .pool_manager import TimerPoolManager, TimerPoolConfig
from .sequence_executor import SequenceExecutor
from .escalation import EscalationEngine

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
    from barnabeenet.services.homeassistant.topology import HATopologyService
    from barnabeenet.services.notifications import NotificationService

logger = logging.getLogger(__name__)


class TimerService:
    """Facade for all timer functionality.
    
    Use this class for all timer operations. It coordinates:
    - Timer pool management
    - Sequence parsing and execution
    - Escalation for alarms
    - Query methods for timer state
    """
    
    def __init__(
        self,
        ha_client: HomeAssistantClient,
        notification_service: NotificationService,
        topology: HATopologyService | None = None,
        pool_config: TimerPoolConfig | None = None,
        default_escalation_config: EscalationConfig | None = None,
    ):
        """Initialize timer service.
        
        Args:
            ha_client: Home Assistant client
            notification_service: Notification service
            topology: HA topology for resolving areas
            pool_config: Timer pool configuration
            default_escalation_config: Default escalation settings
        """
        self._ha = ha_client
        self._notifications = notification_service
        self._default_escalation = default_escalation_config or EscalationConfig()
        
        # Initialize components
        self._pool = TimerPoolManager(ha_client, pool_config)
        self._parser = SequenceParser(topology)
        self._escalation = EscalationEngine(notification_service)
        self._executor = SequenceExecutor(
            timer_pool=self._pool,
            ha_client=ha_client,
            notification_service=notification_service,
            escalation_engine=self._escalation,
        )
    
    async def initialize(self) -> None:
        """Initialize the timer service.
        
        Call this after construction to verify HA entities exist.
        """
        await self._pool.initialize()
    
    # =========================================================================
    # Voice Command Processing
    # =========================================================================
    
    def is_timer_command(self, text: str) -> bool:
        """Check if text appears to be a timer command.
        
        Use this in your Meta Agent to route timer commands.
        """
        return self._parser.is_timer_command(text)
    
    async def process_command(
        self,
        text: str,
        speaker: str | None = None,
        room: str | None = None,
    ) -> dict:
        """Process a timer voice command.
        
        Args:
            text: Voice command text
            speaker: Who said it
            room: Where it was said
            
        Returns:
            Dict with 'success', 'response', and optionally 'timer' or 'sequence'
        """
        # Parse the command
        sequence = self._parser.parse(text, speaker, room)
        
        if not sequence:
            return {
                "success": False,
                "response": "I couldn't understand that timer command."
            }
        
        # Check if this is a simple alarm (single TTS step with delay)
        if self._is_simple_alarm(sequence):
            return await self._handle_simple_alarm(sequence)
        
        # Execute as sequence
        success = await self._executor.execute(sequence)
        
        if success:
            response = self._generate_confirmation(sequence)
            return {
                "success": True,
                "response": response,
                "sequence": sequence.to_dict()
            }
        else:
            return {
                "success": False,
                "response": "I couldn't set that timer. No timer slots available."
            }
    
    def _is_simple_alarm(self, sequence: ActionSequence) -> bool:
        """Check if sequence is a simple alarm timer."""
        if len(sequence.steps) != 1:
            return False
        step = sequence.steps[0]
        return (
            step.action_type.value == "tts_announce" and
            step.delay.total_seconds() > 0 and
            "timer is done" in (step.message or "").lower()
        )
    
    async def _handle_simple_alarm(self, sequence: ActionSequence) -> dict:
        """Handle a simple alarm timer with escalation."""
        step = sequence.steps[0]
        
        timer = await self._pool.create_timer(
            timer_type=TimerType.ALARM,
            duration=step.delay,
            label=sequence.label,
            created_by=sequence.created_by,
            created_in_room=sequence.created_in_room,
            escalation_config=self._default_escalation,
        )
        
        if not timer:
            return {
                "success": False,
                "response": "No timer slots available."
            }
        
        duration_text = format_duration(step.delay)
        return {
            "success": True,
            "response": f"OK, {sequence.label} timer set for {duration_text}.",
            "timer": timer.to_dict()
        }
    
    def _generate_confirmation(self, sequence: ActionSequence) -> str:
        """Generate confirmation message for a sequence."""
        if len(sequence.steps) == 1:
            step = sequence.steps[0]
            duration_text = format_duration(step.delay)
            return f"OK, I'll do that in {duration_text}."
        else:
            return f"OK, I've set up {len(sequence.steps)} steps for you."
    
    # =========================================================================
    # Timer Management
    # =========================================================================
    
    async def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a specific timer."""
        # Also acknowledge any escalation
        await self._escalation.acknowledge(timer_id)
        return await self._pool.cancel_timer(timer_id)
    
    async def cancel_by_label(self, label: str) -> bool:
        """Cancel a timer by its label."""
        timer = self._pool.get_by_label(label)
        if timer:
            return await self.cancel_timer(timer.id)
        return False
    
    async def cancel_all(self) -> int:
        """Cancel all timers and sequences."""
        # Acknowledge all escalations
        await self._escalation.acknowledge_all()
        # Cancel all sequences
        await self._executor.cancel_all_sequences()
        # Cancel all timers
        return await self._pool.cancel_all()
    
    async def pause_timer(self, timer_id: str) -> bool:
        """Pause a timer."""
        return await self._pool.pause_timer(timer_id)
    
    async def resume_timer(self, timer_id: str) -> bool:
        """Resume a paused timer."""
        return await self._pool.resume_timer(timer_id)
    
    async def add_time(self, timer_id: str, additional: timedelta) -> bool:
        """Add time to a running timer."""
        return await self._pool.add_time(timer_id, additional)
    
    async def acknowledge_alarm(self, timer_id: str | None = None) -> bool:
        """Acknowledge an alarm (stop the escalation).
        
        Args:
            timer_id: Specific timer, or None for all
        """
        if timer_id:
            return await self._escalation.acknowledge(timer_id)
        else:
            count = await self._escalation.acknowledge_all()
            return count > 0
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    def get_timer(self, timer_id: str) -> ActiveTimer | None:
        """Get a timer by ID."""
        return self._pool.get_timer(timer_id)
    
    def get_by_label(self, label: str) -> ActiveTimer | None:
        """Get a timer by label."""
        return self._pool.get_by_label(label)
    
    def get_active_timers(self) -> list[ActiveTimer]:
        """Get all active timers."""
        return self._pool.get_active_timers()
    
    def get_active_sequences(self) -> list[ActionSequence]:
        """Get all active sequences."""
        return self._executor.get_active_sequences()
    
    def format_timer_status(self, timer: ActiveTimer) -> str:
        """Format timer status for voice response."""
        remaining = format_duration(timer.remaining)
        return f"Your {timer.label} timer has {remaining} remaining."
    
    def format_all_timers_status(self) -> str:
        """Format status of all timers for voice response."""
        timers = self.get_active_timers()
        
        if not timers:
            return "You have no active timers."
        
        if len(timers) == 1:
            return self.format_timer_status(timers[0])
        
        lines = [f"You have {len(timers)} active timers:"]
        for timer in timers:
            remaining = format_duration(timer.remaining)
            lines.append(f"  {timer.label}: {remaining} remaining")
        
        return "\n".join(lines)
```

---

## Voice Command Patterns

### Commands the System Should Handle

| Command | Parsed As | Timer Type |
|---------|-----------|------------|
| "Set a timer for 5 minutes" | Alarm timer, 5 min | ALARM |
| "Set a pizza timer for 15 minutes" | Alarm timer "pizza", 15 min | ALARM |
| "Five minute timer" | Alarm timer, 5 min | ALARM |
| "Turn on the porch light for 10 minutes" | Sequence: turn_on now, turn_off in 10 min | DEVICE_DURATION |
| "In 5 minutes turn off the fan" | Delayed action: turn_off in 5 min | DELAYED_ACTION |
| "After 10 minutes turn off the office light" | Delayed action: turn_off in 10 min | DELAYED_ACTION |
| "Wait 5 minutes and notify me to check the oven" | Sequence: notification in 5 min | SEQUENCE |
| "Wait 5 min, notify me, then 3 min later turn off the light" | Multi-step sequence | SEQUENCE |
| "Cancel the pizza timer" | Cancel by label | - |
| "Cancel all timers" | Cancel all | - |
| "How much time is left on the pizza timer?" | Query by label | - |
| "What timers are running?" | Query all | - |
| "Pause the timer" | Pause | - |
| "Resume the timer" | Resume | - |
| "Add 5 minutes to the timer" | Add time | - |
| "Stop" / "OK Barnabee" (during alarm) | Acknowledge escalation | - |

### Meta Agent Integration

Add to Meta Agent's classification logic:

```python
# In meta_agent.py

async def classify_intent(self, text: str, context: dict) -> str:
    """Classify the intent of a message."""
    
    # Check for timer commands first (before other patterns)
    if self._timer_service.is_timer_command(text):
        return "timer"
    
    # ... rest of classification
```

Add timer handling in the agent router:

```python
# In agent router

if intent == "timer":
    result = await self._timer_service.process_command(
        text=message,
        speaker=context.get("speaker"),
        room=context.get("room"),
    )
    return TextProcessResponse(
        response_text=result["response"],
        success=result["success"],
        trace=TraceDetails(
            routing_reason="Timer command detected",
            timer_info=result.get("timer") or result.get("sequence"),
        )
    )
```

---

## Testing Scenarios

### Unit Tests

```python
# tests/services/timers/test_duration_parser.py

import pytest
from datetime import timedelta
from barnabeenet.services.timers.duration_parser import parse_duration, normalize_word_numbers


class TestNormalizeWordNumbers:
    def test_simple_numbers(self):
        assert normalize_word_numbers("five minutes") == "5 minutes"
        assert normalize_word_numbers("ten seconds") == "10 seconds"
        assert normalize_word_numbers("one hour") == "1 hour"
    
    def test_compound_numbers(self):
        assert normalize_word_numbers("twenty-five minutes") == "25 minutes"
        assert normalize_word_numbers("thirty two seconds") == "32 seconds"
    
    def test_mixed(self):
        assert normalize_word_numbers("5 minutes") == "5 minutes"  # Already numeric
        assert normalize_word_numbers("a minute") == "1 minute"


class TestParseDuration:
    def test_minutes(self):
        assert parse_duration("5 minutes") == timedelta(minutes=5)
        assert parse_duration("five minutes") == timedelta(minutes=5)
        assert parse_duration("30 mins") == timedelta(minutes=30)
    
    def test_seconds(self):
        assert parse_duration("30 seconds") == timedelta(seconds=30)
        assert parse_duration("45 secs") == timedelta(seconds=45)
    
    def test_hours(self):
        assert parse_duration("1 hour") == timedelta(hours=1)
        assert parse_duration("2 hours") == timedelta(hours=2)
        assert parse_duration("1.5 hours") == timedelta(hours=1, minutes=30)
    
    def test_compound(self):
        assert parse_duration("1 hour 30 minutes") == timedelta(hours=1, minutes=30)
        assert parse_duration("5 minutes 30 seconds") == timedelta(minutes=5, seconds=30)
    
    def test_casual(self):
        assert parse_duration("half an hour") == timedelta(minutes=30)
        assert parse_duration("quarter hour") == timedelta(minutes=15)
        assert parse_duration("a minute") == timedelta(minutes=1)
    
    def test_invalid(self):
        assert parse_duration("") is None
        assert parse_duration("hello world") is None
```

### Integration Tests

```python
# tests/services/timers/test_timer_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta

from barnabeenet.services.timers.service import TimerService
from barnabeenet.services.timers.models import TimerType


@pytest.fixture
def mock_ha_client():
    client = AsyncMock()
    client.call_service = AsyncMock(return_value=MagicMock(success=True))
    client.get_state = AsyncMock(return_value=MagicMock(state="idle"))
    return client


@pytest.fixture
def mock_notifications():
    return AsyncMock()


@pytest.fixture
async def timer_service(mock_ha_client, mock_notifications):
    service = TimerService(
        ha_client=mock_ha_client,
        notification_service=mock_notifications,
    )
    await service.initialize()
    return service


class TestTimerService:
    
    @pytest.mark.asyncio
    async def test_simple_alarm(self, timer_service):
        result = await timer_service.process_command(
            "set a timer for 5 minutes",
            speaker="thom",
            room="kitchen"
        )
        
        assert result["success"]
        assert "5 minutes" in result["response"]
        assert result.get("timer") is not None
    
    @pytest.mark.asyncio
    async def test_named_timer(self, timer_service):
        result = await timer_service.process_command(
            "set a pizza timer for 15 minutes",
            speaker="thom",
            room="kitchen"
        )
        
        assert result["success"]
        assert "pizza" in result["response"].lower()
    
    @pytest.mark.asyncio
    async def test_device_duration(self, timer_service):
        result = await timer_service.process_command(
            "turn on the porch light for 10 minutes",
            speaker="thom",
            room="kitchen"
        )
        
        assert result["success"]
    
    @pytest.mark.asyncio
    async def test_delayed_action(self, timer_service):
        result = await timer_service.process_command(
            "in 5 minutes turn off the office light",
            speaker="thom",
            room="office"
        )
        
        assert result["success"]
    
    @pytest.mark.asyncio
    async def test_cancel_by_label(self, timer_service):
        # First create a timer
        await timer_service.process_command(
            "set a pizza timer for 10 minutes",
            speaker="thom",
            room="kitchen"
        )
        
        # Then cancel it
        result = await timer_service.cancel_by_label("pizza")
        assert result
    
    @pytest.mark.asyncio
    async def test_query_timers(self, timer_service):
        # Create a timer
        await timer_service.process_command(
            "set a timer for 5 minutes",
            speaker="thom",
            room="kitchen"
        )
        
        # Query
        timers = timer_service.get_active_timers()
        assert len(timers) == 1
        
        status = timer_service.format_all_timers_status()
        assert "1 active" in status or "timer" in status.lower()
```

---

## File Structure

```
src/barnabeenet/services/
├── timers/
│   ├── __init__.py
│   ├── models.py              # All data models
│   ├── duration_parser.py     # Duration parsing utilities
│   ├── sequence_parser.py     # Voice command → ActionSequence
│   ├── pool_manager.py        # HA timer entity pool
│   ├── sequence_executor.py   # Multi-step execution
│   ├── escalation.py          # Progressive notifications
│   └── service.py             # Main facade
├── notifications.py           # Mobile notification service
└── homeassistant/
    ├── client.py              # HA API client (existing)
    └── topology.py            # Area/floor resolution (existing)

tests/services/timers/
├── __init__.py
├── test_duration_parser.py
├── test_sequence_parser.py
├── test_pool_manager.py
├── test_sequence_executor.py
├── test_escalation.py
└── test_timer_service.py
```

---

## Summary

This implementation provides:

1. **Echo-equivalent timers** - Simple "set a timer for X" with announcements
2. **Escalating alerts** - Room → Common areas → Phones until acknowledged
3. **Device duration** - "Turn on X for Y minutes"
4. **Delayed actions** - "In X minutes do Y"
5. **Complex sequences** - "Wait X, do Y, then Z"
6. **Word number support** - "five minutes" = "5 minutes"
7. **HA integration** - Uses timer helpers (survives restarts, visible in dashboard)
8. **Full query support** - "How much time left?", "What timers are running?"

The hybrid architecture (HA for countdown, BarnabeeNet for orchestration) gives you the best of both worlds: persistence and visibility from HA, complex logic and escalation from BarnabeeNet.
