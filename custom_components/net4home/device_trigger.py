"""Device triggers for net4home integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN

# Trigger types
TRIGGER_TYPE_RF_KEY_SHORT_HOLD = "rf_key_short_hold"
TRIGGER_TYPE_RF_KEY_LONG_HOLD = "rf_key_long_hold"
TRIGGER_TYPE_RF_KEY_REMOVED_AFTER_SHORT = "rf_key_removed_after_short"
TRIGGER_TYPE_RF_KEY_ANY = "rf_key_any"

TRIGGER_TYPES = {
    TRIGGER_TYPE_RF_KEY_SHORT_HOLD,
    TRIGGER_TYPE_RF_KEY_LONG_HOLD,
    TRIGGER_TYPE_RF_KEY_REMOVED_AFTER_SHORT,
    TRIGGER_TYPE_RF_KEY_ANY,
}

# Trigger descriptions will be loaded from translations

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional("rf_key"): str,  # Optional: specific RF-Key code
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for net4home devices."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        raise InvalidDeviceAutomationConfig(f"Device {device_id} not found")

    # Check if this is an RF-Reader device
    if device.model not in ("UP-RF", "UP-RF-S4AR1"):
        return []

    # Load translations
    translations = await async_get_translations(hass, DOMAIN, "device_automation")
    
    triggers = []
    for trigger_type in TRIGGER_TYPES:
        # Get translated description
        translation_key = f"trigger_type.{trigger_type}"
        description = translations.get(translation_key, trigger_type)
        
        trigger_dict = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            "name": description,
            "description": description,
        }
        triggers.append(trigger_dict)

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    # Load translations
    translations = await async_get_translations(hass, DOMAIN, "device_automation")
    rf_key_description = translations.get("extra_fields.rf_key", "Optional: Specific RF-Key code (e.g., 0105F469E9)")
    
    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional("rf_key", description=rf_key_description): str,
            }
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: callable,
    trigger_info: dict,
) -> callable:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    device_id = config[CONF_DEVICE_ID]
    rf_key_filter = config.get("rf_key")

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        raise InvalidDeviceAutomationConfig(f"Device {device_id} not found")

    # Extract device_id from identifiers (e.g., "MI0099" from identifiers)
    device_identifier = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            device_identifier = identifier[1]
            break

    if not device_identifier:
        raise InvalidDeviceAutomationConfig(f"Device {device_id} has no net4home identifier")

    @callback
    def handle_event(event):
        """Handle the RF key event."""
        event_data = event.data

        # Check if event is for this device
        # device_id can be either uppercase or lowercase, normalize for comparison
        event_device_id = event_data.get("device_id", "").upper()
        if event_device_id != device_identifier.upper():
            return

        # Check trigger type
        state = event_data.get("state")
        if trigger_type == TRIGGER_TYPE_RF_KEY_SHORT_HOLD and state != "short_hold":
            return
        if trigger_type == TRIGGER_TYPE_RF_KEY_LONG_HOLD and state != "long_hold":
            return
        if trigger_type == TRIGGER_TYPE_RF_KEY_REMOVED_AFTER_SHORT and state != "removed_after_short":
            return
        # TRIGGER_TYPE_RF_KEY_ANY matches all states

        # Check RF-Key filter if specified
        if rf_key_filter and event_data.get("rf_key") != rf_key_filter:
            return

        # Trigger the action (action is a coroutine, so we need to schedule it)
        hass.async_run_job(
            action,
            {
                "trigger": {
                    **config,
                    "description": f"RF-Key {event_data.get('rf_key')} ({state})",
                    "rf_key": event_data.get("rf_key"),
                    "state": state,
                    "device_name": event_data.get("device_name"),
                }
            }
        )

    return hass.bus.async_listen("net4home_rf_key_detected", handle_event)
