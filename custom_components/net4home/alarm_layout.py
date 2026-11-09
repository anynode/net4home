"""HS-Safety arm commands, status bits and the Tab1 contact list.

The konfigurator wires these D0_SET values to the base object EE_LC_ADR
(hs_safety.dfm, Button1..Button9):

- 0: disarmed
- 11, 12, 13: Intern 1, Intern 2, Extern, after the module has checked
  that every contact of that level is closed ("mit Prüfung")
- 1, 2, 3: the same three levels without the check ("ohne Prüfung").
  The module then arms even with open contacts, so these are only sent
  when the user presses the explicit button.

EE_LC_ADR is a big-endian word at offset 3 of modulspec line 0.
A full status reply (D0_SENSOR_ACK) carries the active levels in byte 2.
Byte 4 equal to 0 means the module is still synchronising.
The live module also sends a two-byte telegram, command plus that same
level byte, for example 41 0F and 41 08.

The status bits stack upward, which is the opposite of a contact's
membership flags. The event-log codes in hs_safety.pas (from V1.21) use
the low nibble as this byte: $EA Intern 1 is intern1, $EE Intern 2 is
intern1+intern2, $EF Extern is extern+intern1+intern2. The sabotage bit
rides along and does not choose the level. So ext/int1/int2/sab is Extern.

Tab4 is the protocol. Module info byte 6 is the number of 12-byte records,
packed into the modulspec lines that follow Tab0..Tab3. The record number
is big-endian; 0xFFFF is an empty slot.

Tab1 (the trigger list) starts after Tab0. Its lines are flat indices
gTab0len .. gTab0len+gTab1len-1, each 16 bytes:
address (big-endian word), active flags, receive mode, sensor type,
8 bytes of text.
"""

from typing import NamedTuple, Optional

ALARM_SET_DISARM = 0
ALARM_SET_HOME = 11
ALARM_SET_NIGHT = 12
ALARM_SET_AWAY = 13
ALARM_SET_HOME_UNCHECKED = 1
ALARM_SET_NIGHT_UNCHECKED = 2
ALARM_SET_AWAY_UNCHECKED = 3
ALARM_SET_VALUES = frozenset({0, 1, 2, 3, 11, 12, 13})

_BIT_EXTERN = 0x01
_BIT_INTERN1 = 0x02
_BIT_INTERN2 = 0x04
_BIT_SABOTAGE = 0x08

# Record offset of the base object inside modulspec line 0.
_EE_LC_ADR = 3

STATE_DISARMED = "disarmed"
STATE_ARMED_HOME = "armed_home"
STATE_ARMED_NIGHT = "armed_night"
STATE_ARMED_AWAY = "armed_away"
STATE_ARMING = "arming"

LEVEL_LABELS = {
    STATE_DISARMED: "Aus",
    STATE_ARMING: "Schaltung läuft",
    STATE_ARMED_HOME: "Intern 1",
    STATE_ARMED_NIGHT: "Intern 2",
    STATE_ARMED_AWAY: "Extern",
}

TRIGGER_ENTRY_LEN = 16
_AI_EXTERN = 0x01
_AI_INTERN1 = 0x02
_AI_INTERN2 = 0x04
_AI_SABOTAGE = 0x08
_ST_NORMALLY_OPEN = 0x01
_ST_NORMALLY_CLOSED = 0x02

# Which contact flags count for each armed level. An INTERN1 contact is
# active for Intern 1, Intern 2 and Extern ("Intern 1+2+Ext"), an INTERN2
# contact for Intern 2 and Extern, an EXTERN contact only for Extern.
_LEVEL_TRIGGER_MASK = {
    STATE_ARMED_HOME: _AI_INTERN1,
    STATE_ARMED_NIGHT: _AI_INTERN1 | _AI_INTERN2,
    STATE_ARMED_AWAY: _AI_INTERN1 | _AI_INTERN2 | _AI_EXTERN,
}

_LEVEL_TRIGGER_NAMES = {
    STATE_ARMED_HOME: "Intern 1",
    STATE_ARMED_NIGHT: "Intern 2",
    STATE_ARMED_AWAY: "Extern",
}


def alarm_base_from_modulspec(ddata: bytes) -> Optional[int]:
    """Return EE_LC_ADR from a modulspec line-0 reply, or None."""
    record_start = 2
    address_at = record_start + _EE_LC_ADR
    if len(ddata) < address_at + 2 or ddata[1] != 0:
        return None
    address = (ddata[address_at] << 8) | ddata[address_at + 1]
    if address <= 0 or address >= 0xFFFF:
        return None
    return address


def alarm_flags_from_sensor_ack(ddata: bytes) -> Optional[tuple[int, bool]]:
    """Return the level byte and the synchronising flag.

    The configurator reads byte 2, and byte 4 when it is present.
    A two-byte telegram has no high byte, so the level sits in byte 1
    and synchronising stays unknown.
    """
    if len(ddata) >= 3:
        return ddata[2], len(ddata) > 4 and ddata[4] == 0
    if len(ddata) == 2:
        return ddata[1], False
    return None


def alarm_sabotage(flags: int) -> bool:
    """True when a monitored contact reports tamper, not an alarm."""
    return bool(flags & _BIT_SABOTAGE)


def alarm_state_from_status(flags: int, syncing: bool) -> str:
    """Map a D0_SENSOR_ACK status byte to one arming level.

    Extern sets every level bit, Intern 2 sets intern1 and intern2, Intern 1
    sets only intern1. The sabotage bit does not change the level.
    Synchronising without an active level is the arming check.
    """
    if flags & _BIT_EXTERN:
        return STATE_ARMED_AWAY
    if flags & _BIT_INTERN2:
        return STATE_ARMED_NIGHT
    if flags & _BIT_INTERN1:
        return STATE_ARMED_HOME
    if syncing:
        return STATE_ARMING
    return STATE_DISARMED


def is_armed(state: Optional[str]) -> bool:
    """True for the three armed levels."""
    return state in _LEVEL_TRIGGER_MASK


def sabotage_reported(raw_sabotage: Optional[bool], state: Optional[str]) -> bool:
    """Tamper is only reported while the panel is armed.

    The module keeps the sabotage bit set while disarmed, which is why the
    raw bit is shown as an attribute and not as a tamper alarm.
    """
    return bool(raw_sabotage) and is_armed(state)


ALARM_LOG_RECORD_LEN = 12

_LOG_TEXT = {
    0xE0: "Service Aus",
    0xE8: "Deaktiviert",
    0xEA: "Intern 1 scharf",
    0xEE: "Intern 2 scharf",
    0xEF: "Extern scharf",
    0xF0: "3x falscher Key",
    0xF1: "Uhr gestellt",
    0xF2: "Konfigbefehl erkannt",
}


class AlarmTables(NamedTuple):
    """Line counts from the module info reply, plus the protocol length."""

    tab0: int
    tab1: int
    tab2: int
    tab3: int
    events: int

    @property
    def log_start(self) -> int:
        """First modulspec line of the packed protocol."""
        return self.tab0 + self.tab1 + self.tab2 + self.tab3

    @property
    def log_lines(self) -> int:
        """Modulspec lines that hold the 12-byte protocol records."""
        if self.events <= 0:
            return 0
        return (self.events * ALARM_LOG_RECORD_LEN + 15) // 16


def alarm_tables_from_info(ddata: bytes) -> Optional[AlarmTables]:
    """Return the five table lengths from a module info reply (index $FF).

    Byte 6 is the number of protocol records, not a line count.
    """
    if len(ddata) < 7 or ddata[1] != 0xFF:
        return None
    return AlarmTables(ddata[2], ddata[3], ddata[4], ddata[5], ddata[6])


def alarm_log_from_lines(
    lines: dict[int, bytes],
    tables: AlarmTables,
    triggers: dict[int, dict],
) -> list[dict]:
    """Decode the protocol from the modulspec lines that follow Tab3."""
    if tables.log_lines <= 0:
        return []
    blob = b"".join(
        lines.get(tables.log_start + index, b"\xff" * 16)
        for index in range(tables.log_lines)
    )
    return alarm_log_from_bytes(blob[: tables.events * ALARM_LOG_RECORD_LEN], triggers)


def alarm_log_from_bytes(data: bytes, triggers: dict[int, dict]) -> list[dict]:
    """Decode protocol records. Newest entry (highest number) first."""
    events = []
    for offset in range(0, len(data) - ALARM_LOG_RECORD_LEN + 1, ALARM_LOG_RECORD_LEN):
        record = data[offset : offset + ALARM_LOG_RECORD_LEN]
        number = (record[0] << 8) | record[1]
        if number == 0xFFFF:
            continue
        code = record[2]
        hour, minute, second = record[3], record[4], record[5]
        day, month, year = record[6], record[7], record[8]
        trigger = ""
        if code < 0xE0:
            known = triggers.get(code) or {}
            trigger = known.get("name") or f"Auslöser {code + 1}"
            text = "Alarm ausgelöst"
        else:
            text = _LOG_TEXT.get(code, f"Ereignis {code:#04x}")
        if record[9] == 1:
            text = f"{text} / nicht gemeldet"
        stamp = (
            f"{day:02d}.{month:02d}.{year % 100:02d} "
            f"{hour:02d}:{minute:02d}:{second:02d}"
        )
        parts = [stamp]
        if trigger:
            parts.append(trigger)
        parts.append(text)
        events.append(
            {
                "nr": number,
                "time": stamp,
                "trigger": trigger,
                "text": text,
                "line": "  ".join(parts),
            }
        )
    events.sort(key=lambda event: event["nr"], reverse=True)
    return events


def trigger_from_entry(entry: bytes) -> Optional[dict]:
    """Decode one Tab1 trigger entry. None for an empty slot."""
    if len(entry) < TRIGGER_ENTRY_LEN:
        return None
    address = (entry[0] << 8) | entry[1]
    if address in (0, 0xFFFF):
        return None
    flags = entry[2]
    sensor_type = entry[4]
    text = bytes(entry[8:TRIGGER_ENTRY_LEN]).split(b"\x00")[0]
    return {
        "address": address,
        "flags": flags,
        "sabotage": bool(flags & _AI_SABOTAGE),
        "normally_open": bool(sensor_type & _ST_NORMALLY_OPEN),
        "normally_closed": bool(sensor_type & _ST_NORMALLY_CLOSED),
        "name": text.decode("cp1252", errors="replace").strip(),
        "levels": trigger_levels(flags),
    }


def trigger_levels(flags: int) -> list[str]:
    """Armed states in which a contact with these flags is monitored.

    A sabotage contact is only watched for tamper, never for an alarm.
    """
    if flags & _AI_SABOTAGE:
        return []
    return [state for state, mask in _LEVEL_TRIGGER_MASK.items() if flags & mask]


def open_contacts(
    triggers: dict[int, dict],
    contacts: dict[int, bool],
    state: str,
) -> Optional[bool]:
    """Check the contacts monitored in one armed state.

    True when one of them is open, False when all known ones are closed
    (or none is monitored), None when some are unknown and none is open.
    """
    relevant = [t for t in triggers.values() if state in t.get("levels", [])]
    unknown = False
    for trigger in relevant:
        closed = contacts.get(trigger["address"])
        if closed is None:
            unknown = True
        elif not closed:
            return True
    return None if unknown else False


def open_contact_names(
    triggers: dict[int, dict],
    contacts: dict[int, bool],
    state: str,
) -> list[str]:
    """Names of the monitored contacts of one armed state that are open."""
    names = []
    for index in sorted(triggers):
        trigger = triggers[index]
        if state in trigger.get("levels", []) and contacts.get(trigger["address"]) is False:
            names.append(trigger["name"] or f"Auslöser {index + 1}")
    return names


def unknown_contact_names(
    triggers: dict[int, dict],
    contacts: dict[int, bool],
    state: str,
) -> list[str]:
    """Names of the monitored contacts of one armed state without a status reply."""
    names = []
    for index in sorted(triggers):
        trigger = triggers[index]
        if state in trigger.get("levels", []) and contacts.get(trigger["address"]) is None:
            names.append(trigger["name"] or f"Auslöser {index + 1}")
    return names


def ready_for_away(triggers: dict[int, dict], contacts: dict[int, bool]) -> Optional[bool]:
    """True when every contact that Extern monitors is closed.

    None until the trigger list has been read.
    """
    if not triggers:
        return None
    result = open_contacts(triggers, contacts, STATE_ARMED_AWAY)
    return None if result is None else not result


def breach(
    triggers: dict[int, dict],
    contacts: dict[int, bool],
    state: Optional[str],
) -> Optional[bool]:
    """True while armed and a contact of that level is open.

    False while disarmed. None while armed but the trigger list is not known.
    """
    if not is_armed(state):
        return False
    if not triggers:
        return None
    return open_contacts(triggers, contacts, state)


def ensure_alarm_runtime(device) -> None:
    """Add the trigger and contact attributes to a device object."""
    if getattr(device, "alarm_triggers", None) is None:
        device.alarm_triggers = {}
    if getattr(device, "alarm_contacts", None) is None:
        device.alarm_contacts = {}
    if not hasattr(device, "alarm_tab_counts"):
        device.alarm_tab_counts = None
    if getattr(device, "alarm_log_lines", None) is None:
        device.alarm_log_lines = {}
    if not hasattr(device, "alarm_log"):
        device.alarm_log = None


def trigger_level_names(trigger: dict) -> list[str]:
    """Human labels for the levels of one trigger, in arming order."""
    return [_LEVEL_TRIGGER_NAMES[state] for state in trigger.get("levels", [])]
