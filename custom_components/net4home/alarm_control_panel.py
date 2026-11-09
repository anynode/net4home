"""Support for net4home HS-Safety alarm control panel."""
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant import config_entries
from typing import Callable

from .alarm_layout import (
    ALARM_SET_AWAY,
    ALARM_SET_DISARM,
    ALARM_SET_HOME,
    ALARM_SET_NIGHT,
    STATE_ARMED_AWAY,
    STATE_ARMED_HOME,
    STATE_ARMED_NIGHT,
    STATE_ARMING,
    STATE_DISARMED,
)
from .const import DOMAIN
from .helpers import bus_connected, listen_connection, parent_device_link
from .api import Net4HomeApi, Net4HomeDevice

import logging

_LOGGER = logging.getLogger(__name__)

_HA_STATES = {
    STATE_DISARMED: AlarmControlPanelState.DISARMED,
    STATE_ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    STATE_ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    STATE_ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    STATE_ARMING: AlarmControlPanelState.ARMING,
}


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

    _attr_should_poll = False

    @property
    def available(self) -> bool:
        return bus_connected(self.api)

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    # The module has no PIN. The arm commands go out with the contact check
    # (11/12/13); the module itself refuses while a contact is open.
    _attr_code_arm_required = False

    def __init__(self, api: Net4HomeApi, entry: config_entries.ConfigEntry, device: Net4HomeDevice):
        """Initialize the alarm control panel."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}"
        stored = getattr(device, "alarm_state", None)
        self._attr_alarm_state = _HA_STATES.get(stored)

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

    async def async_added_to_hass(self) -> None:
        """Register update listener when entity is added."""
        listen_connection(self)
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, data=None):
        """Apply a status reply from the alarm module."""
        if not isinstance(data, dict):
            return
        state = _HA_STATES.get(data.get("alarm_state"))
        if state is None:
            return
        self._attr_alarm_state = state
        self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.debug(f"Disarming alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_SET_DISARM)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm Intern 1 after the module checks that every contact is closed."""
        _LOGGER.debug(f"Arming home alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_SET_HOME)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm Extern after the module checks that every contact is closed."""
        _LOGGER.debug(f"Arming away alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_SET_AWAY)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Arm Intern 2 after the module checks that every contact is closed."""
        _LOGGER.debug(f"Arming night alarm {self.device.device_id}")
        await self.api.async_set_alarm_state(self.device.device_id, ALARM_SET_NIGHT)
