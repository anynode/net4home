"""Helper functions for net4home device registration and entity creation."""
import logging
import glob
import os
from typing import Optional, Set, Tuple, List, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN
from .models import Net4HomeDevice

_LOGGER = logging.getLogger(__name__)


def decode_powerup_status(powerup_index: Optional[int]) -> str:
    """
    Decode the powerup status index into a readable text.
    
    Args:
        powerup_index: Powerup status index (0-4) or None
        
    Returns:
        Readable text for the powerup status
    """
    if powerup_index is None:
        return "unknown"
    
    powerup_map = {
        0: "OFF",
        1: "ON",
        2: "as before power failure",
        3: "no change",
        4: "ON at 100%",
    }
    
    return powerup_map.get(powerup_index, f"unknown ({powerup_index})")

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
    module_type: Optional[int] = None,
    ns: Optional[int] = None,
    na: Optional[int] = None,
    nm: Optional[int] = None,
    ng: Optional[int] = None,
) -> None:
    """Register a net4home device and create the corresponding entity."""
    entry_id = entry.entry_id
    device_registry = dr.async_get(hass)
    existing_devices = entry.options.get("devices", {})   # <--- AT THE TOP!

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
            "sw_version": sw_version,
            "hw_version": hw_version or "",
            "module_type": module_type,
            "ns": ns,
            "na": na,
            "nm": nm,
            "ng": ng,
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
            _LOGGER.info(f"Updated config for device {device_id} in config entry options")
        else:
            _LOGGER.debug(f"Device {device_id} already present and up-to-date in config entry options.")
        
        # Update Device Registry even if device already exists
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id.upper())}
        )
        if device_entry:
            # Update sw_version and hw_version in Device Registry
            device_registry.async_update_device(
                device_entry.id,
                sw_version=sw_version,
                hw_version=hw_version or None,
            )
            _LOGGER.debug(f"Updated Device Registry for {device_id}: sw_version={sw_version}, hw_version={hw_version}")
        
        # Ensure the device is also in api.devices (for powerup status etc.)
        if api and device_id not in api.devices:
            # Load existing detail_status from config if available
            existing_device = existing_devices.get(device_id, {})
            detail_status = existing_device.get("detail_status", "pending")
            detail_retry_count = existing_device.get("detail_retry_count", 0)
            last_detail_request_str = existing_device.get("last_detail_request")
            last_detail_request = None
            if last_detail_request_str:
                try:
                    from datetime import datetime
                    last_detail_request = datetime.fromisoformat(last_detail_request_str)
                except (ValueError, TypeError):
                    pass
            
            # Load module_type, ns, na, nm, ng from config
            module_type_loaded = existing_device.get("module_type")
            ns_loaded = existing_device.get("ns")
            na_loaded = existing_device.get("na")
            nm_loaded = existing_device.get("nm")
            ng_loaded = existing_device.get("ng")
            
            # Create device object and store it in api.devices
            device = Net4HomeDevice(
                device_id=device_id,
                name=name,
                model=model,
                device_type=device_type or "unknown",
                via_device=via_device,
                objadr=objadr,
                send_state_changes=send_state_changes,
                inverted=inverted,
                detail_status=detail_status,
                detail_retry_count=detail_retry_count,
                last_detail_request=last_detail_request,
                module_type=module_type_loaded if module_type_loaded is not None else module_type,
                ns=ns_loaded if ns_loaded is not None else ns,
                na=na_loaded if na_loaded is not None else na,
                nm=nm_loaded if nm_loaded is not None else nm,
                ng=ng_loaded if ng_loaded is not None else ng,
            )
            api.devices[device_id] = device
            _LOGGER.debug(f"Device {device_id} added to api.devices (already existing)")
        elif api and device_id in api.devices:
            # Update existing device with new module information if available
            device = api.devices[device_id]
            if module_type is not None:
                device.module_type = module_type
            if ns is not None:
                device.ns = ns
            if na is not None:
                device.na = na
            if nm is not None:
                device.nm = nm
            if ng is not None:
                device.ng = ng
        
        return

    # Register device with Home Assistant
    # via_device is NOT set here, but in the entity itself via device_info
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

    # Load existing detail_status from config if available
    existing_device = existing_devices.get(device_id, {})
    detail_status = existing_device.get("detail_status", "pending")
    detail_retry_count = existing_device.get("detail_retry_count", 0)
    last_detail_request_str = existing_device.get("last_detail_request")
    last_detail_request = None
    if last_detail_request_str:
        try:
            from datetime import datetime
            last_detail_request = datetime.fromisoformat(last_detail_request_str)
        except (ValueError, TypeError):
            pass

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
        detail_status=detail_status,
        detail_retry_count=detail_retry_count,
        last_detail_request=last_detail_request,
        module_type=module_type,
        ns=ns,
        na=na,
        nm=nm,
        ng=ng,
    )

    if api:
        api.devices[device_id] = device
    else:
        _LOGGER.warning(f"No API reference – device {device_id} not saved to internal registry")

    # Supported entity types
    known_types = {"light", "switch", "cover", "binary_sensor", "climate", "sensor", "rf_reader", "alarm_control_panel"}
    if device_type in known_types:
        _LOGGER.debug(f"Dispatching new {device_type} entity for {device_id}")
        async_dispatcher_send(hass, f"net4home_new_device_{entry_id}", device)
        # Don't request status immediately - let the detail queue handle it
        # if api:
        #     await api.async_request_status(device_id)

    # Save in config entry options
    try:
        devices = dict(entry.options.get("devices", {}))
        device_data = {
            "device_id": device.device_id,
            "name": device.name,
            "model": device.model,
            "device_type": device.device_type,
            "via_device": device.via_device,
            "send_state_changes": send_state_changes,
            "inverted": device.inverted,
            "detail_status": device.detail_status,
            "detail_retry_count": device.detail_retry_count,
            "sw_version": sw_version,
            "hw_version": hw_version or "",
            "module_type": device.module_type,
            "ns": device.ns,
            "na": device.na,
            "nm": device.nm,
            "ng": device.ng,
        }
        if device.last_detail_request:
            device_data["last_detail_request"] = device.last_detail_request.isoformat()
        devices[device_id] = device_data
        hass.config_entries.async_update_entry(entry, options={"devices": devices})
        _LOGGER.debug(f"Device {device_id} saved to config entry options")
    except Exception as e:
        _LOGGER.error(f"Failed to store device {device_id} in config entry options: {e}")


