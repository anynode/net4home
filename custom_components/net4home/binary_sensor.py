import logging
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant import config_entries

from .const import DOMAIN
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
    _LOGGER.info(f"[BinarySensor] Found {len(binary_sensor_devices)} binary_sensor devices: {[d.device_id for d in binary_sensor_devices]}")

    # ONLY BinarySensor entities (no ConfigSensor entities)
    entities = [
        Net4HomeBinarySensor(api, entry, device)
        for device in binary_sensor_devices
    ]
    _LOGGER.info(f"[BinarySensor] Creating {len(entities)} binary_sensor entities")
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        """Handle new device discovery."""
        if device.device_type != "binary_sensor":
            return
        _LOGGER.debug(f"[BinarySensor] Adding new device {device.device_id}")
        async_add_entities([
            Net4HomeBinarySensor(api, entry, device)
        ])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeBinarySensor(BinarySensorEntity):
    """Representation of a net4home binary sensor."""
    
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
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    @callback
    def _handle_update(self, state: bool):
        """Handle update from dispatcher."""
        self._is_on = not state
        self.async_write_ha_state()
        _LOGGER.debug(f"[BinarySensor] Update {self.device.device_id} → {'ON' if self.is_on else 'OFF'} (inverted={self.inverted})")

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )
