from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN
from .hub import Net4HomeHub, Net4HomeDevice

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up net4home binary sensor entities."""
    hub: Net4HomeHub = hass.data[DOMAIN][entry.entry_id]

    entities = [
        Net4HomeBinarySensor(hub, entry, device)
        for device in hub.devices.values()
        if device.device_type == "binary_sensor"
    ]
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "binary_sensor":
            return
        async_add_entities([Net4HomeBinarySensor(hub, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )

class Net4HomeBinarySensor(BinarySensorEntity):
    """Representation of a net4home binary sensor."""

    def __init__(self, hub: Net4HomeHub, entry, device: Net4HomeDevice):
        self.hub = hub
        self.entry = entry
        self.device = device
        self._state = False
        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}"

    async def async_added_to_hass(self):
        """Register dispatcher to receive updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self, value):
        """Update sensor state from dispatcher."""
        self._state = bool(value)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if the sensor is on."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for this entity."""
        data = self.entry.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            name=self.device.name,
            via_device=(DOMAIN, self.entry.entry_id),
            manufacturer="net4home",
            model=self.device.device_type,
            configuration_url=f"http://{data.get('host')}:{data.get('port')}",
        )
