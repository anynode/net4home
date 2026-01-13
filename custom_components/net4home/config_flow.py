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
        errors = {}

        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=N4H_IP_PORT): int,
            vol.Required("password"): str,
            vol.Optional(CONF_MI, default=DEFAULT_MI): int,
            vol.Optional(CONF_OBJADR, default=DEFAULT_OBJADR): int,
            vol.Optional("discover", default=False): bool,
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
                entry_data = {k: v for k, v in user_input.items() if k != "discover"}
                # devices werden beim ersten Setup nicht angelegt – das macht erst der Options-Flow
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
    def async_get_options_flow(config_entry):
        return Net4HomeOptionsFlowHandler(config_entry)


class Net4HomeOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for net4home, inkl. invertiert-Option für Binary-Sensoren."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        # Lade existierende Geräte aus options, falls vorhanden:
        self.devices = dict(config_entry.options.get("devices", {}))

    async def async_step_init(self, user_input=None):
        # Hier können allgemeine Optionen gesetzt werden (z.B. Verbindung).
        # Wir bieten ein Menü an.
        return self.async_show_menu(
            step_id="init",
            menu_options=["devices"],
            description_placeholders={"count": str(len(self.devices))}
        )

    async def async_step_devices(self, user_input=None):
        errors = {}

        # Dynamisch Schema bauen: pro Binary Sensor ein "inverted"-Feld
        schema_dict = {}
        for dev_id, info in self.devices.items():
            if info["device_type"] == "binary_sensor":
                schema_dict[vol.Optional(f"inverted_{dev_id}", default=info.get("inverted", False))] = bool

        # Optional neue Geräte hinzufügen
        schema_dict[vol.Optional("new_device_id")] = str
        schema_dict[vol.Optional("new_device_name")] = str
        schema_dict[vol.Optional("new_device_type")] = vol.In(
            ["light", "switch", "cover", "binary_sensor", "climate", "sensor", "unknown"]
        )

        schema = vol.Schema(schema_dict)

        if user_input is not None:
            # Update vorhandene Binary Sensoren
            for dev_id, info in self.devices.items():
                if info["device_type"] == "binary_sensor":
                    info["inverted"] = user_input.get(f"inverted_{dev_id}", info.get("inverted", False))

            # Optional neues Gerät anlegen
            if user_input.get("new_device_id") and user_input.get("new_device_type"):
                dev_id = user_input["new_device_id"]
                self.devices[dev_id] = {
                    "device_id": dev_id,
                    "name": user_input.get("new_device_name", dev_id),
                    "model": "Manuell",
                    "device_type": user_input["new_device_type"],
                    "via_device": None,
                }
                _LOGGER.info(f"[net4home] Gerät {dev_id} manuell hinzugefügt")

            # Optionen zurück in die Config schreiben
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
