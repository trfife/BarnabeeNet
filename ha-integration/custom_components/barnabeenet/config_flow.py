"""Config flow for BarnabeeNet integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEFAULT_URL, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BarnabeeNetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BarnabeeNet."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")

            # Test connection to BarnabeeNet
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    f"{url}/api/v1/health",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        # Connection successful
                        return self.async_create_entry(
                            title="BarnabeeNet",
                            data={CONF_URL: url},
                        )
                    else:
                        errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=CONF_DEFAULT_URL): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "default_url": CONF_DEFAULT_URL,
            },
        )
