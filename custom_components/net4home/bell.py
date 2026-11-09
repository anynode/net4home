"""Home Assistant entities for one .WAV-Bell module."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import slugify

from .bell_layout import (
    MUTE_MINUTES,
    attenuation_from_db,
    db_from_attenuation,
    ensure_bell_runtime,
    is_wav_bell,
    label_for_index,
    track_index_from_label,
    track_options,
)
from .const import DOMAIN
from .helpers import parent_device_link

_LOGGER = logging.getLogger(__name__)


class _BellEntity:
    """Shared device link and refresh for every WAV-Bell entity."""

    def _init_bell(self, api, entry, device, suffix: str, label: str) -> None:
        ensure_bell_runtime(device)
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_unique_id = f"{entry.entry_id}_bell_{suffix}_{slugify(device.device_id)}"
        self._attr_name = f"{device.name} {label}"

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def _listen_bell(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_bell_{self.device.device_id.upper()}",
                self._handle_bell,
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_bell(self, *_args) -> None:
        self.async_write_ha_state()


class Net4HomeBellActionButton(_BellEntity, ButtonEntity):
    """One-shot command: ring, play again, silent on/off, or a timed mute."""

    _attr_should_poll = False

    def __init__(self, api, entry, device, suffix: str, label: str, icon: str, action: str, minutes: int | None = None):
        self._init_bell(api, entry, device, suffix, label)
        self._attr_icon = icon
        self._action = action
        self._minutes = minutes

    async def async_press(self) -> None:
        device_id = self.device.device_id
        if self._action == "PLAY":
            track = self.device.bell_selected
            if track is None:
                _LOGGER.warning(
                    "WAV-Bell %s: no track selected, Abspielen did nothing",
                    device_id,
                )
                return
            await self.api.async_send_bell_track(
                device_id,
                track,
                repeats=self.device.bell_repeats,
                interrupt=self.device.bell_interrupt,
                dnr=self.device.bell_dnr,
            )
            return
        if self._action == "MUTE":
            await self.api.async_send_bell_mute(device_id, self._minutes)
            return
        await self.api.async_send_bell_command(device_id, self._action)


class Net4HomeBellTrackSelect(_BellEntity, SelectEntity):
    """Track list. Picking an entry plays it. Abspielen repeats the same one."""

    _attr_should_poll = False

    _attr_icon = "mdi:music-box-multiple"

    def __init__(self, api, entry, device):
        self._init_bell(api, entry, device, "track", "Spur")
        self._attr_options = track_options(device.bell_tracks)
        self._attr_current_option = None

    def _sync_track_list(self) -> None:
        """Options and the current choice are cached. Drop the cache after a change."""
        self._attr_options = track_options(self.device.bell_tracks)
        self._attr_current_option = label_for_index(
            self.device.bell_selected, self.device.bell_tracks
        )
        self.__dict__.pop("options", None)
        self.__dict__.pop("current_option", None)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._sync_track_list()
        await self._listen_bell()

    @callback
    def _handle_bell(self, *_args) -> None:
        self._sync_track_list()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        index = track_index_from_label(option)
        if index is None:
            _LOGGER.warning("WAV-Bell: could not parse track from %s", option)
            return
        self.device.bell_selected = index
        self._sync_track_list()
        self.async_write_ha_state()
        await self.api.async_send_bell_track(
            self.device.device_id,
            index,
            repeats=self.device.bell_repeats,
            interrupt=self.device.bell_interrupt,
            dnr=self.device.bell_dnr,
        )


class Net4HomeBellVolumeNumber(_BellEntity, NumberEntity):
    """Live volume. 0 dB is full, -63 dB is the lowest step the command accepts."""

    _attr_should_poll = False

    _attr_native_min_value = -64
    _attr_native_max_value = 0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, api, entry, device, alarm: bool):
        suffix = "alarm_volume" if alarm else "volume"
        label = "Alarm-Lautstärke" if alarm else "Lautstärke"
        self._init_bell(api, entry, device, suffix, label)
        self._alarm = alarm
        self._attr_icon = "mdi:alarm-light" if alarm else "mdi:volume-high"

    @property
    def native_value(self) -> float | None:
        stored = self.device.bell_alarm_volume if self._alarm else self.device.bell_volume
        return db_from_attenuation(stored)

    async def async_added_to_hass(self) -> None:
        await self._listen_bell()

    async def async_set_native_value(self, value: float) -> None:
        attenuation = attenuation_from_db(value)
        if self._alarm:
            self.device.bell_alarm_volume = attenuation
        else:
            self.device.bell_volume = attenuation
        self.async_write_ha_state()
        await self.api.async_send_bell_volume(
            self.device.device_id, attenuation, alarm=self._alarm
        )


class Net4HomeBellRepeatNumber(_BellEntity, NumberEntity):
    """How often the next Abspielen or Spur choice runs. Kept in Home Assistant."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:repeat"
    _attr_native_min_value = 1
    _attr_native_max_value = 16
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, api, entry, device):
        self._init_bell(api, entry, device, "repeats", "Wiederholungen")

    @property
    def native_value(self) -> float:
        return float(self.device.bell_repeats)

    async def async_added_to_hass(self) -> None:
        await self._listen_bell()

    async def async_set_native_value(self, value: float) -> None:
        self.device.bell_repeats = max(1, min(16, int(value)))
        self.async_write_ha_state()


class Net4HomeBellPowerSwitch(_BellEntity, SwitchEntity):
    """Betrieb. Ein und Aus ohne Quittungston, passend zum Schalter."""

    _attr_should_poll = False

    _attr_icon = "mdi:power"

    def __init__(self, api, entry, device):
        self._init_bell(api, entry, device, "power", "Betrieb")

    @property
    def is_on(self) -> bool | None:
        return self.device.bell_on

    async def async_added_to_hass(self) -> None:
        await self._listen_bell()

    async def async_turn_on(self, **kwargs) -> None:
        self.device.bell_on = True
        self.async_write_ha_state()
        await self.api.async_send_bell_command(self.device.device_id, "ON_SILENT")

    async def async_turn_off(self, **kwargs) -> None:
        self.device.bell_on = False
        self.async_write_ha_state()
        await self.api.async_send_bell_command(self.device.device_id, "OFF_SILENT")


class Net4HomeBellOptionSwitch(_BellEntity, SwitchEntity):
    """Playback flag used by Spur and Abspielen. Nothing is sent until then."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, api, entry, device, suffix: str, label: str, icon: str, field: str):
        self._init_bell(api, entry, device, suffix, label)
        self._attr_icon = icon
        self._field = field

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.device, self._field))

    async def async_added_to_hass(self) -> None:
        await self._listen_bell()

    async def async_turn_on(self, **kwargs) -> None:
        setattr(self.device, self._field, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        setattr(self.device, self._field, False)
        self.async_write_ha_state()


class Net4HomeBellStandardTrackSensor(_BellEntity, SensorEntity):
    """Track played by Klingeln and by a bus button (D0_TOGGLE)."""

    _attr_should_poll = False

    _attr_icon = "mdi:playlist-star"

    def __init__(self, api, entry, device):
        self._init_bell(api, entry, device, "standard_track", "Standard-Spur")

    @property
    def native_value(self) -> str | None:
        return label_for_index(self.device.bell_toggle_track, self.device.bell_tracks)

    async def async_added_to_hass(self) -> None:
        await self._listen_bell()


def extra_bell_buttons(api, entry, device) -> list:
    mute_labels = {60: "Stumm 60 Minuten", 120: "Stumm 120 Minuten", 240: "Stumm 4 Stunden"}
    buttons = [
        Net4HomeBellActionButton(api, entry, device, "ring", "Klingeln", "mdi:bell-ring", "TOGGLE"),
        Net4HomeBellActionButton(api, entry, device, "play", "Abspielen", "mdi:play", "PLAY"),
        Net4HomeBellActionButton(
            api, entry, device, "on_silent", "EIN ohne Ton", "mdi:bell-check-outline", "ON_SILENT"
        ),
        Net4HomeBellActionButton(
            api, entry, device, "off_silent", "AUS ohne Ton", "mdi:bell-off-outline", "OFF_SILENT"
        ),
    ]
    for minutes in MUTE_MINUTES:
        buttons.append(
            Net4HomeBellActionButton(
                api,
                entry,
                device,
                f"mute_{minutes}",
                mute_labels[minutes],
                "mdi:bell-sleep",
                "MUTE",
                minutes,
            )
        )
    return buttons


def bell_numbers(api, entry, device) -> list:
    return [
        Net4HomeBellVolumeNumber(api, entry, device, False),
        Net4HomeBellVolumeNumber(api, entry, device, True),
        Net4HomeBellRepeatNumber(api, entry, device),
    ]


def bell_switches(api, entry, device) -> list:
    return [
        Net4HomeBellPowerSwitch(api, entry, device),
        Net4HomeBellOptionSwitch(
            api, entry, device, "interrupt", "Laufenden Track unterbrechen", "mdi:skip-next", "bell_interrupt"
        ),
        Net4HomeBellOptionSwitch(
            api,
            entry,
            device,
            "dnr",
            "Gleichen Track nicht neu starten",
            "mdi:bell-cancel",
            "bell_dnr",
        ),
    ]


def bell_sensors(api, entry, device) -> list:
    return [Net4HomeBellStandardTrackSensor(api, entry, device)]


__all__ = [
    "bell_numbers",
    "bell_sensors",
    "bell_switches",
    "extra_bell_buttons",
    "is_wav_bell",
    "Net4HomeBellTrackSelect",
]
