"""Initialize the net4home integration."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import Net4HomeClient

PLATFORMS = ["binary_sensor"]  # Start with one platform

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the net4home component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
    """Set up a config entry."""
    client = Net4HomeClient(
        hass,
        entry.data["host"],
        entry.data["port"],
        entry.data["password"],
        entry.data.get("mi"),
        entry.data.get("objadr"),
    )
    await client.async_connect()
    hass.data[DOMAIN][entry.entry_id] = client
    for platform in PLATFORMS:
        hass.config_entries.async_forward_entry_setup(entry, platform)
    return True

async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry
) -> bool:
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
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.async_disconnect()
    return unload_ok