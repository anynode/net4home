"""Dimmer modules (HS-AD1-1x10V, HS-AD3, HS-AD3e).

A timer channel on a dimmer still drives a 0–100% output.
Toggle recalls the last level. A SET command carries the percent.
"""

D0_SET = 50
D0_TOGGLE = 53

DIMMER_MODULE_MODELS = frozenset({"HS-AD1-1x10V", "HS-AD3e", "HS-AD3"})


def is_dimmer_module(model: str | None) -> bool:
    return (model or "") in DIMMER_MODULE_MODELS


def timer_channel_device_type(module_model: str | None) -> str:
    """A timer on a dimmer is a light, so the level can be set. Other timers stay switches."""
    if is_dimmer_module(module_model):
        return "light"
    return "switch"


def light_on_command(model: str | None, brightness: int | None) -> bytes:
    """Command for turning a dimmer on.

    brightness is the Home Assistant value 0–255, or None when the caller
    did not ask for a level. A timer dimmer then recalls the last level.
    Any other dimmer without a level goes to 100%.
    """
    if model == "Timer" and brightness is None:
        return bytes([D0_TOGGLE, 0x00, 0x00])
    level = 255 if brightness is None else brightness
    percent = round(level * 100 / 255)
    return bytes([D0_SET, percent, 0x00])
