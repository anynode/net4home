from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant import config_entries
from typing import Callable

from .bell import bell_switches
from .bell_layout import is_wav_bell
from .const import DOMAIN
from .group_entity import ATTR_GROUPS, Net4HomeGroupSwitch, group_labels, listen_group_attribute, take_new_groups
from .helpers import bus_connected, ensure_connected, listen_connection, parent_device_link
from .api import Net4HomeApi, Net4HomeDevice

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[SwitchEntity], bool], None]
) -> None:
    """Set up net4home switch entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    
    _LOGGER.info(f"[Switch] Setup called with {len(api.devices)} devices in API")
    switch_devices = [d for d in api.devices.values() if d.device_type == "switch"]
    _LOGGER.info(f"[Switch] Found {len(switch_devices)} switch devices: {[d.device_id for d in switch_devices]}")

    bell_seen: set[str] = set()

    def _take_bell(device: Net4HomeDevice) -> list:
        if not is_wav_bell(device) or device.device_id in bell_seen:
            return []
        bell_seen.add(device.device_id)
        return bell_switches(api, entry, device)

    entities = [
        Net4HomeSwitch(api, entry, device)
        for device in switch_devices
    ]
    for device in api.devices.values():
        entities.extend(_take_bell(device))
    hs_time_devices = [
        device
        for device in api.devices.values()
        if device.device_type == "sensor" and device.model == "HS-Time" and not device.via_device
    ]
    for device in hs_time_devices:
        entities.extend(_hs_time_profile_switches(api, entry, device))

    _LOGGER.info(f"[Switch] Creating {len(entities)} switch entities")
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type == "switch":
            async_add_entities([Net4HomeSwitch(api, entry, device)])
        elif device.device_type == "sensor" and device.model == "HS-Time" and not device.via_device:
            async_add_entities(_hs_time_profile_switches(api, entry, device))
        fresh = _take_bell(device)
        if fresh:
            async_add_entities(fresh)

    async def async_device_updated(device_id: str = None):
        if not device_id:
            return
        device = api.devices.get(device_id)
        if not device:
            return
        fresh = _take_bell(device)
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

    seen_groups: set[int] = set()

    async def async_new_groups(groups):
        fresh = take_new_groups(
            "switch",
            seen_groups,
            groups,
            lambda group: Net4HomeGroupSwitch(api, entry, group),
        )
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_groups_{entry.entry_id}", async_new_groups
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated
        )
    )


class Net4HomeSwitch(SwitchEntity):
    """Representation of a net4home switch."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_translation_key = "channel"


    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the switch."""
        self.api = api
        self.entry = entry
        self.device = device
        self._is_on = False
        self._attr_name = device.name
        self.send_state_changes = False
        
        _LOGGER.debug(f"[Switch] Init name={self._attr_name}, device_id={self.device.device_id}, device_type={self.device.device_type}")

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
        """Return whether the switch is on."""
        return self._is_on

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
    def _handle_update(self, is_on: bool):
        """Handle update from dispatcher."""
        _LOGGER.debug(f"[net4home] _handle_update for {self.device.device_id}: {'ON' if is_on else 'OFF'}")
        self._is_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug(f"[net4home] async_turn_on: {self.device.device_id}")
        ensure_connected(self.api)
        await self.api.async_turn_on_switch(self.device.device_id)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.debug(f"[net4home] async_turn_off: {self.device.device_id}")
        ensure_connected(self.api)
        await self.api.async_turn_off_switch(self.device.device_id)


def _hs_time_profile_switches(api, entry, device):
    """Eight profile switches of one HS-Time module."""
    return [
        Net4HomeHsTimeProfileSwitch(api, entry, device, index)
        for index in range(8)
    ]


class Net4HomeHsTimeProfileSwitch(SwitchEntity):
    """One bit of the HS-Time profile mask."""

    _attr_should_poll = False

    _attr_has_entity_name = False

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, index: int):
        """Initialize profile ``index`` (0 is profile 1)."""
        self.api = api
        self.entry = entry
        self.device = device
        self._index = index
        self._mask = getattr(device, "hs_profile_mask", None)
        self._attr_name = f"{device.name} Profil {index + 1}"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_unique_id = (
            f"{entry.entry_id}_{device.device_id.lower()}_hs_profile_{index + 1}"
        )

    @property
    def is_on(self) -> bool:
        """Return whether this profile is part of the active mask."""
        if self._mask is None:
            return False
        return (int(self._mask) & (1 << self._index)) != 0

    @property
    def available(self) -> bool:
        """Stay unavailable until the module has reported the mask."""
        return self._mask is not None and bus_connected(self.api)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the HS-Time module."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_added_to_hass(self):
        """Listen for profile-mask replies."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_hs_profile",
                self._handle_update,
            )
        )
        listen_connection(self)

    @callback
    def _handle_update(self, mask):
        """Store the full profile mask."""
        if isinstance(mask, bool) or not isinstance(mask, int):
            return
        self._mask = mask
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Add this profile to the active mask."""
        await self.api.async_set_hs_time_profile(self.device.device_id, self._index, True)

    async def async_turn_off(self, **kwargs):
        """Remove this profile from the active mask."""
        await self.api.async_set_hs_time_profile(self.device.device_id, self._index, False)
