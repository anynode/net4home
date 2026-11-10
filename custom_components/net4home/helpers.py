"""Helper functions for net4home device registration and entity creation."""
import logging
from typing import Optional, Set, Tuple, List, Dict

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN
from .models import Net4HomeDevice

_LOGGER = logging.getLogger(__name__)


def bus_connected(api) -> bool:
    """True while the bus connector connection is up."""
    return bool(getattr(api, "connected", False))


def ensure_connected(api) -> None:
    """Refuse a command instead of dropping it silently."""
    if not bus_connected(api):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )


def listen_connection(entity) -> None:
    """Write the entity state when the bus connection goes up or down."""

    @callback
    def _changed(_connected: bool) -> None:
        entity.async_write_ha_state()

    entity.async_on_remove(
        async_dispatcher_connect(entity.hass, entity.api.connection_signal, _changed)
    )


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


def registry_device_id(
    hass: HomeAssistant,
    config_entry_id: str,
    device_id: str | None,
) -> str | None:
    """Return the device-registry id for a net4home device id."""
    if not device_id:
        return None
    try:
        return dr.async_get_device_id_by_identifier(
            hass,
            (DOMAIN, device_id.upper()),
            config_entry_id=config_entry_id,
        )
    except ValueError:
        return None


def parent_device_link(
    hass: HomeAssistant,
    config_entry_id: str,
    parent_device_id: str | None,
) -> dict[str, str]:
    """DeviceInfo kwargs that link a child to its parent module.

    Home Assistant 2026.8 no longer accepts ``via_device``. The value is the
    registry id of the parent, looked up from our own module id.
    """
    parent_id = registry_device_id(hass, config_entry_id, parent_device_id)
    if parent_id is None:
        if parent_device_id:
            _LOGGER.warning(
                "Parent device %s is not in the device registry yet",
                parent_device_id,
            )
        return {}
    return {"via_device_id": parent_id}


def ensure_registry_device(
    hass: HomeAssistant,
    entry,
    device_id: str,
    *,
    name: str | None = None,
    model: str | None = None,
    sw_version: str | None = None,
    hw_version: str | None = None,
    via_device: str | None = None,
) -> str:
    """Register a device and return its registry id.

    A parent module is registered before the child that links to it.
    """
    parent_registry_id = None
    if via_device and via_device.upper() != device_id.upper():
        if registry_device_id(hass, entry.entry_id, via_device) is None:
            ensure_registry_device(hass, entry, via_device)
        parent_registry_id = registry_device_id(hass, entry.entry_id, via_device)

    kwargs = {}
    if parent_registry_id:
        kwargs["via_device_id"] = parent_registry_id
    if sw_version is not None:
        kwargs["sw_version"] = sw_version
    if hw_version is not None:
        kwargs["hw_version"] = hw_version

    created = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id.upper())},
        manufacturer="net4home",
        name=name or device_id.upper(),
        model=model,
        **kwargs,
    )
    return created.id


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
    timer_time1: Optional[int] = None,
) -> None:
    """Register a net4home device and create the corresponding entity."""
    entry_id = entry.entry_id
    existing_devices = entry.options.get("devices", {})   # <--- AT THE TOP!
    ensure_registry_device(
        hass,
        entry,
        device_id,
        name=name,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
        via_device=via_device,
    )

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
        if timer_time1 is not None:
            new_config["timer_time1"] = timer_time1
        # Compare all fields that might change. None must not wipe a stored value.
        for key, val in new_config.items():
            if val is None:
                continue
            if current.get(key) != val:
                updated = True
                current[key] = val  # Update the changed field

        if updated:
            devices = dict(entry.options.get("devices", {}))
            stored = dict(devices.get(device_id, current))
            for key, val in new_config.items():
                if val is None:
                    continue
                stored[key] = val
            devices[device_id] = stored
            options = dict(entry.options)
            options["devices"] = devices
            hass.config_entries.async_update_entry(entry, options=options)
            _LOGGER.info(f"Updated config for device {device_id} in config entry options")
        else:
            _LOGGER.debug(f"Device {device_id} already present and up-to-date in config entry options.")

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
            
            # Load module_type, ns, na, nm, ng, timer_time1 from config
            module_type_loaded = existing_device.get("module_type")
            ns_loaded = existing_device.get("ns")
            na_loaded = existing_device.get("na")
            nm_loaded = existing_device.get("nm")
            ng_loaded = existing_device.get("ng")
            timer_time1_loaded = timer_time1 if timer_time1 is not None else existing_device.get("timer_time1")

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
                timer_time1=timer_time1_loaded,
            )
            device.sw_version = sw_version or None
            device.powerup_status = existing_device.get("powerup_status")
            device.min_hell = existing_device.get("min_hell")
            api.devices[device_id] = device
            _LOGGER.debug(f"Device {device_id} added to api.devices (already existing)")
        elif api and device_id in api.devices:
            # Update existing device with new module information if available
            device = api.devices[device_id]
            previous_type = device.device_type
            device.send_state_changes = send_state_changes
            if device_type and device.device_type != device_type:
                device.device_type = device_type
            if model:
                device.model = model
            if sw_version:
                device.sw_version = sw_version
            if timer_time1 is not None:
                device.timer_time1 = timer_time1
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
            if previous_type == "switch" and device.device_type == "light":
                remove_actor_switch_entity(hass, entry_id, device)
                async_dispatcher_send(hass, f"net4home_new_device_{entry_id}", device)

        return

    _LOGGER.debug("Registered new device: %s / %s", device_type or "unknown", device_id)

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
        timer_time1=timer_time1,
    )
    device.sw_version = sw_version or None
    device.powerup_status = existing_device.get("powerup_status")
    device.min_hell = existing_device.get("min_hell")

    if api:
        api.devices[device_id] = device
    else:
        _LOGGER.warning(f"No API reference – device {device_id} not saved to internal registry")

    # Supported entity types (include "module" so MI-only devices like HS-PaketRouter get the Read Device button)
    known_types = {"light", "switch", "cover", "binary_sensor", "climate", "sensor", "rf_reader", "alarm_control_panel", "module"}
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
            "objadr": device.objadr,
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
        if timer_time1 is not None:
            device_data["timer_time1"] = timer_time1
        devices[device_id] = device_data
        options = dict(entry.options)
        options["devices"] = devices
        hass.config_entries.async_update_entry(entry, options=options)
        _LOGGER.debug(f"Device {device_id} saved to config entry options")
    except Exception as e:
        _LOGGER.error(f"Failed to store device {device_id} in config entry options: {e}")


def actor_switch_unique_id(entry_id: str, via_device: str | None, device_id: str) -> str:
    """Unique id of the switch entity that used to represent this channel."""
    from homeassistant.util import slugify

    via = (via_device or "unknown").lower()
    return f"{entry_id}_{slugify(via)}_{slugify(device_id)}"


def remove_actor_switch_entity(hass: HomeAssistant, entry_id: str, device) -> None:
    """Drop the switch entity when a dimmer timer channel becomes a light."""
    from homeassistant.helpers import entity_registry as er

    unique_id = actor_switch_unique_id(entry_id, device.via_device, device.device_id)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("switch", DOMAIN, unique_id)
    if not entity_id:
        return
    registry.async_remove(entity_id)
    _LOGGER.info("Removed switch %s, the channel is a dimmer light now", entity_id)


def migrate_dimmer_timers(hass: HomeAssistant, entry, api) -> None:
    """Timer channels of a dimmer are lights. Stored switches are converted once."""
    from .dimmer_layout import is_dimmer_module

    devices = dict(entry.options.get("devices", {}))
    changed = False
    for device in list(api.devices.values()):
        if device.model != "Timer" or device.device_type != "switch":
            continue
        parent = api.devices.get((device.via_device or "").upper())
        if parent is None or not is_dimmer_module(parent.model):
            continue
        device.device_type = "light"
        remove_actor_switch_entity(hass, entry.entry_id, device)
        stored = devices.get(device.device_id)
        if stored and stored.get("device_type") != "light":
            stored = dict(stored)
            stored["device_type"] = "light"
            devices[device.device_id] = stored
            changed = True
            _LOGGER.info("%s timer channel is a dimmer light", device.device_id)
    if not changed:
        return
    options = dict(entry.options)
    options["devices"] = devices
    hass.config_entries.async_update_entry(entry, options=options)


