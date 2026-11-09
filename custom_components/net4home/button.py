from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import callback
from homeassistant.util import slugify
from .api import Net4HomeApi, Net4HomeDevice

from .alarm_extras import alarm_unchecked_buttons
from .bell import extra_bell_buttons
from .bell_layout import is_wav_bell
from .const import DOMAIN, PLATINE_HW_IS_LCD3
from .helpers import parent_device_link

import logging
_LOGGER = logging.getLogger(__name__)

class Net4HomeDeviceRefreshButton(ButtonEntity):
    """Button entity for refreshing device status."""

    _attr_should_poll = False
    
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

    _attr_should_poll = False
    
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


class Net4HomeClearRfKeysButton(ButtonEntity):
    """Button that deletes every key stored in an UP-RF module."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:key-remove"

    def __init__(self, api, entry, device):
        """Initialize the delete-all button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Alle Schlüssel löschen"
        self._attr_unique_id = f"{entry.entry_id}_rf_keys_clear_{slugify(device.device_id)}"

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
        """Delete all stored keys."""
        await self.api.async_clear_all_rf_keys(self.device.device_id)


class Net4HomeReadDeviceConfigButton(ButtonEntity):
    """Button entity for reading device configuration (same for all MI modules: UP-T, UP-TLH, etc.)."""

    _attr_should_poll = False

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


class Net4HomeResetModuleButton(ButtonEntity):
    """Reboot one MI module, the same command as Reset in the configurator."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart"

    def __init__(self, api, entry, device):
        """Initialize the reset button."""
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Reset Device"
        self._attr_unique_id = f"{entry.entry_id}_reset_module_{slugify(device.device_id)}"

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
        translated_label = translations.get("reset_device", "Reset Device")
        self._attr_name = f"{self.device.name} {translated_label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Reboot this module."""
        await self.api.async_reset_module(self.device.device_id)


class Net4HomeBellOnButton(ButtonEntity):
    """Button entity for WAV-Bell EIN (On)."""

    _attr_should_poll = False

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

    _attr_should_poll = False

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

    _attr_should_poll = False

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

    _attr_should_poll = False

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

    _attr_should_poll = False
    
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
        """Blink the backlight. The display keeps the text it already shows."""
        await self.api.async_send_lcd_text(
            self.device.device_id,
            "",
            light=True,
            blink=True,
            clear=False,
        )


class Net4HomeLCDBuzzerButton(ButtonEntity):
    """Button entity for LCD buzzer control."""

    _attr_should_poll = False
    
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
        """Sound the buzzer and switch the backlight on."""
        await self.api.async_send_lcd_text(
            self.device.device_id,
            "",
            light=True,
            buzzer=True,
            clear=False,
            blink=False,
        )


class Net4HomeLCDConfirmButton(ButtonEntity):
    """Stop a running buzzer or blink and return the display to its idle screen."""

    _attr_should_poll = False

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:check"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Bestätigen"
        self._attr_unique_id = f"{entry.entry_id}_lcd_confirm_{slugify(device.device_id)}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id.upper())},
            name=self.device.name,
            manufacturer="net4home",
            model=self.device.model,
            **parent_device_link(self.hass, self.entry.entry_id, self.device.via_device),
        )

    async def async_press(self) -> None:
        """Clear the text and press OK, which is what stops the buzzer."""
        await self.api.async_acknowledge_lcd(self.device.device_id)


def _lcd_buttons(api, entry, device):
    return [
        Net4HomeLCDBlinkButton(api, entry, device),
        Net4HomeLCDBuzzerButton(api, entry, device),
        Net4HomeLCDConfirmButton(api, entry, device),
    ]


class Net4HomeExtLdUnlockBuzzButton(ButtonEntity):
    """EXT-LD: Entriegeln und Summen (D0_SET 4). Opens the door, so it is not a plain toggle."""

    _attr_should_poll = False

    _attr_icon = "mdi:lock-open-variant"

    def __init__(self, api, entry, device):
        self.api = api
        self.entry = entry
        self.device = device
        self._attr_name = f"{device.name} Entriegeln und Summen"
        self._attr_unique_id = f"{entry.entry_id}_ext_ld_unlock_buzz_{slugify(device.device_id)}"

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

    async def async_press(self) -> None:
        await self.api.async_unlock_ext_ld_buzz(self.device.device_id)


def _bell_buttons(api, entry, device):
    """EIN/AUS/LAUTER/LEISER plus Klingeln, Abspielen, silent on/off and mute."""
    return [
        Net4HomeBellOnButton(api, entry, device),
        Net4HomeBellOffButton(api, entry, device),
        Net4HomeBellVolumeUpButton(api, entry, device),
        Net4HomeBellVolumeDownButton(api, entry, device),
        *extra_bell_buttons(api, entry, device),
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up net4home button entities."""
    api: Net4HomeApi = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"[Button] Setup called with {len(api.devices)} devices in API")
    buttons = []
    bell_seen: set[str] = set()

    def _take_bell(device):
        if not is_wav_bell(device) or device.device_id in bell_seen:
            return []
        bell_seen.add(device.device_id)
        return _bell_buttons(api, entry, device)

    mi_devices = []
    for device in api.devices.values():
        if device.device_type == "lock":
            buttons.append(Net4HomeExtLdUnlockBuzzButton(api, entry, device))
        if device.device_type == "binary_sensor":
            buttons.append(Net4HomeDeviceRefreshButton(api, entry, device))
        elif device.device_id.startswith("MI") and not device.via_device:
            # For all MI devices (WITHOUT via_device): Read Device Config Button
            # Devices with via_device are OBJ-Devices (Child-Devices) and should not be treated as MI-Devices
            # This includes all modules regardless of device_type (module, climate, rf_reader, etc.)
            _LOGGER.debug(f"[Button] Processing MI device {device.device_id}: device_type={device.device_type}, model={device.model}, module_type={device.module_type}")
            mi_devices.append(device.device_id)
            buttons.append(Net4HomeReadDeviceConfigButton(api, entry, device))
            buttons.append(Net4HomeResetModuleButton(api, entry, device))
            # For RF-Reader additionally: Masterkey Learning Button
            if device.device_type == "rf_reader":
                buttons.append(Net4HomeMasterkeyLearningButton(api, entry, device))
                buttons.append(Net4HomeClearRfKeysButton(api, entry, device))
            # For UP-LCD (PLATINE_HW_IS_LCD3): Blink and Buzzer buttons
            # Check both module_type and model name (in case module_type is not yet set)
            is_lcd3 = device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"
            if is_lcd3:
                _LOGGER.debug(f"[Button] Adding LCD buttons for {device.device_id} (module_type={device.module_type}, model={device.model})")
                buttons.extend(_lcd_buttons(api, entry, device))
            buttons.extend(_take_bell(device))
            if device.model == "HS-Safety" and device.device_type == "alarm_control_panel":
                buttons.extend(alarm_unchecked_buttons(api, entry, device))
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
        if device.device_type == "lock":
            async_add_entities([Net4HomeExtLdUnlockBuzzButton(api, entry, device)])
        if device.device_type == "binary_sensor":
            async_add_entities([Net4HomeDeviceRefreshButton(api, entry, device)])
        elif device.device_id.startswith("MI") and not device.via_device:
            # For all MI devices (WITHOUT via_device): Read Device Config Button
            # Devices with via_device are OBJ-Devices (Child-Devices) and should not be treated as MI-Devices
            # This includes all modules regardless of device_type (module, climate, rf_reader, etc.)
            _LOGGER.info(f"[Button] Adding Read Device Config button for MI device {device.device_id} ({device.model}, type: {device.device_type})")
            buttons_to_add = [
                Net4HomeReadDeviceConfigButton(api, entry, device),
                Net4HomeResetModuleButton(api, entry, device),
            ]
            # For RF-Reader additionally: Masterkey Learning Button
            if device.device_type == "rf_reader":
                buttons_to_add.append(Net4HomeMasterkeyLearningButton(api, entry, device))
                buttons_to_add.append(Net4HomeClearRfKeysButton(api, entry, device))
            # For UP-LCD (PLATINE_HW_IS_LCD3): Blink and Buzzer buttons
            # Check both module_type and model name (in case module_type is not yet set)
            is_lcd3 = device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"
            if is_lcd3:
                _LOGGER.debug(f"[Button] Adding LCD buttons for new device {device.device_id} (module_type={device.module_type}, model={device.model})")
                buttons_to_add.extend(_lcd_buttons(api, entry, device))
            buttons_to_add.extend(_take_bell(device))
            if device.model == "HS-Safety" and device.device_type == "alarm_control_panel":
                buttons_to_add.extend(alarm_unchecked_buttons(api, entry, device))
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
                    buttons_to_add = _lcd_buttons(api, entry, device)
                    async_add_entities(buttons_to_add)
                    _LOGGER.info(f"[Button] Added LCD buttons for {device_id} after device update")
                else:
                    fresh = _take_bell(device)
                    if fresh:
                        async_add_entities(fresh)
                        _LOGGER.info("[Button] Added WAV-Bell buttons for %s after device update", device_id)
    
    # Listen for device updates (when objadr is set, etc.)
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"net4home_device_updated_{entry.entry_id}", async_device_updated
        )
    )

