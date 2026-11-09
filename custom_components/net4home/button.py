from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import callback
from homeassistant.util import slugify
from .api import Net4HomeApi, Net4HomeDevice

from .const import DOMAIN, PLATINE_HW_IS_LCD3, PLATINE_HW_IS_BELL2, CI_LCD_OPT_BLINK, CI_LCD_OPT_BUZZER_ON
from .helpers import parent_device_link

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
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
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
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_press(self) -> None:
        """Handle the button press to start Masterkey learning."""
        await self.api.async_start_masterkey_learning(self.device.device_id)


class Net4HomeReadDeviceConfigButton(ButtonEntity):
    """Button entity for reading device configuration (same for all MI modules: UP-T, UP-TLH, etc.)."""

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
    def available(self) -> bool:
        """Return True if the device is still in the API so the button is pressable."""
        return self.api.get_known_device(self.device.device_id) is not None

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
        """Set up translations when entity is added to Home Assistant."""
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        translated_label = translations.get("read_device", "Read Device")
        self._attr_name = f"{self.device.name} {translated_label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press to read device configuration."""
        await self.api.async_read_device_config(self.device.device_id)


class Net4HomeBellOnButton(ButtonEntity):
    """Button entity for WAV-Bell EIN (On)."""

    _attr_icon = "mdi:bell-check"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} EIN"
        self._attr_unique_id = f"{entry.entry_id}_bell_on_{slugify(device.device_id)}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        label = translations.get("bell_on", "EIN")
        self._attr_name = f"{self.device.name} {label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await self.api.async_send_bell_command(self.device.device_id, "ON")


class Net4HomeBellOffButton(ButtonEntity):
    """Button entity for WAV-Bell AUS (Off)."""

    _attr_icon = "mdi:bell-off"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} AUS"
        self._attr_unique_id = f"{entry.entry_id}_bell_off_{slugify(device.device_id)}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        label = translations.get("bell_off", "AUS")
        self._attr_name = f"{self.device.name} {label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await self.api.async_send_bell_command(self.device.device_id, "OFF")


class Net4HomeBellVolumeUpButton(ButtonEntity):
    """Button entity for WAV-Bell LAUTER (Volume Up)."""

    _attr_icon = "mdi:volume-plus"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} LAUTER"
        self._attr_unique_id = f"{entry.entry_id}_bell_vol_up_{slugify(device.device_id)}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        label = translations.get("bell_vol_up", "LAUTER")
        self._attr_name = f"{self.device.name} {label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await self.api.async_send_bell_command(self.device.device_id, "INC_VOL")


class Net4HomeBellVolumeDownButton(ButtonEntity):
    """Button entity for WAV-Bell LEISER (Volume Down)."""

    _attr_icon = "mdi:volume-minus"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} LEISER"
        self._attr_unique_id = f"{entry.entry_id}_bell_vol_down_{slugify(device.device_id)}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    @property
    def available(self) -> bool:
        return self.api.get_known_device(self.device.device_id) is not None

    async def async_added_to_hass(self):
        translations = await async_get_translations(self.hass, DOMAIN, "button")
        label = translations.get("bell_vol_down", "LEISER")
        self._attr_name = f"{self.device.name} {label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await self.api.async_send_bell_command(self.device.device_id, "DEC_VOL")


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
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
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
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
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
            # For WAV-Bell (PLATINE_HW_IS_BELL2): EIN/AUS/LAUTER/LEISER buttons
            is_wav_bell = device.module_type == PLATINE_HW_IS_BELL2 or device.model == ".WAV-Bell"
            if is_wav_bell:
                _LOGGER.debug(f"[Button] Adding WAV-Bell buttons for {device.device_id} (module_type={device.module_type}, model={device.model})")
                buttons_to_add.append(Net4HomeBellOnButton(api, entry, device))
                buttons_to_add.append(Net4HomeBellOffButton(api, entry, device))
                buttons_to_add.append(Net4HomeBellVolumeUpButton(api, entry, device))
                buttons_to_add.append(Net4HomeBellVolumeDownButton(api, entry, device))
            async_add_entities(buttons_to_add)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_new_device_{entry.entry_id}", async_new_device
        )
    )
    
    # Also listen for device updates to add LCD or WAV-Bell buttons when device info becomes available
    async def async_device_updated(device_id: str = None):
        """Handle device updates - add LCD or WAV-Bell buttons when objadr etc. becomes available."""
        if device_id:
            device = api.get_known_device(device_id)
            if not device:
                device = api.devices.get(device_id)
            if device:
                if device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD":
                    _LOGGER.debug(f"[Button] Device updated, adding LCD buttons for {device_id}")
                    buttons_to_add = [
                        Net4HomeLCDBlinkButton(api, entry, device),
                        Net4HomeLCDBuzzerButton(api, entry, device),
                    ]
                    async_add_entities(buttons_to_add)
                    _LOGGER.info(f"[Button] Added LCD buttons for {device_id} after device update")
                elif device.module_type == PLATINE_HW_IS_BELL2 or device.model == ".WAV-Bell":
                    _LOGGER.debug(f"[Button] Device updated, adding WAV-Bell buttons for {device_id}")
                    buttons_to_add = [
                        Net4HomeBellOnButton(api, entry, device),
                        Net4HomeBellOffButton(api, entry, device),
                        Net4HomeBellVolumeUpButton(api, entry, device),
                        Net4HomeBellVolumeDownButton(api, entry, device),
                    ]
                    async_add_entities(buttons_to_add)
                    _LOGGER.info(f"[Button] Added WAV-Bell buttons for {device_id} after device update")
    
    # Listen for device updates (when objadr is set, etc.)
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated
        )
    )

