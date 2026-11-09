"""Stromsensor modules (UP-SI, HS-SI6): module info, threshold lines and power.

Layout from the konfigurator (up_si_16A.pas, uh2nApi.pas):

- Module info reply (modulspec index 255): ddata[2..3] is the base object
  (SI_EE_LM_ADR). For UP-SI, ddata[8] is the number of threshold lines
  (SI_EE_LM_LEN_TAB1). HS-SI6 replies are longer and carry the line count in
  ddata[12]; it has six channels that each use the same four-line block.
- Threshold line n (modulspec index n), with ddata[0] = command, ddata[1] = index:
    ddata[2]      direction: 1 = below (unterschritten), 2 = above (überschritten),
                  0 or 0xFF = line not used
    ddata[3..4]   output address (0x8000 bit = group)
    ddata[5..7]   command to send (D0 command, value, parameter)
    ddata[8..9]   power threshold in W
    ddata[10..11] delay in s
- Channel k uses lines 4k .. 4k+3 and object base + k.
- Power reply (D0_SENSOR_ACK from the channel object): ddata[1..2] is the
  power in W, ddata[3] is the input type, 18 for this module.

Pure functions, no Home Assistant imports, so they can be tested directly.
"""

from dataclasses import dataclass
from typing import Optional

SI_MODEL_CHANNELS = {"UP-SI": 1, "HS-SI6": 6}
SI_LINES_PER_CHANNEL = 4
PIN_IS_SI = 18
D0_SENSOR_ACK = 65

_D0_NAMES = {
    50: "D0_SET",
    51: "D0_INC",
    52: "D0_DEC",
    53: "D0_TOGGLE",
    54: "D0_REQ",
    59: "D0_SET_N",
    69: "D0_SAVE",
}

_DIRECTION = {1: "under", 2: "over"}


@dataclass(frozen=True)
class SiInfo:
    """Module info: base object, number of channels and threshold lines."""

    base: int
    channels: int
    lines: int


def si_channels_for_model(model: Optional[str]) -> int:
    """Channel count from the model name (1 for UP-SI, 6 for HS-SI6)."""
    return SI_MODEL_CHANNELS.get(model or "", 0)


def si_info_from_ddata(model: Optional[str], ddata: bytes) -> Optional[SiInfo]:
    """Parse the module info reply (index 255). None if it does not fit."""
    channels = si_channels_for_model(model)
    if not channels or len(ddata) < 9 or ddata[1] != 0xFF:
        return None
    base = (ddata[2] << 8) | ddata[3]
    if base <= 0 or base >= 0x8000:
        return None
    if channels == 1:
        lines = ddata[8]
    else:
        if len(ddata) < 13:
            return None
        lines = ddata[12]
    if lines <= 0:
        return None
    return SiInfo(base=base, channels=channels, lines=lines)


def si_channel_of_line(line: int) -> int:
    """Channel index that owns a threshold line."""
    return line // SI_LINES_PER_CHANNEL


def si_channel_objects(info: SiInfo) -> list[int]:
    """Object address of every channel, base + channel index."""
    return [info.base + channel for channel in range(info.channels)]


def si_channel_for_objadr(info: Optional[SiInfo], objadr: int) -> Optional[int]:
    """Channel index for a sender object address, None if it is not ours."""
    if info is None:
        return None
    channel = objadr - info.base
    if 0 <= channel < info.channels:
        return channel
    return None


def _command_text(command: bytes) -> str:
    name = _D0_NAMES.get(command[0], f"D0 {command[0]}")
    if command[2] == 0:
        return f"{name} {command[1]}"
    return f"{name} {command[1]} {command[2]}"


def si_entry_from_line(ddata: bytes) -> Optional[dict]:
    """Decode one threshold line. None for an unused line."""
    if len(ddata) < 12:
        return None
    direction = _DIRECTION.get(ddata[2])
    if direction is None:
        return None
    address = (ddata[3] << 8) | ddata[4]
    command = bytes(ddata[5:8])
    if address & 0x8000:
        target = f"G{address & 0x7FFF}"
    else:
        target = f"OBJ {address}"
    return {
        "direction": direction,
        "threshold_w": (ddata[8] << 8) | ddata[9],
        "delay_s": (ddata[10] << 8) | ddata[11],
        "target": target,
        "command": _command_text(command),
    }


def si_power_from_ack(ddata: bytes) -> Optional[int]:
    """Power in W from a channel object reply. None if it is not a power reply."""
    if len(ddata) < 4 or ddata[0] != D0_SENSOR_ACK or ddata[3] != PIN_IS_SI:
        return None
    return (ddata[1] << 8) | ddata[2]


def ensure_si_runtime(device) -> None:
    """Add the module attributes to a device object if they are missing."""
    if getattr(device, "si_info", None) is None:
        device.si_info = None
    if getattr(device, "si_entries", None) is None:
        device.si_entries = {}
    if getattr(device, "si_power", None) is None:
        device.si_power = {}


def channel_thresholds(entries: dict[int, Optional[dict]], channel: int) -> list[dict]:
    """Used threshold lines of one channel, in line order."""
    result = []
    first = channel * SI_LINES_PER_CHANNEL
    for line in range(first, first + SI_LINES_PER_CHANNEL):
        entry = entries.get(line)
        if entry is not None:
            result.append(dict(entry))
    return result
