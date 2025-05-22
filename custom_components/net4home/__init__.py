"""Initialize the net4home integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import Net4HomeHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.debug("Calling async_setup for net4home")
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    _LOGGER.debug("async_setup_entry called for net4home, entry: %s", entry)
    try:
        hub = Net4HomeHub(
            hass,
            entry.data["host"],
            entry.data["port"],
            entry.data["password"],
            entry.data.get("MI"),
            entry.data.get("OBJADR"),
            entry.entry_id,
        )
        _LOGGER.debug("Net4HomeHub created")
        await hub.async_start()
        hass.data[DOMAIN][entry.entry_id] = hub
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("async_setup_entry for net4home finished")
        return True
    except Exception as e:
        _LOGGER.exception("Error in async_setup_entry: %s", e)
        return False

async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    _LOGGER.debug("async_unload_entry called for net4home")
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
