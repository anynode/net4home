"""Diagnostics support for net4home integration."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN
from .helpers import decode_powerup_status


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for the net4home config entry."""
    api = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)

    if not api:
        return {
            "error": "API not available",
            "entry_id": config_entry.entry_id,
        }

    # Gather device info and other relevant data
    devices_info = {}
    device_options = config_entry.options.get("devices", {})

    for device_id, device in api.devices.items():
        dev_opts = device_options.get(device_id, {})
        powerup_status = getattr(device, "powerup_status", None)
        powerup_status_text = decode_powerup_status(powerup_status) if powerup_status is not None else None
        
        device_info = {
            "name": device.name,
            "model": device.model,
            "device_type": device.device_type,
            "via_device": device.via_device or "",
            "objadr": device.objadr,
            "inverted": dev_opts.get("inverted", getattr(device, "inverted", False)),
            "send_state_changes": dev_opts.get("send_state_changes", getattr(device, "send_state_changes", False)),
            "detail_status": getattr(device, "detail_status", "unknown"),
            "detail_retry_count": getattr(device, "detail_retry_count", 0),
        }
        
        # Add powerup status only for actors (switch, light) - NOT for cover (covers do not support powerup)
        if device.device_type in ("switch", "light"):
            device_info["powerup_status"] = powerup_status_text
            device_info["powerup_status_index"] = powerup_status
            # Also show when powerup status has not been set yet
            if powerup_status is None:
                device_info["powerup_status_note"] = "Not yet read (D0_RD_ACTOR_DATA_ACK not received)"
        
        devices_info[device_id] = device_info

    # Connection status
    connection_status = {
        "connected": api._writer is not None and api._reader is not None,
        "host": api._host,
        "port": api._port,
        "mi": api._mi,
        "objadr": api._objadr,
        "reconnect_enabled": getattr(api, "_reconnect_enabled", True),
    }

    # Config entry info
    config_info = {
        "entry_id": config_entry.entry_id,
        "title": config_entry.title,
        "version": config_entry.version,
        "domain": config_entry.domain,
        "source": config_entry.source,
    }

    data = {
        "config_entry": config_info,
        "connection": connection_status,
        "devices": {
            "count": len(devices_info),
            "list": devices_info,
        },
        "statistics": {
            "total_devices": len(api.devices),
            "devices_by_type": {},
        },
    }

    # Count devices by type
    for device in api.devices.values():
        device_type = device.device_type
        data["statistics"]["devices_by_type"][device_type] = data["statistics"]["devices_by_type"].get(device_type, 0) + 1

    # Redact sensitive info like passwords
    return async_redact_data(data, ("connection.password",))
