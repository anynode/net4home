import logging
from typing import NamedTuple
from .const import (
    D0_SET_IP,
    D0_ENUM_ALL,
    D0_ACK_TYP,
    D0_ACK,
    D0_NOACK,
    D0_SET,
    D0_INC,
    D0_DEC,
    D0_TOGGLE,
    D0_REQ,
    D0_ACTOR_ACK,
    D0_SET_N,
    D0_SENSOR_ACK,
    D0_VALUE_ACK,
    D0_VALUE_REQ,
    D0_STATUS_INFO,
    saCYCLIC,
    saACK_REQ,
    saPNR_MASK,
    LOCK_BIT_AKTIV,
    LOCK_BIT_BIN_VALUE,
    MI_EMPTY,
    MI_BRC,
    BROADCASTIP,
    D0_MODUL_BUSY,
    D0_RD_MODULSPEC_DATA,
    D0_RD_MODULSPEC_DATA_ACK,
    D0_WR_MODULSPEC_DATA,
    D0_ENABLE_CONFIGURATION,
    D1_ENABLE_CONFIGURATION_OK_BYTE,
    D1_ENABLE_FCONFIGURATION_OK_BYTE,
    D0_ENABLE_CONFIGURATION_OFF_BYTE,
    D10_CONFIG_ENABLE_BIT,
    D10_FCONFIG_ENABLE_BIT,
    D0_SET_SERIAL,
    D0_GET_SERIAL_REQ,
    D0_GET_SERIAL_ACK,
    D0_START,
    D0_STOP,
    D0_SET_TIME_VAL,
    D0_DIM,
    D0_START_DIM,
    D0_LOCK,
    D0_LOCK_STATE_REQ,
    D0_LOCK_STATE_ACK,
    D0_SAVE,
    D0_RECALL,
    D0_STOP_LOOP,
    D0_MODUL_SPECIFIC_INFO,
    D0_SEND_STORED,
    D0_ERASE_GRP_DATA,
    D0_SMS,
    D1_SMS_TEXTBUF_INIT,
    D1_SMS_PRIORITY_BIT1,
    D1_SMS_PRIORITY_BIT0,
    D1_SMS_PRIORITY_BITS,
    D1_SEND_SMS_USE_TELBOOK,
    D1_SEND_SMS_USE_NUMBER,
    D1_SMS_ADD_TEXT,
    D1_SMS_COPY_TEXT,
    D1_SEND_SMS_USE_TELBOOK_MASK,
    D0_SET_UP,
    D0_SET_DOWN,
    D0_STARTDIM_UP,
    D0_STARTDIM_DOWN,
    D0_VALUE_NOTREADY,
    D0_SAVE_CALIBRATION,
    D0_SET_PROFIL,
    D0_CHANGE_PROFIL,
    D0_RD_EE16_DATA,
    D0_RD_EE16_DATA_ACK,
    D0_WR_EE16_DATA,
    D0_TRANSFER,
    D0_TRANSFER_CLEAR_TCS,
    D0_TRANSFER_READ_TCS,
    D0_TRANSFER_SELECT_MEM,
    D0_TRANSFER_START_UPDATE,
    D0_TRANSFER_SELECT_MEM_FLASH,
    D0_TRANSFER_SELECT_MEM_EEPROM,
    D0_TRANSFER_RD,
    D0_TRANSFER_RESET,
    D0_TRANSFER_BOOTLOADER,
    D0_TRANSFER_CALC_CS,
    D0_TRANSFER_WR,
    D0_TRANSFER_ERASE,
    D0_SLEEP,
    IN_HW_NR_IS_CLOCK,
    DCF77_SYNC_PHASE,
    DCT_FEIERTAG,
    DCF77_KEIN_EMPFANG,
    DCF77_SOMMERZEIT,
    DCF77_SOMMERZEIT_ANGUENDIGUNG,
    VAL_IS_WORD16,
    IN_HW_NR_IS_TEMP,
    IN_HW_NR_IS_PRESS_TENDENZ,
    IN_HW_NR_IS_PRESS_MBAR,
    IN_HW_NR_IS_LICHT_ANALOG,
    IN_HW_NR_IS_KMH,
    USE_FROMEL_16BIT_X8,
    VAL_IS_MENGE_LITER,
    USE_FROMEL_16BIT_X10,
    IN_HW_NR_IS_REGEN,
    IN_HW_NR_IS_HUMIDITY,
    VAL_IS_MIN_TAG_WORD_SA,
    VAL_IS_MIN_TAG_WORD_SU,
    IN_HW_NR_IS_RF_TAG_READER,
)

    
_LOGGER = logging.getLogger(__name__)


class TN4Hpaket(NamedTuple):
    type8: int          # byte (0..255)
    ipsrc: int          # word (0..65535)
    ipdest: int         # word
    objsrc: int         # word
    ddatalen: int       # byte
    ddata: bytes        # rohes Datenfeld
    csRX: int           # byte
    csCalc: int         # byte
    length: int         # byte
    posb: int           # byte


def n4h_parse(payload_bytes: bytes) -> tuple[str, TN4Hpaket]:
    payload = payload_bytes.hex()
    ret = ""

    _LOGGER.warning("Paket Payload: %s", payload_bytes.hex())

    if len(payload) < 40:
        return ("Payload zu kurz für Parsing", None)

    ip = int(payload[2:4] + payload[0:2], 16)
    ret += f"IP={ip}\t"

    unknown = payload[4:16]
    ret += f"({unknown})\t"

    type8 = int(payload[16:18], 16)
    ret += f"type8={type8}\t"

    # MI = ipsrc
    mi_str = payload[18:20] + payload[16:18]
    ipsrc = int(mi_str, 16)
    ret += f"MI={mi_str}\t"

    ipdst = int(payload[22:24] + payload[20:22], 16)
    ret += f"ipdst={ipdst}\t"

    objsrc = int(payload[26:28] + payload[24:26], 16)
    ret += f"objsrc={objsrc}\t"

    datalen = int(payload[28:30], 16)
    ret += f"datalen={datalen}\t"

    ddata_end = 30 + datalen * 2
    if len(payload) < ddata_end + 8:
        return ("Payload zu kurz für ddata und Checkbytes", None)

    ddata_hex = payload[30:ddata_end]
    ret += f"ddata={ddata_hex}\t"

    pos = ddata_end

    csRX = int(payload[pos:pos+2], 16)
    csCalc = int(payload[pos+2:pos+4], 16)
    length = int(payload[pos+4:pos+6], 16)
    posb = int(payload[pos+6:pos+8], 16)
    ret += f"({csRX}/{csCalc}/{length}/{posb})"

    # ddata als Bytes
    ddata_bytes = bytes.fromhex(ddata_hex)

    paket = TN4Hpaket(
        type8=type8,
        ipsrc=ipsrc,
        ipdest=ipdst,
        objsrc=objsrc,
        ddatalen=datalen,
        ddata=ddata_bytes,
        csRX=csRX,
        csCalc=csCalc,
        length=length,
        posb=posb,
    )

    # log_line = f"OBJ {ipsrc:04X}   {objsrc:05d} >  {ipdst:04X} {datalen:02X} {' '.join(ddata_hex.upper()[i:i+2] for i in range(0, len(ddata_hex), 2))}  {interpret_n4h_sFkt(paket)}"
    log_line = f"OBJ {ipsrc:04X}   {objsrc:05d} >  {ipdst:04X} {datalen:02X} {' '.join(ddata_hex.upper()[i:i+2] for i in range(0, len(ddata_hex), 2)).ljust(45)} {interpret_n4h_sFkt(paket)}"

    _LOGGER.debug(log_line)

    return ret, paket

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
    if len(padr) < 2:
        raise ValueError("padr muss mindestens 2 Bytes lang sein")
    adr = padr[0] * 256 + padr[1]
    if adr & 0x8000 == 0x8000:
        return f"GRP {adr - 0x8000}"
    else:
        return f"OBJ {adr}"

def adr_to_text(adr: int) -> str:
    if adr & 0x8000 == 0x8000:
        return f"G{adr - 0x8000}"
    else:
        return str(adr)

def adr_to_text_gruppe(adr: int) -> str:
    return str(adr & 0x7FFF)

def text_to_adr(s: str) -> int:
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
    while len(s) > 0 and not s[0].isdigit():
        s = s[1:]
    try:
        value = int(s)
    except ValueError:
        value = 0
    return value | 0x8000

def interpret_n4h_sFkt(paket) -> str:

    sFkt = ""

    if paket.ddatalen == 0:
        return "keine Daten"

    # Beispiel: LCD-Text falls ddata[0] == D0_SET_N und ddata[1] == 0xF0
    if paket.ddatalen >= 2 and paket.ddata[0] == D0_SET_N and paket.ddata[1] == 0xF0:
        try:
            text = paket.ddata[5:paket.ddatalen].decode("latin1")
        except Exception:
            text = "<decode error>"
        sFkt = f"LCD-Text [{text}]"
        return sFkt

    # Statusflags aus type8
    if paket.type8 & saCYCLIC:
        pnr = (paket.type8 & saPNR_MASK) >> 4
        sFkt += f"CY{pnr} "

    if paket.type8 & saACK_REQ:
        pnr = (paket.type8 & saPNR_MASK) >> 4
        sFkt += f"AR{pnr} "

    # Basierend auf ddata[0] können weitere Interpretationen ergänzt werden
    b0 = paket.ddata[0]

    if b0 == D0_SET_N:
        sFkt += f"D0_SET_N, {paket.ddata[1]},{paket.ddata[2]}"
    elif b0 == D0_ACK:
        sFkt += "D0_ACK"
    elif b0 == D0_NOACK:
        sFkt += "NO_ACK (Error)"
    elif b0 == D0_ACTOR_ACK:
        sFkt += "D0_ACTOR_ACK"
    elif b0 == D0_VALUE_ACK:
        sFkt += "D0_VALUE_ACK"
        sFkt += " " + decode_and_print_value_ack(paket.ddata)
    elif b0 == D0_VALUE_REQ:
        sFkt += "D0_VALUE_REQ"
    elif b0 == D0_STATUS_INFO:
        sFkt += "D0_STATUS_INFO"
    elif b0 == D0_SENSOR_ACK:
        sFkt += "D0_SENSOR_ACK"
    elif b0 == D0_TOGGLE:
        sFkt += "D0_TOGGLE"
    elif b0 == D0_REQ:
        sFkt += "D0_REQ"
    elif b0 == D0_INC:
        sFkt += "D0_INC"
    elif b0 == D0_DEC:
        sFkt += "D0_DEC"
    elif b0 == D0_ENUM_ALL:
        sFkt += "D0_ENUM_ALL"
    else:
        sFkt += f"Unbekanntes Paket 0x{b0:02X}"

    return sFkt.strip()

def int_to_str2(i: int) -> str:
    """Wandelt eine Zahl in einen zweistelligen String mit führender Null um."""
    return f"{i:02d}"


def bcd_to_bin(bcd_in: int) -> int:
    """Konvertiert eine BCD-codierte Zahl (Byte) in eine Ganzzahl."""
    return ((bcd_in & 0xF0) >> 4) * 10 + (bcd_in & 0x0F)

def su_woche_bit_mask_to_text(dow: int) -> str:
    result = ''
    result += 'Mo' if dow & 0x01 else '--'
    result += 'Di' if dow & 0x02 else '--'
    result += 'Mi' if dow & 0x04 else '--'
    result += 'Do' if dow & 0x08 else '--'
    result += 'Fr' if dow & 0x10 else '--'
    result += 'Sa' if dow & 0x20 else '--'
    result += 'So' if dow & 0x40 else '--'
    result += 'Fe' if dow & 0x80 else '--'
    return result

def su_woche_bit_mask_to_text2(dow: int) -> str:
    result = ''
    if dow & 0x01:
        result += 'Mo'
    if dow & 0x02:
        result += 'Di'
    if dow & 0x04:
        result += 'Mi'
    if dow & 0x08:
        result += 'Do'
    if dow & 0x10:
        result += 'Fr'
    if dow & 0x20:
        result += 'Sa'
    if dow & 0x40:
        result += 'So'
    if dow & 0x80:
        result += 'Fe'
    return result

def wochentag_to_text(dow: int) -> str:
    mapping = {
        0: 'Mo',
        1: 'Di',
        2: 'Mi',
        3: 'Do',
        4: 'Fr',
        5: 'Sa',
        6: 'So'
    }
    return mapping.get(dow, '')


def decode_and_print_value_ack(paket: bytes) -> str:
    """
    Decodiert ein D0_VALUE_ACK-Paket (paket ist bytes, entspricht paket.ddata).
    Liefert einen beschreibenden String zurück.
    """
    # Lokale Statusvariablen
    s_last_value_ack_text = ""
    gs_last_key_info = ""
    g_analog_value = 0

    s = ""
    ddata = paket

    # Konstanten (nur die relevanten)
    IN_HW_NR_IS_CLOCK = 6
    DCF77_SYNC_PHASE = 0x10
    DCT_FEIERTAG = 0x08
    DCF77_KEIN_EMPFANG = 0x04
    DCF77_SOMMERZEIT = 0x01
    DCF77_SOMMERZEIT_ANGUENDIGUNG = 0x02

    VAL_IS_WORD16 = 14
    IN_HW_NR_IS_TEMP = 9
    IN_HW_NR_IS_PRESS_TENDENZ = 49
    IN_HW_NR_IS_PRESS_MBAR = 48
    IN_HW_NR_IS_LICHT_ANALOG = 5
    IN_HW_NR_IS_KMH = 41
    USE_FROMEL_16BIT_X8 = 7
    VAL_IS_MENGE_LITER = 53
    USE_FROMEL_16BIT_X10 = 8
    IN_HW_NR_IS_REGEN = 47
    IN_HW_NR_IS_HUMIDITY = 11
    VAL_IS_MIN_TAG_WORD_SA = 50
    VAL_IS_MIN_TAG_WORD_SU = 51
    IN_HW_NR_IS_RF_TAG_READER = 7

    # Auswertung
    #if len(ddata) < 6:
    #    return "Paket zu kurz"

    if ddata[1] == IN_HW_NR_IS_CLOCK:
        flags = ddata[11]
        if flags & DCF77_SYNC_PHASE:
            s += " sync..."
        if flags & DCT_FEIERTAG:
            s += " Feiertag"
        if flags & DCF77_KEIN_EMPFANG:
            s += " KEIN-EMPFANG"
        if flags & DCF77_SOMMERZEIT:
            s += " MESZ"
        else:
            s += " MEZ"
        if flags & DCF77_SOMMERZEIT_ANGUENDIGUNG:
            s += " SOMMERZEIT_ANGUENDIGUNG"
        s = (
            "Uhrzeit "
            + int_to_str2(bcd_to_bin(ddata[5]))
            + ":"
            + int_to_str2(bcd_to_bin(ddata[4]))
            + ":"
            + int_to_str2(bcd_to_bin(ddata[3]))
            + "  "
            + int_to_str2(bcd_to_bin(ddata[6]))
            + "."
            + int_to_str2(bcd_to_bin(ddata[7]))
            + "."
            + str(2000 + bcd_to_bin(ddata[10]))
            + " "
            + su_woche_bit_mask_to_text2(1 << bcd_to_bin(ddata[8]))
            + s
        )
        s_last_value_ack_text = s
    elif ddata[1] == VAL_IS_WORD16:
        i_analog_value = ddata[3] * 256 + ddata[4]
        s_last_value_ack_text = str(i_analog_value)
        s = "word16 " + str(i_analog_value)
    elif ddata[1] == IN_HW_NR_IS_TEMP:
        i_analog_value = ddata[3] * 256 + ddata[4]
        if i_analog_value > 0x8000:
            i_analog_value -= 0x10000
        i_analog_value = (i_analog_value * 10) // 16
        s_last_value_ack_text = f"{i_analog_value / 10:.1f}°C"
        s = "Temperatur " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_PRESS_TENDENZ:
        i_analog_value = ddata[4]
        if i_analog_value == 0:
            s_last_value_ack_text = "noch nicht verfügbar (Tendenz ist erst 60 Minuten nach Powerup verfügbar)"
        elif i_analog_value == 1:
            s_last_value_ack_text = "stark fallend (unbeständiges Tiefdrucksystem, Sturm)"
        elif i_analog_value == 2:
            s_last_value_ack_text = "fallend (stabiles Schlechtwetter)"
        elif i_analog_value == 3:
            s_last_value_ack_text = "konstant (stabiles Wetter)"
        elif i_analog_value == 4:
            s_last_value_ack_text = "steigend (stabiles Schönwetter)"
        elif i_analog_value == 5:
            s_last_value_ack_text = "stark steigend (unbeständiges Hochdrucksystem)"
        else:
            s_last_value_ack_text = "nicht erlaubter Wert " + str(i_analog_value)
        s = "Luftdruck Tendenz: " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_PRESS_MBAR:
        i_analog_value = ddata[3] * 256 + ddata[4]
        s_last_value_ack_text = f"{i_analog_value / 10:.1f} hPas"
        s = "Druck " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_LICHT_ANALOG:
        i_analog_value = ddata[3] * 256 + ddata[4]
        s_last_value_ack_text = str(i_analog_value)
        s = "Licht " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_KMH:
        i_analog_value = ddata[3] * 256 + ddata[4]
        if ddata[2] == USE_FROMEL_16BIT_X8:
            i_analog_value = i_analog_value // 8
        s_last_value_ack_text = f"{i_analog_value} km/h"
        s = "Geschwindigkeit " + s_last_value_ack_text
    elif ddata[1] == VAL_IS_MENGE_LITER:
        r_analog_value = ddata[3] * 256 + ddata[4]
        if ddata[2] == USE_FROMEL_16BIT_X10:
            r_analog_value = r_analog_value / 10
        s_last_value_ack_text = f"{r_analog_value:.1f} Liter/h"
        s = "Regenmenge " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_REGEN:
        i_analog_value = ddata[3] * 256 + ddata[4]
        s_last_value_ack_text = f"{i_analog_value} %"
        s = "Regen " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_HUMIDITY:
        i_analog_value = ddata[3] * 256 + ddata[4]
        s_last_value_ack_text = f"{i_analog_value} %"
        s = "Feuchte/Regen " + s_last_value_ack_text
    elif ddata[1] in [VAL_IS_MIN_TAG_WORD_SA, VAL_IS_MIN_TAG_WORD_SU]:
        i_analog_value = ddata[3] * 256 + ddata[4]
        # w1440TimeToStr wird nicht definiert, hier ein simpler Ersatz (hh:mm)
        hh = i_analog_value >> 8
        mm = i_analog_value & 0xFF
        s_last_value_ack_text = f"{hh:02d}:{mm:02d} hh:mm"
        if ddata[1] == VAL_IS_MIN_TAG_WORD_SA:
            s_last_value_ack_text += " Sonnenaufgang heute"
        else:
            s_last_value_ack_text += " Sonnenuntergang heute"
        s = "Zeit " + s_last_value_ack_text
    elif ddata[1] == IN_HW_NR_IS_RF_TAG_READER:
        gs_last_key_info = (
            f"{ddata[3]:02X}{ddata[4]:02X}{ddata[5]:02X}{ddata[6]:02X}{ddata[7]:02X}"
        )
        tag_state = ddata[9] & 6
        if tag_state == 0:
            gs_last_key_info += " vorgehalten"
        elif tag_state == 2:
            gs_last_key_info += " lang vorgehalten"
        elif tag_state == 4:
            gs_last_key_info += " weggezogen nach kurz"
        s = "RF-Key " + gs_last_key_info
        s_last_value_ack_text = gs_last_key_info
    else:
        analog_value = ddata[2] * 256 + ddata[3]
        s = f"D0_VALUE_ACK {analog_value} diff {analog_value - g_analog_value}"
        s_last_value_ack_text = str(analog_value)
        g_analog_value = analog_value

    return s
