"""Support for net4home integration."""
import asyncio
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant import config_entries

from .const import DOMAIN
from .hub import Net4HomeHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "light"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the net4home integration."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    
    try:
        hub = Net4HomeHub(
            hass,
            entry.data["host"],
            entry.data["port"],
            entry.data["password"],
            entry.data.get("MI"),
            entry.data.get("OBJADR"),
            entry.entry_id,
            devices=entry.options.get("devices") if entry.options else None,
        )
        await hub.async_start()

        hass.data[DOMAIN][entry.entry_id] = hub

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        unsub = entry.add_update_listener(options_update_listener)
        hub.unsub_options_update_listener = unsub
        entry.async_on_unload(unsub)

        return True
    except Exception as e:
        _LOGGER.exception("Error in async_setup_entry: %s", e)
        return False

async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> bool:

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_stop()
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.debug("Reload net4home hub config entry due to options change")
    await hass.config_entries.async_reload(entry.entry_id)

async def options_update_listener(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Reload net4home config entry due to options update")
    await hass.config_entries.async_reload(config_entry.entry_id)
