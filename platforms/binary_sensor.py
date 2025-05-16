"""Binary sensor platform for net4home."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [Net4HomeBinarySensor(client)],
        update_before_add=True
    )

class Net4HomeBinarySensor(BinarySensorEntity):
    """Representation of a net4home binary sensor."""

    def __init__(self, client):
        self.client = client
        self._state = False

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_update(self) -> None:
        # TODO: fetch and update sensor state
        pass