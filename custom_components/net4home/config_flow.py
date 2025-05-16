"""Config flow for net4home integration with uppercase MI/OBJADR."""
from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR, CONF_MI, CONF_OBJADR

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
                vol.Optional(CONF_MI, default=DEFAULT_MI): int,
                vol.Optional(CONF_OBJADR, default=DEFAULT_OBJADR): int,
            })
            return self.async_show_form(
                step_id="user",
                data_schema=schema
            )

        # Validate by attempting handshake
        client = Net4HomeClient(
            self.hass,
            user_input["host"],
            user_input["port"],
            user_input["password"],
            user_input.get(CONF_MI),
            user_input.get(CONF_OBJADR),
        )
        try:
            await client.async_connect()
            await client.async_disconnect()
        except Exception:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"}
            )

        return self.async_create_entry(
            title=user_input["host"],
            data=user_input
        )

    async def async_step_zeroconf(self, discovery_info):
        host = discovery_info.get("host")
        port = discovery_info.get("port", DEFAULT_PORT)
        return await self.async_step_user({
            "host": host,
            "port": port,
            "password": "",
            CONF_MI: DEFAULT_MI,
            CONF_OBJADR: DEFAULT_OBJADR,
        })