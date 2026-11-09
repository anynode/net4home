from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback


from .const import DOMAIN
from .helpers import decode_powerup_status, parent_device_link

import logging
_LOGGER = logging.getLogger(__name__)

# Diagnostic for inverted flag (binary_sensor)
class Net4HomeInvertedDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for inverted flag."""

    _attr_should_poll = False
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:swap-vertical"

    def __init__(self, entry, device):
        """Initialize the inverted diagnostic sensor."""
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Inverted"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_inverted_{device.device_id}"

    @property
    def native_value(self):
        """Return the inverted flag value."""
        devices_opts = self.entry.options.get("devices", {})
        dev_opts = devices_opts.get(self.device.device_id, {})
        return dev_opts.get("inverted", False)

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

# Diagnostic for send_state_changes
class Net4HomeSendStateChangesDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for send_state_changes flag."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:sync-alert"

    def __init__(self, entry, device):
        """Initialize the send state changes diagnostic sensor."""
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} State changes"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_send_state_changes_{device.device_id}"

    @property
    def native_value(self):
        """Return the send_state_changes flag value."""
        devices_opts = self.entry.options.get("devices", {})
        lookup_key = self.device.device_id
        dev_opts = devices_opts.get(lookup_key, {})
        from_device = getattr(self.device, "send_state_changes", False)
        value = dev_opts.get("send_state_changes", from_device)
        result = "true" if value else "false"
        _LOGGER.debug(
            "[Diagnostic State changes] device_id=%s device_type=%s lookup_key=%r "
            "options_keys=%s found_in_options=%s dev_opts.send_state_changes=%s "
            "device.send_state_changes=%s -> native_value=%s",
            self.device.device_id,
            getattr(self.device, "device_type", "?"),
            lookup_key,
            list(devices_opts.keys()),
            lookup_key in devices_opts,
            dev_opts.get("send_state_changes"),
            from_device,
            result,
        )
        return result

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_diagnostic_update_{self.device.device_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self):
        """Handle update signal from dispatcher."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

def _actor_setting(sensor, key):
    """Current value on the device, or the copy stored in the config entry."""
    device = sensor.api.devices.get(sensor.device.device_id, sensor.device)
    value = getattr(device, key, None)
    if value is not None:
        return value
    stored = sensor.entry.options.get("devices", {}).get(sensor.device.device_id, {})
    return stored.get(key)


# Diagnostic for powerup_status
class Net4HomePowerupStatusDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for powerup status."""

    _attr_should_poll = False
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:power-cycle"

    def __init__(self, entry, device, api):
        """Initialize the powerup status diagnostic sensor."""
        self.entry = entry
        self.device = device
        self.api = api
        self._attr_name = f"{device.name} PowerUp"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_powerup_status_{device.device_id}"

    @property
    def native_value(self):
        """Return the powerup status value."""
        powerup_status = _actor_setting(self, "powerup_status")
        if powerup_status is None:
            return "Not yet read"
        return decode_powerup_status(powerup_status)
    
    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_diagnostic_update_{self.device.device_id}",
                self._handle_update,
            )
        )
    
    @callback
    def _handle_update(self):
        """Handle update signal from dispatcher."""
        self.async_write_ha_state()
        
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

# Diagnostic for timer_time1 (only for timer actors)
class Net4HomeTimerTime1DiagnosticSensor(SensorEntity):
    """Diagnostic sensor for timer time1."""

    _attr_should_poll = False
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry, device, api):
        """Initialize the timer time1 diagnostic sensor."""
        self.entry = entry
        self.device = device
        self.api = api
        self._attr_name = f"{device.name} Timer"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_timer_time1_{device.device_id}"

    @property
    def native_value(self):
        timer_time1 = getattr(self.device, "timer_time1", None)
        if timer_time1 is None:
            return "Noch nicht ausgelesen"
        return f"{timer_time1} s"
    
    async def async_added_to_hass(self):
        """Register update listener when entity is added."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_diagnostic_update_{self.device.device_id}",
                self._handle_update,
            )
        )
    
    @callback
    def _handle_update(self):
        """Handle update signal from dispatcher."""
        self.async_write_ha_state()
        
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

# Diagnostic for min_hell (only for dimmers)
class Net4HomeMinHellDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for minimum brightness."""

    _attr_should_poll = False
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:brightness-4"

    def __init__(self, entry, device, api):
        """Initialize the minimum brightness diagnostic sensor."""
        self.entry = entry
        self.device = device
        self.api = api
        self._attr_name = f"{device.name} Minimum brightness"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_min_hell_{device.device_id}"

    @property
    def native_value(self):
        """Return the minimum brightness value."""
        min_hell = _actor_setting(self, "min_hell")
        if min_hell is None:
            return "Not yet read"
        return f"{min_hell}%"
    
    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_diagnostic_update_{self.device.device_id}",
                self._handle_update,
            )
        )
    
    @callback
    def _handle_update(self):
        """Handle update signal from dispatcher."""
        self.async_write_ha_state()
        
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

# Diagnostic for timer_time1 for covers (Run time)
class Net4HomeCoverRunTimeDiagnosticSensor(SensorEntity):
    """Diagnostic sensor for cover run time."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry, device, api):
        """Initialize the cover run time diagnostic sensor."""
        self.entry = entry
        self.device = device
        self.api = api
        self._attr_name = f"{device.name} Run time"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_cover_run_time_{device.device_id}"

    @property
    def native_value(self):
        timer_time1 = getattr(self.device, "timer_time1", None)
        result = timer_time1 if timer_time1 is not None else None
        _LOGGER.debug(
            "[Diagnostic Cover Run time] device_id=%s device_type=%s timer_time1=%s -> native_value=%s (state will be %s)",
            self.device.device_id,
            getattr(self.device, "device_type", "?"),
            timer_time1,
            result,
            "unknown" if result is None else repr(result),
        )
        return result

    async def async_added_to_hass(self):
        """Register update listener when entity is added."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"net4home_diagnostic_update_{self.device.device_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self):
        """Handle update signal from dispatcher."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )