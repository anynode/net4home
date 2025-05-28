import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant import config_entries

from .const import DOMAIN
from .api import Net4HomeApi, Net4HomeDevice
from typing import Callable

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[CoverEntity], bool], None]
) -> None:
    """Set up net4home cover entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug(f"Starting setup_entry with {len(api.devices)} known devices")
    for d in api.devices.values():
        _LOGGER.debug(f"→ {d.device_id} ({d.device_type})")

    entities = [
        Net4HomeCover(api, entry, device)
        for device in api.devices.values()
        if device.device_type == "cover"
    ]
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "cover":
            return
        async_add_entities([Net4HomeCover(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeCover(CoverEntity):
    _attr_has_entity_name = False

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        self.api = api
        self.entry = entry
        self.device = device
        self._is_closed = True
        self._attr_name = device.name
        _LOGGER.debug(f"[Cover] Init name={self._attr_name}, device_id={self.device.device_id}, device_type={self.device.device_type}")

    @property
    def unique_id(self) -> str:
        via = (self.device.via_device or "unknown").lower()
        return f"{self.entry.entry_id}_{slugify(via)}_{slugify(self.device.device_id)}"

    @property
    def is_closed(self):
        return self._is_closed

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
    def _handle_update(self, is_closed: bool):
        _LOGGER.debug(f"[net4home] _handle_update for {self.device.device_id}: {'CLOSED' if is_closed else 'OPEN'}")
        self._is_closed = is_closed
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        _LOGGER.debug(f"[net4home] async_turn_open: {self.device.device_id}")
        self._is_closed = False
        await self.api.async_open_cover(self.device.device_id)

    async def async_close_cover(self, **kwargs):
        _LOGGER.debug(f"[net4home] async_turn_close: {self.device.device_id}")
        self._is_closed = True
        await self.api.async_close_cover(self.device.device_id)

    async def async_stop_cover(self, **kwargs):
        _LOGGER.debug(f"[net4home] async_turn_stop: {self.device.device_id}")
        await self.api.async_stop_cover(self.device.device_id)

