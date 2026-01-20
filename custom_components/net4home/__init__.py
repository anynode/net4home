"""Support for net4home integration."""
import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .models import Net4HomeDevice
from .const import DOMAIN
from .api import Net4HomeApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light", "switch", "cover", "binary_sensor", "climate", "sensor", "button", "alarm_control_panel"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the net4home integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up net4home hub connection from a config entry."""
    try:
        # IP connection
        api = Net4HomeApi(
            hass=hass,
            host=entry.options.get("host", entry.data.get("host", "")),
            port=entry.options.get("port", entry.data.get("port", 3478)),
            password=entry.options.get("password", entry.data.get("password", "")),
            mi=entry.options.get("MI", entry.data.get("MI")),
            objadr=entry.options.get("OBJADR", entry.data.get("OBJADR")),
            entry_id=entry.entry_id,
            entry=entry,
        )

        stored_devices = entry.options.get("devices", {})
        from homeassistant.helpers import device_registry as dr
        
        for dev in stored_devices.values():
            # Load detail_status from config
            detail_status = dev.get("detail_status", "pending")
            detail_retry_count = dev.get("detail_retry_count", 0)
            last_detail_request_str = dev.get("last_detail_request")
            last_detail_request = None
            if last_detail_request_str:
                try:
                    from datetime import datetime
                    last_detail_request = datetime.fromisoformat(last_detail_request_str)
                except (ValueError, TypeError):
                    pass
            
            # Load sw_version, hw_version, module_type, ns, na, nm, ng from config
            sw_version = dev.get("sw_version", "")
            hw_version = dev.get("hw_version", "")
            module_type = dev.get("module_type")
            ns = dev.get("ns")
            na = dev.get("na")
            nm = dev.get("nm")
            ng = dev.get("ng")
            
            device = Net4HomeDevice(
                device_id=dev["device_id"],
                name=dev["name"],
                model=dev["model"],
                device_type=dev["device_type"],
                via_device=dev.get("via_device"),
                objadr=dev.get("objadr", int(dev["device_id"][3:]) if dev["device_id"].startswith("OBJ") else None),
                send_state_changes=dev.get("send_state_changes", False),
                detail_status=detail_status,
                detail_retry_count=detail_retry_count,
                last_detail_request=last_detail_request,
                module_type=module_type,
                ns=ns,
                na=na,
                nm=nm,
                ng=ng,
            )
            api.devices[device.device_id] = device
            _LOGGER.debug(f"Loaded device from config: {device.device_id} ({device.device_type}, detail_status: {detail_status})")
            
            # Register only modules in Device Registry on startup
            if device.device_type == "module":
                device_registry = dr.async_get(hass)
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, device.device_id.upper())},
                    manufacturer="net4home",
                    name=device.name,
                    model=device.model,
                    sw_version=sw_version,
                    hw_version=hw_version,
                    connections=set(),
                    via_device=None,
                )
                _LOGGER.debug(f"Registered module device {device.device_id} in device registry on startup (sw_version={sw_version}, hw_version={hw_version})")

        hass.data[DOMAIN][entry.entry_id] = api
        _LOGGER.info(f"Loaded {len(api.devices)} devices from config before platform setup: {[d.device_id for d in api.devices.values()]}")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info(f"Platform setup completed. Devices in API: {len(api.devices)}")

        # Diagnostics function is automatically detected by Home Assistant
        # when named async_get_config_entry_diagnostics and defined in __init__.py

        async def delayed_dispatch():
            """Delayed dispatch of new devices."""
            await asyncio.sleep(0.1)
            for device in api.devices.values():
                
                if device.device_type == "switch":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")
                    
                elif device.device_type == "cover":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")
                    
                elif device.device_type == "light":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

                elif device.device_type == "climate":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

                elif device.device_type == "sensor":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

                elif device.device_type == "binary_sensor":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

                elif device.device_type == "alarm_control_panel":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

        # asyncio.create_task(delayed_dispatch())

        _LOGGER.debug(f"List of loaded devices: {list(api.devices.keys())}")

        await api.async_connect()
        # Start listener task and store reference for proper cleanup
        api._listen_task = asyncio.create_task(api.async_listen())
        
        # Start detail queue manager for load-balanced detail queries
        await api.async_start_detail_retrieval()

        # Debug service
        async def handle_debug_devices(call):
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            api = hass.data[DOMAIN].get(target_entry_id)
            if not api:
                _LOGGER.warning(f"[net4home] No API object for entry_id {target_entry_id}")
                return
            for dev_id, dev in api.devices.items():
                _LOGGER.info(f"[net4home] Device: {dev_id} → Type: {dev.device_type}, Name: {dev.name}")

        hass.services.async_register(DOMAIN, "debug_devices", handle_debug_devices)

        # Clear devices
        async def handle_clear_devices(call):
            """Handle clear_devices service call."""
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            config_entry = hass.config_entries.async_get_entry(target_entry_id)
            if not config_entry:
                _LOGGER.warning(f"[net4home] No ConfigEntry for entry_id {target_entry_id}")
                return
            hass.config_entries.async_update_entry(config_entry, options={"devices": {}})
            _LOGGER.info(f"[net4home] Devices for entry_id {target_entry_id} cleared")

        hass.services.async_register(DOMAIN, "clear_devices", handle_clear_devices)

        # Device discovery (ENUM_ALL)
        async def handle_enum_all(call):
            """Handle enum_all service call."""
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            api = hass.data[DOMAIN].get(target_entry_id)
            if not api:
                _LOGGER.warning(f"[net4home] No API object for entry_id {target_entry_id}")
                return

            try:
                await api.send_enum_all()
                _LOGGER.info(f"[net4home] ENUM_ALL sent to bus (entry_id {target_entry_id})")
            except Exception as e:
                _LOGGER.error(f"[net4home] Error during ENUM_ALL: {e}")

        hass.services.async_register(DOMAIN, "enum_all", handle_enum_all)

        return True

    except Exception as e:
        _LOGGER.exception("Error in async_setup_entry: %s", e)
        return False


async def options_update_listener1(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> None:
    """Reload net4home config entry due to options change."""
    _LOGGER.debug("Reload net4home config entry due to options change")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["skip_disconnect"] = True
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop detail queue manager
    api = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if api:
        await api.async_stop_detail_retrieval()
    
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        skip_disconnect = hass.data[DOMAIN].pop("skip_disconnect", False)
        hub: Net4HomeApi = hass.data[DOMAIN].pop(entry.entry_id)

        if not skip_disconnect:
            _LOGGER.info("Unload: Closing connection to bus")
            await hub.async_disconnect()
        else:
            _LOGGER.debug("Unload: Connection remains open (reload due to options)")

        if callable(getattr(hub, "async_stop", None)):
            await hub.async_stop()

    return unload_ok


