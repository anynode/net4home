from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up net4home binary sensor entities."""
    client = hass.data[DOMAIN][entry.entry_id]
    # Beispiel: Sensor für OBJADR aus den Konfigurationsdaten anlegen
    objadr = entry.data.get("OBJADR", 3602)
    async_add_entities([Net4HomeBinarySensor(client, entry, objadr)], True)

class Net4HomeBinarySensor(BinarySensorEntity):
    """Representation of a net4home binary sensor."""

    def __init__(self, client, entry, objadr):
        self.client = client
        self.entry = entry
        self._objadr = objadr
        self._state = False
        self._attr_name = f"net4home_{objadr}"
        self._attr_unique_id = f"{entry.entry_id}_{objadr}"

    async def async_added_to_hass(self):
        """Register dispatcher to receive updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"net4home_update_{self._objadr}", self._handle_update
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
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="net4home bus",
            manufacturer="net4home",
            model="Busconnector",
            configuration_url=f"http://{data.get('host')}:{data.get('port')}",
        )
