"""Support for net4home select entities (WAV-Bell track selection)."""
import logging
from typing import Callable

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .api import Net4HomeApi, Net4HomeDevice
from .bell import Net4HomeBellTrackSelect
from .bell_layout import is_wav_bell
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities: Callable):
    """Set up net4home select entities (WAV-Bell track)."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()

    def _take(device: Net4HomeDevice) -> list:
        if not is_wav_bell(device) or device.device_id in seen:
            return []
        seen.add(device.device_id)
        return [Net4HomeBellTrackSelect(api, entry, device)]

    selects = []
    for device in api.devices.values():
        selects.extend(_take(device))
    _LOGGER.info("[Select] Creating %s WAV-Bell track select(s)", len(selects))
    async_add_entities(selects, True)

    async def async_new_device(device: Net4HomeDevice):
        fresh = _take(device)
        if fresh:
            async_add_entities(fresh)

    async def async_device_updated(device_id: str = None):
        if not device_id:
            return
        device = api.get_known_device(device_id) or api.devices.get(device_id)
        if not device:
            return
        fresh = _take(device)
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated)
    )
