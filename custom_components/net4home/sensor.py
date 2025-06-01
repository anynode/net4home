import logging
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature, PERCENTAGE, LIGHT_LUX
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify
from homeassistant.core import callback

from .const import DOMAIN
from .api import Net4HomeApi, Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    ("temperature", "Temperatur", UnitOfTemperature.CELSIUS),
    ("humidity", "Luftfeuchtigkeit", PERCENTAGE),
    ("illuminance", "Lichtstärke", LIGHT_LUX),
    ("targettemp", "Aktueller Sollwert", UnitOfTemperature.CELSIUS),
    ("presetday", "Vorgabe Tag", UnitOfTemperature.CELSIUS),
    ("presetnight", "Vorgabe Nacht", UnitOfTemperature.CELSIUS),
]

async def async_setup_entry(hass, entry, async_add_entities: Callable):
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for device in api.devices.values():
        if device.device_type == "climate":
            for sensor_key, sensor_name, unit in SENSOR_TYPES:
                entities.append(Net4HomeSensor(api, entry, device, sensor_key, sensor_name, unit))

    async_add_entities(entities)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "climate":
            return
        sensors = [
            Net4HomeSensor(api, entry, device, key, name, unit)
            for key, name, unit in SENSOR_TYPES
        ]
        async_add_entities(sensors)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )

class Net4HomeSensor(SensorEntity):
    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, sensor_type: str, name: str, unit: str):
        self.api = api
        self.entry = entry
        self.device = device
        self.sensor_type = sensor_type
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_{sensor_type}"
        self._attr_native_unit_of_measurement = unit
        self._state = None

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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, data):
        new_value = data.get(self.sensor_type)
        if new_value is not None:
            self._state = new_value
            # write state safely in the event loop
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
