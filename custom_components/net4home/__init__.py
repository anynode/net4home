"""Support for net4home integration."""
import asyncio
from datetime import datetime
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .models import Net4HomeDevice
from .const import (
    DOMAIN,
    CONF_AUTO_DISCOVERY,
    CONF_READ_GROUPS_ON_STARTUP,
    CONF_READ_MODULE_INFO_ON_STARTUP,
    PLATFORMS,
)
from .api import Net4HomeApi
from .helpers import ensure_registry_device, migrate_dimmer_timers
from .lcd_service import async_setup_lcd_service
from .rf_access import RfKeyStore, DETECTED_EVENT, async_setup_services, store_key

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ENTRY_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})


def _api_for_call(hass: HomeAssistant, call: ServiceCall) -> Net4HomeApi:
    """Return the API addressed by a service call."""
    apis = {
        entry_id: api
        for entry_id, api in hass.data.get(DOMAIN, {}).items()
        if isinstance(api, Net4HomeApi)
    }
    entry_id = call.data.get("entry_id")
    if entry_id:
        api = apis.get(entry_id)
    elif len(apis) == 1:
        api = next(iter(apis.values()))
    else:
        api = None
    if api is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )
    return api


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the net4home integration."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_debug_devices(call: ServiceCall) -> None:
        api = _api_for_call(hass, call)
        for dev_id, dev in api.devices.items():
            _LOGGER.info("Device: %s, type %s, name %s", dev_id, dev.device_type, dev.name)

    async def handle_clear_devices(call: ServiceCall) -> None:
        api = _api_for_call(hass, call)
        entry = api._entry
        options = dict(entry.options)
        options["devices"] = {}
        hass.config_entries.async_update_entry(entry, options=options)
        _LOGGER.info("Stored devices of entry %s cleared", entry.entry_id)

    async def handle_enum_all(call: ServiceCall) -> None:
        api = _api_for_call(hass, call)
        await api.send_enum_all()
        _LOGGER.info("ENUM_ALL sent to bus (entry %s)", api._entry_id)

    hass.services.async_register(DOMAIN, "debug_devices", handle_debug_devices, schema=ENTRY_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_devices", handle_clear_devices, schema=ENTRY_SCHEMA)
    hass.services.async_register(DOMAIN, "enum_all", handle_enum_all, schema=ENTRY_SCHEMA)
    async_setup_services(hass)
    async_setup_lcd_service(hass)
    return True


def _load_stored_devices(hass: HomeAssistant, entry: ConfigEntry, api: Net4HomeApi) -> None:
    """Rebuild the device list from the config entry options."""
    loaded_devices = []

    for dev in entry.options.get("devices", {}).values():
        detail_status = dev.get("detail_status", "pending")
        detail_retry_count = dev.get("detail_retry_count", 0)
        last_detail_request = None
        if last_detail_request_str := dev.get("last_detail_request"):
            try:
                last_detail_request = datetime.fromisoformat(last_detail_request_str)
            except (ValueError, TypeError):
                pass

        sw_version = dev.get("sw_version", "")
        hw_version = dev.get("hw_version", "")
        # Migration: UP-T/UP-TLH stored as "module" should be treated as "climate"
        device_type = dev["device_type"]
        if device_type == "module" and dev.get("model") in ("UP-T", "UP-TLH"):
            device_type = "climate"
        # Migration: EXT-LD stored as "module" before the lock platform existed
        if device_type == "module" and dev.get("model") == "EXT-LD":
            device_type = "lock"

        # Normalize device_id to uppercase so API lookups (e.g. from packet device_id) and dispatcher keys match
        normalized_device_id = (dev["device_id"] or "").upper()
        stored_objadr = dev.get("objadr")
        if stored_objadr is None and (dev["device_id"] or "").startswith("OBJ"):
            stored_objadr = int(dev["device_id"][3:])
        if isinstance(stored_objadr, int) and stored_objadr <= 0:
            stored_objadr = None
        device = Net4HomeDevice(
            device_id=normalized_device_id,
            name=dev["name"],
            model=dev["model"],
            device_type=device_type,
            via_device=dev.get("via_device"),
            objadr=stored_objadr,
            send_state_changes=dev.get("send_state_changes", False),
            detail_status=detail_status,
            detail_retry_count=detail_retry_count,
            last_detail_request=last_detail_request,
            module_type=dev.get("module_type"),
            ns=dev.get("ns"),
            na=dev.get("na"),
            nm=dev.get("nm"),
            ng=dev.get("ng"),
            timer_time1=dev.get("timer_time1"),
            powerup_status=dev.get("powerup_status"),
            min_hell=dev.get("min_hell"),
        )
        device.sw_version = sw_version or None
        api.devices[normalized_device_id] = device
        loaded_devices.append((device, sw_version, hw_version))

    # Parents first, then children, so via_device_id can point at a registry id.
    for parents in (True, False):
        for device, sw_version, hw_version in loaded_devices:
            if bool(device.via_device) == parents:
                continue
            ensure_registry_device(
                hass,
                entry,
                device.device_id,
                name=device.name,
                model=device.model,
                sw_version=sw_version,
                hw_version=hw_version,
                via_device=device.via_device,
            )

    migrate_dimmer_timers(hass, entry, api)
    _LOGGER.info("Loaded %s devices from config", len(api.devices))


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up net4home hub connection from a config entry."""
    host = entry.options.get("host", entry.data.get("host", ""))
    port = entry.options.get("port", entry.data.get("port", 3478))
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{host}:{port}")
    api = Net4HomeApi(
        hass=hass,
        host=host,
        port=port,
        password=entry.options.get("password", entry.data.get("password", "")),
        mi=entry.options.get("MI", entry.data.get("MI")),
        objadr=entry.options.get("OBJADR", entry.data.get("OBJADR")),
        entry_id=entry.entry_id,
        entry=entry,
        auto_discovery_enabled=entry.data.get(CONF_AUTO_DISCOVERY, True),
        read_groups_on_startup=entry.data.get(CONF_READ_GROUPS_ON_STARTUP, True),
        read_module_info_on_startup=entry.data.get(CONF_READ_MODULE_INFO_ON_STARTUP, True),
    )

    try:
        await api.async_connect()
    except (OSError, TimeoutError) as err:
        await api.async_disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": str(host), "port": str(port), "error": str(err) or type(err).__name__},
        ) from err

    try:
        _load_stored_devices(hass, entry, api)
        hass.data[DOMAIN][entry.entry_id] = api

        # RF key directory (persistent) and access events per reader
        rf_store = RfKeyStore(hass, entry.entry_id, api)
        await rf_store.async_load()
        hass.data[DOMAIN][store_key(entry.entry_id)] = rf_store
        entry.async_on_unload(hass.bus.async_listen(DETECTED_EVENT, rf_store.handle_detected))

        async def _update_listener(hass_arg: HomeAssistant, config_entry: config_entries.ConfigEntry) -> None:
            """Apply startup switches changed in the options flow."""
            api_instance = hass_arg.data.get(DOMAIN, {}).get(config_entry.entry_id)
            if api_instance:
                api_instance._auto_discovery_enabled = config_entry.data.get(CONF_AUTO_DISCOVERY, True)
                api_instance.read_groups_on_startup = config_entry.data.get(
                    CONF_READ_GROUPS_ON_STARTUP, True
                )
                api_instance.read_module_info_on_startup = config_entry.data.get(
                    CONF_READ_MODULE_INFO_ON_STARTUP, True
                )

        entry.async_on_unload(entry.add_update_listener(_update_listener))

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        api._listen_task = entry.async_create_background_task(
            hass, api.async_listen(), f"net4home listener {entry.entry_id}"
        )
        await api.async_start_detail_retrieval()
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(store_key(entry.entry_id), None)
        await api.async_disconnect()
        raise

    async def _finish_startup() -> None:
        try:
            if not any(
                not device.via_device and str(device.device_id).startswith("MI")
                for device in api.devices.values()
            ):
                _LOGGER.info("No modules stored yet, searching the bus")
                await api.send_enum_all()
                await api.async_wait_for_enumeration()
                _LOGGER.info("Bus search finished, reading module info")
                await api.async_wait_for_detail_queue()
            else:
                await asyncio.sleep(5)
            if api.read_module_info_on_startup:
                await api.async_load_bell_modules()
            else:
                _LOGGER.info("Module info read on startup is off")
            await api.async_ensure_tlh_measured_sensors()
            await api.async_refresh_legacy_tlh_sensors()
            await api.async_activate_all_sensors()
            await api.async_refresh_preset_values_up_tlh()
            await api.async_refresh_climate_setpoints()
            await api.async_refresh_alarm_panels()
            await api.async_refresh_si_modules()
            await api.async_refresh_ext_ld_locks()
            await api.async_refresh_hs_time(
                include_schedule=api.read_module_info_on_startup
            )
            if api.read_module_info_on_startup:
                await api.async_refresh_rf_key_lists()
                await api.async_reread_incomplete_actor_modules()
                await api.async_load_missing_actor_settings()
            await api.async_load_groups()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Startup reads failed")

    entry.async_create_background_task(
        hass, _finish_startup(), f"net4home startup {entry.entry_id}"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    api = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if api:
        await api.async_stop_detail_retrieval()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hub: Net4HomeApi = hass.data[DOMAIN].pop(entry.entry_id)
        rf_store = hass.data[DOMAIN].pop(store_key(entry.entry_id), None)
        if rf_store is not None:
            await rf_store.async_save()

        _LOGGER.info("Unload: Closing connection to bus")
        await hub.async_disconnect()

        if callable(getattr(hub, "async_stop", None)):
            await hub.async_stop()

    return unload_ok
