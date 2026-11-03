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
        "HS-S4AJ2",
        "HS-S4AR4",
        "S32A32",
    }
)


def is_binary_input_module(model: str | None) -> bool:
    """Return True when the module's sensor channels are binary inputs."""
    return bool(model) and model in BINARY_INPUT_MODELS
