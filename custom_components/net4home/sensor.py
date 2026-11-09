import logging
from typing import Callable
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE, LIGHT_LUX, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.core import callback

from .alarm_extras import alarm_level_sensors
from .hs_time import command_text, schedule_row_active
from .bell import bell_sensors
from .bell_layout import is_wav_bell
from .const import DOMAIN
from .si_extras import si_power_sensors
from .si_layout import SI_MODEL_CHANNELS
from .rf_keys import RF_KEY_COUNT
from .rf_access import RfKeyDirectorySensor, store_key
from .helpers import parent_device_link
from .api import Net4HomeApi, Net4HomeDevice
from .diagnostic_sensor import (
    Net4HomeCoverRunTimeDiagnosticSensor,
    Net4HomeInvertedDiagnosticSensor,
    Net4HomeMinHellDiagnosticSensor,
    Net4HomePowerupStatusDiagnosticSensor,
    Net4HomeSendStateChangesDiagnosticSensor,
    Net4HomeTimerTime1DiagnosticSensor,
)

_LOGGER = logging.getLogger(__name__)

CLIMATE_SENSOR_TYPES = [
    ("targettemp", UnitOfTemperature.CELSIUS),
    ("presetday", UnitOfTemperature.CELSIUS),
    ("presetnight", UnitOfTemperature.CELSIUS),
]

HS_TIME_SENSOR_TYPES = [
    ("broadcast interval", None),  # Text string (e.g. "1 Minute", "5 Minuten")
    ("sunrise", None),  # Time string (HH:MM)
    ("sunset", None),  # Time string (HH:MM)
]

def _actor_diagnostic_entities(entry, api, device):
    """Diagnostic sensors that belong to the sensor platform, not the actor platform."""
    if device.device_type == "light":
        entities = [
            Net4HomeSendStateChangesDiagnosticSensor(entry, device),
            Net4HomePowerupStatusDiagnosticSensor(entry, device, api),
            Net4HomeMinHellDiagnosticSensor(entry, device, api),
        ]
        if device.model == "Timer":
            entities.append(Net4HomeTimerTime1DiagnosticSensor(entry, device, api))
        return entities
    if device.device_type == "switch":
        entities = [
            Net4HomeSendStateChangesDiagnosticSensor(entry, device),
            Net4HomePowerupStatusDiagnosticSensor(entry, device, api),
        ]
        if device.model == "Timer":
            entities.append(Net4HomeTimerTime1DiagnosticSensor(entry, device, api))
        return entities
    if device.device_type == "cover":
        return [
            Net4HomeSendStateChangesDiagnosticSensor(entry, device),
            Net4HomeCoverRunTimeDiagnosticSensor(entry, device, api),
        ]
    return []


SENSOR_MODEL_TO_TYPE_UNIT = {
    "humidity": ("humidity", PERCENTAGE),
    "temperature": ("temperature", UnitOfTemperature.CELSIUS),
    "illuminance": ("illuminance", LIGHT_LUX),
    "sunrise": ("sunrise", None),  # Time string (HH:MM)
    "sunset": ("sunset", None),  # Time string (HH:MM)
    "broadcast interval": ("broadcast interval", None),  # Text string (e.g. "1 Minute", "5 Minuten")
}

async def async_setup_entry(hass, entry, async_add_entities: Callable):
    """Set up net4home sensor entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    entities = []
    diagnostic_entities = []
    _LOGGER.info(f"[Sensor] Setup called with {len(api.devices)} devices in API")
    _LOGGER.debug(f"Listening for new devices with key: net4home_new_device_{entry.entry_id}")

    # Climate device sensors
    climate_devices = [d for d in api.devices.values() if d.device_type == "climate"]
    _LOGGER.info(f"[Sensor] Found {len(climate_devices)} climate devices")
    for device in climate_devices:
        for sensor_key, unit in CLIMATE_SENSOR_TYPES:
            entities.append(Net4HomeSensor(api, entry, device, sensor_key, unit))
    
    # HS-Time device sensors (direkt am MI-Device, wie bei UP-TLH)
    hs_time_devices = [d for d in api.devices.values() if d.device_type == "sensor" and d.model == "HS-Time"]
    _LOGGER.info(f"[Sensor] Found {len(hs_time_devices)} HS-Time devices")
    for device in hs_time_devices:
        for sensor_key, unit in HS_TIME_SENSOR_TYPES:
            entities.append(Net4HomeSensor(api, entry, device, sensor_key, unit))
        entities.append(Net4HomeHsTimeClockSensor(api, entry, device))
        entities.append(Net4HomeHsTimeMinutesSensor(api, entry, device))
        entities.append(Net4HomeHsTimeScheduleSensor(api, entry, device))

    # Sensor devices (exclude HS-Time, already handled above)
    sensor_devices = [d for d in api.devices.values() if d.device_type == "sensor" and d.model != "HS-Time"]
    _LOGGER.info(f"[Sensor] Found {len(sensor_devices)} sensor devices: {[d.device_id for d in sensor_devices]}")
    for device in sensor_devices:
        sensor_info = SENSOR_MODEL_TO_TYPE_UNIT.get((device.model or "").lower())
        if sensor_info is None and (device.model or "").lower() == "sensor" and device.via_device:
            # UP-TLH/UP-T OBJ sensors may be stored with model "Sensor"; derive type from name
            name = (device.name or "").lower()
            if "temperature" in name:
                sensor_info = ("temperature", UnitOfTemperature.CELSIUS)
            elif "illuminance" in name:
                sensor_info = ("illuminance", LIGHT_LUX)
            elif "humidity" in name:
                sensor_info = ("humidity", PERCENTAGE)
        if sensor_info is None:
            _LOGGER.warning(f"Unknown sensor model {device.model} for device {device.device_id}")
            continue
        sensor_key, unit = sensor_info
        entities.append(Net4HomeSensor(api, entry, device, sensor_key, unit))
        _LOGGER.info(f"Append sensor model {device.model} for device {device.device_id} {sensor_info}")

    # RF-Reader devices (only MI devices, not OBJ child devices)
    # IMPORTANT: Devices with via_device are OBJ devices, even if device_id starts with "MI"
    rf_reader_devices = [d for d in api.devices.values() if d.device_type == "rf_reader" and d.device_id.startswith("MI") and not d.via_device]
    _LOGGER.info(f"[Sensor] Found {len(rf_reader_devices)} RF-Reader devices: {[d.device_id for d in rf_reader_devices]}")
    for device in rf_reader_devices:
        entities.extend(_rf_reader_sensors(api, entry, device))

    # DIAGNOSTIC entities for binary sensors!
    binary_sensor_devices = [d for d in api.devices.values() if d.device_type == "binary_sensor"]
    _LOGGER.info(f"[Sensor] Found {len(binary_sensor_devices)} binary_sensor devices")
    for device in binary_sensor_devices:
        diagnostic_entities.append(Net4HomeInvertedDiagnosticSensor(entry, device))

    for device in api.devices.values():
        diagnostic_entities.extend(_actor_diagnostic_entities(entry, api, device))

    bell_seen: set[str] = set()

    def _take_bell(device: Net4HomeDevice) -> list:
        if not is_wav_bell(device) or device.device_id in bell_seen:
            return []
        bell_seen.add(device.device_id)
        return bell_sensors(api, entry, device)

    alarm_seen: set[str] = set()

    def _take_alarm(device: Net4HomeDevice) -> list:
        if (
            device.model != "HS-Safety"
            or device.device_type != "alarm_control_panel"
            or device.device_id in alarm_seen
        ):
            return []
        alarm_seen.add(device.device_id)
        return alarm_level_sensors(api, entry, device)

    si_seen: set[str] = set()

    def _take_si(device: Net4HomeDevice) -> list:
        if (
            device.model not in SI_MODEL_CHANNELS
            or not device.device_id.startswith("MI")
            or device.device_id in si_seen
        ):
            return []
        si_seen.add(device.device_id)
        return si_power_sensors(api, entry, device)

    for device in api.devices.values():
        entities.extend(_take_bell(device))
        entities.extend(_take_alarm(device))
        entities.extend(_take_si(device))

    _LOGGER.info(f"[Sensor] Creating {len(entities)} sensor entities and {len(diagnostic_entities)} diagnostic entities")
    rf_store = hass.data[DOMAIN].get(store_key(entry.entry_id))
    if rf_store is not None:
        entities.append(RfKeyDirectorySensor(entry.entry_id, rf_store))

    async_add_entities(entities + diagnostic_entities, True)  

    async def async_new_device(device: Net4HomeDevice):
        """Handle new device discovery."""
        _LOGGER.debug(f"async_new_device triggered for: {device.device_id}, model: {device.model}, type: {device.device_type}")
        fresh = _take_bell(device) + _take_alarm(device) + _take_si(device)
        if fresh:
            async_add_entities(fresh)
        if device.device_type == "climate":
            sensors = [
                Net4HomeSensor(api, entry, device, key, unit)
                for key, unit in CLIMATE_SENSOR_TYPES
            ]
            async_add_entities(sensors)
        elif device.device_type == "sensor" and device.model == "HS-Time":
            # HS-Time devices: Create all sensors directly on the MI device (like UP-TLH)
            sensors = [
                Net4HomeSensor(api, entry, device, key, unit)
                for key, unit in HS_TIME_SENSOR_TYPES
            ]
            sensors.append(Net4HomeHsTimeClockSensor(api, entry, device))
            sensors.append(Net4HomeHsTimeMinutesSensor(api, entry, device))
            sensors.append(Net4HomeHsTimeScheduleSensor(api, entry, device))
            _LOGGER.debug(f"Creating {len(sensors)} HS-Time sensors for {device.device_id}")
            async_add_entities(sensors)
        elif device.device_type == "sensor":
            model_key = device.model.lower() if device.model else ""
            sensor_info = SENSOR_MODEL_TO_TYPE_UNIT.get(model_key)
            if sensor_info is None and model_key == "sensor" and device.via_device:
                name = (device.name or "").lower()
                if "temperature" in name:
                    sensor_info = ("temperature", UnitOfTemperature.CELSIUS)
                elif "illuminance" in name:
                    sensor_info = ("illuminance", LIGHT_LUX)
                elif "humidity" in name:
                    sensor_info = ("humidity", PERCENTAGE)
            if sensor_info is None:
                _LOGGER.warning(f"Unknown sensor model {device.model} for device {device.device_id}")
                return
            sensor_key, unit = sensor_info
            _LOGGER.debug(f"Creating sensor: {sensor_key} for {device.device_id}")
            async_add_entities([Net4HomeSensor(api, entry, device, sensor_key, unit)])
        elif device.device_type == "rf_reader" and device.device_id.startswith("MI") and not device.via_device:
            # Only create sensor entities for MI devices, not OBJ child devices
            # IMPORTANT: Devices with via_device are OBJ devices, even if device_id starts with "MI"
            _LOGGER.debug(f"Creating RF-Reader sensor for {device.device_id}")
            async_add_entities(_rf_reader_sensors(api, entry, device))
        elif device.device_type == "binary_sensor":
            # NEW: also create a diagnostic entity and button for newly detected devices!
            async_add_entities([
                Net4HomeInvertedDiagnosticSensor(entry, device),
            ])
        diagnostics = _actor_diagnostic_entities(entry, api, device)
        if diagnostics:
            async_add_entities(diagnostics)

    async def async_device_updated(device_id: str = None):
        if not device_id:
            return
        device = api.devices.get(device_id)
        if not device:
            return
        fresh = _take_bell(device) + _take_alarm(device) + _take_si(device)
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated
        )
    )

class Net4HomeSensor(SensorEntity):
    """Representation of a net4home sensor."""

    _attr_should_poll = False
    
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, sensor_type: str, unit: str):
        """Initialize the sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        self.sensor_type = sensor_type
        self._unit = unit
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_{sensor_type}"
        self._attr_native_unit_of_measurement = unit
        # Set device_class for unit conversion, UI, and voice/cloud
        if sensor_type in ("temperature", "targettemp", "presetday", "presetnight"):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif sensor_type == "humidity":
            self._attr_device_class = SensorDeviceClass.HUMIDITY
        elif sensor_type == "illuminance":
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        else:
            self._attr_device_class = None
        if sensor_type in ("temperature", "humidity", "illuminance"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        # Initial state from device if already received (e.g. before entity registered)
        if sensor_type == "targettemp" and getattr(device, "targettemp", None) is not None:
            self._state = device.targettemp
        elif sensor_type == "presetday" and getattr(device, "presetday", None) is not None:
            self._state = device.presetday
        elif sensor_type == "presetnight" and getattr(device, "presetnight", None) is not None:
            self._state = device.presetnight
        elif sensor_type in ("temperature", "humidity", "illuminance") and getattr(device, sensor_type, None) is not None:
            self._state = getattr(device, sensor_type)
        elif sensor_type in ("broadcast interval", "sunrise", "sunset"):
            self._state = getattr(device, f"hs_{sensor_type.replace(' ', '_')}", None)
        else:
            self._state = None
        # Avoid duplicating type in name when device name already describes it (e.g. "Humidity Sensor 25406")
        if (device.model or "").lower() == sensor_type:
            self._attr_name = device.name
        else:
            self._attr_name = f"{device.name} {sensor_type}"
        # Mark available when we have a value (climate sensors show "Unbekannt" when unavailable or state None)
        self._attr_available = self._state is not None or (
            self.sensor_type in ("presetday", "presetnight", "targettemp")
            and getattr(device, self.sensor_type, None) is not None
        )

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        if self._state is not None:
            return self._state
        # Fallback: use value stored on device (e.g. from 0xF0 / D0_ACTOR_ACK before entity was listening)
        if self.sensor_type == "targettemp":
            return getattr(self.device, "targettemp", None)
        if self.sensor_type == "presetday":
            return getattr(self.device, "presetday", None)
        if self.sensor_type == "presetnight":
            return getattr(self.device, "presetnight", None)
        if self.sensor_type in ("temperature", "humidity", "illuminance"):
            return getattr(self.device, self.sensor_type, None)
        if self.sensor_type in ("broadcast interval", "sunrise", "sunset"):
            return getattr(self.device, f"hs_{self.sensor_type.replace(' ', '_')}", None)
        return None

    @property
    def available(self) -> bool:
        """Entity is available when we have a value to show (avoids 'Unbekannt' in UI)."""
        if self.native_value is not None:
            return True
        return getattr(self, "_attr_available", True)

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

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "sensor")
        translated_name = translations.get(self.sensor_type, self.sensor_type)
        # Avoid duplicating type in name when device name already describes it (e.g. "Humidity Sensor 25406")
        if (self.device.model or "").lower() == self.sensor_type:
            self._attr_name = self.device.name
        else:
            self._attr_name = f"{self.device.name} {translated_name}"

        # Sync from device if we have no state yet (e.g. 0xF0 arrived before this entity registered)
        if self._state is None and self.sensor_type in (
            "presetday",
            "presetnight",
            "targettemp",
            "temperature",
            "humidity",
            "illuminance",
        ):
            val = getattr(self.device, self.sensor_type, None)
            if val is not None:
                self._state = val
                self._attr_available = True
        self.async_write_ha_state()

        # Normalize dispatcher key to uppercase so it matches API (device_id from packet is always uppercase)
        dispatcher_key = f"net4home_update_{self.device.device_id.upper()}_{slugify(self.sensor_type)}"
        _LOGGER.debug(f"{self.entity_id} listening for dispatcher key: {dispatcher_key}")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dispatcher_key,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, value):
        """Handle update from dispatcher."""
        self._state = value
        self._attr_available = True
        self.async_write_ha_state()
        if self.sensor_type in ("presetday", "presetnight", "targettemp"):
            _LOGGER.debug(f"{self.entity_id} received {self.sensor_type}={value}")

        if self.sensor_type == "temperature":
            signal_key = f"net4home_temperature_update_{self.device.via_device}"
            async_dispatcher_send(self.hass, signal_key, value)

        # Forward to climate only when sensor is OBJ child (via_device set). For MI devices
        # (e.g. UP-T) the API already dispatches to device_id; climate uses device.* as fallback.
        if self.sensor_type in {"targettemp", "presetday", "presetnight"} and self.device.via_device:
            target_id = self.device.via_device.upper()
            signal_key = f"net4home_update_{target_id}"
            async_dispatcher_send(self.hass, signal_key, {self.sensor_type: value})


class Net4HomeHsTimeClockSensor(SensorEntity):
    """Local time reported by an HS-Time module."""

    _attr_should_poll = False

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = False

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the clock."""
        self.api = api
        self.entry = entry
        self.device = device
        self._clock = getattr(device, "hs_clock", None)
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_hs_clock"
        self._attr_name = f"{device.name} Uhrzeit"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self):
        """Return the module time in the Home Assistant timezone."""
        clock_time = (self._clock or {}).get("time")
        if not clock_time or self.hass is None:
            return None
        timezone = dt_util.get_time_zone(self.hass.config.time_zone)
        try:
            return datetime(
                clock_time["year"],
                clock_time["month"],
                clock_time["day"],
                clock_time["hour"],
                clock_time["minute"],
                clock_time["second"],
                tzinfo=timezone,
            )
        except (KeyError, TypeError, ValueError):
            return None

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
        """Listen for clock replies."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_hs_clock",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, clock: dict):
        """Store a clock reply."""
        if isinstance(clock, dict):
            self._clock = clock
            self.async_write_ha_state()


class Net4HomeHsTimeMinutesSensor(SensorEntity):
    """Minutes since the last DCF reception."""

    _attr_should_poll = False

    _attr_has_entity_name = False
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-outline"

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the reception-gap sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        clock = getattr(device, "hs_clock", None) or {}
        self._minutes = clock.get("minutes_without_reception")
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_hs_no_reception"
        self._attr_name = f"{device.name} Minuten ohne Empfang"

    @property
    def native_value(self):
        """Return the minute counter from the module."""
        return self._minutes

    @property
    def available(self) -> bool:
        """Stay unavailable until the first clock reply."""
        return self._minutes is not None

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
        """Listen for clock replies."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_hs_clock",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, clock: dict):
        """Store the minute counter."""
        if isinstance(clock, dict) and "minutes_without_reception" in clock:
            self._minutes = clock["minutes_without_reception"]
            self.async_write_ha_state()


_TARGET_KIND = {
    "light": "light",
    "switch": "switch",
    "cover": "cover",
    "alarm_control_panel": "alarm",
}


class Net4HomeHsTimeScheduleSensor(SensorEntity):
    """Switching table of an HS-Time module, one row per used line."""

    _attr_should_poll = False

    _attr_icon = "mdi:table-clock"
    _attr_has_entity_name = False

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the schedule sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        self._rows: list = []
        self._value = None
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_hs_schedule"
        self._attr_name = f"{device.name} Schaltuhr"
        self._refresh()

    @property
    def native_value(self):
        """How many rows the table has, and how many match the current profile."""
        return self._value

    @property
    def extra_state_attributes(self):
        """Rows for a table card, plus the same table as markdown."""
        return {"rows": self._rows, "markdown": self._markdown()}

    def _markdown(self) -> str:
        header = "| Nr | Wann | Zeit | Tage | Ziel | Befehl | Profile | Aktiv |"
        lines = [header, "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for row in self._rows:
            shown = "ja" if row["active"] else ""
            lines.append(
                f"| {row['nr']} | {row['mode']} | {row['when']} | {row['weekdays']} "
                f"| {row['target']} | {row['command']} | {row['profiles']} | {shown} |"
            )
        return "\n".join(lines)

    def _targets(self) -> dict:
        found = {}
        for item in self.api.devices.values():
            address = item.objadr
            if not address:
                continue
            kind = _TARGET_KIND.get(item.device_type)
            current = found.get(address)
            if current is None or (kind and not current[1]):
                found[address] = (item.name, kind)
        return found

    def _refresh(self) -> None:
        stored = getattr(self.device, "hs_schedule", None)
        if stored is None:
            self._rows = []
            self._value = None
            return
        targets = self._targets()
        mask = getattr(self.device, "hs_profile_mask", None)
        weekday = None
        holiday = False
        if self.hass is not None:
            weekday = dt_util.now().weekday()
        clock = getattr(self.device, "hs_clock", None) or {}
        holiday = bool(clock.get("holiday"))
        rows = []
        active_count = 0
        for row in stored:
            name, kind = targets.get(row["address"], (None, None))
            active = schedule_row_active(row, mask, weekday, holiday)
            if active:
                active_count += 1
            when = row["time"]
            if row["date"]:
                when = f"{row['date']} {when}".strip()
            rows.append(
                {
                    "nr": row["nr"],
                    "mode": row["mode"],
                    "when": when,
                    "weekdays": row["weekdays"],
                    "target": name or str(row["address"]),
                    "address": row["address"],
                    "command": command_text(row["command"], kind),
                    "profiles": row["profiles"],
                    "active": active,
                }
            )
        self._rows = rows
        if not rows:
            self._value = "Keine Schaltpunkte"
        elif mask is None:
            self._value = f"{len(rows)} Schaltpunkte"
        else:
            self._value = f"{len(rows)} Schaltpunkte, {active_count} aktiv"

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
        """Listen for the table, the profile mask and the clock."""
        mi = self.device.device_id.upper()
        for suffix in ("hs_schedule", "hs_profile", "hs_clock"):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"net4home_update_{mi}_{suffix}",
                    self._handle_update,
                )
            )
        self._refresh()
        self.async_write_ha_state()

    @callback
    def _handle_update(self, _data=None):
        """Rebuild the table from the device."""
        self._refresh()
        self.async_write_ha_state()


class Net4HomeRfReaderSensor(SensorEntity):
    """Sensor entity for UP-RF RF-Key reader devices."""

    _attr_should_poll = False
    
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the RF reader sensor."""
        self.api = api
        self.entry = entry
        self.device = device
        self._rf_key = None
        self._state = None
        self._last_read = None
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_rf_key"
        self._attr_name = f"{device.name} RF-Key"
        self._attr_native_unit_of_measurement = None

    @property
    def native_value(self):
        """Return the RF-Key code as the sensor value."""
        return self._rf_key

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {}
        if self._state:
            attrs["state"] = self._state
        if self._last_read:
            attrs["last_read"] = self._last_read
        return attrs

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

    async def async_added_to_hass(self):
        """Set up dispatcher connection when entity is added to Home Assistant."""
        translations = await async_get_translations(self.hass, DOMAIN, "sensor")
        translated_name = translations.get("rf_key", "RF-Key")
        self._attr_name = f"{self.device.name} {translated_name}"

        self.async_write_ha_state()

        dispatcher_key = f"net4home_update_{self.device.device_id.upper()}_rf_key"
        _LOGGER.debug(f"{self.entity_id} listening for dispatcher key: {dispatcher_key}")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dispatcher_key,
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, data: dict):
        """Handle RF-Key update from dispatcher."""
        self._rf_key = data.get("rf_key")
        self._state = data.get("state")
        self._last_read = datetime.now().isoformat()
        self.async_write_ha_state()
        _LOGGER.debug(f"RF-Key update for {self.device.device_id}: {self._rf_key} ({self._state})")


def _rf_reader_sensors(api, entry, device):
    """Last presented key plus the ten stored slots of one UP-RF module."""
    return [Net4HomeRfReaderSensor(api, entry, device)] + [
        Net4HomeRfKeySlotSensor(api, entry, device, index)
        for index in range(RF_KEY_COUNT)
    ]


class Net4HomeRfKeySlotSensor(SensorEntity):
    """One of the ten keys stored in an UP-RF module."""

    _attr_should_poll = False

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, index: int):
        """Initialize the key slot."""
        self.api = api
        self.entry = entry
        self.device = device
        self._index = index
        self._code = None
        self._master = False
        self._attr_unique_id = (
            f"{entry.entry_id}_{slugify(device.device_id)}_rf_key_slot_{index}"
        )
        self._attr_icon = "mdi:key"
        stored = getattr(device, "rf_keys", None)
        slot = stored[index] if isinstance(stored, list) and len(stored) > index else None
        self._apply_slot(slot)

    def _apply_slot(self, slot) -> None:
        """Store the code and mark the master slot in the entity name."""
        code = ""
        master = False
        if isinstance(slot, dict):
            code = slot.get("code") or ""
            master = bool(slot.get("master")) and bool(code)
        self._code = code or None
        self._master = master
        label = f"Schlüssel {self._index + 1}"
        if master:
            label = f"{label} Master"
        self._attr_name = f"{self.device.name} {label}"
        self._attr_icon = "mdi:key-star" if master else "mdi:key"

    @property
    def native_value(self):
        """Return the stored key code."""
        return self._code

    @property
    def available(self) -> bool:
        """An empty slot stays on the device without a value."""
        return self._code is not None

    @property
    def extra_state_attributes(self):
        """Expose the slot number and whether this key is the master."""
        return {"slot": self._index + 1, "master": self._master}

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

    async def async_added_to_hass(self):
        """Listen for updates of this slot."""
        self.async_write_ha_state()
        dispatcher_key = (
            f"net4home_update_{self.device.device_id.upper()}_rf_slot_{self._index}"
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, dispatcher_key, self._handle_update)
        )

    @callback
    def _handle_update(self, data: dict):
        """Apply a slot update from the key list."""
        self._apply_slot(data)
        self.async_write_ha_state()
