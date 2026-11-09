"""Service that sends one free-text packet to an UP-LCD."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATINE_HW_IS_LCD3

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND = "send_lcd_text"


def _apis(hass: HomeAssistant):
    data = hass.data.get(DOMAIN, {})
    return [item for item in data.values() if hasattr(item, "async_send_lcd_text")]


def _is_lcd(device) -> bool:
    return device.module_type == PLATINE_HW_IS_LCD3 or device.model == "UP-LCD"


async def _send(call: ServiceCall) -> None:
    hass = call.hass
    device_id = str(call.data["device_id"]).strip().upper()
    if device_id.isdigit():
        device_id = f"MI{int(device_id):04X}"
    elif not device_id.startswith("MI"):
        device_id = f"MI{device_id}"
    entry_id = call.data.get("entry_id")
    apis = _apis(hass)
    if entry_id:
        apis = [api for api in apis if getattr(api, "_entry_id", None) == entry_id or getattr(getattr(api, "_entry", None), "entry_id", None) == entry_id]
    target = None
    api = None
    for candidate in apis:
        device = candidate.devices.get(device_id)
        if device is not None and _is_lcd(device):
            api = candidate
            target = device
            break
    if api is None or target is None:
        _LOGGER.warning("send_lcd_text: %s is not an UP-LCD", device_id)
        return
    await api.async_send_lcd_text(
        target.device_id,
        call.data.get("message", ""),
        light=call.data.get("light", True),
        light_long=call.data.get("light_long", False),
        blink=call.data.get("blink", False),
        blink_frequency=call.data.get("blink_frequency", 10),
        clear=call.data.get("clear", True),
        buzzer=call.data.get("buzzer", False),
        new_line=call.data.get("new_line", False),
        x=call.data.get("x"),
        y=call.data.get("y"),
    )


def async_setup_lcd_service(hass: HomeAssistant) -> None:
    """Register the text service once."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND,
        _send,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
                vol.Required("message"): cv.string,
                vol.Optional("light", default=True): cv.boolean,
                vol.Optional("light_long", default=False): cv.boolean,
                vol.Optional("blink", default=False): cv.boolean,
                vol.Optional("blink_frequency", default=10): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
                vol.Optional("clear", default=True): cv.boolean,
                vol.Optional("buzzer", default=False): cv.boolean,
                vol.Optional("new_line", default=False): cv.boolean,
                vol.Optional("x"): vol.All(vol.Coerce(int), vol.Range(min=0, max=15)),
                vol.Optional("y"): vol.All(vol.Coerce(int), vol.Range(min=0, max=15)),
                vol.Optional("entry_id"): cv.string,
            }
        ),
    )
