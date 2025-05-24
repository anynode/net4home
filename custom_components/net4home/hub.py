import logging
import asyncio

from dataclasses import dataclass, field
from typing import Dict, Optional
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .api import Net4HomeApi
from .helpers import register_device_in_registry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class Net4HomeDevice:
    device_id: str
    device_type: str
    name: str
    data: dict = field(default_factory=dict)


class Net4HomeHub:
    def __init__(
        self, hass: HomeAssistant, host, port, password, mi, objadr, entry_id: str, devices=None
    ):
        self.hass = hass
        self.entry_id = entry_id
        self.api = Net4HomeApi(hass=hass, host=host,  port=port, password=password, mi=mi, objadr=objadr, entry_id=entry_id)        
        self.devices: Dict[str, Net4HomeDevice] = {}
        self.unsub_options_update_listener = None
        self._pending_devices = devices or []

    async def async_start(self):
        await self.api.async_connect()
        self.hass.loop.create_task(self.api.async_listen())

        # Parallele Registrierung aller Pending Devices
        await asyncio.gather(
            *[
                self.register_device(
                    str(dev.get("device_id")),
                    dev.get("device_type", ""),
                    dev.get("name"),
                    dev.get("model"),
                    dev.get("sw_version"),
                )
                for dev in self._pending_devices
            ]
        )

    async def async_stop(self):
        await self.api.async_disconnect()

    async def register_device(
        self,
        device_id: str,
        device_type: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        sw_version: Optional[str] = None,
    ) -> Net4HomeDevice:
        """
        Registriere ein neues Device im Hub und im Device Registry.
        """
        if device_id in self.devices:
            return self.devices[device_id]

        device = Net4HomeDevice(device_id, device_type, name or device_id)
        self.devices[device_id] = device

        # Registriere das Device im HA Device Registry (async)
        await register_device_in_registry(
            self.hass,
            self.entry_id,
            device_id,
            name or device_id,
            model or device_type,
            sw_version or "unknown",
        )

        # Informiere andere Komponenten über neues Device (Dispatcher)
        async_dispatcher_send(self.hass, f"net4home_new_device_{self.entry_id}", device)
        _LOGGER.debug("Registered new device %s of type %s", device_id, device_type)
        return device

    async def async_handle_new_device(
        self,
        device_id: str,
        device_type: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        sw_version: Optional[str] = None,
    ) -> Net4HomeDevice:
        """
        Async Callback: neues Gerät vom n4htools aus an den Hub melden.
        """
        _LOGGER.debug(
            "async_handle_new_device called with device_id=%s, device_type=%s",
            device_id,
            device_type,
        )
        return await self.register_device(device_id, device_type, name, model, sw_version)
