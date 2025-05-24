from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def register_device_in_registry(
    hass: HomeAssistant,
    entry_id: str,
    device_id: str,
    name: str,
    model: str,
    sw_version: str,
):
    device_registry = dr.async_get(hass)
    connections = set()

    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="net4home",
        name=name,
        model=model,
        sw_version=sw_version,
        connections=connections,
    )
