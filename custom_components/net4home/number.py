"""Day and night setpoints of a UP-TLH or UP-T, writable from Home Assistant."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import slugify

from .api import Net4HomeApi, Net4HomeDevice
from .bell import bell_numbers
from .bell_layout import is_wav_bell
from .const import DOMAIN
from .helpers import parent_device_link

_LOGGER = logging.getLogger(__name__)

# The konfigurator accepts 0 °C (day value unused). The bus stores tenths.
_MIN_TEMP = 0.0
_MAX_TEMP = 40.0
_STEP = 0.1


def _is_thermostat(device: Net4HomeDevice) -> bool:
    return (
        device.device_type == "climate"
        and device.model in ("UP-TLH", "UP-T")
        and device.device_id.startswith("MI")
    )


async def async_setup_entry(hass, entry, async_add_entities: Callable):
    """Create a Tagwert and a Nachtwert number for every UP-TLH and UP-T."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()

    def _take_bell(device: Net4HomeDevice) -> list:
        if not is_wav_bell(device) or device.device_id in seen:
            return []
        seen.add(device.device_id)
        return bell_numbers(api, entry, device)

    entities = [
        entity
        for device in api.devices.values()
        if _is_thermostat(device)
        for entity in _preset_numbers(api, entry, device)
    ]
    for device in api.devices.values():
        entities.extend(_take_bell(device))
    _LOGGER.info("[Number] Creating %s number entities", len(entities))
    async_add_entities(entities)

    @callback
    def _async_new_device(device: Net4HomeDevice) -> None:
        fresh = []
        if _is_thermostat(device):
            fresh.extend(_preset_numbers(api, entry, device))
        fresh.extend(_take_bell(device))
        if fresh:
            async_add_entities(fresh)

    def _async_device_updated(device_id: str = None) -> None:
        if not device_id:
            return
        device = api.devices.get(device_id)
        if not device:
            return
        fresh = _take_bell(device)
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"net4home_new_device_{entry.entry_id}", _async_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", _async_device_updated
        )
    )


def _preset_numbers(api, entry, device):
    return [
        Net4HomePresetNumber(api, entry, device, "day"),
        Net4HomePresetNumber(api, entry, device, "night"),
    ]


class Net4HomePresetNumber(NumberEntity):
    """One of the two stored setpoints. A change writes both, because the module stores one record."""

    _attr_should_poll = False

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = _MIN_TEMP
    _attr_native_max_value = _MAX_TEMP
    _attr_native_step = _STEP
    _attr_mode = NumberMode.BOX

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice, kind: str):
        self.api = api
        self.entry = entry
        self.device = device
        self._kind = kind
        self._attr_key = "presetday" if kind == "day" else "presetnight"
        self._default_name = "Tagwert" if kind == "day" else "Nachtwert"
        self._attr_icon = "mdi:weather-sunny" if kind == "day" else "mdi:weather-night"
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.device_id)}_{self._attr_key}"
        self._attr_name = f"{device.name} {self._default_name}"

    @property
    def native_value(self) -> float | None:
        value = getattr(self.device, self._attr_key, None)
        return None if value is None else float(value)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_added_to_hass(self) -> None:
        translations = await async_get_translations(self.hass, DOMAIN, "number")
        label = translations.get(self._attr_key, self._default_name)
        self._attr_name = f"{self.device.name} {label}"
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}_{self._attr_key}",
                self._handle_update,
            )
        )
        self.async_write_ha_state()

    @callback
    def _handle_update(self, value) -> None:
        if value is not None:
            setattr(self.device, self._attr_key, float(value))
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Write this setpoint. The other one is sent unchanged."""
        day = self.device.presetday if self._kind == "night" else value
        night = self.device.presetnight if self._kind == "day" else value
        if day is None or night is None:
            _LOGGER.warning(
                "%s: the other setpoint is not known yet, so the pair was not written",
                self.entity_id,
            )
            return
        await self.api.async_set_climate_presets(self.device.device_id, float(day), float(night))
