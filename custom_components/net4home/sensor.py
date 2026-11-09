import logging
from typing import Callable
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE, LIGHT_LUX
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify
from homeassistant.core import callback

from .const import DOMAIN
from .helpers import parent_device_link
from .api import Net4HomeApi, Net4HomeDevice
from .diagnostic_sensor import Net4HomeInvertedDiagnosticSensor

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
        entities.append(Net4HomeRfReaderSensor(api, entry, device))

    # DIAGNOSTIC entities for binary sensors!
    binary_sensor_devices = [d for d in api.devices.values() if d.device_type == "binary_sensor"]
    _LOGGER.info(f"[Sensor] Found {len(binary_sensor_devices)} binary_sensor devices")
    for device in binary_sensor_devices:
        diagnostic_entities.append(Net4HomeInvertedDiagnosticSensor(entry, device))

    _LOGGER.info(f"[Sensor] Creating {len(entities)} sensor entities and {len(diagnostic_entities)} diagnostic entities")
    async_add_entities(entities + diagnostic_entities, True)  

    async def async_new_device(device: Net4HomeDevice):
        """Handle new device discovery."""
        _LOGGER.debug(f"async_new_device triggered for: {device.device_id}, model: {device.model}, type: {device.device_type}")
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
            async_add_entities([Net4HomeRfReaderSensor(api, entry, device)])
        elif device.device_type == "binary_sensor":
            # NEW: also create a diagnostic entity and button for newly detected devices!
            async_add_entities([
                Net4HomeInvertedDiagnosticSensor(entry, device),
            ])

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )

class Net4HomeSensor(SensorEntity):
    """Representation of a net4home sensor."""
    
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
        # Initial state from device if already received (e.g. before entity registered)
        if sensor_type == "targettemp" and getattr(device, "targettemp", None) is not None:
            self._state = device.targettemp
        elif sensor_type == "presetday" and getattr(device, "presetday", None) is not None:
            self._state = device.presetday
        elif sensor_type == "presetnight" and getattr(device, "presetnight", None) is not None:
            self._state = device.presetnight
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
        if self._state is None and self.sensor_type in ("presetday", "presetnight", "targettemp"):
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


class Net4HomeRfReaderSensor(SensorEntity):
    """Sensor entity for UP-RF RF-Key reader devices."""
    
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
