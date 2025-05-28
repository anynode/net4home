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

PLATFORMS: list[Platform] = ["switch", "cover"]

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
            )
            api.devices[device.device_id] = device
            _LOGGER.debug(f"Loaded device from config: {device.device_id} ({device.device_type})")

        hass.data[DOMAIN][entry.entry_id] = api
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        async def delayed_dispatch():
            await asyncio.sleep(0.1)
            for device in api.devices.values():
                if device.device_type == "switch":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")
                elif device.device_type == "cover":
                    async_dispatcher_send(hass, f"net4home_new_device_{entry.entry_id}", device)
                    _LOGGER.debug(f"Entity dispatched for {device.device_id}")

        # asyncio.create_task(delayed_dispatch())

        _LOGGER.debug(f"List of loaded devices: {list(api.devices.keys())}")

        await api.async_connect()
        asyncio.create_task(api.async_listen())

        async def delayed_status_request(device_id: str, delay: float):
            await asyncio.sleep(delay)
            await api.async_request_status(device_id)

        for idx, device in enumerate(api.devices.values()):
            if device.device_type == "switch":
                delay_seconds = idx * 0.2  # 200ms delay
                asyncio.create_task(delayed_status_request(device.device_id, delay_seconds))

        #unsub = entry.add_update_listener(options_update_listener)
        #api.unsub_options_update_listener = unsub
        #entry.async_on_unload(unsub)

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

