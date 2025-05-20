import logging

_LOGGER = logging.getLogger(__name__)


def n4hbus_compress_section(p_uncompressed: str) -> str:
    cs = sum(int(p_uncompressed[i*2:i*2+2], 16) for i in range(len(p_uncompressed)//2))
    length = len(p_uncompressed) // 2
    hi = length >> 8
    lo = length & 0xFF
    p_compressed = f"{hi:02X}{lo:02X}"
    p = 0
    while p < length:
        p_compressed += p_uncompressed[p*2:p*2+2]
        p += 1
    p_compressed += "C0"
    p_compressed += f"{(cs>>24)&0xFF:02X}{(cs>>16)&0xFF:02X}{(cs>>8)&0xFF:02X}{cs&0xFF:02X}"
    plen = len(p_compressed) // 2
    p_compressed = f"{plen:02X}000000" + p_compressed
    return p_compressed


def n4hbus_decomp_section(p2: str, fs: int) -> str:
    ret = ''
    zaehler = 0
    ende = False
    err = False
    gPout = ''
    maxoutlen = 372
    while (zaehler < fs) and (len(gPout) < maxoutlen*2) and not ende and not err:
        bb = p2[zaehler*2:zaehler*2+2]
        bbval = int(bb, 16)
        if (bbval & 192) == 192:
            ende = True
            zaehler += 1
        elif (bbval & 192) == 0:
            bc = p2[(zaehler+1)*2:(zaehler+1)*2+2]
            inBlock = (int(bb, 16) << 8) + int(bc, 16)
            zaehler += 2
            while inBlock > 0:
                gPout += p2[zaehler*2:zaehler*2+2]
                zaehler += 1
                inBlock -= 1
        elif (bbval & 192) == 64:
            bc = p2[(zaehler+1)*2:(zaehler+1)*2+2]
            inBlock = ((int(bb, 16) << 8) + int(bc, 16)) & 16383
            bbval_next = p2[(zaehler+2)*2:(zaehler+2)*2+2]
            zaehler += 3
            while inBlock > 0:
                gPout += bbval_next
                inBlock -= 1
        elif (bbval & 0xC0) == 0x80:
            err = True
            zaehler += 1
    if (not err) and ende:
        ret = gPout
    return ret


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
