"""Power sensors of UP-SI (1 channel) and HS-SI6 (6 channels).

State: current power in W, pushed by the channel object (D0_SENSOR_ACK).
Attributes: object address and the used threshold lines of that channel
(direction, threshold_w, delay_s, target, command). Nothing is written.
"""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .helpers import parent_device_link
from .si_layout import SI_MODEL_CHANNELS, channel_thresholds, si_channel_objects

_LOGGER = logging.getLogger(__name__)


class Net4HomeSiPowerSensor(SensorEntity):
    """Power of one channel of a UP-SI or HS-SI6."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, api, entry, device, channel: int) -> None:
        self.api = api
        self.entry = entry
        self.device = device
        self._device_id = device.device_id.upper()
        self.channel = channel
        channels = SI_MODEL_CHANNELS.get(device.model, 1)
        suffix = f" Kanal {channel + 1}" if channels > 1 else ""
        self._attr_name = f"{device.name} Leistung{suffix}"
        self._attr_unique_id = f"{entry.entry_id}_si_power_{device.device_id.upper()}_{channel}"

    def _current_device(self):
        """The api may replace the device object (registration); always read the current one."""
        return self.api.devices.get(self._device_id, self.device)

    @property
    def device_info(self) -> DeviceInfo:
        device = self._current_device()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device.name,
            manufacturer="net4home",
            model=device.model,
            **parent_device_link(self.hass, self.entry.entry_id, device.via_device),
        )

    @property
    def native_value(self):
        return (getattr(self._current_device(), "si_power", None) or {}).get(self.channel)

    @property
    def extra_state_attributes(self) -> dict:
        device = self._current_device()
        info = getattr(device, "si_info", None)
        objadr = None
        if info is not None and self.channel < info.channels:
            objadr = si_channel_objects(info)[self.channel]
        entries = getattr(device, "si_entries", None) or {}
        return {
            "objadr": objadr,
            "thresholds": channel_thresholds(entries, self.channel),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        signal = f"net4home_si_{self._device_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_si_signal)
        )

    @callback
    def _handle_si_signal(self, _data=None) -> None:
        self.async_write_ha_state()


def si_power_sensors(api, entry, device) -> list:
    """One power sensor per channel of an UP-SI or HS-SI6."""
    channels = SI_MODEL_CHANNELS.get(device.model, 0)
    return [Net4HomeSiPowerSensor(api, entry, device, channel) for channel in range(channels)]
