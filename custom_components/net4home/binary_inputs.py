"""Digital input modules that expose one binary sensor per channel.

The channel list comes from the module's sensor count (ns). Each channel is
registered when its D0_RD_SENSOR_DATA_ACK arrives, and later state changes
arrive as D0_SENSOR_ACK for that channel's object address.
"""

BINARY_INPUT_MODELS = frozenset(
    {
        "UP-S4",
        "UP-S4+",
        "UP-S8",
        "EXT-S32",
        "UP-GL",
        "S4A2",
        "S4AD1",
        "UP-S4AJ1",
        "UP-PIR2-Connect",
        "HS-S4AJ2",
        "HS-S4AR4",
        "S32A32",
    }
)


def is_binary_input_module(model: str | None) -> bool:
    """Return True when the module's sensor channels are binary inputs."""
    return bool(model) and model in BINARY_INPUT_MODELS


# Contact types from the konfigurator sensor table (uh2nApi.pas).
# 1 button, 3 three-byte button, 13 PIR, 14 glass break.
DIGITAL_PIN_TYPES = frozenset({1, 3, 13, 14})

# These modules also have sensor-table rows, but the rows are not contacts.
_NOT_CONTACT_MODELS = frozenset(
    {"UP-TLH", "UP-T", "UP-RF", "UP-RF-S4AR1", "HS-Time"}
)


def is_binary_sensor_channel(model: str | None, pin_typ: int) -> bool:
    """Return True when one sensor-table row should become a binary sensor.

    A known input module registers every channel that has an object address.
    On any other module a row is registered only when its pin type is a contact.
    """
    if is_binary_input_module(model):
        return True
    if model in _NOT_CONTACT_MODELS:
        return False
    return pin_typ in DIGITAL_PIN_TYPES
