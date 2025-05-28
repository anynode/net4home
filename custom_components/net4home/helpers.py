"""Helper functions for net4home device registration and entity creation."""
import asyncio  
import logging

from typing import Optional, Set, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
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
) -> None:
    """Register a device and dispatch a corresponding entity if applicable."""
    entry_id = entry.entry_id
    device_registry = dr.async_get(hass)

    if api and device_id in api.devices:
        _LOGGER.debug(f"Device {device_id} already known, looking for changes")
        existing_device = api.devices[device_id]
        existing_device.name = name
        existing_device.device_type = device_type or existing_device.device_type
        return  

    connections: Set[Tuple[str, str]] = set()

    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="net4home",
        name=name,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        connections=connections,
    )

    _LOGGER.info(f"Registered a new device: {device_type} / {device_id}")

    device = Net4HomeDevice(
        device_id=device_id,
        name=name,
        model=model,
        device_type=device_type or "unknown",
        via_device=via_device,
        objadr=objadr
    )

    if api:
        api.devices[device_id] = device
    else:
        _LOGGER.warning(f"API reference missing – device {device_id} will not be saved")

    if device_type == "switch":
        _LOGGER.debug(f"Prepare switch entity: {device_id}")
        async_dispatcher_send(hass, f"net4home_new_device_{entry_id}", device)
        if api:
            await api.async_request_status(device_id)

    if device_type == "cover":
        _LOGGER.debug(f"Prepare cover entity: {device_id}")
        async_dispatcher_send(hass, f"net4home_new_device_{entry_id}", device)
        if api:
            await api.async_request_status(device_id)


    try:
        devices = dict(entry.options.get("devices", {}))
        devices[device_id] = {
            "device_id": device.device_id,
            "name": device.name,
            "model": device.model,
            "device_type": device.device_type,
            "via_device": device.via_device,
        }
        hass.config_entries.async_update_entry(entry, options={"devices": devices})
        _LOGGER.debug(f"Device {device_id} permanently saved")
    except Exception as e:
        _LOGGER.error(f"Error while saving details for device {device_id} in entry.options: {e}")
