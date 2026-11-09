"""Access events for UP-RF readers: one event entity per reader."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .api import Net4HomeApi, Net4HomeDevice
from .const import DOMAIN
from .helpers import parent_device_link
from .rf_access import access_signal, store_key
from .rf_key_book import ACCESS_STATES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Create one access event entity per UP-RF reader module."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    store = hass.data[DOMAIN][store_key(entry.entry_id)]

    def _is_reader(device: Net4HomeDevice) -> bool:
        return (
            device.device_type == "rf_reader"
            and device.device_id.startswith("MI")
            and not device.via_device
        )

    entities = [
        Net4HomeRfAccessEvent(entry, device, store)
        for device in api.devices.values()
        if _is_reader(device)
    ]
    _LOGGER.info("[Event] Creating %s RF access entities", len(entities))
    async_add_entities(entities)

    @callback
    def _async_new_device(device: Net4HomeDevice) -> None:
        if _is_reader(device):
            async_add_entities([Net4HomeRfAccessEvent(entry, device, store)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", _async_new_device)
    )


class Net4HomeRfAccessEvent(EventEntity):
    """Fires once per key presentation at one reader."""

    _attr_should_poll = False

    _attr_has_entity_name = False
    _attr_event_types = list(ACCESS_STATES)
    _attr_icon = "mdi:key-wireless"

    def __init__(self, entry, device: Net4HomeDevice, store) -> None:
        self.entry = entry
        self.device = device
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_rf_access"
        self._attr_name = f"{device.name} Zutritt"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                access_signal(self.device.device_id),
                self._handle_access,
            )
        )

    @callback
    def _handle_access(self, payload: dict[str, Any]) -> None:
        state = payload.get("state")
        if state not in ACCESS_STATES:
            state = "unknown"
        attributes = {
            "rf_key": payload.get("rf_key"),
            "key_name": payload.get("key_name"),
            "person": payload.get("person"),
            "person_name": payload.get("person_name"),
        }
        self._trigger_event(state, attributes)
        self.async_write_ha_state()
