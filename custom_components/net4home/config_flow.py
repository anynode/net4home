"""Config flow for net4home integration."""
import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    N4H_IP_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    CONF_MI,
    CONF_OBJADR,
)
from .api import Net4HomeApi

_LOGGER = logging.getLogger(__name__)


class Net4HomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step - go directly to IP configuration."""
        return await self.async_step_ip(user_input=None)

    async def async_step_ip(self, user_input=None):
        """Handle IP connection configuration."""
        errors = {}

        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=N4H_IP_PORT): int,
            vol.Required("password"): str,
            vol.Required(CONF_MI, default=DEFAULT_MI): int,
            vol.Required(CONF_OBJADR, default=DEFAULT_OBJADR): int,
            vol.Optional("discover", default=False): bool,
        })

        if user_input is not None:
            client = Net4HomeApi(
                hass=self.hass,
                host=user_input["host"],
                port=user_input["port"],
                password=user_input["password"],
                mi=user_input.get(CONF_MI),
                objadr=user_input.get(CONF_OBJADR),
            )

            try:
                await client.async_connect()
                if user_input.get("discover"):
                    await client.send_enum_all()
            except (OSError, socket.gaierror):
                errors["host"] = "host_not_found"
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as ex:
                _LOGGER.exception("Unknown error in ConfigFlow", exc_info=ex)
                errors["base"] = "unknown"
            else:
                entry_data = {
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "password": user_input["password"],
                    CONF_MI: user_input[CONF_MI],
                    CONF_OBJADR: user_input[CONF_OBJADR],
                }
                # devices are not created during initial setup – that is done by the options flow
                return self.async_create_entry(
                    title=user_input["host"],
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="ip",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        # In Home Assistant 2025.12+, config_entry is automatically available
        # as a property in OptionsFlow - don't pass it to __init__
        return Net4HomeOptionsFlowHandler()


class Net4HomeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for net4home integration."""

    def __init__(self):
        """Initialize the options flow handler."""
        # In Home Assistant 2025.12+, config_entry is automatically available
        # as a read-only property via self.config_entry
        # No need to accept it as a parameter or set it manually
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Single step for options including ENUM_ALL trigger settings."""
        errors = {}
        
        # Load existing devices from options
        devices = dict(self.config_entry.options.get("devices", {}))
        
        # Get MI and OBJADR from config.data
        current_mi = self.config_entry.data.get(CONF_MI, DEFAULT_MI)
        current_objadr = self.config_entry.data.get(CONF_OBJADR, DEFAULT_OBJADR)

        # Build dynamic schema: ENUM_ALL option with MI and OBJADR
        schema_dict = {
            vol.Optional(CONF_MI, default=current_mi): int,
            vol.Optional(CONF_OBJADR, default=current_objadr): int,
            vol.Optional("trigger_enum_all", default=False): bool,
        }
        
        schema = vol.Schema(schema_dict)
        
        if user_input is not None:
            # If MI or OBJADR were changed, update config.data
            if CONF_MI in user_input or CONF_OBJADR in user_input:
                new_data = dict(self.config_entry.data)
                if CONF_MI in user_input:
                    new_data[CONF_MI] = user_input[CONF_MI]
                if CONF_OBJADR in user_input:
                    new_data[CONF_OBJADR] = user_input[CONF_OBJADR]
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                _LOGGER.info(f"[net4home] MI/OBJADR updated: MI={new_data.get(CONF_MI)}, OBJADR={new_data.get(CONF_OBJADR)}")
            
            # If ENUM_ALL should be triggered
            if user_input.get("trigger_enum_all"):
                # Get the API instance
                api = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if api:
                    try:
                        await api.send_enum_all()
                        _LOGGER.info(f"[net4home] ENUM_ALL manually triggered (entry_id {self.config_entry.entry_id})")
                    except Exception as e:
                        _LOGGER.error(f"[net4home] Error during manual ENUM_ALL: {e}", exc_info=True)
                        errors["base"] = "enum_all_failed"
                else:
                    errors["base"] = "api_not_available"
                    _LOGGER.warning(f"[net4home] API not available for entry_id {self.config_entry.entry_id}")

            # Write options back to config (only if no errors)
            if not errors:
                new_options = dict(self.config_entry.options)
                new_options["devices"] = devices
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
                return self.async_create_entry(title="", data={})
        
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "entry_id": self.config_entry.entry_id,
            }
        )
