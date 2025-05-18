"""Initialize the net4home integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import Net4HomeClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]  # oder ["binary_sensor", "sensor", "switch", ...]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the net4home component."""
    _LOGGER.debug("Calling async_setup for net4home")
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    """Set up a config entry."""
    _LOGGER.debug("async_setup_entry called for net4home, entry: %s", entry)
    try:
        client = Net4HomeClient(
            hass,
            entry.data["host"],
            entry.data["port"],
            entry.data["password"],
            entry.data.get("MI"),
            entry.data.get("OBJADR"),
        )
        _LOGGER.debug("Net4HomeClient created")
        await client.async_connect()
        _LOGGER.debug("Net4HomeClient connected")
        hass.data[DOMAIN][entry.entry_id] = client
        hass.loop.create_task(client.async_listen())
        # NEU: Zukunftssichere Mehrfachregistrierung der Plattformen!
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
    """Unload a config entry."""
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
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.async_disconnect()
    return unload_ok
