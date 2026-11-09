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

from .const import DOMAIN
from .group_entity import ATTR_GROUPS, Net4HomeGroupLight, group_labels, listen_group_attribute, take_new_groups
from .helpers import bus_connected, ensure_connected, listen_connection, parent_device_link
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
    
    _LOGGER.info(f"[Light] Setup called with {len(api.devices)} devices in API")
    light_devices = [d for d in api.devices.values() if d.device_type == "light"]
    _LOGGER.info(f"[Light] Found {len(light_devices)} light devices: {[d.device_id for d in light_devices]}")

    entities = [
        Net4HomeLight(api, entry, device)
        for device in light_devices
    ]

    _LOGGER.info(f"[Light] Creating {len(entities)} light entities")
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "light":
            return
        async_add_entities([Net4HomeLight(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

    seen_groups: set[int] = set()

    async def async_new_groups(groups):
        fresh = take_new_groups(
            "light",
            seen_groups,
            groups,
            lambda group: Net4HomeGroupLight(api, entry, group),
        )
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_groups_{entry.entry_id}", async_new_groups
        )
    )


class Net4HomeLight(LightEntity):
    """Representation of a net4home light."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_translation_key = "channel"
    _supported_color_modes = frozenset({ColorMode.BRIGHTNESS})
    
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the light."""
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
        """Return a unique ID for the entity."""
        via = (self.device.via_device or "unknown").lower()
        return f"{self.entry.entry_id}_{slugify(via)}_{slugify(self.device.device_id)}"

    @property
    def available(self) -> bool:
        return bus_connected(self.api)

    @property
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return self._is_on
  
    @property
    def brightness(self) -> int:
        """Return the brightness of the light (0-255)."""
        return self._brightness  
  
    @property
    def supported_color_modes(self) -> set[str]:
        """Return supported color modes."""
        return self._supported_color_modes

    @property
    def color_mode(self) -> str:
        """Return the current color mode."""
        return ColorMode.BRIGHTNESS
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        _LOGGER.debug(f"Entity DeviceInfo: {self.device.device_id}")
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "device_id": self.device.device_id,
            "model": self.device.model,
            "via_device": self.device.via_device or "",
            "send_state_changes": bool(getattr(self.device, "send_state_changes", False)),
            ATTR_GROUPS: group_labels(self),
        }


    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        _LOGGER.debug(f"[net4home] async_added_to_hass for {self.device.device_id}")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )
        listen_group_attribute(self)
        listen_connection(self)

    @callback
    def _handle_update(self, update_data):
        """Handle update from dispatcher."""
        if isinstance(update_data, dict):
            self._is_on = update_data.get("is_on", self._is_on)
            self._brightness = update_data.get("brightness", self._brightness)
        else:
            self._is_on = bool(update_data)
        self.async_write_ha_state()


    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        _LOGGER.debug(f"Turning light OFF: {self.device.device_id}")
        ensure_connected(self.api)
        self._is_on = False
        await self.api.async_turn_off_light(self.device.device_id)
        self.async_write_ha_state()


    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        ensure_connected(self.api)
        if self.device.model == "Timer" and kwargs.get("brightness") is None:
            _LOGGER.debug("Recalling last dimmer level: %s", self.device.device_id)
            await self.api.async_turn_on_light(self.device.device_id, None)
            self._is_on = True
            self.async_write_ha_state()
            return

        brightness = kwargs.get("brightness", 255)
        if brightness is None:
            brightness = 255

        _LOGGER.debug(f"Turning light ON with brightness {brightness}: {self.device.device_id}")
        await self.api.async_turn_on_light(self.device.device_id, brightness)

        self._is_on = True
        self._brightness = brightness
        self.async_write_ha_state()



