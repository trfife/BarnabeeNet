"""Graceful Fallback Service - Never say "I don't know".

When the fast path fails (pattern match, entity resolution, etc.),
this service escalates to the LLM with full context so it can make
an intelligent attempt rather than returning unhelpful error messages.

Design principles:
- The LLM has access to all HA entities, user location, recent context
- With this context, the LLM can almost always make a reasonable guess
- Execute the most likely interpretation
- Log fallback usage for self-improvement
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from barnabeenet.services.homeassistant.client import HomeAssistantClient
    from barnabeenet.services.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


# Patterns that indicate a failure response that should be escalated
FAILURE_PATTERNS = [
    r"I couldn't find",
    r"I don't know",
    r"I'm not sure which",
    r"couldn't be found",
    r"unable to find",
    r"No entities affected",
    r"entity may not exist",
    r"check .* connection",
]

FAILURE_REGEX = re.compile("|".join(FAILURE_PATTERNS), re.IGNORECASE)


@dataclass
class FallbackContext:
    """Context assembled for the LLM fallback."""

    # Original request
    original_text: str
    failure_reason: str

    # User context
    speaker: str | None = None
    room: str | None = None

    # HA context (summarized for LLM)
    available_entities: list[dict[str, str]] = field(default_factory=list)  # [{name, domain, area}]
    person_locations: dict[str, str] = field(default_factory=dict)  # {name: location}
    areas: list[str] = field(default_factory=list)

    # Recent context
    recent_commands: list[str] = field(default_factory=list)


@dataclass
class FallbackResult:
    """Result of a fallback attempt."""

    success: bool
    response: str
    action_taken: dict[str, Any] | None = None  # If we resolved to a device action
    confidence: float = 0.0
    fallback_used: bool = True


class GracefulFallbackService:
    """Service for handling graceful fallbacks to LLM when fast path fails."""

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        ha_client: HomeAssistantClient | None = None,
    ):
        self._llm_client = llm_client
        self._ha_client = ha_client
        self._recent_commands: list[str] = []  # Rolling buffer of recent commands
        self._max_recent_commands = 5

    def is_failure_response(self, response: str) -> bool:
        """Check if a response indicates a failure that should be escalated.

        Args:
            response: The response text from an agent

        Returns:
            True if this looks like a failure response
        """
        return bool(FAILURE_REGEX.search(response))

    def add_recent_command(self, command: str) -> None:
        """Track a recent command for context.

        Args:
            command: The command text
        """
        self._recent_commands.append(command)
        if len(self._recent_commands) > self._max_recent_commands:
            self._recent_commands.pop(0)

    async def assemble_context(
        self,
        original_text: str,
        failure_reason: str,
        speaker: str | None = None,
        room: str | None = None,
    ) -> FallbackContext:
        """Assemble full context for the LLM fallback.

        Args:
            original_text: The user's original request
            failure_reason: Why the fast path failed
            speaker: Who is speaking
            room: Where the request came from

        Returns:
            FallbackContext with all available information
        """
        context = FallbackContext(
            original_text=original_text,
            failure_reason=failure_reason,
            speaker=speaker,
            room=room,
            recent_commands=list(self._recent_commands),
        )

        # Get HA context
        if self._ha_client and self._ha_client.connected:
            try:
                # Get entity summary (name, domain, area for each)
                entities = []
                for entity in self._ha_client._entity_registry.all():
                    entities.append(
                        {
                            "name": entity.friendly_name,
                            "domain": entity.domain,
                            "area": entity.area_id or "unknown",
                            "entity_id": entity.entity_id,
                        }
                    )
                context.available_entities = entities

                # Get areas
                if hasattr(self._ha_client, "_areas"):
                    context.areas = [a.name for a in self._ha_client._areas.values()]

                # Get person locations
                person_entities = [e for e in entities if e["domain"] == "person"]
                for person in person_entities:
                    try:
                        state = await self._ha_client.get_state(person["entity_id"])
                        if state:
                            context.person_locations[person["name"]] = state.state
                    except Exception:
                        pass

            except Exception as e:
                logger.warning("Could not get HA context for fallback: %s", e)

        return context

    def _build_entity_summary(self, entities: list[dict[str, str]], max_entities: int = 100) -> str:
        """Build a concise entity summary for the LLM prompt.

        Groups entities by domain and area for readability.
        """
        if not entities:
            return "No Home Assistant entities available."

        # Group by domain
        by_domain: dict[str, list[dict[str, str]]] = {}
        for e in entities:
            domain = e["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(e)

        # Build summary (prioritize controllable domains)
        priority_domains = ["light", "switch", "fan", "cover", "climate", "lock", "media_player"]
        other_domains = [d for d in by_domain.keys() if d not in priority_domains]

        lines = []
        count = 0

        for domain in priority_domains + other_domains:
            if domain not in by_domain:
                continue
            if count >= max_entities:
                break

            domain_entities = by_domain[domain]
            entity_names = [f"{e['name']} ({e['area']})" for e in domain_entities[:15]]
            remaining = len(domain_entities) - 15
            if remaining > 0:
                entity_names.append(f"...and {remaining} more")

            lines.append(f"{domain}: {', '.join(entity_names)}")
            count += len(domain_entities[:15])

        return "\n".join(lines)

    async def attempt_fallback(
        self,
        original_text: str,
        failure_reason: str,
        speaker: str | None = None,
        room: str | None = None,
        intent_hint: str | None = None,
    ) -> FallbackResult:
        """Attempt to handle a request using LLM fallback with full context.

        Args:
            original_text: The user's original request
            failure_reason: Why the fast path failed
            speaker: Who is speaking
            room: Where the request came from
            intent_hint: Hint about what kind of request this is (action, query, etc.)

        Returns:
            FallbackResult with the LLM's attempt
        """
        if not self._llm_client:
            logger.warning("No LLM client available for fallback")
            return FallbackResult(
                success=False,
                response=failure_reason,  # Return original failure
                fallback_used=False,
            )

        # Assemble full context
        context = await self.assemble_context(
            original_text=original_text,
            failure_reason=failure_reason,
            speaker=speaker,
            room=room,
        )

        # Build the LLM prompt
        entity_summary = self._build_entity_summary(context.available_entities)

        person_info = ""
        if context.person_locations:
            locations = [f"{name}: {loc}" for name, loc in context.person_locations.items()]
            person_info = f"\n\nPerson locations:\n{chr(10).join(locations)}"

        recent_info = ""
        if context.recent_commands:
            recent_info = "\n\nRecent commands from this user:\n- " + "\n- ".join(
                context.recent_commands
            )

        system_prompt = f"""You are Barnabee, a helpful smart home assistant. The user made a request that the system couldn't handle automatically. Use the context below to make your best intelligent attempt.

IMPORTANT: Never say "I don't know" or "I couldn't find that." Always make your best attempt with the information available. If you're unsure, make a reasonable guess and offer to correct if wrong.

Available Home Assistant entities:
{entity_summary}{person_info}{recent_info}

User's room: {context.room or "unknown"}
Speaker: {context.speaker or "unknown"}

The automatic system failed with: "{context.failure_reason}"

Based on the available entities and context, interpret what the user wants and respond helpfully. If they're asking about a device, find the closest match. If they're asking about a person, use the location data. Be warm and helpful."""

        user_prompt = f'User request: "{context.original_text}"'

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                agent_type="interaction",  # Use interaction model for quality
                user_input=original_text,
            )

            logger.info(
                "Graceful fallback succeeded",
                extra={
                    "original_text": original_text,
                    "failure_reason": failure_reason,
                    "response_preview": response.text[:100] if response.text else "",
                },
            )

            return FallbackResult(
                success=True,
                response=response.text,
                confidence=0.7,  # Medium confidence for LLM fallback
                fallback_used=True,
            )

        except Exception as e:
            logger.error("LLM fallback failed: %s", e)
            return FallbackResult(
                success=False,
                response=failure_reason,  # Return original failure
                fallback_used=True,
            )


# Singleton instance
_fallback_service: GracefulFallbackService | None = None


async def get_fallback_service(
    llm_client: OpenRouterClient | None = None,
    ha_client: HomeAssistantClient | None = None,
) -> GracefulFallbackService:
    """Get or create the singleton fallback service.

    Args:
        llm_client: LLM client (will be used to update singleton if provided)
        ha_client: HA client (will be used to update singleton if provided)

    Returns:
        The fallback service singleton
    """
    global _fallback_service

    if _fallback_service is None:
        _fallback_service = GracefulFallbackService(
            llm_client=llm_client,
            ha_client=ha_client,
        )
    else:
        # Update clients if provided
        if llm_client:
            _fallback_service._llm_client = llm_client
        if ha_client:
            _fallback_service._ha_client = ha_client

    return _fallback_service
