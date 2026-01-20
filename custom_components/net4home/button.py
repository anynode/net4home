from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import callback
from homeassistant.util import slugify
from .api import Net4HomeApi, Net4HomeDevice

from .const import DOMAIN, PLATINE_HW_IS_LCD3, CI_LCD_OPT_BLINK, CI_LCD_OPT_BUZZER_ON

import logging
_LOGGER = logging.getLogger(__name__)

class Net4HomeDeviceRefreshButton(ButtonEntity):
    """Button entity for refreshing device status."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, api, entry, device):
        """Initialize the refresh button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Read state"
        self._attr_unique_id = f"{entry.entry_id}_diagnostic_refresh_{device.device_id}"

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

    async def async_press(self) -> None:
        """Handle the button press to refresh status."""
        await self.api.async_request_status(self.device.device_id)


class Net4HomeMasterkeyLearningButton(ButtonEntity):
    """Button entity for masterkey learning."""
    
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:key-plus"

    def __init__(self, api, entry, device):
        """Initialize the masterkey learning button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Learn Masterkey"
        self._attr_unique_id = f"{entry.entry_id}_masterkey_learning_{slugify(device.device_id)}"

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

    async def async_press(self) -> None:
        """Handle the button press to start Masterkey learning."""
        await self.api.async_start_masterkey_learning(self.device.device_id)


class Net4HomeReadDeviceConfigButton(ButtonEntity):
    """Button entity for reading device configuration."""
    
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:file-document-outline"

    def __init__(self, api, entry, device):
        """Initialize the read device config button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Read Device"
        self._attr_unique_id = f"{entry.entry_id}_read_config_{slugify(device.device_id)}"

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
        """Set up translations when entity is added to Home Assistant."""
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        translated_label = translations.get("read_device", "Read Device")
        self._attr_name = f"{self.device.name} {translated_label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press to read device configuration."""
        await self.api.async_read_device_config(self.device.device_id)


class Net4HomeLCDBlinkButton(ButtonEntity):
    """Button entity for LCD blink control."""
    
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:flash"

    def __init__(self, api, entry, device):
        """Initialize the LCD blink button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Blinken"
        self._attr_unique_id = f"{entry.entry_id}_lcd_blink_{slugify(device.device_id)}"

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

    async def async_press(self) -> None:
        """Handle the button press to trigger LCD blink."""
        await self.api.async_send_lcd_command(
            device_id=self.device.device_id,
            options=CI_LCD_OPT_BLINK,
            text="",  # Empty text for simple blink command
            freq=100  # 1 Hz
        )


class Net4HomeLCDBuzzerButton(ButtonEntity):
    """Button entity for LCD buzzer control."""
    
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bell"

    def __init__(self, api, entry, device):
        """Initialize the LCD buzzer button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Buzzer"
        self._attr_unique_id = f"{entry.entry_id}_lcd_buzzer_{slugify(device.device_id)}"

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

    async def async_press(self) -> None:
        """Handle the button press to trigger LCD buzzer."""
        await self.api.async_send_lcd_command(
            device_id=self.device.device_id,
            options=CI_LCD_OPT_BUZZER_ON,
            text="",  # Empty text for simple buzzer command
            freq=100  # 1 Hz
        )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up net4home button entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"[Button] Setup called with {len(api.devices)} devices in API")
    buttons = []
    mi_devices = []
    for device in api.devices.values():
        if device.device_type == "binary_sensor":
            buttons.append(Net4HomeDeviceRefreshButton(api, entry, device))
        elif device.device_id.startswith("MI") and not device.via_device:
            # For all MI devices (WITHOUT via_device): Read Device Config Button
            # Devices with via_device are OBJ-Devices (Child-Devices) and should not be treated as MI-Devices
            # This includes all modules regardless of device_type (module, climate, rf_reader, etc.)
            _LOGGER.debug(f"[Button] Processing MI device {device.device_id}: device_type={device.device_type}, model={device.model}, module_type={device.module_type}")
            mi_devices.append(device.device_id)
            buttons.append(Net4HomeReadDeviceConfigButton(api, entry, device))
            # For RF-Reader additionally: Masterkey Learning Button
            if device.device_type == "rf_reader":
                buttons.append(Net4HomeMasterkeyLearningButton(api, entry, device))
            # For UP-LCD (PLATINE_HW_IS_LCD3): Blink and Buzzer buttons
            # Check both module_type and model name (in case module_type is not yet set)
            is_lcd3 = device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"
            if is_lcd3:
                _LOGGER.debug(f"[Button] Adding LCD buttons for {device.device_id} (module_type={device.module_type}, model={device.model})")
                buttons.append(Net4HomeLCDBlinkButton(api, entry, device))
                buttons.append(Net4HomeLCDBuzzerButton(api, entry, device))
    _LOGGER.info(f"[Button] Found {len(mi_devices)} MI devices: {mi_devices}")
    _LOGGER.info(f"[Button] Creating {len(buttons)} button entities")
    
    # Log which devices are LCD devices for debugging
    lcd_devices = [d.device_id for d in api.devices.values() if (d.module_type == PLATINE_HW_IS_LCD3 or d.model == "UP-LCD")]
    if lcd_devices:
        _LOGGER.info(f"[Button] LCD devices found: {lcd_devices}")
    else:
        _LOGGER.warning(f"[Button] No LCD devices found. Available devices: {[(d.device_id, d.model, d.module_type) for d in api.devices.values() if d.device_type == 'module']}")
    
    async_add_entities(buttons, True)

    async def async_new_device(device: Net4HomeDevice):
        """Handle new device discovery."""
        _LOGGER.debug(f"[Button] async_new_device called for {device.device_id} (type: {device.device_type}, via_device: {device.via_device})")
        if device.device_type == "binary_sensor":
            async_add_entities([Net4HomeDeviceRefreshButton(api, entry, device)])
        elif device.device_id.startswith("MI") and not device.via_device:
            # For all MI devices (WITHOUT via_device): Read Device Config Button
            # Devices with via_device are OBJ-Devices (Child-Devices) and should not be treated as MI-Devices
            # This includes all modules regardless of device_type (module, climate, rf_reader, etc.)
            _LOGGER.info(f"[Button] Adding Read Device Config button for MI device {device.device_id} ({device.model}, type: {device.device_type})")
            buttons_to_add = [Net4HomeReadDeviceConfigButton(api, entry, device)]
            # For RF-Reader additionally: Masterkey Learning Button
            if device.device_type == "rf_reader":
                buttons_to_add.append(Net4HomeMasterkeyLearningButton(api, entry, device))
            # For UP-LCD (PLATINE_HW_IS_LCD3): Blink and Buzzer buttons
            # Check both module_type and model name (in case module_type is not yet set)
            is_lcd3 = device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"
            if is_lcd3:
                _LOGGER.debug(f"[Button] Adding LCD buttons for new device {device.device_id} (module_type={device.module_type}, model={device.model})")
                buttons_to_add.append(Net4HomeLCDBlinkButton(api, entry, device))
                buttons_to_add.append(Net4HomeLCDBuzzerButton(api, entry, device))
            async_add_entities(buttons_to_add)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )
    
    # Also listen for device updates to add LCD buttons when device info becomes available
    async def async_device_updated(device_id: str = None):
        """Handle device updates - add LCD buttons if device is now identified as UP-LCD."""
        if device_id:
            device = api.devices.get(device_id)
            if device and (device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"):
                # Check if LCD buttons already exist
                # We can't easily check this, so we'll just try to add them
                # Home Assistant will ignore duplicates based on unique_id
                _LOGGER.debug(f"[Button] Device updated, checking LCD buttons for {device_id} (module_type={device.module_type}, model={device.model})")
                buttons_to_add = []
                buttons_to_add.append(Net4HomeLCDBlinkButton(api, entry, device))
                buttons_to_add.append(Net4HomeLCDBuzzerButton(api, entry, device))
                async_add_entities(buttons_to_add)
                _LOGGER.info(f"[Button] Added LCD buttons for {device_id} after device update")
    
    # Listen for device updates (when objadr is set, etc.)
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated
        )
    )

