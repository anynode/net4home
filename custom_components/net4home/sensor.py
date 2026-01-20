import logging
from typing import Callable
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature, PERCENTAGE, LIGHT_LUX
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify
from homeassistant.core import callback

from .const import DOMAIN
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

    # Sensor devices
    sensor_devices = [d for d in api.devices.values() if d.device_type == "sensor"]
    _LOGGER.info(f"[Sensor] Found {len(sensor_devices)} sensor devices: {[d.device_id for d in sensor_devices]}")
    for device in sensor_devices:
        sensor_info = SENSOR_MODEL_TO_TYPE_UNIT.get(device.model.lower())
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
        self._state = None
        self._attr_name = f"{device.name} {sensor_type}"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._state

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

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "sensor")
        translated_name = translations.get(self.sensor_type, self.sensor_type)
        self._attr_name = f"{self.device.name} {translated_name}"

        self.async_write_ha_state()

        # Normalize sensor_type for dispatcher key (spaces become underscores)
        dispatcher_key = f"net4home_update_{self.device.device_id}_{slugify(self.sensor_type)}"
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
        self.async_write_ha_state()

        if self.sensor_type == "temperature":
            signal_key = f"net4home_temperature_update_{self.device.via_device}"
            async_dispatcher_send(self.hass, signal_key, value)

        if self.sensor_type in {"targettemp", "presetday", "presetnight"}:
            signal_key = f"net4home_update_{self.device.via_device}"
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
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    async def async_added_to_hass(self):
        """Set up dispatcher connection when entity is added to Home Assistant."""
        translations = await async_get_translations(self.hass, DOMAIN, "sensor")
        translated_name = translations.get("rf_key", "RF-Key")
        self._attr_name = f"{self.device.name} {translated_name}"

        self.async_write_ha_state()

        dispatcher_key = f"net4home_update_{self.device.device_id}_rf_key"
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
