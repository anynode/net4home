import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

from .const import DOMAIN
from .hub import Net4HomeHub, Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    hub: Net4HomeHub = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Net4HomeSwitch(hub, entry, device)
        for device in hub.devices.values()
        if device.device_type == "switch"
    ]
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "switch":
            return
        async_add_entities([Net4HomeSwitch(hub, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

class Net4HomeSwitch(SwitchEntity):
    def __init__(self, hub: Net4HomeHub, entry, device: Net4HomeDevice):
        self.hub = hub
        self.entry = entry
        self.device = device
        self._is_on = False
        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}"
        self._attr_objadr = device.objadr
        self._attr_via_device = device.via_device_id and {device.via_device_id} or set()

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, is_on: bool):
        self._is_on = is_on
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._is_on

    @property
    def via_device(self) -> set[str]:
        return self._attr_via_device

    async def async_turn_on(self, **kwargs):
        await self.hub.async_turn_on_switch(self.device.device_id)

    async def async_turn_off(self, **kwargs):
        await self.hub.async_turn_off_switch(self.device.device_id)
