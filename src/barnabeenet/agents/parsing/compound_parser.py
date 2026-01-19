"""Compound Command Parser.

Parses compound commands like "turn on the lights in the kitchen and close the blinds"
into multiple command segments that can be executed separately.

Key features:
- Splits on conjunctions: "and", "then", "also", "plus"
- Identifies execution mode: parallel ("and") vs sequential ("then")
- Parses each segment independently using regex patterns
- No LLM required - fully deterministic parsing
"""

from __future__ import annotations

import logging
import re
from typing import Any

from barnabeenet.models.ha_commands import (
    CommandSegment,
    HAServiceCall,
    HATarget,
    ParsedCommand,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Domain Inference from Target Nouns
# =============================================================================

# Maps target words to HA domains for building the service name
TARGET_NOUN_TO_DOMAIN: dict[str, str] = {
    # Lights
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "bulb": "light",
    "bulbs": "light",
    # Fans
    "fan": "fan",
    "fans": "fan",
    "ceiling fan": "fan",
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
    "garage": "cover",
    "garage door": "cover",
    # Locks
    "lock": "lock",
    "locks": "lock",
    "door": "lock",
    "doors": "lock",
    "deadbolt": "lock",
    # Climate
    "thermostat": "climate",
    "temperature": "climate",
    "ac": "climate",
    "air conditioning": "climate",
    "heat": "climate",
    "heater": "climate",
    "hvac": "climate",
    # Media
    "tv": "media_player",
    "television": "media_player",
    "speaker": "media_player",
    "speakers": "media_player",
    "music": "media_player",
    # Switches
    "switch": "switch",
    "switches": "switch",
    "outlet": "switch",
    "outlets": "switch",
    "plug": "switch",
    "plugs": "switch",
    # Scene
    "scene": "scene",
    "mode": "scene",
}


# =============================================================================
# Action Verb to Service Mapping
# =============================================================================

# Maps action verbs to (action_name, default_domain)
ACTION_VERB_TO_SERVICE: dict[str, tuple[str, str | None]] = {
    # On/Off actions
    "turn on": ("turn_on", None),
    "turn off": ("turn_off", None),
    "switch on": ("turn_on", None),
    "switch off": ("turn_off", None),
    "enable": ("turn_on", None),
    "disable": ("turn_off", None),
    # Typo-tolerant
    "trun on": ("turn_on", None),
    "trun off": ("turn_off", None),
    "tunr on": ("turn_on", None),
    "tunr off": ("turn_off", None),
    # Light-specific
    "dim": ("turn_on", "light"),  # turn_on with brightness
    "brighten": ("turn_on", "light"),
    # Cover actions
    "open": ("open_cover", "cover"),
    "close": ("close_cover", "cover"),
    # Lock actions
    "lock": ("lock", "lock"),
    "unlock": ("unlock", "lock"),
    # Media actions
    "play": ("media_play", "media_player"),
    "pause": ("media_pause", "media_player"),
    "stop": ("media_stop", "media_player"),
    "skip": ("media_next_track", "media_player"),
    # Generic set
    "set": ("turn_on", None),  # Depends on domain
}


# =============================================================================
# Parsing Patterns
# =============================================================================

# Patterns for extracting command components
# Each pattern should capture: action, target, location (optional), value (optional)

COMMAND_PATTERNS: list[tuple[re.Pattern[str], dict[str, int]]] = [
    # "turn on/off [the] {target} [in/at [the] {location}]"
    (
        re.compile(
            r"^(?P<action>(?:turn|trun|tunr|switch|swtich|swich)\s+(?:on|of+))\s+"
            r"(?:all\s+)?(?:the\s+)?(?:of\s+the\s+)?(?P<target>\w+(?:\s+\w+)?)"
            r"(?:\s+(?:in|at|on)\s+(?:the\s+)?(?P<location>.+?))?$",
            re.IGNORECASE,
        ),
        {"action": 1, "target": 2, "location": 3},
    ),
    # "dim/brighten [the] {target} [in {location}] [to {value}]"
    (
        re.compile(
            r"^(?P<action>dim|brighten)\s+"
            r"(?:the\s+)?(?P<target>\w+(?:\s+\w+)?)"
            r"(?:\s+(?:in|at)\s+(?:the\s+)?(?P<location>.+?))?"
            r"(?:\s+to\s+(?P<value>\d+%?))?$",
            re.IGNORECASE,
        ),
        {"action": 1, "target": 2, "location": 3, "value": 4},
    ),
    # "set [the] {target} [in {location}] to {value}"
    (
        re.compile(
            r"^(?P<action>set)\s+"
            r"(?:the\s+)?(?P<target>\w+(?:\s+\w+)?)"
            r"(?:\s+(?:in|at)\s+(?:the\s+)?(?P<location>.+?))?"
            r"\s+to\s+(?P<value>.+)$",
            re.IGNORECASE,
        ),
        {"action": 1, "target": 2, "location": 3, "value": 4},
    ),
    # "open/close [the] {target} [in {location}]"
    (
        re.compile(
            r"^(?P<action>open|close)\s+"
            r"(?:all\s+)?(?:the\s+)?(?:of\s+the\s+)?(?P<target>\w+(?:\s+\w+)?)"
            r"(?:\s+(?:in|at|on)\s+(?:the\s+)?(?P<location>.+?))?$",
            re.IGNORECASE,
        ),
        {"action": 1, "target": 2, "location": 3},
    ),
    # "lock/unlock [the] {target}"
    (
        re.compile(
            r"^(?P<action>lock|unlock)\s+"
            r"(?:the\s+)?(?P<target>.+)$",
            re.IGNORECASE,
        ),
        {"action": 1, "target": 2},
    ),
    # Timer patterns: "set a timer for {duration}"
    (
        re.compile(
            r"^(?P<action>set)\s+(?:a\s+)?(?:(?P<label>\w+)\s+)?timer\s+"
            r"(?:for\s+)?(?P<value>\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))$",
            re.IGNORECASE,
        ),
        {"action": 1, "label": 2, "value": 3},
    ),
    # "{duration} timer"
    (
        re.compile(
            r"^(?P<value>\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))\s+timer$",
            re.IGNORECASE,
        ),
        {"action": "timer", "value": 1},
    ),
]


# Conjunction patterns for splitting compound commands
CONJUNCTION_PATTERNS = [
    (re.compile(r"\s+and\s+then\s+", re.IGNORECASE), "sequential"),
    (re.compile(r"\s+then\s+", re.IGNORECASE), "sequential"),
    (re.compile(r"\s+and\s+also\s+", re.IGNORECASE), "parallel"),
    (re.compile(r"\s+also\s+", re.IGNORECASE), "parallel"),
    (re.compile(r"\s+plus\s+", re.IGNORECASE), "parallel"),
    (re.compile(r"\s+and\s+", re.IGNORECASE), "parallel"),
]


class CompoundCommandParser:
    """Parser for compound voice commands.

    Splits commands on conjunctions and parses each segment independently.
    Uses regex patterns - no LLM required.

    Example:
        parser = CompoundCommandParser()
        result = parser.parse("turn on the lights in the kitchen and close the blinds")
        # result.segments = [
        #   CommandSegment(action="turn_on", target_noun="lights", location="kitchen"),
        #   CommandSegment(action="close", target_noun="blinds", location=None),
        # ]
    """

    def __init__(self) -> None:
        """Initialize the parser."""
        pass

    def parse(self, text: str) -> ParsedCommand:
        """Parse a command into segments.

        Args:
            text: The raw command text

        Returns:
            ParsedCommand with segments and metadata
        """
        text = text.strip()
        result = ParsedCommand(original_text=text)

        # Check if this is a compound command
        segments_text, execution_mode = self._split_on_conjunctions(text)

        if len(segments_text) > 1:
            result.is_compound = True
            result.execution_mode = execution_mode

        # Parse each segment, carrying forward the action from previous segments
        # This handles "turn on X and Y" → "turn on X" + "turn on Y"
        last_action: str | None = None
        for segment_text in segments_text:
            segment = self._parse_segment(segment_text.strip())
            if segment:
                last_action = segment.action
                result.segments.append(segment)
            else:
                # Try to parse with inherited action from previous segment
                if last_action:
                    # Prepend the action to the segment text
                    augmented_text = f"{last_action.replace('_', ' ')} {segment_text.strip()}"
                    segment = self._parse_segment(augmented_text)
                    if segment:
                        result.segments.append(segment)
                        continue
                result.parse_errors.append(f"Could not parse: '{segment_text}'")

        return result

    def _split_on_conjunctions(self, text: str) -> tuple[list[str], str]:
        """Split text on conjunctions, determine execution mode.

        Args:
            text: Command text

        Returns:
            Tuple of (segments, execution_mode)
        """
        # Try each conjunction pattern
        for pattern, mode in CONJUNCTION_PATTERNS:
            parts = pattern.split(text)
            if len(parts) > 1:
                # Found a split - use this conjunction's mode
                return [p.strip() for p in parts if p.strip()], mode

        # No conjunction found - single segment
        return [text], "parallel"

    def _parse_segment(self, text: str) -> CommandSegment | None:
        """Parse a single command segment.

        Args:
            text: Single command text (no conjunctions)

        Returns:
            CommandSegment if parsed, None otherwise
        """
        text = text.strip()

        # Try each pattern
        for pattern, _group_map in COMMAND_PATTERNS:
            match = pattern.match(text)
            if match:
                groups = match.groupdict()

                # Extract action
                action_text = groups.get("action", "").lower().strip()
                action = self._normalize_action(action_text)

                # Extract target noun
                target = groups.get("target", "").lower().strip()
                # Handle special case: "light" from "office light"
                target_noun = self._extract_target_noun(target)

                # Extract location (may be in target for patterns like "kitchen lights")
                location = groups.get("location")
                if location:
                    location = location.strip()

                # Try to extract location from target if not explicit
                if not location and target:
                    embedded_location = self._extract_embedded_location(target)
                    if embedded_location:
                        location = embedded_location

                # Extract value
                value = groups.get("value")
                if value:
                    value = value.strip()

                return CommandSegment(
                    action=action,
                    target_noun=target_noun,
                    location=location,
                    value=value,
                    raw_text=text,
                    confidence=0.9,
                )

        # No pattern matched - try basic extraction
        return self._basic_parse(text)

    def _basic_parse(self, text: str) -> CommandSegment | None:
        """Basic fallback parsing when no pattern matches.

        Tries to extract action and target from simple commands.
        """
        words = text.lower().split()
        if len(words) < 2:
            return None

        # Look for action verb
        action = None
        target_start = 0

        # Check two-word actions first
        if len(words) >= 2:
            two_word = f"{words[0]} {words[1]}"
            if two_word in ACTION_VERB_TO_SERVICE:
                action = self._normalize_action(two_word)
                target_start = 2

        # Check single-word actions
        if not action and words[0] in ACTION_VERB_TO_SERVICE:
            action = self._normalize_action(words[0])
            target_start = 1

        if not action:
            return None

        # Rest is target (and possibly location)
        remaining = " ".join(words[target_start:])
        remaining = re.sub(r"^(the|a|all|all the)\s+", "", remaining)

        # Try to extract location
        location_match = re.search(r"\s+(in|at|on)\s+(?:the\s+)?(.+)$", remaining)
        if location_match:
            location = location_match.group(2).strip()
            target = remaining[: location_match.start()].strip()
        else:
            location = None
            target = remaining

        target_noun = self._extract_target_noun(target)

        if not target_noun:
            return None

        return CommandSegment(
            action=action,
            target_noun=target_noun,
            location=location,
            raw_text=text,
            confidence=0.7,
        )

    def _normalize_action(self, action_text: str) -> str:
        """Normalize action text to standard action name.

        Args:
            action_text: Raw action text (e.g., "turn on", "trun off")

        Returns:
            Normalized action (e.g., "turn_on", "turn_off")
        """
        action_text = action_text.lower().strip()

        # Handle typos
        action_text = re.sub(r"\btrun\b", "turn", action_text)
        action_text = re.sub(r"\btunr\b", "turn", action_text)
        action_text = re.sub(r"\bswtich\b", "switch", action_text)
        action_text = re.sub(r"\bswich\b", "switch", action_text)

        # Normalize "of" to "off"
        action_text = re.sub(r"\bof\b", "off", action_text)

        # Map to standard action
        if action_text in ACTION_VERB_TO_SERVICE:
            return ACTION_VERB_TO_SERVICE[action_text][0]

        # Default: replace spaces with underscores
        return action_text.replace(" ", "_")

    def _extract_target_noun(self, target: str) -> str:
        """Extract the device type noun from a target phrase.

        Args:
            target: Target phrase (e.g., "office light", "kitchen blinds")

        Returns:
            Device type noun (e.g., "light", "blinds")
        """
        target = target.lower().strip()

        # Check if any known target noun is in the phrase
        for noun in TARGET_NOUN_TO_DOMAIN:
            if noun in target:
                return noun

        # Return the last word as the target noun (e.g., "dining table light" -> "light")
        words = target.split()
        if words:
            return words[-1]

        return target

    def _extract_embedded_location(self, target: str) -> str | None:
        """Extract location embedded in target phrase.

        E.g., "kitchen light" -> "kitchen"

        Args:
            target: Target phrase

        Returns:
            Location if found, None otherwise
        """
        # Common location words that might be embedded
        location_words = {
            "kitchen",
            "living room",
            "bedroom",
            "bathroom",
            "office",
            "dining",
            "garage",
            "basement",
            "attic",
            "hallway",
            "porch",
            "patio",
            "den",
            "study",
        }

        target_lower = target.lower()
        for location in location_words:
            if location in target_lower:
                return location

        return None

    def to_service_calls(
        self,
        parsed: ParsedCommand,
        speaker_area: str | None = None,
    ) -> list[HAServiceCall]:
        """Convert parsed command to HA service calls.

        Args:
            parsed: Parsed command with segments
            speaker_area: Default area if no location specified

        Returns:
            List of HAServiceCall ready for execution
        """
        calls: list[HAServiceCall] = []

        for segment in parsed.segments:
            call = self._segment_to_service_call(segment, speaker_area)
            if call:
                call.execution_mode = parsed.execution_mode
                calls.append(call)

        return calls

    def _segment_to_service_call(
        self,
        segment: CommandSegment,
        speaker_area: str | None = None,
    ) -> HAServiceCall | None:
        """Convert a command segment to an HA service call.

        Args:
            segment: Parsed command segment
            speaker_area: Default area if no location specified

        Returns:
            HAServiceCall or None if cannot convert
        """
        # Determine domain from target noun
        domain = TARGET_NOUN_TO_DOMAIN.get(segment.target_noun)

        # Special handling for certain actions that imply domain
        if not domain and segment.action in ACTION_VERB_TO_SERVICE:
            _, implied_domain = ACTION_VERB_TO_SERVICE.get(segment.action, (None, None))
            domain = implied_domain

        # Default to homeassistant domain for generic on/off
        if not domain:
            domain = "homeassistant"

        # Build service name
        action_name = segment.action
        if domain == "homeassistant":
            # Generic turn_on/turn_off
            service = f"homeassistant.{action_name}"
        else:
            service = f"{domain}.{action_name}"

        # Build target
        location = segment.location or speaker_area
        if location:
            target = HATarget.from_area(location)
        else:
            # No location - will need entity resolution
            target = HATarget()

        # Build data
        data: dict[str, Any] = {}
        if segment.value:
            # Parse value
            if segment.value.endswith("%"):
                # Brightness percentage
                try:
                    brightness = int(segment.value.rstrip("%"))
                    data["brightness_pct"] = brightness
                except ValueError:
                    pass
            elif "degree" in segment.value.lower() or "°" in segment.value:
                # Temperature
                try:
                    temp_str = re.sub(r"[^\d.]", "", segment.value)
                    data["temperature"] = float(temp_str)
                except ValueError:
                    pass
            else:
                # Generic value
                data["value"] = segment.value

        return HAServiceCall(
            service=service,
            target=target,
            data=data,
            source_text=segment.raw_text,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def parse_command(text: str) -> ParsedCommand:
    """Parse a command using the default parser.

    Args:
        text: Command text

    Returns:
        ParsedCommand with segments
    """
    parser = CompoundCommandParser()
    return parser.parse(text)


def is_compound_command(text: str) -> bool:
    """Check if text contains multiple commands.

    Args:
        text: Command text

    Returns:
        True if compound command
    """
    parser = CompoundCommandParser()
    result = parser.parse(text)
    return result.is_compound


__all__ = [
    "CompoundCommandParser",
    "parse_command",
    "is_compound_command",
    "TARGET_NOUN_TO_DOMAIN",
    "ACTION_VERB_TO_SERVICE",
]
