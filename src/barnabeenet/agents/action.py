"""Action Agent - Device control and home automation.

The Action Agent translates natural language commands into device control
specifications. It handles:
- Turning devices on/off
- Setting values (temperature, brightness, volume)
- Locking/unlocking doors
- Opening/closing covers
- Media control (play, pause, stop)
- Scene activation

This agent generates action specifications that can be executed by
Home Assistant or other automation systems.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from barnabeenet.agents.base import Agent
from barnabeenet.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the agent can perform."""

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    TOGGLE = "toggle"
    SET_VALUE = "set_value"
    INCREASE = "increase"
    DECREASE = "decrease"
    LOCK = "lock"
    UNLOCK = "unlock"
    OPEN = "open"
    CLOSE = "close"
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    SKIP = "skip"
    ACTIVATE_SCENE = "activate_scene"
    UNKNOWN = "unknown"


class DeviceDomain(Enum):
    """Home Assistant device domains."""

    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    COVER = "cover"
    LOCK = "lock"
    MEDIA_PLAYER = "media_player"
    FAN = "fan"
    SCENE = "scene"
    SCRIPT = "script"
    VACUUM = "vacuum"
    UNKNOWN = "unknown"


@dataclass
class ActionSpec:
    """Specification for a device action."""

    action_type: ActionType
    domain: DeviceDomain
    entity_name: str  # Human-readable name from user input
    entity_id: str | None = None  # Resolved Home Assistant entity_id
    service: str | None = None  # Home Assistant service to call
    service_data: dict[str, Any] = field(default_factory=dict)
    target_value: Any = None  # For set_value actions
    confidence: float = 0.0
    requires_confirmation: bool = False
    spoken_response: str = ""
    # Batch/area support
    is_batch: bool = False  # True if targeting multiple entities
    target_area: str | None = None  # Area/room name (e.g., "living room")
    target_floor: str | None = None  # Floor name (e.g., "downstairs")
    entity_ids: list[str] = field(default_factory=list)  # Multiple entity IDs for batch


@dataclass
class ActionResult:
    """Result of action execution."""

    success: bool
    action: ActionSpec
    message: str
    executed: bool = False  # False if only parsed, not executed


# Patterns for rule-based action parsing
# NOTE: Order matters! More specific patterns should come before generic ones.
ACTION_PATTERNS: list[tuple[str, ActionType, DeviceDomain | None]] = [
    # Batch on/off patterns - MUST come before single entity patterns
    # "turn off all the lights downstairs", "turn on lights in living room"
    (
        r"^turn (on|off) all (?:the |of the )?(.+?)(?:\s+(?:in|on)\s+(?:the )?(.+))?$",
        ActionType.TURN_ON,
        None,
    ),
    (
        r"^turn (on|off) (?:the )?(.+?)(?:\s+(?:in|on)\s+(?:the )?(.+))$",
        ActionType.TURN_ON,
        None,
    ),
    # Standard on/off patterns
    (r"^turn (on|off) (?:the )?(.+)$", ActionType.TURN_ON, None),
    (r"^switch (on|off) (?:the )?(.+)$", ActionType.TURN_ON, None),
    (r"^(enable|disable) (?:the )?(.+)$", ActionType.TURN_ON, None),
    # Light patterns
    (r"^(dim|brighten) (?:the )?(.+?)(?: to (\d+)%?)?$", ActionType.SET_VALUE, DeviceDomain.LIGHT),
    (r"^set (?:the )?(.+?) brightness to (\d+)%?$", ActionType.SET_VALUE, DeviceDomain.LIGHT),
    # Climate patterns - MUST come before generic "set X to Y"
    (
        r"^set (?:the )?(temperature|thermostat) to (\d+)°?(?:f|c)?$",
        ActionType.SET_VALUE,
        DeviceDomain.CLIMATE,
    ),
    (
        r"^set (?:the )?(.+?) to (\d+)°(?:f|c)?$",  # Anything with degree symbol is climate
        ActionType.SET_VALUE,
        DeviceDomain.CLIMATE,
    ),
    (
        r"^(heat|cool) (?:the )?(.+?) to (\d+)°?(?:f|c)?$",
        ActionType.SET_VALUE,
        DeviceDomain.CLIMATE,
    ),
    # Lock patterns
    (r"^(lock|unlock) (?:the )?(.+)$", ActionType.LOCK, DeviceDomain.LOCK),
    # Batch cover patterns - MUST come before single cover patterns
    # "close all the blinds in living room", "open blinds in the kitchen"
    (
        r"^(open|close) all (?:the |of the )?(.+?)(?:\s+(?:in|on)\s+(?:the )?(.+))?$",
        ActionType.OPEN,
        DeviceDomain.COVER,
    ),
    (
        r"^(open|close) (?:the )?(.+?)(?:\s+(?:in|on)\s+(?:the )?(.+))$",
        ActionType.OPEN,
        DeviceDomain.COVER,
    ),
    # Single cover patterns
    (r"^(open|close) (?:the )?(.+)$", ActionType.OPEN, DeviceDomain.COVER),
    # Media patterns
    (
        r"^(play|pause|stop|skip)(?: (?:the )?(?:music|video|media)?(?:on (?:the )?)?(.*))?$",
        ActionType.PLAY,
        DeviceDomain.MEDIA_PLAYER,
    ),
    # Scene patterns
    (r"^activate (?:the )?(.+?)(?: scene)?$", ActionType.ACTIVATE_SCENE, DeviceDomain.SCENE),
    (
        r"^(?:start|run) (?:the )?(.+?) (?:scene|mode)$",
        ActionType.ACTIVATE_SCENE,
        DeviceDomain.SCENE,
    ),
    # Generic set patterns
    (r"^set (?:the )?(.+?) to (.+)$", ActionType.SET_VALUE, None),
    (r"^change (?:the )?(.+?) to (.+)$", ActionType.SET_VALUE, None),
]

# High-risk actions that require confirmation
HIGH_RISK_ACTIONS = {
    (ActionType.UNLOCK, DeviceDomain.LOCK),
    (ActionType.OPEN, DeviceDomain.COVER),  # Garage doors, etc.
}

# Domain inference from entity names
DOMAIN_KEYWORDS: dict[str, DeviceDomain] = {
    "light": DeviceDomain.LIGHT,
    "lamp": DeviceDomain.LIGHT,
    "bulb": DeviceDomain.LIGHT,
    "switch": DeviceDomain.SWITCH,
    "outlet": DeviceDomain.SWITCH,
    "plug": DeviceDomain.SWITCH,
    "thermostat": DeviceDomain.CLIMATE,
    "temperature": DeviceDomain.CLIMATE,
    "hvac": DeviceDomain.CLIMATE,
    "ac": DeviceDomain.CLIMATE,
    "heater": DeviceDomain.CLIMATE,
    "door": DeviceDomain.LOCK,
    "lock": DeviceDomain.LOCK,
    "deadbolt": DeviceDomain.LOCK,
    "garage": DeviceDomain.COVER,
    "blind": DeviceDomain.COVER,
    "shade": DeviceDomain.COVER,
    "curtain": DeviceDomain.COVER,
    "cover": DeviceDomain.COVER,
    "tv": DeviceDomain.MEDIA_PLAYER,
    "speaker": DeviceDomain.MEDIA_PLAYER,
    "music": DeviceDomain.MEDIA_PLAYER,
    "fan": DeviceDomain.FAN,
    "vacuum": DeviceDomain.VACUUM,
    "scene": DeviceDomain.SCENE,
    "mode": DeviceDomain.SCENE,
}


class ActionAgent(Agent):
    """Agent for device control and home automation.

    Translates natural language commands into device control specifications.
    Can work standalone (generating specs) or integrated with Home Assistant.
    """

    name = "action"

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        entity_resolver: Any | None = None,  # Future: Home Assistant entity resolver
    ) -> None:
        self._llm_client = llm_client
        self._entity_resolver = entity_resolver
        self._compiled_patterns: list[tuple[re.Pattern[str], ActionType, DeviceDomain | None]] = []

    async def init(self) -> None:
        """Initialize the Action Agent."""
        # Compile action patterns
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), action_type, domain)
            for pattern, action_type, domain in ACTION_PATTERNS
        ]
        logger.info("ActionAgent initialized with %d patterns", len(self._compiled_patterns))

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._compiled_patterns.clear()

    async def handle_input(self, text: str, context: dict | None = None) -> dict[str, Any]:
        """Handle an action request.

        Args:
            text: The natural language command
            context: Optional context with speaker, room, etc.

        Returns:
            Dictionary with action specification and response
        """
        start_time = time.perf_counter()
        context = context or {}
        text = text.strip()

        # Parse the action
        action_spec = await self.parse_action(text, context)

        latency_ms = (time.perf_counter() - start_time) * 1000

        if action_spec.action_type == ActionType.UNKNOWN:
            return {
                "response": "I'm not sure what you'd like me to do. Could you be more specific?",
                "agent": self.name,
                "action": None,
                "success": False,
                "latency_ms": latency_ms,
            }

        # Check if confirmation is needed
        if action_spec.requires_confirmation:
            return {
                "response": f"Are you sure you want to {action_spec.spoken_response}?",
                "agent": self.name,
                "action": self._action_to_dict(action_spec),
                "requires_confirmation": True,
                "success": True,
                "latency_ms": latency_ms,
            }

        return {
            "response": action_spec.spoken_response,
            "agent": self.name,
            "action": self._action_to_dict(action_spec),
            "success": True,
            "latency_ms": latency_ms,
        }

    async def parse_action(self, text: str, context: dict | None = None) -> ActionSpec:
        """Parse natural language into an action specification.

        Tries rule-based parsing first, falls back to LLM if needed.
        """
        context = context or {}
        text_lower = text.lower().strip()

        # Try rule-based parsing first (fast path)
        action_spec = self._rule_based_parse(text_lower, context)
        if action_spec and action_spec.action_type != ActionType.UNKNOWN:
            logger.debug("Rule-based parse: %s", action_spec.action_type.value)
            return action_spec

        # Fall back to LLM parsing if available
        if self._llm_client:
            action_spec = await self._llm_parse(text, context)
            if action_spec:
                logger.debug("LLM parse: %s", action_spec.action_type.value)
                return action_spec

        # Return unknown action
        return ActionSpec(
            action_type=ActionType.UNKNOWN,
            domain=DeviceDomain.UNKNOWN,
            entity_name="",
            confidence=0.0,
            spoken_response="I couldn't understand that action.",
        )

    def _rule_based_parse(self, text: str, context: dict) -> ActionSpec | None:
        """Parse action using rule-based patterns."""
        for pattern, action_type, default_domain in self._compiled_patterns:
            match = pattern.match(text)
            if match:
                return self._build_action_from_match(
                    match, action_type, default_domain, text, context
                )
        return None

    def _build_action_from_match(
        self,
        match: re.Match[str],
        action_type: ActionType,
        default_domain: DeviceDomain | None,
        text: str,
        context: dict,
    ) -> ActionSpec:
        """Build an ActionSpec from a regex match."""
        groups = match.groups()

        # Extract entity name and other info based on action type
        entity_name = ""
        target_value = None
        actual_action = action_type
        target_area: str | None = None
        is_batch = False

        if action_type == ActionType.TURN_ON:
            # Handle batch patterns: (on/off, device_type, area?)
            # e.g., "turn off all the lights in living room"
            state = groups[0].lower()
            actual_action = ActionType.TURN_ON if state in ("on", "enable") else ActionType.TURN_OFF

            # Check if this is a batch command (has area/location)
            if len(groups) >= 3 and groups[2]:
                # Batch with location: (on/off, device_type, location)
                entity_name = groups[1] if groups[1] else ""
                target_area = groups[2].strip() if groups[2] else None
                is_batch = True
            else:
                # Single entity: (on/off, entity_name)
                entity_name = groups[1] if len(groups) > 1 else ""
                # Check if entity_name contains batch keywords
                if self._is_batch_reference(entity_name):
                    is_batch = True
                    entity_name, target_area = self._parse_batch_reference(entity_name)

        elif action_type == ActionType.SET_VALUE:
            if default_domain == DeviceDomain.LIGHT:
                # Dim/brighten: (action, entity, percent?)
                if "dim" in text or "brighten" in text:
                    action_word = groups[0]
                    entity_name = groups[1] if len(groups) > 1 else ""
                    percent = groups[2] if len(groups) > 2 and groups[2] else None
                    if percent:
                        target_value = int(percent)
                    else:
                        target_value = 30 if action_word == "dim" else 100
                else:
                    # Set brightness: (entity, percent)
                    entity_name = groups[0] if groups[0] else ""
                    target_value = int(groups[1]) if len(groups) > 1 and groups[1] else None
            elif default_domain == DeviceDomain.CLIMATE:
                # Set temperature: (entity?, temp)
                if len(groups) >= 2:
                    entity_name = groups[0] if groups[0] else "thermostat"
                    target_value = int(groups[1]) if groups[1] else None
                elif len(groups) == 1:
                    entity_name = "thermostat"
                    target_value = int(groups[0]) if groups[0] else None
            else:
                # Generic set: (entity, value)
                entity_name = groups[0] if groups else ""
                target_value = groups[1] if len(groups) > 1 else None

        elif action_type in (ActionType.LOCK, ActionType.UNLOCK):
            # (lock/unlock, entity)
            lock_action = groups[0].lower()
            entity_name = groups[1] if len(groups) > 1 else ""
            actual_action = ActionType.LOCK if lock_action == "lock" else ActionType.UNLOCK

        elif action_type in (ActionType.OPEN, ActionType.CLOSE):
            # Handle batch patterns: (open/close, device_type, area?)
            cover_action = groups[0].lower()
            actual_action = ActionType.OPEN if cover_action == "open" else ActionType.CLOSE

            # Check if this is a batch command (has area/location)
            if len(groups) >= 3 and groups[2]:
                # Batch with location: (open/close, device_type, location)
                entity_name = groups[1] if groups[1] else ""
                target_area = groups[2].strip() if groups[2] else None
                is_batch = True
            else:
                # Single entity: (open/close, entity_name)
                entity_name = groups[1] if len(groups) > 1 else ""
                # Check if entity_name contains batch keywords
                if self._is_batch_reference(entity_name):
                    is_batch = True
                    entity_name, target_area = self._parse_batch_reference(entity_name)

        elif action_type in (ActionType.PLAY, ActionType.PAUSE, ActionType.STOP, ActionType.SKIP):
            # (play/pause/stop/skip, entity?)
            media_action = groups[0].lower()
            entity_name = groups[1] if len(groups) > 1 and groups[1] else "media player"
            action_map = {
                "play": ActionType.PLAY,
                "pause": ActionType.PAUSE,
                "stop": ActionType.STOP,
                "skip": ActionType.SKIP,
            }
            actual_action = action_map.get(media_action, ActionType.PLAY)

        elif action_type == ActionType.ACTIVATE_SCENE:
            # (scene_name)
            entity_name = groups[0] if groups else ""

        # Clean up entity name
        entity_name = entity_name.strip()

        # Infer domain if not specified
        domain = default_domain or self._infer_domain(entity_name, actual_action)

        # Generate service call info
        service = self._get_service(actual_action, domain)

        # Build service data
        service_data: dict[str, Any] = {}
        if target_value is not None:
            if domain == DeviceDomain.LIGHT:
                service_data["brightness_pct"] = target_value
            elif domain == DeviceDomain.CLIMATE:
                service_data["temperature"] = target_value
            else:
                service_data["value"] = target_value

        # Check if high-risk action
        requires_confirmation = (actual_action, domain) in HIGH_RISK_ACTIONS

        # Generate spoken response
        spoken_response = self._generate_response(
            actual_action, entity_name, target_value, domain, target_area, is_batch
        )

        return ActionSpec(
            action_type=actual_action,
            domain=domain,
            entity_name=entity_name,
            entity_id=self._resolve_entity_id(entity_name, domain) if not is_batch else None,
            service=service,
            service_data=service_data,
            target_value=target_value,
            confidence=0.9,
            requires_confirmation=requires_confirmation,
            spoken_response=spoken_response,
            is_batch=is_batch,
            target_area=target_area,
        )

    def _infer_domain(self, entity_name: str, action_type: ActionType) -> DeviceDomain:
        """Infer device domain from entity name and action type."""
        name_lower = entity_name.lower()

        # Check keywords in entity name
        for keyword, domain in DOMAIN_KEYWORDS.items():
            if keyword in name_lower:
                return domain

        # Infer from action type
        action_domain_map = {
            ActionType.LOCK: DeviceDomain.LOCK,
            ActionType.UNLOCK: DeviceDomain.LOCK,
            ActionType.OPEN: DeviceDomain.COVER,
            ActionType.CLOSE: DeviceDomain.COVER,
            ActionType.PLAY: DeviceDomain.MEDIA_PLAYER,
            ActionType.PAUSE: DeviceDomain.MEDIA_PLAYER,
            ActionType.STOP: DeviceDomain.MEDIA_PLAYER,
            ActionType.SKIP: DeviceDomain.MEDIA_PLAYER,
            ActionType.ACTIVATE_SCENE: DeviceDomain.SCENE,
        }

        return action_domain_map.get(action_type, DeviceDomain.SWITCH)

    def _get_service(self, action_type: ActionType, domain: DeviceDomain) -> str:
        """Get Home Assistant service name for action."""
        service_map = {
            ActionType.TURN_ON: "turn_on",
            ActionType.TURN_OFF: "turn_off",
            ActionType.TOGGLE: "toggle",
            ActionType.SET_VALUE: "turn_on",  # Most set operations use turn_on with data
            ActionType.INCREASE: "turn_on",
            ActionType.DECREASE: "turn_on",
            ActionType.LOCK: "lock",
            ActionType.UNLOCK: "unlock",
            ActionType.OPEN: "open_cover",
            ActionType.CLOSE: "close_cover",
            ActionType.PLAY: "media_play",
            ActionType.PAUSE: "media_pause",
            ActionType.STOP: "media_stop",
            ActionType.SKIP: "media_next_track",
            ActionType.ACTIVATE_SCENE: "turn_on",
        }

        service = service_map.get(action_type, "turn_on")
        return f"{domain.value}.{service}"

    def _resolve_entity_id(self, entity_name: str, domain: DeviceDomain) -> str | None:
        """Resolve entity name to Home Assistant entity_id.

        Future: Use entity_resolver for actual resolution.
        For now, generate a placeholder.
        """
        if self._entity_resolver:
            # Future: actual resolution
            pass

        # Generate placeholder entity_id
        if entity_name:
            safe_name = re.sub(r"[^a-z0-9]+", "_", entity_name.lower()).strip("_")
            return f"{domain.value}.{safe_name}"
        return None

    def _generate_response(
        self,
        action_type: ActionType,
        entity_name: str,
        target_value: Any,
        domain: DeviceDomain,
        target_area: str | None = None,
        is_batch: bool = False,
    ) -> str:
        """Generate natural language response for action."""
        # Build entity description
        if is_batch and target_area:
            entity_display = f"{entity_name} in {target_area}"
        elif is_batch:
            entity_display = f"all {entity_name}"
        else:
            entity_display = entity_name or "the device"

        responses = {
            ActionType.TURN_ON: f"Turning on {entity_display}.",
            ActionType.TURN_OFF: f"Turning off {entity_display}.",
            ActionType.TOGGLE: f"Toggling {entity_display}.",
            ActionType.LOCK: f"Locking {entity_display}.",
            ActionType.UNLOCK: f"unlock {entity_display}",  # For confirmation prompt
            ActionType.OPEN: f"Opening {entity_display}.",
            ActionType.CLOSE: f"Closing {entity_display}.",
            ActionType.PLAY: f"Playing on {entity_display}.",
            ActionType.PAUSE: f"Pausing {entity_display}.",
            ActionType.STOP: f"Stopping {entity_display}.",
            ActionType.SKIP: f"Skipping to next track on {entity_display}.",
            ActionType.ACTIVATE_SCENE: f"Activating {entity_display} scene.",
        }

        if action_type == ActionType.SET_VALUE:
            if domain == DeviceDomain.LIGHT:
                return f"Setting {entity_display} to {target_value}%."
            elif domain == DeviceDomain.CLIMATE:
                return f"Setting {entity_display} to {target_value} degrees."
            else:
                return f"Setting {entity_display} to {target_value}."

        return responses.get(action_type, f"Executing action on {entity_display}.")

    def _is_batch_reference(self, text: str) -> bool:
        """Check if text refers to multiple devices (batch operation)."""
        text_lower = text.lower()
        # Keywords that indicate batch operations
        batch_keywords = [
            "all ",
            "every ",
            "all the ",
            "every the ",
            " downstairs",
            " upstairs",
            " floor",
        ]
        for keyword in batch_keywords:
            if keyword in text_lower or text_lower.startswith(keyword.strip()):
                return True
        # Check for plural device types followed by location
        # e.g., "lights in kitchen", "blinds in living room"
        if re.search(r"\b(lights|blinds|switches|fans|covers)\s+(in|on)\s+", text_lower):
            return True
        return False

    def _parse_batch_reference(self, text: str) -> tuple[str, str | None]:
        """Parse batch reference into device type and area.

        Returns:
            Tuple of (device_type, area_name or None)
        """
        text_lower = text.lower()

        # Remove "all" prefix
        text_lower = re.sub(r"^all\s+(?:the\s+)?", "", text_lower)

        # Check for floor references
        floor_patterns = [
            (r"(.+?)\s+(downstairs|upstairs|first floor|second floor)$", True),
            (r"(.+?)\s+(?:in|on)\s+(?:the\s+)?(.+)$", False),
        ]

        for pattern, _is_floor in floor_patterns:
            match = re.match(pattern, text_lower)
            if match:
                device_type = match.group(1).strip()
                location = match.group(2).strip()
                return device_type, location

        # No location found, return whole text as device type
        return text_lower.strip(), None

    async def _llm_parse(self, text: str, context: dict) -> ActionSpec | None:
        """Use LLM to parse complex action requests."""
        if not self._llm_client:
            return None

        system_prompt = """You are an action parser for a smart home assistant.
Parse the user's request into a device control action.

Respond with JSON:
{
  "action_type": "turn_on|turn_off|set_value|lock|unlock|open|close|play|pause|stop|skip|activate_scene",
  "domain": "light|switch|climate|cover|lock|media_player|fan|scene",
  "entity_name": "<device name from the request>",
  "target_value": <value if applicable, null otherwise>,
  "spoken_response": "<natural confirmation message>"
}

If you cannot parse the request, respond with:
{"action_type": "unknown", "reason": "<explanation>"}"""

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Parse: {text}"},
                ],
                agent_type="action",
                user_input=text,
            )

            import json

            result = json.loads(response.text)

            if result.get("action_type") == "unknown":
                return None

            action_type = ActionType(result.get("action_type", "unknown"))
            domain = DeviceDomain(result.get("domain", "unknown"))

            return ActionSpec(
                action_type=action_type,
                domain=domain,
                entity_name=result.get("entity_name", ""),
                entity_id=self._resolve_entity_id(result.get("entity_name", ""), domain),
                service=self._get_service(action_type, domain),
                target_value=result.get("target_value"),
                confidence=0.8,
                requires_confirmation=(action_type, domain) in HIGH_RISK_ACTIONS,
                spoken_response=result.get("spoken_response", ""),
            )

        except Exception as e:
            logger.warning("LLM action parsing failed: %s", e)
            return None

    def _action_to_dict(self, action: ActionSpec) -> dict[str, Any]:
        """Convert ActionSpec to dictionary for response."""
        result = {
            "action_type": action.action_type.value,
            "domain": action.domain.value,
            "entity_name": action.entity_name,
            "entity_id": action.entity_id,
            "service": action.service,
            "service_data": action.service_data,
            "target_value": action.target_value,
            "confidence": action.confidence,
            "requires_confirmation": action.requires_confirmation,
        }
        # Add batch-related fields if present
        if action.is_batch:
            result["is_batch"] = True
            result["target_area"] = action.target_area
            result["target_floor"] = action.target_floor
            result["entity_ids"] = action.entity_ids
        return result


__all__ = [
    "ActionAgent",
    "ActionSpec",
    "ActionResult",
    "ActionType",
    "DeviceDomain",
]
