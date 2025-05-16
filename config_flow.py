"""Config flow for net4home integration."""
from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR

class Net4HomeFlowHandler(
    config_entries.ConfigFlow,
    domain=DOMAIN
):
    """Handle a config flow for net4home."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema({
                vol.Required("host"): str,
                vol.Required("port", default=DEFAULT_PORT): int,
                vol.Required("password"): str,
                vol.Optional("mi", default=DEFAULT_MI): int,
                vol.Optional("objadr", default=DEFAULT_OBJADR): int,
            })
            return self.async_show_form(
                step_id="user",
                data_schema=schema
            )

        # TODO: validate connection and create entry
        return self.async_create_entry(
            title=user_input["host"],
            data=user_input
        )

    async def async_step_zeroconf(self, discovery_info):
        host = discovery_info["host"]
        # TODO: extract port/service from discovery_info
        return await self.async_step_user({"host": host})