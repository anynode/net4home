"""UP-RF keys stored in the module table.

The configurator keeps them in 16-byte modulspec lines:

- line 2, byte 0: master slot index
- line 3: keys 0..2, line 4: keys 3..5, line 5: keys 6..8, line 6: key 9
- each key is 5 bytes

The door window can also return one slot per packet: byte 2 is the index,
bytes 3..7 the key, byte 8 is non-zero for the master. Delete all stored
keys is D0_WR_MODULSPEC_DATA, 0xFB, 0.
"""

from typing import Optional

RF_KEY_COUNT = 10
RF_KEY_TABLE_LINES = (2, 3, 4, 5, 6)
_EMPTY_CODES = frozenset({"0000000000", "FFFFFFFFFF"})


def _key_code(raw: bytes) -> str:
    code = bytes(raw[:5]).hex().upper()
    if code in _EMPTY_CODES:
        return ""
    return code


def parse_rf_key_record(ddata: bytes) -> Optional[tuple[int, str, bool]]:
    """Return ``(index, code, is_master)`` from a door-window slot packet."""
    if len(ddata) < 9:
        return None
    index = ddata[2]
    if index >= RF_KEY_COUNT:
        return None
    code = _key_code(ddata[3:8])
    if not code:
        return index, "", False
    return index, code, ddata[8] != 0


def parse_rf_master_index(ddata: bytes) -> Optional[int]:
    """Return the master slot from modulspec line 2."""
    if len(ddata) < 3 or ddata[1] != 2:
        return None
    index = ddata[2]
    if index >= RF_KEY_COUNT:
        return None
    return index


def parse_rf_key_table_line(ddata: bytes) -> Optional[list[tuple[int, str]]]:
    """Return ``(slot, code)`` pairs from modulspec lines 3..6."""
    if len(ddata) < 7 or ddata[1] not in (3, 4, 5, 6):
        return None
    record = ddata[2:]
    if ddata[1] == 6:
        indexes = (9,)
    else:
        base = (ddata[1] - 3) * 3
        indexes = (base, base + 1, base + 2)
    slots = []
    for number, slot in enumerate(indexes):
        start = number * 5
        chunk = record[start:start + 5]
        if len(chunk) < 5:
            break
        slots.append((slot, _key_code(chunk)))
    return slots or None
