from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
import voluptuous as vol
import socket
import asyncio
import logging

from .const import DOMAIN, N4H_IP_PORT, DEFAULT_MI, DEFAULT_OBJADR, CONF_MI, CONF_OBJADR
from .api import Net4HomeApi

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)

_LOGGER = logging.getLogger(__name__)

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
                user_input.get(CONF_OBJADR),
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
        
        return self.async_show_menu(
            step_id="user",
            menu_options=["discovery", "manual"],
            description_placeholders={
                "model": "Example model",
            }
        )            
        
        @staticmethod
        @callback
        def async_get_options_flow(
            config_entry: ConfigEntry,
        ) -> Net4HomeOptionsFlowHandler:
            """Get the options flow for net4home"""
            return Net4HomeOptionsFlowHandler()       

class Net4HomeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Net4Home config flow."""

    #def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    #    self.config_entry = config_entry
    #    # Kopie der Geräte aus Optionen für lokale Bearbeitung
    #    self.devices = list(self.config_entry.options.get("devices", []))
    
    async def async_step_init(self, user_input=None):
        errors = {}

        schema = vol.Schema(
            {
                vol.Required("host", default=self.entry.data.get("host")): str,
                vol.Required("port", default=self.entry.data.get("port", N4H_IP_PORT)): int,
                vol.Required("password", default=self.entry.data.get("password")): str,
                vol.Optional(CONF_MI, default=self.entry.data.get(CONF_MI, DEFAULT_MI)): int,
                vol.Optional(CONF_OBJADR, default=self.entry.data.get(CONF_OBJADR, DEFAULT_OBJADR)): int,
            #    vol.Optional("device_module_type", default=""): str,
            #    vol.Optional("device_mi", default=None): int,
            }
        )

        if user_input is not None:
            client = Net4HomeApi(
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
            except (OSError, socket.gaierror):
                errors["host"] = "host_not_found"
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input["host"],
                    data=user_input,
                )

                #device_mi = user_input.get("device_mi")
                #device_type = user_input.get("device_module_type")

                #if device_mi is not None and device_type:
                #    if any(d.get("mi") == device_mi for d in self.devices):
                #        errors["device_mi"] = "duplicate_device"
                #    else:
                #        self.devices.append({"mi": device_mi, "module_type": device_type})
                #elif device_mi is not None or device_type:
                #    errors["base"] = "both_fields_required"

                #if errors:
                #    return self.async_show_form(
                #        step_id="init", data_schema=schema, errors=errors
                #    )
                #else:
                #    options = dict(self.entry.options)
                #    options["devices"] = self.devices

                #    data = {
                #        "host": user_input["host"],
                #        "port": user_input["port"],
                #        "password": user_input["password"],
                #        CONF_MI: user_input.get(CONF_MI),
                #        CONF_OBJADR: user_input.get(CONF_OBJADR),
                #    }

                 #   self.hass.config_entries.async_update_entry(
                 #       self.entry, data=data, options=options
                 #   )
                 #   await self.hass.config_entries.async_reload(self.entry.entry_id)
                 #   return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )    
