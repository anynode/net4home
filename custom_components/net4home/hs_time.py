"""HS-Time clock reply and the eight profile switches.

The configurator reads the clock with D0_VALUE_REQ to the base object.
D0_VALUE_ACK type 6 carries BCD time in bytes 3..7 and 10, status bits in
byte 11 and minutes without DCF reception in byte 12. The active profiles
are one bitmask: D0_REQ answers with D0_ACTOR_ACK byte 2, D0_SET writes it.
"""

from typing import Optional

IN_HW_NR_IS_CLOCK = 6
PROFILE_COUNT = 8

DCF_DAYLIGHT_SAVING = 0x01
DCF_NO_RECEPTION = 0x04
DCF_HOLIDAY = 0x08
DCF_SYNC_PHASE = 0x10


def _bcd(value: int) -> Optional[int]:
    """Return a byte that is valid BCD, or None."""
    high = (value >> 4) & 0x0F
    low = value & 0x0F
    if high > 9 or low > 9:
        return None
    return high * 10 + low


def parse_hs_time_clock(ddata: bytes) -> Optional[dict]:
    """Return clock fields from a D0_VALUE_ACK of type IN_HW_NR_IS_CLOCK.

    ``time`` is None when the BCD fields are not a real date. The status
    bits stay available so a module that is still synchronising can be shown.
    """
    if len(ddata) < 13 or ddata[1] != IN_HW_NR_IS_CLOCK:
        return None
    second = _bcd(ddata[3])
    minute = _bcd(ddata[4])
    hour = _bcd(ddata[5])
    day = _bcd(ddata[6])
    month = _bcd(ddata[7])
    year = _bcd(ddata[10])
    clock_time = None
    if None not in (second, minute, hour, day, month, year):
        if (
            1 <= month <= 12
            and 1 <= day <= 31
            and 0 <= hour <= 23
            and 0 <= minute <= 59
            and 0 <= second <= 59
        ):
            clock_time = {
                "year": 2000 + year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            }
    flags = ddata[11]
    return {
        "time": clock_time,
        "synced": (flags & DCF_SYNC_PHASE) == 0,
        "reception": (flags & DCF_NO_RECEPTION) == 0,
        "minutes_without_reception": ddata[12],
        "daylight_saving": (flags & DCF_DAYLIGHT_SAVING) != 0,
        "holiday": (flags & DCF_HOLIDAY) != 0,
    }


def sun_time_from_ack(ddata: bytes) -> Optional[str]:
    """HH:MM from a sunrise or sunset value reply.

    The minute count is a big-endian word at bytes 3 and 4, the same word
    w1440TimeToStr reads. Byte 2 is the formula type and is not part of the
    time. A word above 1440 is a negative offset, shown with a trailing minus.
    """
    if len(ddata) < 5:
        return None
    word = (ddata[3] << 8) | ddata[4]
    negative = word > 1440
    minutes = (0x10000 - word) if negative else word
    hours, minute = divmod(minutes, 60)
    text = f"{hours:02d}:{minute:02d}"
    return f"{text}-" if negative else text


def sun_object_offsets(sw_version: Optional[str], tab_count: Optional[int] = None) -> tuple[int, int]:
    """Offsets of today's sunrise and sunset from the base object.

    The configurator reads them at base + 1 + TabEntryCount and base + 2.
    From software 2.01 the profile table has 48 lines, before that 16.
    """
    count = tab_count if tab_count in (16, 48) else None
    if count is None:
        count = 48 if _user_version_at_least(sw_version, 2, 1) else 16
    return count + 1, count + 2


def _user_version_at_least(sw_version: Optional[str], major: int, minor: int) -> bool:
    """True when the user part of a version such as ``4.04/2.01`` is high enough."""
    if not sw_version or "/" not in sw_version:
        return False
    parts = sw_version.split("/", 1)[1].split(".")
    if len(parts) < 2:
        return False
    try:
        found = (int(parts[0]), int(parts[1]))
    except ValueError:
        return False
    return found >= (major, minor)


def profile_mask_with(mask: int, index: int, turn_on: bool) -> int:
    """Return the profile bitmask with one of the eight profiles changed."""
    if index < 0 or index >= PROFILE_COUNT:
        return mask & 0xFF
    bit = 1 << index
    if turn_on:
        return (mask | bit) & 0xFF
    return (mask & ~bit) & 0xFF


# TsuTabEntry, one modulspec line. The configurator swaps the address word,
# so the two bytes on the wire are shown as a big-endian object address.
MODE_OFF = 0
MODE_HOURLY = 1
MODE_DAILY = 2
MODE_MONTHLY = 3
MODE_RANDOM = 4
MODE_YEARLY = 5
MODE_SUNRISE = 7
MODE_SUNSET = 8

_MODE_LABELS = {
    MODE_OFF: "Deaktiv",
    MODE_HOURLY: "Stündlich",
    MODE_DAILY: "Täglich",
    MODE_MONTHLY: "Monatlich",
    MODE_RANDOM: "Zufall",
    MODE_YEARLY: "Jährlich",
    MODE_SUNRISE: "Relativ zum Sonnenaufgang",
    MODE_SUNSET: "Relativ zum Sonnenuntergang",
}
_WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So", "Fe")
_WEEKDAY_MODES = (MODE_DAILY, MODE_SUNRISE, MODE_SUNSET)

_CMD_SET = 50
_CMD_SET_UP = 76
_CMD_SET_DOWN = 77
_ALARM_COMMANDS = {
    0: "Aus",
    1: "Intern 1",
    2: "Intern 2",
    3: "Extern",
    11: "Intern 1 mit Prüfung",
    12: "Intern 2 mit Prüfung",
    13: "Extern mit Prüfung",
}
_COVER_MOVE = {1: "Ab", 3: "Auf"}


def weekday_text(dow: int) -> str:
    """Weekday bitmask the way the configurator prints it, with -- for gaps."""
    return "".join(
        label if dow & (1 << index) else "--"
        for index, label in enumerate(_WEEKDAYS)
    )


def profile_text(mask: int) -> str:
    """Profile bitmask as 1..8, or alle / keine."""
    mask &= 0xFF
    if mask == 0xFF:
        return "alle"
    if mask == 0:
        return "keine"
    return ",".join(str(index + 1) for index in range(PROFILE_COUNT) if mask & (1 << index))


def _offset_time(hour: int, minute: int) -> str:
    """Minute word used for sunrise and sunset offsets, minus when past 1440."""
    word = ((hour & 0xFF) << 8) | (minute & 0xFF)
    if word > 1440:
        word = 65536 - word
        sign = "-"
    else:
        sign = ""
    return f"{word // 60:02d}:{word % 60:02d}{sign}"


def command_text(command: tuple, kind: Optional[str]) -> str:
    """Short label for the three command bytes, using the target's kind."""
    if len(command) < 2:
        return ""
    code = command[0] & 0xFF
    value = command[1] & 0xFF
    if code == _CMD_SET_UP and value <= 100:
        return f"Fahren bis {value}% (AUF)"
    if code == _CMD_SET_DOWN and value <= 100:
        return f"Fahren bis {value}% (AB)"
    if code != _CMD_SET:
        return " ".join(f"{byte:02X}" for byte in command[:3])
    if kind == "alarm":
        return _ALARM_COMMANDS.get(value, f"Befehl {value}")
    if kind == "cover":
        if value in _COVER_MOVE:
            return _COVER_MOVE[value]
        if value <= 100:
            return f"Fahren bis {value}%"
    if kind in ("light", "switch"):
        if value == 0:
            return "Aus"
        if value == 100:
            return "Ein"
        if value <= 100:
            return f"{value} %"
    if value == 0:
        return "Aus"
    if value == 100:
        return "Ein"
    return f"Befehl {value}"


def schedule_entry_from_line(payload: bytes, index: int, base: Optional[int] = None) -> Optional[dict]:
    """One switching row from a modulspec line payload (bytes after the index).

    Mode 0 and 0xFF are empty rows and return None.
    """
    if len(payload) < 12 or payload[0] in (MODE_OFF, 0xFF):
        return None
    mode = payload[0]
    hour, minute, day, month, dow = (byte & 0xFF for byte in payload[1:6])
    address = ((payload[6] & 0xFF) << 8) | (payload[7] & 0xFF)
    command = tuple(byte & 0xFF for byte in payload[8:11])
    profile = payload[11] & 0xFF
    if mode in (MODE_SUNRISE, MODE_SUNSET):
        when = _offset_time(hour, minute)
    elif mode == MODE_HOURLY:
        when = f"XX:{minute:02X}"
    elif mode == MODE_RANDOM:
        when = ""
    else:
        when = f"{hour:02X}:{minute:02X}"
    date = ""
    if mode == MODE_YEARLY:
        date = f"{day:02X}.{month:02X}."
    elif mode == MODE_MONTHLY:
        date = f"{day:02X}."
    row = {
        "nr": index + 1,
        "mode_id": mode,
        "mode": _MODE_LABELS.get(mode, f"Modus {mode}"),
        "date": date,
        "time": when,
        "dow": dow,
        "weekdays": weekday_text(dow) if mode in _WEEKDAY_MODES else "",
        "address": address,
        "command": command,
        "profile_mask": profile,
        "profiles": profile_text(profile),
    }
    if base:
        row["object"] = base + index + 1
    return row


def schedule_rows_from_lines(lines: dict, count: int, base: Optional[int] = None) -> list:
    """Active rows of a schedule table, in line order. Missing lines are skipped."""
    rows = []
    for index in range(count):
        payload = lines.get(index)
        if not payload:
            continue
        row = schedule_entry_from_line(payload, index, base)
        if row is not None:
            rows.append(row)
    return rows


def schedule_row_active(row: dict, profile_mask: Optional[int], weekday: Optional[int] = None, holiday: bool = False) -> Optional[bool]:
    """Whether this row can fire: one of its profiles is on, and the day matches.

    ``weekday`` is 0 for Monday. None skips the weekday check. A holiday also
    matches the Feiertag bit.
    """
    if profile_mask is None:
        return None
    mask = profile_mask & 0xFF
    profile = row.get("profile_mask", 0) & 0xFF
    if profile == 0 or mask == 0 or (profile != 0xFF and (profile & mask) == 0):
        return False
    if row.get("mode_id") in _WEEKDAY_MODES and weekday is not None:
        bits = 1 << (weekday & 7)
        if holiday:
            bits |= 0x80
        if (row.get("dow", 0) & bits) == 0:
            return False
    return True
