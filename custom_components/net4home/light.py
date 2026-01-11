from homeassistant.components.light import LightEntity
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util.color import value_to_brightness
from homeassistant.util.percentage import percentage_to_ranged_value
from homeassistant.util import slugify
from homeassistant import config_entries
from typing import Callable

from .diagnostic_sensor import Net4HomeSendStateChangesDiagnosticSensor
from .const import DOMAIN
from .api import Net4HomeApi, Net4HomeDevice

import logging
import math

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[LightEntity], bool], None]
) -> None:
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Net4HomeLight(api, entry, device)
        for device in api.devices.values()
        if device.device_type == "light"
    ]

    diagnostic_entities = [
        Net4HomeSendStateChangesDiagnosticSensor(entry, device)
        for device in api.devices.values()
        if device.device_type == "light"
    ]

    async_add_entities(entities + diagnostic_entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "light":
            return
        async_add_entities([
            Net4HomeLight(api, entry, device),
            Net4HomeSendStateChangesDiagnosticSensor(entry, device)
        ])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeLight(LightEntity):
    _attr_has_entity_name = False
    _supported_color_modes = frozenset({ColorMode.BRIGHTNESS})
    
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        self.api = api
        self.entry = entry
        self.device = device
        self._is_on = False
        self._brightness = 255
        self._attr_name = device.name
        self.send_state_changes = False
        _LOGGER.debug(f"[Light] Init name={self._attr_name}, device_id={self.device.device_id}, device_type={self.device.device_type}")

    @property
    def unique_id(self) -> str:
        via = (self.device.via_device or "unknown").lower()
        return f"{self.entry.entry_id}_{slugify(via)}_{slugify(self.device.device_id)}"

    @property
    def is_on(self) -> bool:
        return self._is_on
  
    @property
    def brightness(self) -> int:
        """Return the brightness of the light (0-255)."""
        return self._brightness  
  
    @property
    def supported_color_modes(self) -> set[str]:
        return self._supported_color_modes

    @property
    def color_mode(self) -> str:
        return ColorMode.BRIGHTNESS
    
    @property
    def device_info(self) -> DeviceInfo:
        _LOGGER.debug(f"Entity DeviceInfo: {self.device.device_id}")
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "device_id": self.device.device_id,
            "model": self.device.model,
            "via_device": self.device.via_device or "",
            "send_state_changes": self.send_state_changes,  
        }


    async def async_added_to_hass(self):
        _LOGGER.debug(f"[net4home] async_added_to_hass für {self.device.device_id}")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, update_data):
        if isinstance(update_data, dict):
            self._is_on = update_data.get("is_on", self._is_on)
            self._brightness = update_data.get("brightness", self._brightness)
        else:
            self._is_on = bool(update_data)
        self.async_write_ha_state()


    async def async_turn_off(self, **kwargs):
        _LOGGER.debug(f"Schalte Light AUS: {self.device.device_id}")
        self._is_on = False
        await self.api.async_turn_off_light(self.device.device_id)
        self.async_write_ha_state()


    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get("brightness", 255)
        
        if brightness is None:
            brightness = 255

        _LOGGER.debug(f"Schalte Light EIN mit Helligkeit {brightness}: {self.device.device_id}")
        await self.api.async_turn_on_light(self.device.device_id, brightness)

        self._is_on = True
        self._brightness = brightness
        self.async_write_ha_state()



