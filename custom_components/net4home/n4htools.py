import logging

_LOGGER = logging.getLogger(__name__)


def log_parsed_packet(header: bytes, payload: bytes):
    """Log a parsed packet in a human readable form."""
    try:
        # TN4Hpaket-Struktur aus n4h_L2_def.pas:
        # type8 (1B), ipsrc (2B), ipdest (2B), objsrc (2B), ddatalen (1B), ddata (64B), csRX (1B), csCalc (1B), len (1B), posb (1B)
        if len(payload) < 8:
            _LOGGER.warning("Paket zu kurz für Parsing: %s", payload.hex())
            return
        type8 = payload[0]
        ipsrc = int.from_bytes(payload[1:3], "little")
        ipdest = int.from_bytes(payload[3:5], "little")
        objsrc = int.from_bytes(payload[5:7], "little")
        ddatalen = payload[7]
        ddata = payload[8:8+ddatalen]
        objdst = ipdest

        mi_str = f"{ipsrc:05d}"
        objsrc_str = f"{objsrc:05d}"
        objdst_str = f"{objdst:05d}"
        objadr_str = f"{objdst:04x}".upper()
        ddata_str = " ".join(f"{b:02X}" for b in ddata)
        logstr = f"OBJ {objadr_str}   {mi_str} >  {objdst_str} {type8:02X} {ddata_str}"
        _LOGGER.info(logstr)
    except Exception as ex:
        _LOGGER.error("Fehler beim Paket-Parsing: %s", ex)

def adr_to_text_obj_grp(padr: bytes) -> str:
    """
    Entspricht Pascal AdrToTextOBJ_GRP(padr: pbyte).
    padr: bytes-Objekt mit mindestens 2 Bytes.
    Liest zwei Bytes, kombiniert zu einem Wort (word = 16 Bit),
    prüft oberstes Bit und gibt 'GRP N' oder 'OBJ N' zurück.
    """
    if len(padr) < 2:
        raise ValueError("padr muss mindestens 2 Bytes lang sein")
    adr = padr[0] * 256 + padr[1]
    if adr & 0x8000 == 0x8000:
        return f"GRP {adr - 0x8000}"
    else:
        return f"OBJ {adr}"

def adr_to_text(adr: int) -> str:
    """
    Entspricht Pascal AdrToText(adr: word).
    Wenn höchstes Bit gesetzt, 'G'+Zahl, sonst nur Zahl.
    """
    if adr & 0x8000 == 0x8000:
        return f"G{adr - 0x8000}"
    else:
        return str(adr)

def adr_to_text_gruppe(adr: int) -> str:
    """
    Entspricht Pascal AdrToTextGruppe(adr: word).
    Gibt nur die unteren 15 Bits als Dezimalzahl zurück.
    """
    return str(adr & 0x7FFF)

def text_to_adr(s: str) -> int:
    """
    Entspricht Pascal TextToAdr(s: string).
    Prüft auf 'G' oder 'g' am Anfang, entfernt alle Buchstaben vorne,
    konvertiert Rest zu Zahl und addiert 0x8000 falls 'G' gesetzt war.
    """
    adr = 0x8000 if ('G' in s.upper()) else 0
    # Alle führenden Nicht-Ziffern entfernen
    while len(s) > 0 and not s[0].isdigit():
        s = s[1:]
    try:
        value = int(s)
    except ValueError:
        value = 0
    return adr + value

def text_to_adr_gruppe(s: str) -> int:
    """
    Entspricht Pascal TextToAdrGruppe(s: string).
    Entfernt führende Nicht-Ziffern und gibt Zahl mit gesetztem 0x8000 zurück.
    """
    while len(s) > 0 and not s[0].isdigit():
        s = s[1:]
    try:
        value = int(s)
    except ValueError:
        value = 0
    return value | 0x8000
