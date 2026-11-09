"""Support for net4home EXT-LD motor locks (Motorriegel)."""
from homeassistant import config_entries
from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from typing import Callable

from .const import DOMAIN
from .group_entity import ATTR_GROUPS, group_labels, listen_group_attribute
from .helpers import bus_connected, ensure_connected, listen_connection, parent_device_link
from .api import Net4HomeApi, Net4HomeDevice

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[LockEntity], bool], None],
) -> None:
    """Set up net4home motor lock entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    lock_devices = [d for d in api.devices.values() if d.device_type == "lock"]
    _LOGGER.info("[Lock] Creating %s EXT-LD lock entities", len(lock_devices))
    async_add_entities([Net4HomeLock(api, entry, d) for d in lock_devices], True)

    @callback
    def _async_new_device(device: Net4HomeDevice) -> None:
        if device.device_type == "lock":
            _LOGGER.info("[Lock] New EXT-LD lock detected: %s", device.device_id)
            async_add_entities([Net4HomeLock(api, entry, device)], True)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", _async_new_device)
    )


class Net4HomeLock(LockEntity):
    """EXT-LD motor lock. Locking and unlocking go to the base object of the module."""

    _attr_should_poll = False
    _attr_translation_key = "channel"

    def __init__(self, api: Net4HomeApi, entry: config_entries.ConfigEntry, device: Net4HomeDevice):
        """Initialize the lock."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}"

    @property
    def _status(self) -> dict | None:
        return getattr(self.device, "ext_ld_status", None)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def available(self) -> bool:
        return bus_connected(self.api)

    @property
    def is_locked(self) -> bool | None:
        """Return True if the bolt is thrown. None until the first status reply."""
        status = self._status
        if status is None:
            return None
        return status["locked"]

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the other status bits of the module."""
        status = self._status
        groups = group_labels(self)
        if status is None:
            return {ATTR_GROUPS: groups} if groups else None
        attrs = {
            "door_closed": status["door_closed"],
            "night_mode": status["night_mode"],
            "button_allowed": status["button_allowed"],
            # 0x40 "manuell verdreht" is not verified yet, so it is shown here and not as a state
            "manually_turned": status["manually_turned"],
            "flags": f"0x{status['flags']:02X}",
        }
        if groups:
            attrs[ATTR_GROUPS] = groups
        return attrs

    async def async_lock(self, **kwargs) -> None:
        """Lock the door (D0_SET 1)."""
        ensure_connected(self.api)
        await self.api.async_set_ext_ld_lock(self.device.device_id, True)

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the door (D0_SET 3). Confirm this in the dashboard, see docs."""
        ensure_connected(self.api)
        await self.api.async_set_ext_ld_lock(self.device.device_id, False)

    async def async_added_to_hass(self) -> None:
        """Listen for status replies."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_lock",
                self._handle_update,
            )
        )
        listen_group_attribute(self)
        listen_connection(self)

    @callback
    def _handle_update(self, status: dict) -> None:
        """Store a status reply and write the state."""
        self.device.ext_ld_status = status
        self.async_write_ha_state()
