import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
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
    """Config flow for net4home."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=N4H_IP_PORT): int,
            vol.Required("password"): str,
            vol.Optional(CONF_MI, default=DEFAULT_MI): int,
            vol.Optional(CONF_OBJADR, default=DEFAULT_OBJADR): int,
            vol.Optional("discover", default=False): bool,  # <- neue Checkbox
        })

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

                if user_input.get("discover"):
                    await client.send_enum_all()
                    _LOGGER.info("[net4home] Discover devices wurde im Setup aktiviert → ENUM_ALL gesendet")

                await client.async_disconnect()

            except (OSError, socket.gaierror):
                errors["host"] = "host_not_found"
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as ex:
                _LOGGER.exception("Unbekannter Fehler im ConfigFlow", exc_info=ex)
                errors["base"] = "unknown"
            else:
                entry_data = {k: v for k, v in user_input.items() if k != "discover"}

                return self.async_create_entry(
                    title=user_input["host"],
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        return Net4HomeOptionsFlowHandler(config_entry)


class Net4HomeOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Options flow for net4home."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry)
        self.devices = dict(config_entry.options.get("devices", {}))

    async def async_step_init(self, user_input=None):
        errors = {}

        schema = vol.Schema({
            vol.Required("host", default=self.config_entry.data.get("host")): str,
            vol.Required("port", default=self.config_entry.data.get("port", N4H_IP_PORT)): int,
            vol.Required("password", default=self.config_entry.data.get("password")): str,
            vol.Optional(CONF_MI, default=self.config_entry.data.get(CONF_MI, DEFAULT_MI)): int,
            vol.Optional(CONF_OBJADR, default=self.config_entry.data.get(CONF_OBJADR, DEFAULT_OBJADR)): int,
        })

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
                _LOGGER.exception("Fehler im OptionsFlow")
                errors["base"] = "unknown"
            else:
                new_options = dict(self.config_entry.options)
                new_options.update(user_input)
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
                return self.async_create_entry(title="", data={})

        return self.async_show_menu(
            step_id="init",
            menu_options=["devices"],
            description_placeholders={"count": str(len(self.devices))},
        )

    async def async_step_devices(self, user_input=None):
        errors = {}

        device_choices = {
            dev_id: f"{info['name']} ({info['device_type']})"
            for dev_id, info in self.devices.items()
        }

        schema = vol.Schema({
            vol.Optional("delete_device"): vol.In(device_choices),
            vol.Optional("new_device_id"): str,
            vol.Optional("new_device_name"): str,
            vol.Optional("new_device_type"): vol.In(["switch", "sensor", "light", "unknown"]),
        })

        if user_input is not None:
            if user_input.get("delete_device"):
                deleted = user_input["delete_device"]
                if deleted in self.devices:
                    del self.devices[deleted]
                    _LOGGER.info(f"[net4home] Gerät {deleted} gelöscht")

            elif user_input.get("new_device_id") and user_input.get("new_device_type"):
                dev_id = user_input["new_device_id"]
                self.devices[dev_id] = {
                    "device_id": dev_id,
                    "name": user_input.get("new_device_name", dev_id),
                    "model": "Manuell",
                    "device_type": user_input["new_device_type"],
                    "via_device": None,
                }
                _LOGGER.info(f"[net4home] Gerät {dev_id} manuell hinzugefügt")

            new_options = dict(self.config_entry.options)
            new_options["devices"] = self.devices
            self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="devices",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "count": str(len(self.devices)),
            }
        )
