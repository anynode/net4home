"""EXT-LD (Motorriegel) telegram helpers.

Values come from the konfigurator sources:
- Ext_LDu.pas: D0_SET 1 = verriegeln, D0_SET 3 = entriegeln, D0_ACTOR_ACK flags in ddata[2]
- uh2nApi.pas: GOR_* status bits, EE_ADR_LOCAL_ADR
- n4h_AdrTypen.pas: command table of OT_EXT_LD_BASE
"""
from typing import Optional

D0_SET = 50
D0_REQ = 54
D0_ACTOR_ACK = 55

# D0_SET value on the base object (objadr)
EXT_LD_LOCK_VALUE = 1  # Verriegeln
EXT_LD_UNLOCK_VALUE = 3  # Entriegeln (Konfigurator "Entriegeln")
EXT_LD_UNLOCK_BUZZ_VALUE = 4  # Entriegeln und Summen (Ext_LDu.pas bentriegeln_und_summenClick)

# Status bits in ddata[2] of D0_ACTOR_ACK
GOR_VERRIEGELT = 0x01
GOR_DIR_A = 0x02
GOR_DIR_B = 0x04
GOR_NACHTBETRIEB = 0x08
GOR_TUER_IST_GESCHLOSSEN = 0x10
GOR_TASTE_ERLAUBT = 0x20
GOR_MANUELL_VERDREHT = 0x40

# Modulspec line 0 (12 bytes per line since V1.12). ddata[0] = command, ddata[1] = line,
# ddata[2] = first byte of the line. EE_ADR_LOCAL_ADR is at record offset 5 (2 bytes, big endian).
_RECORD_START = 2
_EE_ADR_LOCAL_ADR = 5


def ext_ld_base_from_modulspec(ddata: bytes) -> Optional[int]:
    """Return the base object address (EE_ADR_LOCAL_ADR) from a modulspec line-0 reply."""
    address_at = _RECORD_START + _EE_ADR_LOCAL_ADR
    if len(ddata) < address_at + 2 or ddata[1] != 0:
        return None
    address = (ddata[address_at] << 8) | ddata[address_at + 1]
    if address <= 0 or address >= 0xFFFF:
        return None
    return address


def ext_ld_status(ddata: bytes) -> Optional[dict]:
    """Decode a D0_ACTOR_ACK reply of an EXT-LD module.

    Returns None if the telegram is not a D0_ACTOR_ACK with a status byte.
    """
    if len(ddata) < 3 or ddata[0] != D0_ACTOR_ACK:
        return None
    flags = ddata[2]
    manually_turned = bool(flags & GOR_MANUELL_VERDREHT)
    return {
        "locked": bool(flags & GOR_VERRIEGELT),
        "manually_turned": manually_turned,
        "door_closed": bool(flags & GOR_TUER_IST_GESCHLOSSEN),
        "night_mode": bool(flags & GOR_NACHTBETRIEB),
        "button_allowed": bool(flags & GOR_TASTE_ERLAUBT),
        "flags": flags,
    }
