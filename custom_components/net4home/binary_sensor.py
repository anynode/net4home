import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant import config_entries

from .alarm_extras import alarm_binary_sensors, async_listen_alarm_contacts
from .alarm_layout import sabotage_reported
from .const import DOMAIN
from .helpers import bus_connected, listen_connection, parent_device_link
from .api import Net4HomeApi, Net4HomeDevice
# NO import from .config_sensor here!

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: Callable[[list[BinarySensorEntity], bool], None]
) -> None:
    """Set up net4home binary sensor entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.info(f"[BinarySensor] Starting setup_entry with {len(api.devices)} known devices")
    binary_sensor_devices = [d for d in api.devices.values() if d.device_type == "binary_sensor"]
    alarm_devices = [d for d in api.devices.values() if d.device_type == "alarm_control_panel"]
    _LOGGER.info("[BinarySensor] Found %s binary_sensor devices", len(binary_sensor_devices))

    # ONLY BinarySensor entities (no ConfigSensor entities)
    entities = [
        Net4HomeBinarySensor(api, entry, device)
        for device in binary_sensor_devices
    ]
    entities.extend(
        Net4HomeAlarmSabotageSensor(api, entry, device)
        for device in alarm_devices
    )
    for device in alarm_devices:
        entities.extend(alarm_binary_sensors(api, entry, device))
        async_listen_alarm_contacts(hass, entry, api, device, async_add_entities)
    hs_time_devices = [
        device
        for device in api.devices.values()
        if device.device_type == "sensor" and device.model == "HS-Time"
    ]
    for device in hs_time_devices:
        entities.extend(_hs_time_flag_sensors(api, entry, device))
    _LOGGER.info(f"[BinarySensor] Creating {len(entities)} binary_sensor entities")
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        """Handle new device discovery."""
        if device.device_type == "binary_sensor":
            _LOGGER.debug(f"[BinarySensor] Adding new device {device.device_id}")
            async_add_entities([
                Net4HomeBinarySensor(api, entry, device)
            ])
            return
        if device.device_type == "alarm_control_panel":
            async_add_entities([
                Net4HomeAlarmSabotageSensor(api, entry, device),
                *alarm_binary_sensors(api, entry, device),
            ])
            async_listen_alarm_contacts(hass, entry, api, device, async_add_entities)
            return
        if device.device_type == "sensor" and device.model == "HS-Time":
            async_add_entities(_hs_time_flag_sensors(api, entry, device))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeBinarySensor(BinarySensorEntity):
    """Representation of a net4home binary sensor."""

    _attr_should_poll = False

    @property
    def available(self) -> bool:
        return bus_connected(self.api)
    
    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the binary sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        self._is_on = False
        self._attr_name = device.name
        via = (device.via_device or "unknown").lower()
        self._attr_unique_id = f"{entry.entry_id}_{slugify(via)}_{slugify(device.device_id)}"
        _LOGGER.debug(f"[BinarySensor] Init {self._attr_name} ({self._attr_unique_id})")

    @property
    def inverted(self) -> bool:
        """Return whether the sensor is inverted."""
        devices_opts = self.entry.options.get("devices", {})
        dev_opts = devices_opts.get(self.device.device_id, {})
        return dev_opts.get("inverted", False)

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        state = self._is_on
        if self.inverted:
            state = not state
        return state

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {"inverted": self.inverted}

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

    @callback
    def _handle_update(self, state: bool):
        """Handle update from dispatcher."""
        self._is_on = not state
        self.async_write_ha_state()
        _LOGGER.debug(f"[BinarySensor] Update {self.device.device_id} → {'ON' if self.is_on else 'OFF'} (inverted={self.inverted})")

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        listen_connection(self)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )


class Net4HomeAlarmSabotageSensor(BinarySensorEntity):
    """Tamper check of an HS-Safety panel. This is not an alarm.

    The module keeps the sabotage bit set while disarmed, so the tamper
    state is only reported while the panel is armed. The raw bit stays
    available as an attribute.
    """

    _attr_should_poll = False

    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.TAMPER

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the sabotage sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        self._raw = getattr(device, "alarm_sabotage", None)
        self._state = getattr(device, "alarm_state", None)
        self._attr_name = "Sabotage"
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_sabotage"

    @property
    def is_on(self) -> bool | None:
        """Return True when a contact reports tamper while the panel is armed."""
        if self._raw is None:
            return None
        return sabotage_reported(self._raw, self._state)

    @property
    def extra_state_attributes(self):
        """Raw sabotage bit and arming level from the last status reply."""
        return {"sabotage_raw": self._raw, "alarm_state": self._state}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the alarm device this check belongs to."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @callback
    def _handle_update(self, data=None):
        """Apply the sabotage bit and arming level from an alarm status reply."""
        if not isinstance(data, dict):
            return
        if "sabotage" in data:
            self._raw = bool(data["sabotage"])
        if "alarm_state" in data:
            self._state = data["alarm_state"]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )


_HS_TIME_FLAGS = (
    ("synced", "Synchron", "mdi:clock-check"),
    ("reception", "Empfang", "mdi:radio-tower"),
    ("daylight_saving", "Sommerzeit", "mdi:weather-sunny"),
    ("holiday", "Feiertag", "mdi:calendar-star"),
)


def _hs_time_flag_sensors(api, entry, device):
    """DCF status bits that belong on the HS-Time module."""
    return [
        Net4HomeHsTimeFlagSensor(api, entry, device, key, name, icon)
        for key, name, icon in _HS_TIME_FLAGS
    ]


class Net4HomeHsTimeFlagSensor(BinarySensorEntity):
    """One status bit from the HS-Time clock reply."""

    _attr_should_poll = False

    _attr_has_entity_name = False

    def __init__(self, api, entry, device, key: str, name: str, icon: str):
        """Initialize the flag."""
        self.api = api
        self.entry = entry
        self.device = device
        self._key = key
        clock = getattr(device, "hs_clock", None) or {}
        self._is_on = clock.get(key)
        self._attr_name = f"{device.name} {name}"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id.lower()}_hs_{key}"

    @property
    def is_on(self) -> bool | None:
        """Return the flag. None until the first clock reply."""
        return self._is_on

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

    @callback
    def _handle_update(self, clock):
        """Apply one flag from a clock reply."""
        if not isinstance(clock, dict) or self._key not in clock:
            return
        self._is_on = bool(clock[self._key])
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Listen for clock replies."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_hs_clock",
                self._handle_update,
            )
        )
