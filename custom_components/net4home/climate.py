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
from .api import Net4HomeApi, Net4HomeDevice

_LOGGER = logging.getLogger(__name__)


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
    
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
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
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_target_temperature = 21.0
        self._attr_current_temperature = 21.0
        self._attr_presetday_temperature = 20
        self._attr_presetnight_temperature = 10.0

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            via_device=(DOMAIN, self.device.via_device.upper()) if self.device.via_device else None,
        )

    async def async_added_to_hass(self):
        """Register update listener when entity is added."""
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
        self._attr_current_temperature = value
        self.async_write_ha_state()

    @callback
    def _handle_update(self, data: dict):
        """Handle incoming update from API."""
        # Update HVAC Mode based on status bits (if available)
        hvac_mode_str = data.get("hvac_mode")
        if hvac_mode_str:
            if hvac_mode_str == "heat":
                self._attr_hvac_mode = HVACMode.HEAT
            elif hvac_mode_str == "cool":
                self._attr_hvac_mode = HVACMode.COOL
            elif hvac_mode_str == "heat_cool":
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            elif hvac_mode_str == "off":
                self._attr_hvac_mode = HVACMode.OFF
        else:
            # Fallback: Use is_on (for compatibility)
            self._attr_hvac_mode = HVACMode.HEAT if data.get("is_on", True) else HVACMode.OFF
        
        self._attr_target_temperature = data.get("targettemp", self._attr_target_temperature)
        self._attr_current_temperature = data.get("current_temp", self._attr_current_temperature)
        self._attr_presetday_temperature = data.get("presetday", self._attr_presetday_temperature)
        self._attr_presetnight_temperature = data.get("presetnight", self._attr_presetnight_temperature)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode (heat, cool, heat_cool, off)."""
        self._attr_hvac_mode = hvac_mode
        await self.api.async_set_climate_mode(self.device.device_id, hvac_mode)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None:
            self._attr_target_temperature = temp
            await self.api.async_set_temperature(self.device.device_id, temp)
            self.async_write_ha_state()
