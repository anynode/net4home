import logging
from typing import Callable

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

SENSOR_MODEL_TO_TYPE_UNIT = {
    "humidity": ("humidity", PERCENTAGE),
    "temperature": ("temperature", UnitOfTemperature.CELSIUS),
    "illuminance": ("illuminance", LIGHT_LUX),
}

async def async_setup_entry(hass, entry, async_add_entities: Callable):
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    entities = []
    diagnostic_entities = []
    _LOGGER.debug(f"Listening for new devices with key: net4home_new_device_{entry.entry_id}")

    # Climate device sensors
    for device in api.devices.values():
        if device.device_type == "climate":
            for sensor_key, unit in CLIMATE_SENSOR_TYPES:
                entities.append(Net4HomeSensor(api, entry, device, sensor_key, unit))

    # Sensor devices
    for device in api.devices.values():
        if device.device_type == "sensor":
            sensor_info = SENSOR_MODEL_TO_TYPE_UNIT.get(device.model.lower())
            if sensor_info is None:
                _LOGGER.warning(f"Unbekanntes Sensor-Modell {device.model} für Gerät {device.device_id}")
                continue
            sensor_key, unit = sensor_info
            entities.append(Net4HomeSensor(api, entry, device, sensor_key, unit))
            _LOGGER.warning(f"Append sensor model {device.model} for device {device.device_id} {sensor_info}")

    # DIAGNOSTIC-Entities für BinarySensoren!
    for device in api.devices.values():
        if device.device_type == "binary_sensor":
            diagnostic_entities.append(Net4HomeInvertedDiagnosticSensor(entry, device))

    async_add_entities(entities + diagnostic_entities)  

    async def async_new_device(device: Net4HomeDevice):
        _LOGGER.debug(f"async_new_device triggered for: {device.device_id}, model: {device.model}, type: {device.device_type}")
        if device.device_type == "climate":
            sensors = [
                Net4HomeSensor(api, entry, device, key, unit)
                for key, unit in CLIMATE_SENSOR_TYPES
            ]
            async_add_entities(sensors)
        elif device.device_type == "sensor":
            model_key = device.model.lower() if device.model else ""
            sensor_info = SENSOR_MODEL_TO_TYPE_UNIT.get(model_key)
            if sensor_info is None:
                _LOGGER.warning(f"Unbekanntes Sensor-Modell {device.model} für Gerät {device.device_id}")
                return
            sensor_key, unit = sensor_info
            _LOGGER.debug(f"Creating sensor: {sensor_key} for {device.device_id}")
            async_add_entities([Net4HomeSensor(api, entry, device, sensor_key, unit)])
        elif device.device_type == "binary_sensor":
            # NEU: auch bei neu erkannten Devices eine Diagnose-Entity und Button anlegen!
            async_add_entities([
                Net4HomeInvertedDiagnosticSensor(entry, device),
            ])

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )

class Net4HomeSensor(SensorEntity):
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, sensor_type: str, unit: str):
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
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
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

        dispatcher_key = f"net4home_update_{self.device.device_id}_{self.sensor_type}"
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
        self._state = value
        self.async_write_ha_state()

        if self.sensor_type == "temperature":
            signal_key = f"net4home_temperature_update_{self.device.via_device}"
            async_dispatcher_send(self.hass, signal_key, value)

        if self.sensor_type in {"targettemp", "presetday", "presetnight"}:
            signal_key = f"net4home_update_{self.device.via_device}"
            async_dispatcher_send(self.hass, signal_key, {self.sensor_type: value})
