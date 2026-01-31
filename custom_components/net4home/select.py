"""Support for net4home select entities (e.g. WAV-Bell track selection)."""
import logging
from typing import Callable

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify

from .api import Net4HomeApi, Net4HomeDevice
from .const import DOMAIN, PLATINE_HW_IS_BELL2

_LOGGER = logging.getLogger(__name__)

# WAV-Bell: 32 tracks, 0–31 in protocol; options shown as "Track 1" … "Track 32"
WAV_BELL_TRACK_OPTIONS = [f"Track {i + 1}" for i in range(32)]


class Net4HomeBellTrackSelect(SelectEntity):
    """Select entity for WAV-Bell: choose which track to play (1–32, protocol 0–31)."""

    _attr_icon = "mdi:music-box-multiple"
    _attr_options = WAV_BELL_TRACK_OPTIONS

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Track"
        self._attr_unique_id = f"{entry.entry_id}_bell_track_{slugify(device.device_id)}"
        self._attr_current_option = None  # Unknown until user selects or device reports

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "select")
        label = translations.get("bell_track", "Track")
        self._attr_name = f"{self.device.name} {label}"
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Play the selected track. Option is 'Track 1' … 'Track 32'."""
        try:
            # "Track N" -> 0-based index N-1
            num = int(option.split()[1])
            if not 1 <= num <= 32:
                _LOGGER.warning(f"WAV-Bell: invalid option {option}")
                return
            track_index = num - 1
        except (IndexError, ValueError):
            _LOGGER.warning(f"WAV-Bell: could not parse track from option {option}")
            return
        await self.api.async_send_bell_track(
            self.device.device_id,
            track=track_index,
            repeats=1,
            interrupt=True,
            dnr=False,
        )
        self._attr_current_option = option
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities: Callable):
    """Set up net4home select entities (e.g. WAV-Bell track)."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"[Select] Setup called with {len(api.devices)} devices in API")
    selects = []
    for device in api.devices.values():
        if not (device.device_id.startswith("MI") and not device.via_device):
            continue
        is_wav_bell = device.module_type == PLATINE_HW_IS_BELL2 or device.model == ".WAV-Bell"
        if is_wav_bell:
            selects.append(Net4HomeBellTrackSelect(api, entry, device))
    _LOGGER.info(f"[Select] Creating {len(selects)} WAV-Bell track select(s)")
    async_add_entities(selects, True)

    async def async_new_device(device: Net4HomeDevice):
        if not (device.device_id.startswith("MI") and not device.via_device):
            return
        is_wav_bell = device.module_type == PLATINE_HW_IS_BELL2 or device.model == ".WAV-Bell"
        if is_wav_bell:
            _LOGGER.debug(f"[Select] Adding WAV-Bell track select for {device.device_id}")
            async_add_entities([Net4HomeBellTrackSelect(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", async_new_device)
    )

    async def async_device_updated(device_id: str = None):
        if not device_id:
            return
        device = api.get_known_device(device_id) or api.devices.get(device_id)
        if not device:
            return
        if device.module_type == PLATINE_HW_IS_BELL2 or device.model == ".WAV-Bell":
            _LOGGER.debug(f"[Select] Device updated, adding WAV-Bell track select for {device_id}")
            async_add_entities([Net4HomeBellTrackSelect(api, entry, device)])
            _LOGGER.info(f"[Select] Added WAV-Bell track select for {device_id} after device update")

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated)
    )
