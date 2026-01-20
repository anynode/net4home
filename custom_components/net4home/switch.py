from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant import config_entries
from typing import Callable

from .diagnostic_sensor import Net4HomeSendStateChangesDiagnosticSensor, Net4HomePowerupStatusDiagnosticSensor, Net4HomeTimerTime1DiagnosticSensor
from .const import DOMAIN
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

    entities = [
        Net4HomeSwitch(api, entry, device)
        for device in switch_devices
    ]

    diagnostic_entities = [
        Net4HomeSendStateChangesDiagnosticSensor(entry, device)
        for device in switch_devices
    ]
    
    powerup_diagnostic_entities = [
        Net4HomePowerupStatusDiagnosticSensor(entry, device, api)
        for device in switch_devices
    ]
    
    # Timer time1 only for timer actuators
    timer_time1_diagnostic_entities = [
        Net4HomeTimerTime1DiagnosticSensor(entry, device, api)
        for device in switch_devices
        if device.model == "Timer"
    ]

    _LOGGER.info(f"[Switch] Creating {len(entities)} switch entities and {len(diagnostic_entities) + len(powerup_diagnostic_entities) + len(timer_time1_diagnostic_entities)} diagnostic entities")
    async_add_entities(entities + diagnostic_entities + powerup_diagnostic_entities + timer_time1_diagnostic_entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "switch":
            return
        entities_to_add = [
            Net4HomeSwitch(api, entry, device),
            Net4HomeSendStateChangesDiagnosticSensor(entry, device),
            Net4HomePowerupStatusDiagnosticSensor(entry, device, api)
        ]
        # Add timer time1 only for timer actors
        if device.model == "Timer":
            entities_to_add.append(Net4HomeTimerTime1DiagnosticSensor(entry, device, api))
        async_add_entities(entities_to_add)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeSwitch(SwitchEntity):
    """Representation of a net4home switch."""
    
    _attr_has_entity_name = False


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
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "device_id": self.device.device_id,
            "model": self.device.model,
            "via_device": self.device.via_device or "",
            "send_state_changes": self.send_state_changes,  
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

    @callback
    def _handle_update(self, is_on: bool):
        """Handle update from dispatcher."""
        _LOGGER.debug(f"[net4home] _handle_update for {self.device.device_id}: {'ON' if is_on else 'OFF'}")
        self._is_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug(f"[net4home] async_turn_on: {self.device.device_id}")
        await self.api.async_turn_on_switch(self.device.device_id)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.debug(f"[net4home] async_turn_off: {self.device.device_id}")
        await self.api.async_turn_off_switch(self.device.device_id)
