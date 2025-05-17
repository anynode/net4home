from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

class Net4HomeBinarySensor(BinarySensorEntity):
    def __init__(self, client, objadr):
        self.client = client
        self._objadr = objadr
        self._state = False

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"net4home_update_{self._objadr}", self._handle_update
            )
        )

    @callback
    def _handle_update(self, value):
        self._state = bool(value)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self._state
