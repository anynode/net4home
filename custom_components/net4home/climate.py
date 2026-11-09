import logging
from typing import Callable

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import slugify
from homeassistant.core import callback

from .const import DOMAIN
from .helpers import bus_connected, listen_connection, parent_device_link
from .api import Net4HomeApi, Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

_HVAC_MODES = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "heat_cool": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
}


def _hvac_mode_from_regulators(heat_active, cool_active):
    """Climate mode from the two controller flags. Unknown until both are known."""
    if heat_active is None or cool_active is None:
        return None
    if heat_active and cool_active:
        return HVACMode.HEAT_COOL
    if heat_active:
        return HVACMode.HEAT
    if cool_active:
        return HVACMode.COOL
    return HVACMode.OFF


async def async_setup_entry(hass, entry, async_add_entities: Callable):
    """Set up net4home climate entities from a config entry."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    
    _LOGGER.info(f"[Climate] Setup called with {len(api.devices)} devices in API")
    climate_devices = [d for d in api.devices.values() if d.device_type == "climate"]
    _LOGGER.info(f"[Climate] Found {len(climate_devices)} climate devices: {[d.device_id for d in climate_devices]}")

    entities = [
        Net4HomeClimate(api, entry, device)
        for device in climate_devices
    ]

    _LOGGER.info(f"[Climate] Creating {len(entities)} climate entities")
    async_add_entities(entities, True)

    async def async_new_device(device: Net4HomeDevice):
        if device.device_type != "climate":
            return
        async_add_entities([Net4HomeClimate(api, entry, device)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )


class Net4HomeClimate(ClimateEntity):
    """Representation of a net4home climate device."""

    _attr_should_poll = False

    @property
    def available(self) -> bool:
        return bus_connected(self.api)
    
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, api: Net4HomeApi, entry, device: Net4HomeDevice):
        """Initialize the climate device."""
        self.api = api
        self.entry = entry
        self.device = device

        self._attr_name = device.name
        self._attr_unique_id = f"{entry.entry_id}_{slugify(device.via_device or 'unknown')}_{slugify(device.device_id)}"
        self._heat_active = getattr(device, "heat_active", None)
        self._cool_active = getattr(device, "cool_active", None)
        self._attr_hvac_mode = _hvac_mode_from_regulators(self._heat_active, self._cool_active)
        self._attr_native_target_temperature = getattr(device, "targettemp", None)
        self._attr_native_current_temperature = None
        self._attr_presetday_temperature = (
            device.presetday if getattr(device, "presetday", None) is not None else 20.0
        )
        self._attr_presetnight_temperature = (
            device.presetnight if getattr(device, "presetnight", None) is not None else 10.0
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_added_to_hass(self):
        """Register update listener when entity is added."""
        listen_connection(self)
        # General updates for climate device
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_update_{self.device.device_id.upper()}",
                self._handle_update,
            )
        )

        # Listen for temperature updates from linked sensor
        temp_signal = f"net4home_temperature_update_{self.device.device_id}"
        _LOGGER.debug(f"{self.entity_id} listening for sensor temperature updates: {temp_signal}")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                temp_signal,
                self._handle_temperature_update,
            )
        )

    @callback
    def _handle_temperature_update(self, value: float):
        """Handle temperature update from sensor."""
        self._attr_native_current_temperature = value
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Heating and cooling controller, as two independent flags."""
        return {
            "heat_active": self._heat_active,
            "cool_active": self._cool_active,
        }

    @callback
    def _handle_update(self, data: dict):
        """Handle incoming update from API."""
        if "heat_active" in data:
            self._heat_active = data["heat_active"]
        if "cool_active" in data:
            self._cool_active = data["cool_active"]
        # Update HVAC Mode only when explicitly in payload (e.g. D0_ACTOR_ACK / D0_SET_N), not on targettemp-only updates (D0_SET)
        hvac_mode_str = data.get("hvac_mode")
        if hvac_mode_str is not None:
            self._attr_hvac_mode = _HVAC_MODES.get(hvac_mode_str, self._attr_hvac_mode)
        elif "is_on" in data:
            # Fallback: Use is_on only when explicitly present (for compatibility)
            self._attr_hvac_mode = HVACMode.HEAT if data.get("is_on", True) else HVACMode.OFF
        # else: do not change _attr_hvac_mode (e.g. D0_SET only sends targettemp)
        
        if "targettemp" in data:
            self._attr_native_target_temperature = data["targettemp"]
        elif getattr(self.device, "targettemp", None) is not None:
            self._attr_native_target_temperature = self.device.targettemp
        self._attr_native_current_temperature = data.get(
            "current_temp", self._attr_native_current_temperature
        )
        self._attr_presetday_temperature = data.get("presetday") if "presetday" in data else (
            self.device.presetday if getattr(self.device, "presetday", None) is not None else self._attr_presetday_temperature
        )
        self._attr_presetnight_temperature = data.get("presetnight") if "presetnight" in data else (
            self.device.presetnight if getattr(self.device, "presetnight", None) is not None else self._attr_presetnight_temperature
        )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode (heat, cool, heat_cool, off)."""
        self._attr_hvac_mode = hvac_mode
        self._heat_active = hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL)
        self._cool_active = hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
        await self.api.async_set_climate_mode(self.device.device_id, hvac_mode)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None:
            self._attr_native_target_temperature = temp
            await self.api.async_set_temperature(self.device.device_id, temp)
            self.async_write_ha_state()
