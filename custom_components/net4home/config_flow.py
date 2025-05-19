"""Config flow for net4home integration."""

import logging
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD

from .const import DOMAIN, DEFAULT_PORT, CONF_MI, CONF_OBJADR
from .api import Net4HomeApi

_LOGGER = logging.getLogger(__name__)


class Net4HomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for net4home."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._password: str | None = None
        self._mi: str | None = None
        self._objadr: str | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input.get(CONF_PORT, DEFAULT_PORT)
            self._password = user_input[CONF_PASSWORD]
            self._mi = user_input.get(CONF_MI)
            self._objadr = user_input.get(CONF_OBJADR)

            api = Net4HomeApi(
                host=self._host,
                port=self._port,
                password=self._password,
                mi=self._mi,
                objadr=self._objadr,
                logger=_LOGGER,
            )
            try:
                await api.async_connect()
            except Exception as err:
                _LOGGER.error("Failed to connect to net4home Bus connector: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # Connection succeeded, create entry
                return self.async_create_entry(
                    title=self._host,
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_PASSWORD: self._password,
                        CONF_MI: self._mi,
                        CONF_OBJADR: self._objadr,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_MI): str,
                vol.Optional(CONF_OBJADR): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
