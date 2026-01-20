"""Support for net4home HS-Safety alarm control panel."""
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant import config_entries
from typing import Callable

from .const import DOMAIN
from .api import Net4HomeApi, Net4HomeDevice

import logging

_LOGGER = logging.getLogger(__name__)

# Alarm states mapping
# According to docs: 
# 0 = Unscharf (DISARMED)
# 1 = Extern Scharf (ARMED_AWAY)
# 2 = Intern 2 Scharf (ARMED_NIGHT)
# 3 = Intern 1 Scharf (ARMED_HOME)
ALARM_MODE_UNSCHARF = 0  # Unscharf
ALARM_MODE_EXTERN = 1  # Extern Scharf
ALARM_MODE_INTERN2 = 2  # Intern 2 Scharf
ALARM_MODE_INTERN1 = 3  # Intern 1 Scharf


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[AlarmControlPanelEntity], bool], None]
) -> None:
    """Set up net4home alarm control panel entities."""
    try:
        api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
        
        _LOGGER.info(f"[Alarm] Setup called with {len(api.devices)} devices in API")
        _LOGGER.debug(f"[Alarm] All devices: {[(d.device_id, d.device_type, d.model) for d in api.devices.values()]}")
        alarm_devices = [d for d in api.devices.values() if d.device_type == "alarm_control_panel"]
        _LOGGER.info(f"[Alarm] Found {len(alarm_devices)} alarm devices: {[(d.device_id, d.model, d.objadr) for d in alarm_devices]}")
    except Exception as e:
        _LOGGER.error(f"[Alarm] Error during setup: {e}", exc_info=True)
        return
    
    try:
        entities = [
            Net4HomeAlarmControlPanel(api, entry, device)
            for device in alarm_devices
        ]

        _LOGGER.info(f"[Alarm] Creating {len(entities)} alarm control panel entities")
        async_add_entities(entities, True)

        async def async_new_device(device: Net4HomeDevice):
            """Handle new device discovery."""
            try:
                if device.device_type == "alarm_control_panel":
                    _LOGGER.info(f"[Alarm] New alarm device detected: {device.device_id}")
                    entity = Net4HomeAlarmControlPanel(api, entry, device)
                    async_add_entities([entity], True)
            except Exception as e:
                _LOGGER.error(f"[Alarm] Error creating entity for new device {device.device_id}: {e}", exc_info=True)

        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    except Exception as e:
        _LOGGER.error(f"[Alarm] Error creating entities: {e}", exc_info=True)


class Net4HomeAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of a net4home HS-Safety alarm control panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, api: Net4HomeApi, entry: config_entries.ConfigEntry, device: Net4HomeDevice):
        """Initialize the alarm control panel."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}"
        self._attr_alarm_state = AlarmControlPanelState.DISARMED
        self._current_mode = None  # Stores the current alarm mode (0-3)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, data=None):
        """Handle update signal from dispatcher."""
        # TODO: Update state based on received data
        # For now, we just write the state
        self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.debug(f"Disarming alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_MODE_UNSCHARF)
        self._current_mode = ALARM_MODE_UNSCHARF
        self._attr_alarm_state = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command (Intern 1 Scharf)."""
        _LOGGER.debug(f"Arming home alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_MODE_INTERN1)
        self._current_mode = ALARM_MODE_INTERN1
        self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command (Extern Scharf)."""
        _LOGGER.debug(f"Arming away alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_MODE_EXTERN)
        self._current_mode = ALARM_MODE_EXTERN
        self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command (Intern 2 Scharf)."""
        _LOGGER.debug(f"Arming night alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_MODE_INTERN2)
        self._current_mode = ALARM_MODE_INTERN2
        self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        self.async_write_ha_state()
