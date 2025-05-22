import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import Net4HomeApi

_LOGGER = logging.getLogger(__name__)


@dataclass
class Net4HomeDevice:
    """Representation of a single net4home device."""

    device_id: str
    device_type: str
    name: str
    data: dict = field(default_factory=dict)


class Net4HomeHub:
    """Manage a connection to a net4home server."""

    def __init__(self, hass, host, port, password, mi, objadr, entry_id: str, modules=None):
        self.hass = hass
        self.entry_id = entry_id
        self.api = Net4HomeApi(hass, host, port, password, mi, objadr)
        self.devices: Dict[str, Net4HomeDevice] = {}

    async def async_start(self):
        """Connect to the server and start listening."""
        await self.api.async_connect()
        self.hass.loop.create_task(self.api.async_listen())

    async def async_stop(self):
        """Close the connection to the server."""
        await self.api.async_disconnect()

    def register_device(self, device_id: str, device_type: str, name: Optional[str] = None) -> Net4HomeDevice:
        """Register a new device and notify listeners."""
        if device_id in self.devices:
            return self.devices[device_id]

        device = Net4HomeDevice(device_id, device_type, name or device_id)
        self.devices[device_id] = device
        async_dispatcher_send(self.hass, f"net4home_new_device_{self.entry_id}", device)
        _LOGGER.debug("Registered new device %s of type %s", device_id, device_type)
        return device

