"""Config flow for Kia Connected Services integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_HOST,
    CONF_PORT
    
)

from .const import DOMAIN, INTEGRATION_TITLE, CONNECT_FAIL_AUTH, CONNECT_FAIL_NETWORK, DEFAULT_PORT
from .onesmartwrapper import OneSmartWrapper

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    wrapper = OneSmartWrapper(
        username = data[CONF_USERNAME],
        password = data[CONF_PASSWORD],
        host = data[CONF_HOST],
        port = data[CONF_PORT],
        hass = hass
    )

    # try:
    connection_status = await wrapper.connect()
    # except:
    #     raise CannotConnect
    if connection_status == CONNECT_FAIL_AUTH:
        raise InvalidAuth
    elif connection_status == CONNECT_FAIL_NETWORK:
        raise CannotConnect
    
    
    # Return info that you want to store in the config entry.
    return {"title": INTEGRATION_TITLE}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kia Connected Services."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
