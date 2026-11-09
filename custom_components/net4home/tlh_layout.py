"""UP-TLH measured-value object addresses depend on the module user software.

The konfigurator (TLHconfigU.senorDataToZeile) switches at user version 1.17
(swvUSER12 >= $100+17):

- 1.17 and newer, for example 4.04/1.22: temperature, illuminance and humidity
  are fixed at adrBase+3, +4 and +5.
- Older, for example 3.00/1.09: each channel record stores its own object
  address (modulspec bytes 2 and 3). There is no fixed offset. On MI0254 the
  records say 25401, 25402 and 25403. On MI0259 the setpoint is object 800
  and the records say 25901, 25902 and 25903.
"""

from typing import Optional

# swvUSER1=1, swvUSER2=17. Below this, sensor addresses are not fixed.
TLH_FIXED_SENSOR_MAP_FROM = (1, 17)
_SENSOR_TYPES = ("temperature", "illuminance", "humidity")


def parse_user_software(sw_version: Optional[str]) -> Optional[tuple[int, int]]:
    """Return (user major, user minor) from a version such as ``4.04/1.22``."""
    if not sw_version or "/" not in sw_version:
        return None
    user = sw_version.split("/", 1)[1].strip()
    if user[:1] in ("V", "v"):
        user = user[1:]
    major_text, dot, minor_text = user.partition(".")
    if not dot:
        return None
    try:
        return int(major_text), int(minor_text)
    except ValueError:
        return None


def climate_regulators(status: int) -> tuple[bool, bool, str]:
    """Heating and cooling controller from the setpoint status byte.

    Bit 0 is the heating controller, bit 1 the cooling controller. The mode
    names match Home Assistant climate modes.
    """
    heat_active = (status & 0x01) != 0
    cool_active = (status & 0x02) != 0
    if heat_active and cool_active:
        mode = "heat_cool"
    elif heat_active:
        mode = "heat"
    elif cool_active:
        mode = "cool"
    else:
        mode = "off"
    return heat_active, cool_active, mode


def tlh_uses_fixed_sensor_map(sw_version: Optional[str]) -> bool:
    """True for user software 1.17 and newer, and when the version is unknown."""
    user = parse_user_software(sw_version)
    if user is None:
        return True
    return user >= TLH_FIXED_SENSOR_MAP_FROM


def tlh_measured_sensor(
    adr_base: Optional[int],
    channel: int,
    sw_version: Optional[str],
    packet_address: Optional[int] = None,
) -> Optional[tuple[int, str]]:
    """Object address and sensor type for UP-TLH channel 0, 1 or 2.

    ``packet_address`` is the address stored in an old channel record
    (modulspec bytes 2 and 3, big endian). Older firmware has no fixed
    offset, so a missing record address is not guessed.
    """
    if channel not in (0, 1, 2):
        return None
    sensor_type = _SENSOR_TYPES[channel]
    if tlh_uses_fixed_sensor_map(sw_version):
        if adr_base is None or adr_base <= 0:
            return None
        return adr_base + 3 + channel, sensor_type
    if packet_address is not None and 0 < packet_address < 0xFFFF:
        return packet_address, sensor_type
    return None


def pack_day_night_record(day_c: float, night_c: float) -> bytes:
    """Modulspec index 0xF0 record, without the command byte.

    Layout matches the read reply: index, day high, day low, night high, night low.
    Temperatures are tenths of a degree. 17.0 °C is 170, which is 0x00AA.
    """

    def _word(value: float) -> tuple[int, int]:
        raw = int(round(float(value) * 10))
        if raw < 0 or raw > 0xFFFF:
            raise ValueError(f"temperature {value} is outside 0..6553.5 °C")
        return (raw >> 8) & 0xFF, raw & 0xFF

    day_hi, day_lo = _word(day_c)
    night_hi, night_lo = _word(night_c)
    return bytes([0xF0, day_hi, day_lo, night_hi, night_lo])
