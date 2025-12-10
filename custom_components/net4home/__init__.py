"""Support for net4home integration."""
import asyncio
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .models import Net4HomeDevice
from .const import DOMAIN
from .api import Net4HomeApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = ["light", "switch", "cover", "binary_sensor", "climate", "sensor"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    try:
        api = Net4HomeApi(
            hass=hass,
            host=entry.options.get("host", entry.data["host"]),
            port=entry.options.get("port", entry.data["port"]),
            password=entry.options.get("password", entry.data["password"]),
            mi=entry.options.get("MI", entry.data.get("MI")),
            objadr=entry.options.get("OBJADR", entry.data.get("OBJADR")),
            entry_id=entry.entry_id,
            entry=entry,
        )

        stored_devices = entry.options.get("devices", {})
        for dev in stored_devices.values():
            device = Net4HomeDevice(
                device_id=dev["device_id"],
                name=dev["name"],
                model=dev["model"],
                device_type=dev["device_type"],
                via_device=dev.get("via_device"),
                objadr=dev.get("objadr", int(dev["device_id"][3:]) if dev["device_id"].startswith("OBJ") else None),
                send_state_changes=dev.get("send_state_changes", False), 
            )
            api.devices[device.device_id] = device
            _LOGGER.debug(f"Loaded device from config: {device.device_id} ({device.device_type})")

        hass.data[DOMAIN][entry.entry_id] = api
        
        # Register options update listener
        entry.async_on_unload(
            entry.add_update_listener(options_update_listener1)
        )
        
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        #diagnostics.async_register_diagnostics(
        #    hass,
        #    DOMAIN,
        #    entry.entry_id,
        #    async_get_diagnostics
        #)

        async def delayed_dispatch():
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

        # asyncio.create_task(delayed_dispatch())

        _LOGGER.debug(f"List of loaded devices: {list(api.devices.keys())}")

        await api.async_connect()
        api._listen_task = asyncio.create_task(api.async_listen())

        async def delayed_status_request(device_id: str, delay: float):
            await asyncio.sleep(delay)
            await api.async_request_status(device_id)

        for idx, device in enumerate(api.devices.values()):
            if device.device_type == "switch":
                delay_seconds = idx * 0.2  # 200ms delay
                asyncio.create_task(delayed_status_request(device.device_id, delay_seconds))

        # Debug-Service
        async def handle_debug_devices(call):
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            api = hass.data[DOMAIN].get(target_entry_id)
            if not api:
                _LOGGER.warning(f"[net4home] Kein API-Objekt für entry_id {target_entry_id}")
                return
            for dev_id, dev in api.devices.items():
                _LOGGER.info(f"[net4home] Gerät: {dev_id} → Typ: {dev.device_type}, Name: {dev.name}")

        hass.services.async_register(DOMAIN, "debug_devices", handle_debug_devices)

        # Geräte löschen
        async def handle_clear_devices(call):
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            config_entry = hass.config_entries.async_get_entry(target_entry_id)
            if not config_entry:
                _LOGGER.warning(f"[net4home] Kein ConfigEntry für entry_id {target_entry_id}")
                return
            hass.config_entries.async_update_entry(config_entry, options={"devices": {}})
            _LOGGER.info(f"[net4home] Geräte für entry_id {target_entry_id} gelöscht")

        hass.services.async_register(DOMAIN, "clear_devices", handle_clear_devices)

        # Geräte-Erkennung (ENUM_ALL)
        async def handle_enum_all(call):
            target_entry_id = call.data.get("entry_id", entry.entry_id)
            api = hass.data[DOMAIN].get(target_entry_id)
            if not api:
                _LOGGER.warning(f"[net4home] Kein API-Objekt für entry_id {target_entry_id}")
                return

            try:
                await api.send_enum_all()
                _LOGGER.info(f"[net4home] ENUM_ALL an den Bus gesendet (entry_id {target_entry_id})")
            except Exception as e:
                _LOGGER.error(f"[net4home] Fehler bei ENUM_ALL: {e}")

        hass.services.async_register(DOMAIN, "enum_all", handle_enum_all)

        return True

    except Exception as e:
        _LOGGER.exception("Error in async_setup_entry: %s", e)
        return False


async def options_update_listener1(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> None:
    _LOGGER.debug("Reload net4home config entry wegen Optionen-Änderung")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["skip_disconnect"] = True
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        # Unregister services
        hass.services.async_remove(DOMAIN, "debug_devices")
        hass.services.async_remove(DOMAIN, "clear_devices")
        hass.services.async_remove(DOMAIN, "enum_all")
        
        skip_disconnect = hass.data[DOMAIN].pop("skip_disconnect", False)
        hub: Net4HomeApi = hass.data[DOMAIN].pop(entry.entry_id)

        if not skip_disconnect:
            _LOGGER.info("Unload: Verbindung zum Bus wird geschlossen")
            await hub.async_disconnect()
        else:
            _LOGGER.debug("Unload: Verbindung bleibt offen (Reload durch Optionen)")

        if callable(getattr(hub, "async_stop", None)):
            await hub.async_stop()

    return unload_ok


def _redact_sensitive_data(data: dict, keys_to_redact: dict) -> dict:
    """Redact sensitive data from diagnostics."""
    result = data.copy()
    for key, subkeys in keys_to_redact.items():
        if key in result:
            if isinstance(result[key], dict):
                result[key] = result[key].copy()
                for subkey in subkeys:
                    if subkey in result[key]:
                        result[key][subkey] = "**REDACTED**"
    return result


async def async_get_diagnostics(hass, config_entry):
    """Return diagnostics for the net4home config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]

    if not api:
        return {}

    # Gather device info and other relevant data
    devices_info = {}
    for device_id, device in api.devices.items():
        devices_info[device_id] = {
            "name": device.name,
            "model": device.model,
            "device_type": device.device_type,
            "via_device": device.via_device,
            # add any other info you want to expose
        }

    data = {
        "devices": devices_info,
        "connection_info": {
            "host": api._host,
            "port": api._port,
            "mi": api._mi,
            "objadr": api._objadr,
            # any other connection parameters
        },
    }

    # redact sensitive info like passwords if present
    return _redact_sensitive_data(data, {"connection_info": ["password"]})
        