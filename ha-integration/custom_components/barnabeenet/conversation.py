"""Conversation agent for BarnabeeNet.

This module implements the conversation agent that integrates with
Home Assistant's Assist feature. When a user speaks to Assist,
the text is forwarded to BarnabeeNet for processing.
"""

from __future__ import annotations

import logging
from typing import Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationInput, ConversationResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHAT_ENDPOINT, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BarnabeeNet conversation agent."""
    agent = BarnabeeNetConversationAgent(hass, config_entry)
    async_add_entities([agent])


class BarnabeeNetConversationAgent(conversation.ConversationEntity):
    """BarnabeeNet conversation agent.

    This agent forwards conversation input to the BarnabeeNet API
    and returns the response. It automatically detects the speaker
    from the Home Assistant user context.
    """

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_conversation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "BarnabeeNet",
            "manufacturer": "BarnabeeNet",
            "model": "Conversation Agent",
        }

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages (all languages)."""
        return "*"

    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        """Process a conversation input and return the response."""
        text = user_input.text
        conversation_id = user_input.conversation_id

        # Get speaker name from HA user context
        speaker = await self._get_speaker_name(user_input)

        # Get room/area context if available
        room = None
        if user_input.device_id:
            room = await self._get_device_area(user_input.device_id)

        _LOGGER.debug(
            "Processing: text=%s, speaker=%s, room=%s, conversation_id=%s",
            text,
            speaker,
            room,
            conversation_id,
        )

        # Call BarnabeeNet API
        try:
            response_text, new_conversation_id = await self._call_barnabeenet(
                text=text,
                speaker=speaker,
                room=room,
                conversation_id=conversation_id,
            )
        except Exception as err:
            _LOGGER.error("Error calling BarnabeeNet: %s", err)
            response_text = "Sorry, I couldn't reach BarnabeeNet right now."
            new_conversation_id = conversation_id

        # Build response
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(response_text)

        return ConversationResult(
            response=response,
            conversation_id=new_conversation_id or conversation_id,
        )

    async def _get_speaker_name(self, user_input: ConversationInput) -> str | None:
        """Get the speaker name from HA user context."""
        if not user_input.context or not user_input.context.user_id:
            return None

        user_id = user_input.context.user_id

        # Look up person entity with this user_id
        for state in self.hass.states.async_all("person"):
            if state.attributes.get("user_id") == user_id:
                # Return the person's name (lowercase for consistency)
                return state.name.lower()

        # Fallback: try to get user directly
        user = await self.hass.auth.async_get_user(user_id)
        if user:
            return user.name.lower()

        return None

    async def _get_device_area(self, device_id: str) -> str | None:
        """Get the area name for a device."""
        device_registry = self.hass.helpers.device_registry.async_get(self.hass)
        device = device_registry.async_get(device_id)

        if device and device.area_id:
            area_registry = self.hass.helpers.area_registry.async_get(self.hass)
            area = area_registry.async_get_area(device.area_id)
            if area:
                return area.name.lower().replace(" ", "_")

        return None

    async def _call_barnabeenet(
        self,
        text: str,
        speaker: str | None,
        room: str | None,
        conversation_id: str | None,
    ) -> tuple[str, str | None]:
        """Call the BarnabeeNet chat API.

        Returns:
            Tuple of (response_text, conversation_id)
        """
        url = self.config_entry.data[CONF_URL]
        endpoint = f"{url}{CHAT_ENDPOINT}"

        payload = {"text": text}
        if speaker:
            payload["speaker"] = speaker
        if room:
            payload["room"] = room
        if conversation_id:
            payload["conversation_id"] = conversation_id

        session = async_get_clientsession(self.hass)

        async with session.post(
            endpoint,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"BarnabeeNet returned {response.status}: {error_text}")

            data = await response.json()
            return data.get("response", ""), data.get("conversation_id")
