"""Helper functions for net4home device registration and entity creation."""
import logging
from typing import Optional, Set, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .models import Net4HomeDevice

_LOGGER = logging.getLogger(__name__)

async def register_device_in_registry(
    hass: HomeAssistant,
    entry,
    device_id: str,
    name: str,
    model: str,
    sw_version: str,
    hw_version: Optional[str] = None,
    device_type: Optional[str] = None,
    via_device: Optional[str] = None,
    api: Optional[object] = None,
    objadr: Optional[int] = None,
    send_state_changes: bool = False,
    inverted: Optional[bool] = False,
) -> None:
    """Register a net4home device and create the corresponding entity."""
    entry_id = entry.entry_id
    device_registry = dr.async_get(hass)
    existing_devices = entry.options.get("devices", {})   # <--- GANZ OBEN!

    # Check, if the device is already in internal registry object
    # if api and device_id in api.devices:
    #    _LOGGER.debug(f"Device {device_id} already registered internally, skipping registration.")
    #    return

    if device_id in existing_devices:
        # Device already exists, check for changes
        updated = False
        current = existing_devices[device_id]
        new_config = {
            "device_id": device_id,
            "name": name,
            "model": model,
            "device_type": device_type or "unknown",
            "via_device": via_device,
            "send_state_changes": send_state_changes,
            "inverted": inverted,
        }
        # Compare all fields that might change
        for key, val in new_config.items():
            if current.get(key) != val:
                updated = True
                current[key] = val  # Update the changed field

        if updated:
            devices = dict(existing_devices)
            devices[device_id] = current
            hass.config_entries.async_update_entry(entry, options={"devices": devices})
            _LOGGER.info(f"Updated config for device {device_id} (e.g., inverted={inverted}) in config entry options")
        else:
            _LOGGER.debug(f"Device {device_id} already present and up-to-date in config entry options.")
        return

    # Register device with Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="net4home",
        name=name,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        connections=set(),
    )

    _LOGGER.info(f"Registered new device: {device_type or 'unknown'} / {device_id}")

    # Register internally
    device = Net4HomeDevice(
        device_id=device_id,
        name=name,
        model=model,
        device_type=device_type or "unknown",
        via_device=via_device,
        objadr=objadr,
        send_state_changes=send_state_changes,
        inverted=inverted,
    )

    if api:
        api.devices[device_id] = device
    else:
        _LOGGER.warning(f"No API reference – device {device_id} not saved to internal registry")

    # Supported entity types
    known_types = {"light", "switch", "cover", "binary_sensor", "climate", "sensor"}
    if device_type in known_types:
        _LOGGER.debug(f"Dispatching new {device_type} entity for {device_id}")
        async_dispatcher_send(hass, f"net4home_new_device_{entry_id}", device)
        if api:
            await api.async_request_status(device_id)

    # Save in config entry options
    try:
        devices = dict(entry.options.get("devices", {}))
        devices[device_id] = {
            "device_id": device.device_id,
            "name": device.name,
            "model": device.model,
            "device_type": device.device_type,
            "via_device": device.via_device,
            "send_state_changes": send_state_changes,
            "inverted": device.inverted,
        }
        hass.config_entries.async_update_entry(entry, options={"devices": devices})
        _LOGGER.debug(f"Device {device_id} saved to config entry options")
    except Exception as e:
        _LOGGER.error(f"Failed to store device {device_id} in config entry options: {e}")

