from homeassistant import config_entries
import voluptuous as vol
import socket
import asyncio
import logging

from .const import DOMAIN, N4H_IP_PORT, DEFAULT_MI, DEFAULT_OBJADR, CONF_MI, CONF_OBJADR
from .api import Net4HomeApi

class Net4HomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = Net4HomeApi(
                    self.hass,
                    user_input["host"],
                    user_input["port"],
                    user_input["password"],
                    user_input.get(CONF_MI),
                    user_input.get(CONF_OBJADR)
            )
            
            try:
                await client.async_connect()
                await client.async_disconnect()
            except (OSError, socket.gaierror):
                errors["host"] = "host_not_found"
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError as ce:
                errors["base"] = "cannot_connect"
            except Exception as ex:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input["host"],
                    data=user_input,
                )

        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=N4H_IP_PORT): int,
            vol.Required("password"): str,
            vol.Optional(CONF_MI, default=DEFAULT_MI): int,
            vol.Optional(CONF_OBJADR, default=DEFAULT_OBJADR): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
