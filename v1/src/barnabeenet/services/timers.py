"""Timer Manager for BarnabeeNet.

Manages three types of timers using Home Assistant's timer helper entities:
1. Alarm Timer - "Set a timer for 5 minutes" → announce when done
2. Device Duration Timer - "Turn on the porch light for 10 minutes" → turn off when done
3. Delayed Action Timer - "In 3 minutes, turn off the fan" → execute action when done

Pre-requisite: Create 5-10 timer helper entities in HA named timer.barnabee_1
through timer.barnabee_10. These form a pool that BarnabeeNet allocates from.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient

logger = logging.getLogger(__name__)


class TimerType(str, Enum):
    """Types of timers."""

    ALARM = "alarm"  # Basic timer with TTS announcement
    DEVICE_DURATION = "device_duration"  # Turn device on/off for duration
    DELAYED_ACTION = "delayed_action"  # Execute action after delay


@dataclass
class ActiveTimer:
    """An active timer managed by BarnabeeNet."""

    id: str  # UUID
    timer_type: TimerType
    ha_timer_entity: str  # e.g., "timer.barnabee_1"
    label: str  # Human-friendly label (e.g., "pizza timer", "porch light")
    duration: timedelta
    started_at: datetime
    ends_at: datetime
    speaker: str | None = None  # Who created it
    room: str | None = None  # Where it was created
    # For device_duration and delayed_action
    on_complete: dict[str, Any] | None = None  # Service call to execute
    # For chained actions
    chained_actions: list[dict[str, Any]] = field(default_factory=list)  # List of {delay, action}
    paused_at: datetime | None = None  # When timer was paused
    paused_duration: timedelta = field(default_factory=lambda: timedelta(0))  # Total paused time

    @property
    def remaining(self) -> timedelta:
        """Get remaining time on the timer."""
        if self.paused_at:
            # Timer is paused - return remaining time when paused
            paused_remaining = self.ends_at - self.paused_at
            return paused_remaining if paused_remaining > timedelta(0) else timedelta(0)

        now = datetime.now()
        if now >= self.ends_at:
            return timedelta(0)
        return self.ends_at - now

    @property
    def is_paused(self) -> bool:
        """Check if timer is currently paused."""
        return self.paused_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if timer has expired."""
        return datetime.now() >= self.ends_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "timer_type": self.timer_type.value,
            "ha_timer_entity": self.ha_timer_entity,
            "label": self.label,
            "duration_seconds": self.duration.total_seconds(),
            "started_at": self.started_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "remaining_seconds": self.remaining.total_seconds(),
            "speaker": self.speaker,
            "room": self.room,
            "on_complete": self.on_complete,
            "is_paused": self.is_paused,
        }


@dataclass
class TimerPoolConfig:
    """Configuration for the timer entity pool."""

    # Pattern for timer entities in HA
    entity_pattern: str = "timer.barnabee_{n}"
    # Number of timer entities in the pool
    pool_size: int = 10
    # Prefix for entity IDs
    prefix: str = "timer.barnabee_"


@dataclass
class TimerPool:
    """Pool of HA timer entities."""

    available: list[str] = field(default_factory=list)
    in_use: dict[str, str] = field(default_factory=dict)  # timer_id -> entity_id

    def allocate(self) -> str | None:
        """Allocate a timer entity from the pool."""
        if not self.available:
            return None
        entity = self.available.pop(0)
        return entity

    def release(self, entity: str) -> None:
        """Return a timer entity to the pool."""
        # Remove from in_use if present
        timer_ids_to_remove = [tid for tid, eid in self.in_use.items() if eid == entity]
        for tid in timer_ids_to_remove:
            del self.in_use[tid]
        # Add back to available if not already there
        if entity not in self.available:
            self.available.append(entity)


# =============================================================================
# Duration Parsing
# =============================================================================

# Word to number mapping
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90,
    "a": 1, "an": 1,
}


def word_to_number(text: str) -> int | None:
    """Convert word number to int (e.g., 'five' -> 5, 'twenty five' -> 25)."""
    text = text.lower().strip()

    # Try direct match
    if text in WORD_NUMBERS:
        return WORD_NUMBERS[text]

    # Try as integer
    try:
        return int(text)
    except ValueError:
        pass

    # Try compound numbers like "twenty five"
    parts = text.replace("-", " ").split()
    if len(parts) == 2:
        first = WORD_NUMBERS.get(parts[0])
        second = WORD_NUMBERS.get(parts[1])
        if first is not None and second is not None:
            if first >= 20 and second < 10:
                return first + second

    return None


# Patterns for parsing duration strings
DURATION_PATTERNS = [
    # Word numbers: "five minutes", "ten seconds"
    (r"(\w+(?:\s+\w+)?)\s*(?:minutes?|mins?)", "word_minutes"),
    (r"(\w+(?:\s+\w+)?)\s*(?:seconds?|secs?)", "word_seconds"),
    (r"(\w+(?:\s+\w+)?)\s*(?:hours?|hrs?)", "word_hours"),
    # Numeric: "5 minutes", "30 seconds"
    (r"(\d+)\s*(?:minutes?|mins?)", "minutes"),
    (r"(\d+)\s*(?:seconds?|secs?)", "seconds"),
    (r"(\d+)\s*(?:hours?|hrs?)", "hours"),
    # Float hours: "1.5 hours"
    (r"(\d+\.?\d*)\s*(?:hours?|hrs?)", "hours_float"),
    # Special phrases
    (r"half\s+(?:an?\s+)?hour", "half_hour"),
    (r"quarter\s+(?:of\s+)?(?:an?\s+)?hour", "quarter_hour"),
    (r"(?:a|an)\s+hour", "one_hour"),
    (r"(?:a|an)\s+minute", "one_minute"),
]


def parse_duration(text: str) -> timedelta | None:
    """Parse a duration string into a timedelta.

    Examples:
        - "5 minutes" -> timedelta(minutes=5)
        - "five minutes" -> timedelta(minutes=5)
        - "30 seconds" -> timedelta(seconds=30)
        - "1 hour" -> timedelta(hours=1)
        - "1.5 hours" -> timedelta(hours=1.5)
        - "half an hour" -> timedelta(minutes=30)
        - "a minute" -> timedelta(minutes=1)

    Args:
        text: Duration string

    Returns:
        timedelta if parsed, None otherwise
    """
    text = text.lower().strip()

    for pattern, unit in DURATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            if unit == "half_hour":
                return timedelta(minutes=30)
            elif unit == "quarter_hour":
                return timedelta(minutes=15)
            elif unit == "one_hour":
                return timedelta(hours=1)
            elif unit == "one_minute":
                return timedelta(minutes=1)
            elif unit == "hours_float":
                hours = float(match.group(1))
                return timedelta(hours=hours)
            elif unit == "word_minutes":
                value = word_to_number(match.group(1))
                if value is not None:
                    return timedelta(minutes=value)
            elif unit == "word_seconds":
                value = word_to_number(match.group(1))
                if value is not None:
                    return timedelta(seconds=value)
            elif unit == "word_hours":
                value = word_to_number(match.group(1))
                if value is not None:
                    return timedelta(hours=value)
            elif unit == "minutes":
                value = int(match.group(1))
                return timedelta(minutes=value)
            elif unit == "seconds":
                value = int(match.group(1))
                return timedelta(seconds=value)
            elif unit == "hours":
                value = int(match.group(1))
                return timedelta(hours=value)

    return None


def format_duration(td: timedelta) -> str:
    """Format a timedelta as human-readable text.

    Examples:
        - timedelta(minutes=5) -> "5 minutes"
        - timedelta(seconds=30) -> "30 seconds"
        - timedelta(hours=1, minutes=30) -> "1 hour 30 minutes"

    Args:
        td: timedelta to format

    Returns:
        Human-readable duration string
    """
    total_seconds = int(td.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if minutes < 60:
        parts = [f"{minutes} minute{'s' if minutes != 1 else ''}"]
        if seconds > 0:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        return " ".join(parts)

    hours = minutes // 60
    minutes = minutes % 60

    parts = [f"{hours} hour{'s' if hours != 1 else ''}"]
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts)


# =============================================================================
# Timer Pattern Recognition
# =============================================================================

# Word numbers for duration parsing
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "forty-five": 45, "fortyfive": 45,
    "sixty": 60, "ninety": 90,
}

# Alarm timer patterns
ALARM_PATTERNS = [
    # "set a 30 second timer" / "set a 5 minute timer" (duration before "timer")
    r"set\s+(?:a\s+)?(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+timer",
    # "set a two minute timer" / "set a five second timer" (word number before "timer")
    r"set\s+(?:a\s+)?(\w+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+timer",
    # "set a timer for 5 minutes"
    r"set\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)",
    # "5 minute timer"
    r"(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+timer",
    # "two minute timer" (word number)
    r"(\w+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+timer",
    # "set a pizza timer for 10 minutes"
    r"set\s+(?:a\s+)?(\w+)\s+timer\s+(?:for\s+)?(.+)",
    # "start a timer for 5 minutes"
    r"start\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)",
]

# Device duration patterns
DEVICE_DURATION_PATTERNS = [
    # "turn on the porch light for 10 minutes"
    r"(turn\s+on|switch\s+on)\s+(?:the\s+)?(.+?)\s+for\s+(.+)",
    # "lights on for 5 minutes"
    r"(.+?)\s+on\s+for\s+(.+)",
]

# Delayed action patterns - ORDER MATTERS! More specific patterns first.
# All patterns capture the FULL action text (e.g., "turn off the office light")
DELAYED_ACTION_PATTERNS = [
    # "in 60 seconds turn off the office light" - captures full action "turn off the office light"
    r"in\s+(\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))\s+(turn\s+(?:off|on)\s+(?:the\s+)?.+)",
    # "in 3 minutes, turn off the fan" - with comma separator
    r"in\s+(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s*,\s*(?:then\s+)?(.+)",
    # "in 3 minutes turn off the fan" - without comma, action must start with turn/switch
    r"in\s+(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+(?:then\s+)?((?:turn|switch).+)",
    # "in five minutes turn off the fan" - word numbers
    r"in\s+(\w+\s+(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s*,?\s*(?:then\s+)?(.+)",
    # "after 5 minutes turn off the lights"
    r"after\s+(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s*,?\s*(?:then\s+)?(.+)",
    # "wait 2 minutes and turn off the TV"
    r"wait\s+(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))\s+(?:and|then)\s+(.+)",
    # "turn off the fan in 3 minutes" - action comes first
    r"((?:turn|switch)\s+(?:off|on)\s+(?:the\s+)?.+?)\s+in\s+(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))$",
]

# Timer query patterns (with label capture)
TIMER_QUERY_PATTERNS = [
    # "how long on lasagna"
    r"how\s+long\s+(?:on|for|left\s+on)\s+(.+)",
    # "how much time left on pizza"
    r"how\s+much\s+time\s+left\s+(?:on|for)\s+(.+)",
    # "time left on lasagna"
    r"time\s+left\s+(?:on|for)\s+(.+)",
    # "how long is the lasagna timer"
    r"how\s+long\s+is\s+(?:the\s+)?(.+?)\s+timer",
    # "what's left on lasagna"
    r"what'?s?\s+left\s+(?:on|for)\s+(.+)",
]

# Timer list patterns (list all timers, no label required)
TIMER_LIST_PATTERNS = [
    # "what timers do I have" / "what timers are set"
    r"what\s+timers?\s+(?:do\s+I\s+have|are\s+(?:set|running|active))",
    # "list my timers" / "show my timers"
    r"(?:list|show)\s+(?:my\s+)?timers?",
    # "how long is left on my timer" (generic, no specific label)
    r"how\s+long\s+(?:is\s+)?left\s+on\s+(?:my|the)\s+timer",
    # "how much time is left on my timer"
    r"how\s+much\s+time\s+(?:is\s+)?left\s+on\s+(?:my|the)\s+timer",
    # "any timers running" / "any timers" / "are there any timers"
    r"(?:any|are\s+there(?:\s+any)?)\s+timers?(?:\s+(?:running|set|active))?",
    # "do I have any timers"
    r"do\s+I\s+have\s+(?:any\s+)?timers?(?:\s+(?:set|running|active))?",
    # "timer status" / "timers status"
    r"timers?\s+status",
    # "how many timers do I have"
    r"how\s+many\s+timers?\s+(?:do\s+I\s+have|are\s+(?:set|running|active))?",
]

# Generic timer control patterns (no specific label - affects all/most recent timer)
TIMER_GENERIC_CONTROL_PATTERNS = [
    # "stop my timer" / "cancel my timer" / "stop the timer" / "cancel the timers"
    r"^(stop|cancel|pause|resume)\s+(?:my|the|all)\s+timers?$",
    # "stop timer" / "cancel timer"
    r"^(stop|cancel|pause|resume)\s+timer$",
]

# Timer control patterns with specific labels
# IMPORTANT: These must require "timer" in the text to avoid matching media commands
# like "pause the tv" or "stop the music"
TIMER_CONTROL_PATTERNS = [
    # "pause the lasagna timer" - requires "timer" in text
    r"pause\s+(?:the\s+)?(.+?)\s+timer$",
    # "resume the lasagna timer"
    r"resume\s+(?:the\s+)?(.+?)\s+timer$",
    # "stop the lasagna timer"
    r"stop\s+(?:the\s+)?(.+?)\s+timer$",
    # "cancel the lasagna timer"
    r"cancel\s+(?:the\s+)?(.+?)\s+timer$",
    # "start the lasagna timer"
    r"start\s+(?:the\s+)?(.+?)\s+timer$",
]

# Media keywords that should NOT be treated as timer labels
MEDIA_KEYWORDS = {"tv", "music", "video", "speaker", "playback", "song", "track", "album"}


class TimerOperation(str, Enum):
    """Timer operations."""

    CREATE = "create"
    QUERY = "query"
    LIST = "list"  # List all active timers
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    CANCEL_ALL = "cancel_all"  # Cancel all/most recent timer (generic "stop my timer")
    START = "start"
    STOP = "stop"


@dataclass
class TimerParseResult:
    """Result of parsing a timer command."""

    timer_type: TimerType | None = None
    duration: timedelta | None = None
    label: str | None = None
    # For device duration / delayed action
    action_text: str | None = None
    target_device: str | None = None
    is_timer_command: bool = False
    operation: TimerOperation | None = None  # query, pause, resume, cancel, etc.


def parse_timer_command(text: str) -> TimerParseResult:
    """Parse text to check if it's a timer command.

    Args:
        text: Command text

    Returns:
        TimerParseResult with parsed information
    """
    text = text.strip()
    result = TimerParseResult()

    # Check timer LIST patterns first (list all timers, no label)
    for pattern in TIMER_LIST_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            result.operation = TimerOperation.LIST
            return result

    # Check timer query patterns (query specific timer by label)
    for pattern in TIMER_QUERY_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            result.operation = TimerOperation.QUERY
            label = match.group(1).strip()
            # Strip trailing "timer" and leading "the" from label
            label = re.sub(r'\s+timer$', '', label, flags=re.IGNORECASE).strip()
            label = re.sub(r'^the\s+', '', label, flags=re.IGNORECASE).strip()
            # Also strip trailing punctuation
            label = re.sub(r'[?!.,]+$', '', label).strip()
            result.label = label
            return result

    # Check alarm patterns EARLY - before control patterns
    # This ensures "start a timer for 5 minutes" creates a timer, not treated as "start" operation
    for pattern in ALARM_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            result.timer_type = TimerType.ALARM
            groups = match.groups()

            if len(groups) == 1:
                # Simple timer: "set a timer for 5 minutes"
                result.duration = parse_duration(groups[0])
                result.label = "timer"
            elif len(groups) == 2:
                # Labeled timer: "set a pizza timer for 10 minutes"
                result.label = groups[0]
                result.duration = parse_duration(groups[1])

            return result

    # Check GENERIC timer control patterns (e.g., "stop my timer", "cancel the timer")
    # These don't have a specific label and should cancel most recent or all timers
    for pattern in TIMER_GENERIC_CONTROL_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            action = match.group(1).lower()

            if action in ("stop", "cancel"):
                result.operation = TimerOperation.CANCEL_ALL
            elif action == "pause":
                result.operation = TimerOperation.PAUSE
                result.label = None  # Will pause most recent
            elif action == "resume":
                result.operation = TimerOperation.RESUME
                result.label = None  # Will resume most recent

            return result

    # Check timer control patterns with specific labels
    for pattern in TIMER_CONTROL_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            label = match.group(1).strip()

            # Skip if label is generic (my, the, all, timer) - should have matched generic patterns
            if label.lower() in ("my", "the", "all", "timer", "timers"):
                continue

            # Strip trailing "timer" from label (e.g., "the pizza timer" -> "pizza")
            label = re.sub(r'\s+timer$', '', label, flags=re.IGNORECASE).strip()
            # Also strip leading "the" (e.g., "the pizza" -> "pizza")
            label = re.sub(r'^the\s+', '', label, flags=re.IGNORECASE).strip()

            result.label = label

            # Determine operation from pattern
            text_lower = text.lower()
            if "pause" in text_lower:
                result.operation = TimerOperation.PAUSE
            elif "resume" in text_lower:
                result.operation = TimerOperation.RESUME
            elif "cancel" in text_lower or ("stop" in text_lower and "timer" in text_lower):
                # Only match "stop" if "timer" is in the text to avoid media stop
                result.operation = TimerOperation.CANCEL
            elif "start" in text_lower:
                result.operation = TimerOperation.START

            return result

    # Check device duration patterns
    for pattern in DEVICE_DURATION_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            result.timer_type = TimerType.DEVICE_DURATION
            groups = match.groups()

            if len(groups) == 3:
                # "turn on the porch light for 10 minutes"
                result.target_device = groups[1].strip()
                result.duration = parse_duration(groups[2])
                result.label = result.target_device
            elif len(groups) == 2:
                # "lights on for 5 minutes"
                result.target_device = groups[0].strip()
                result.duration = parse_duration(groups[1])
                result.label = result.target_device

            if result.duration:
                return result

    # Check delayed action patterns
    for pattern in DELAYED_ACTION_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            result.is_timer_command = True
            result.timer_type = TimerType.DELAYED_ACTION
            groups = match.groups()

            if len(groups) == 2:
                # Order depends on pattern
                text_lower = text.lower()
                if "in " in text_lower[:10] or "after " in text_lower[:10] or "wait " in text_lower[:10]:
                    # "in 3 minutes, turn off the fan" or "in 60 seconds turn off the office light"
                    result.duration = parse_duration(groups[0])
                    result.action_text = groups[1].strip()
                else:
                    # "turn off the fan in 3 minutes"
                    result.action_text = groups[0].strip()
                    result.duration = parse_duration(groups[1])

                result.label = result.action_text[:30] if result.action_text else "delayed"

            if result.duration:
                return result

    return result


class TimerManager:
    """Manages BarnabeeNet timers using HA timer entities.

    Responsibilities:
    - Pool management (allocate/release timer entities)
    - Active timer registry
    - Subscribe to HA events: timer.finished, timer.cancelled
    - Execute on_complete actions when timers finish
    - Publish events to message bus for TTS announcements
    """

    def __init__(
        self,
        ha_client: HomeAssistantClient,
        config: TimerPoolConfig | None = None,
    ) -> None:
        """Initialize the timer manager.

        Args:
            ha_client: Home Assistant client
            config: Pool configuration
        """
        self._ha = ha_client
        self._config = config or TimerPoolConfig()
        self._pool = TimerPool()
        self._active_timers: dict[str, ActiveTimer] = {}
        self._event_task: asyncio.Task[None] | None = None
        self._callbacks: list[Any] = []
        self._initialized = False
        self._callback_registered = False

    @property
    def is_initialized(self) -> bool:
        """Check if timer manager is initialized."""
        return self._initialized

    async def init(self) -> None:
        """Initialize the timer manager.

        Discovers available timer entities in HA and sets up event subscription.
        """
        if self._initialized:
            logger.debug("TimerManager already initialized")
            return

        # Ensure HA client is connected
        if not await self._ha.ensure_connected():
            logger.warning("Home Assistant not connected, timer manager initialization deferred")
            return

        # Discover timer entities
        await self._discover_timer_entities()

        # Register state change callback (only once)
        if not self._callback_registered:
            self._ha.add_state_change_callback(self._on_state_change)
            self._callback_registered = True
            logger.info("Registered timer state change callback")

        # Start WebSocket event subscription if not already running
        if not self._ha.is_subscribed:
            logger.info("Starting HA WebSocket event subscription for timer events")
            await self._ha.subscribe_to_events()

        self._initialized = True
        logger.info(
            "TimerManager initialized with %d available timer entities",
            len(self._pool.available),
        )

    async def _discover_timer_entities(self) -> None:
        """Discover timer.barnabee_* entities in HA."""
        self._pool.available.clear()

        # Ensure HA is connected
        if not await self._ha.ensure_connected():
            logger.warning("Home Assistant not connected, cannot discover timer entities")
            return

        # Query HA directly for timer entities
        logger.info("Discovering timer entities with prefix: %s (checking 1-%d)", self._config.prefix, self._config.pool_size)
        for i in range(1, self._config.pool_size + 1):
            entity_id = f"{self._config.prefix}{i}"
            try:
                # Try to get the state of this entity - if it exists, we can use it
                state = await self._ha.get_state(entity_id)
                if state:
                    self._pool.available.append(entity_id)
                    logger.info("Found timer entity: %s (state: %s)", entity_id, state.state)
                else:
                    logger.debug("Timer entity not found: %s (404 or None)", entity_id)
            except Exception as e:
                logger.warning("Error checking timer entity %s: %s", entity_id, e)

        if not self._pool.available:
            logger.warning(
                "No timer entities found matching pattern %s*. "
                "Create timer helpers in Home Assistant named timer.barnabee_1 through timer.barnabee_10.",
                self._config.prefix,
            )
        else:
            logger.info("Discovered %d timer entities: %s", len(self._pool.available), self._pool.available)

    async def create_timer(
        self,
        timer_type: TimerType,
        duration: timedelta,
        label: str | None = None,
        speaker: str | None = None,
        room: str | None = None,
        on_complete: dict[str, Any] | None = None,
    ) -> ActiveTimer | None:
        """Create a new timer.

        Args:
            timer_type: Type of timer
            duration: Timer duration
            label: Human-friendly label
            speaker: Who created it
            room: Where it was created
            on_complete: Service call to execute when timer finishes

        Returns:
            ActiveTimer if created, None if no entities available
        """
        # Initialize if not yet done
        if not self._initialized:
            logger.info("TimerManager not initialized, initializing now...")
            await self.init()

        # If still no entities available, try to rediscover
        if not self._pool.available:
            logger.info("No timer entities in pool, attempting rediscovery...")
            await self._discover_timer_entities()
            logger.info("After rediscovery: %d entities available", len(self._pool.available))

        # Allocate a timer entity
        entity_id = self._pool.allocate()
        if not entity_id:
            logger.warning(
                "No timer entities available in pool (available: %d, in_use: %d, active_timers: %d)",
                len(self._pool.available),
                len(self._pool.in_use),
                len(self._active_timers),
            )
            return None

        # Create timer record
        timer_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        timer = ActiveTimer(
            id=timer_id,
            timer_type=timer_type,
            ha_timer_entity=entity_id,
            label=label or f"timer_{timer_id}",
            duration=duration,
            started_at=now,
            ends_at=now + duration,
            speaker=speaker,
            room=room,
            on_complete=on_complete,
        )

        # Start the HA timer
        try:
            # Format duration as HH:MM:SS for HA timer service
            total_secs = int(duration.total_seconds())
            hours = total_secs // 3600
            minutes = (total_secs % 3600) // 60
            seconds = total_secs % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            logger.info(
                "Starting HA timer %s with duration %s (%d seconds)",
                entity_id, duration_str, total_secs
            )

            result = await self._ha.call_service(
                "timer.start",
                entity_id=entity_id,
                duration=duration_str,
            )

            if not result.success:
                logger.error("Failed to start HA timer: %s", result.message)
                self._pool.release(entity_id)
                return None

        except Exception as e:
            logger.error("Error starting HA timer: %s", e, exc_info=True)
            self._pool.release(entity_id)
            return None

        # Register timer
        self._active_timers[timer_id] = timer
        self._pool.in_use[timer_id] = entity_id

        logger.info(
            "Created %s timer '%s' for %s (entity: %s, timer_id: %s)",
            timer_type.value,
            timer.label,
            format_duration(duration),
            entity_id,
            timer_id,
        )
        logger.info(
            "Active timers count: %d, Pool available: %d, Pool in_use: %d",
            len(self._active_timers),
            len(self._pool.available),
            len(self._pool.in_use),
        )

        return timer

    def _on_state_change(self, event: Any) -> None:
        """Handle HA state change events.

        Looks for timer.finished events on our managed timers.
        """
        # Check if this is one of our timer entities
        entity_id = event.entity_id
        if not entity_id.startswith(self._config.prefix):
            return

        # Check if timer became "idle" (finished)
        new_state = event.new_state
        old_state = event.old_state

        logger.debug(
            "Timer state change: %s from '%s' to '%s'",
            entity_id, old_state, new_state
        )

        if old_state == "active" and new_state == "idle":
            # Timer finished - find and handle it
            logger.info("Timer %s finished (active -> idle)", entity_id)
            asyncio.create_task(self._handle_timer_finished(entity_id))
        elif old_state == "paused" and new_state == "idle":
            # Timer was paused and then finished (resumed and completed)
            logger.info("Timer %s finished from paused state", entity_id)
            asyncio.create_task(self._handle_timer_finished(entity_id))

    async def _handle_timer_finished(self, entity_id: str) -> None:
        """Handle a timer finishing.

        Args:
            entity_id: The HA timer entity that finished
        """
        # Find the timer
        timer = None
        for _tid, t in self._active_timers.items():
            if t.ha_timer_entity == entity_id:
                timer = t
                break

        if not timer:
            logger.debug("Timer finished but not in registry: %s", entity_id)
            return

        logger.info(
            "Timer '%s' (%s) finished - executing completion action",
            timer.label,
            timer.timer_type.value,
        )

        # Handle based on type
        if timer.timer_type == TimerType.ALARM:
            # Just announce - TTS will be triggered by event
            await self._announce_timer_finished(timer)

        elif timer.timer_type == TimerType.DEVICE_DURATION:
            # Execute the "off" action
            if timer.on_complete:
                await self._execute_on_complete(timer)
            await self._announce_timer_finished(timer)

        elif timer.timer_type == TimerType.DELAYED_ACTION:
            # Execute the delayed action
            if timer.on_complete:
                await self._execute_on_complete(timer)

        # Handle chained actions
        if timer.chained_actions:
            await self._execute_chained_actions(timer)

        # Clean up
        await self._remove_timer(timer.id)

    async def _execute_chained_actions(self, timer: ActiveTimer) -> None:
        """Execute chained actions sequentially with delays.

        Args:
            timer: Timer with chained actions
        """
        for i, chained in enumerate(timer.chained_actions):
            delay = chained["delay"]
            action = chained["action"]

            # Wait for the delay
            if delay.total_seconds() > 0:
                await asyncio.sleep(delay.total_seconds())

            # Execute the action
            try:
                service = action.get("service", "")
                entity_id = action.get("entity_id")
                service_data = action.get("data", {})

                result = await self._ha.call_service(
                    service,
                    entity_id=entity_id,
                    **service_data,
                )

                if result.success:
                    logger.info(
                        "Executed chained action %d/%d for timer '%s': %s for %s",
                        i + 1,
                        len(timer.chained_actions),
                        timer.label,
                        service,
                        entity_id,
                    )
                else:
                    logger.error(
                        "Failed to execute chained action %d/%d: %s - %s",
                        i + 1,
                        len(timer.chained_actions),
                        service,
                        result.message,
                    )
            except Exception as e:
                logger.error("Error executing chained action %d/%d: %s", i + 1, len(timer.chained_actions), e)

    async def _announce_timer_finished(self, timer: ActiveTimer) -> None:
        """Announce that a timer finished via message bus/TTS.

        Args:
            timer: The timer that finished
        """
        # Publish event for TTS announcement
        message = f"Your {timer.label} timer is done!"

        logger.info("Timer announcement: %s", message)

        # TODO: Publish to message bus for TTS
        # await message_bus.publish("timer.finished", {
        #     "timer_id": timer.id,
        #     "label": timer.label,
        #     "room": timer.room,
        #     "message": message,
        # })

    async def _execute_on_complete(self, timer: ActiveTimer) -> None:
        """Execute the on_complete action for a timer.

        Args:
            timer: The timer with action to execute
        """
        if not timer.on_complete:
            return

        try:
            service = timer.on_complete.get("service", "")
            entity_id = timer.on_complete.get("entity_id")
            service_data = timer.on_complete.get("data", {})

            logger.info(
                "Executing timer on_complete: %s for %s",
                service, entity_id
            )

            # Get state before action (for verification)
            state_before = None
            if entity_id:
                try:
                    state_before = await self._ha.get_state(entity_id)
                    if state_before:
                        logger.debug("State before action: %s = %s", entity_id, state_before.state)
                except Exception as e:
                    logger.debug("Error getting state before action for %s: %s", entity_id, e)

            result = await self._ha.call_service(
                service,
                entity_id=entity_id,
                **service_data,
            )

            if result.success:
                # Get state after action (for verification)
                state_after = None
                if entity_id:
                    try:
                        await asyncio.sleep(0.5)  # Brief delay for state to update
                        state_after = await self._ha.get_state(entity_id)
                    except Exception as e:
                        logger.debug("Could not get state after action: %s", e)

                # Log execution with state verification
                state_before_str = state_before.state if state_before else "unknown"
                state_after_str = state_after.state if state_after else "unknown"

                # Check if state actually changed
                state_changed = state_before and state_after and state_before.state != state_after.state
                change_indicator = "CHANGED" if state_changed else ("NO CHANGE" if state_before_str != "unknown" else "UNKNOWN")

                logger.info(
                    "Timer on_complete executed: %s for %s [%s] (state: %s -> %s)",
                    service,
                    entity_id,
                    change_indicator,
                    state_before_str,
                    state_after_str,
                )

                # Also log affected states from service call result if available
                if hasattr(result, 'response_data') and result.response_data:
                    affected = result.response_data.get('affected_states', [])
                    if affected:
                        logger.info("Service call affected %d entities", len(affected))
                    else:
                        logger.warning("Service call returned 0 affected entities - entity may not exist: %s", entity_id)
            else:
                logger.error(
                    "Failed to execute timer on_complete: %s for %s - %s",
                    service,
                    entity_id,
                    result.message,
                )

        except Exception as e:
            logger.error("Error executing timer on_complete: %s", e, exc_info=True)

    async def _remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the registry and release its entity.

        Args:
            timer_id: ID of the timer to remove
        """
        timer = self._active_timers.pop(timer_id, None)
        if timer:
            self._pool.release(timer.ha_timer_entity)
            logger.info("Released timer entity %s back to pool", timer.ha_timer_entity)

    async def pause_timer(self, timer_id: str) -> bool:
        """Pause an active timer.

        Args:
            timer_id: ID of the timer to pause

        Returns:
            True if paused, False if not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False

        if timer.is_paused:
            logger.debug("Timer '%s' is already paused", timer.label)
            return True

        try:
            await self._ha.call_service(
                "timer.pause",
                entity_id=timer.ha_timer_entity,
            )
            timer.paused_at = datetime.now()
            logger.info("Paused timer '%s'", timer.label)
            return True
        except Exception as e:
            logger.error("Error pausing HA timer: %s", e)
            return False

    async def resume_timer(self, timer_id: str) -> bool:
        """Resume a paused timer.

        Args:
            timer_id: ID of the timer to resume

        Returns:
            True if resumed, False if not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False

        if not timer.is_paused:
            logger.debug("Timer '%s' is not paused", timer.label)
            return True

        try:
            # Calculate how long it was paused
            if timer.paused_at:
                pause_duration = datetime.now() - timer.paused_at
                timer.paused_duration += pause_duration
                # Adjust ends_at to account for pause time
                timer.ends_at += pause_duration
                timer.paused_at = None

            await self._ha.call_service(
                "timer.start",
                entity_id=timer.ha_timer_entity,
            )
            logger.info("Resumed timer '%s'", timer.label)
            return True
        except Exception as e:
            logger.error("Error resuming HA timer: %s", e)
            return False

    async def cancel_timer(self, timer_id: str) -> bool:
        """Cancel an active timer.

        Args:
            timer_id: ID of the timer to cancel

        Returns:
            True if cancelled, False if not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False

        try:
            await self._ha.call_service(
                "timer.cancel",
                entity_id=timer.ha_timer_entity,
            )
        except Exception as e:
            logger.error("Error cancelling HA timer: %s", e)

        await self._remove_timer(timer_id)
        logger.info("Cancelled timer '%s'", timer.label)
        return True

    async def cancel_timer_by_label(self, label: str) -> bool:
        """Cancel a timer by its label.

        Args:
            label: Label of the timer to cancel

        Returns:
            True if cancelled, False if not found
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
        count = 0
        timer_ids = list(self._active_timers.keys())
        for timer_id in timer_ids:
            if await self.cancel_timer(timer_id):
                count += 1
        return count

    def get_active_timers(self) -> list[ActiveTimer]:
        """Get all active timers.

        Returns:
            List of active timers
        """
        return list(self._active_timers.values())

    def get_timer(self, timer_id: str) -> ActiveTimer | None:
        """Get a timer by ID.

        Args:
            timer_id: Timer ID

        Returns:
            ActiveTimer if found, None otherwise
        """
        return self._active_timers.get(timer_id)

    def get_timer_by_label(self, label: str) -> ActiveTimer | None:
        """Get a timer by its label.

        Args:
            label: Timer label

        Returns:
            ActiveTimer if found, None otherwise
        """
        label_lower = label.lower()
        for timer in self._active_timers.values():
            if timer.label.lower() == label_lower:
                return timer
        return None

    def get_remaining(self, timer_id: str) -> timedelta | None:
        """Get remaining time on a timer.

        Args:
            timer_id: Timer ID

        Returns:
            Remaining time, or None if not found
        """
        timer = self._active_timers.get(timer_id)
        if timer:
            return timer.remaining
        return None

    def query_timer(self, label: str) -> dict[str, Any] | None:
        """Query timer status by label (e.g., "how long on lasagna").

        Args:
            label: Timer label to query

        Returns:
            Dict with timer info, or None if not found
        """
        timer = self.get_timer_by_label(label)
        if not timer:
            return None

        return {
            "id": timer.id,
            "label": timer.label,
            "remaining": format_duration(timer.remaining),
            "remaining_seconds": int(timer.remaining.total_seconds()),
            "duration": format_duration(timer.duration),
            "started_at": timer.started_at.isoformat(),
            "ends_at": timer.ends_at.isoformat(),
            "is_paused": timer.is_paused,
            "timer_type": timer.timer_type.value,
        }

    async def add_chained_action(
        self,
        timer_id: str,
        delay: timedelta,
        action: dict[str, Any],
    ) -> bool:
        """Add a chained action to a timer.

        Args:
            timer_id: Timer ID
            delay: Delay after timer finishes (or after previous chained action)
            action: Service call dict (service, entity_id, data)

        Returns:
            True if added, False if timer not found
        """
        timer = self._active_timers.get(timer_id)
        if not timer:
            return False

        timer.chained_actions.append({
            "delay": delay,
            "action": action,
        })
        logger.info("Added chained action to timer '%s': %s after %s", timer.label, action, format_duration(delay))
        return True

    def get_status(self) -> dict[str, Any]:
        """Get timer manager status for API/debugging.

        Returns:
            Status dict with pool and timer info
        """
        return {
            "initialized": self._initialized,
            "callback_registered": self._callback_registered,
            "pool_available": len(self._pool.available),
            "pool_in_use": len(self._pool.in_use),
            "active_timers": len(self._active_timers),
            "available_entities": self._pool.available,
            "timers": [t.to_dict() for t in self._active_timers.values()],
        }


# =============================================================================
# Singleton Pattern
# =============================================================================

_timer_manager: TimerManager | None = None


async def get_timer_manager(
    ha_client: HomeAssistantClient | None = None,
) -> TimerManager | None:
    """Get or create the timer manager singleton.

    Args:
        ha_client: HA client (required for first call)

    Returns:
        TimerManager instance, or None if no HA client
    """
    global _timer_manager

    if _timer_manager is not None:
        return _timer_manager

    if ha_client is None:
        try:
            from barnabeenet.api.routes.homeassistant import get_ha_client

            ha_client = await get_ha_client()
        except Exception as e:
            logger.warning("Could not get HA client for timer manager: %s", e)
            return None

    if ha_client is None:
        logger.warning("No HA client available, timer manager cannot be created")
        return None

    _timer_manager = TimerManager(ha_client)
    await _timer_manager.init()
    return _timer_manager


async def init_timer_manager(ha_client: HomeAssistantClient) -> TimerManager | None:
    """Initialize the timer manager with a specific HA client.

    This should be called during application startup.

    Args:
        ha_client: Home Assistant client

    Returns:
        TimerManager instance
    """
    global _timer_manager

    if _timer_manager is not None:
        logger.info("Timer manager already initialized")
        return _timer_manager

    _timer_manager = TimerManager(ha_client)
    await _timer_manager.init()
    return _timer_manager


def get_timer_manager_sync() -> TimerManager | None:
    """Get the timer manager singleton (synchronous version).

    Returns None if not initialized.
    """
    return _timer_manager


def reset_timer_manager() -> None:
    """Reset the timer manager singleton (for testing)."""
    global _timer_manager
    _timer_manager = None


__all__ = [
    "TimerType",
    "TimerOperation",
    "ActiveTimer",
    "TimerPoolConfig",
    "TimerManager",
    "parse_duration",
    "format_duration",
    "parse_timer_command",
    "TimerParseResult",
    "get_timer_manager",
    "init_timer_manager",
    "get_timer_manager_sync",
    "reset_timer_manager",
]
