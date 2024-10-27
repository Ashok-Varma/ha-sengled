"""Config Flow"""
import logging

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .api import API, AuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SengledConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sengled Config flow for handling user and zeroconf configuration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                _LOGGER.debug("Starting authentication with user input: %s", user_input)
                await API.check_auth(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                _LOGGER.info("Authentication successful for %s", user_input[CONF_USERNAME])
                return self.async_create_entry(title=DOMAIN, data=user_input)
            except AuthError:
                errors["base"] = "login_failed"
                _LOGGER.error("Authentication failed for user %s", user_input[CONF_USERNAME])
            except Exception as e:
                errors["base"] = "unknown_error"
                _LOGGER.exception("Unexpected error during authentication: %s", e)

        data_schema = {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery flow (currently not implemented)."""
        _LOGGER.debug("Zeroconf discovery received: %r", discovery_info)
        return self.async_abort(reason="not_implemented")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the flow for additional options if needed in the future."""
        return SengledOptionsFlowHandler(config_entry)


class SengledOptionsFlowHandler(ConfigFlow):
    """Handle Sengled integration options."""

    VERSION = 1

    def __init__(self, config_entry):
        """Initialize the options flow handler."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the options form."""
        options_schema = vol.Schema({
            vol.Optional('polling_interval', default=30): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            vol.Optional('enable_effects', default=True): cv.boolean,
        })

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=options_schema)
