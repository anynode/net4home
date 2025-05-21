class CompressionError(Exception):
    """Exception für Fehler bei der Dekompression."""
    pass


decompressor_err = 0
decompressor_errAdr = 0


def decompress(data: bytes, use_cs: bool = True, max_out_len: int = 10000) -> bytes:
    """
    Entspricht der Pascal-Funktion decompSection.
    Dekomprimiert Daten mit RLL-ähnlichem Verfahren.

    Args:
        data: komprimierte Eingabedaten als Bytes
        use_cs: Prüfsummenprüfung aktivieren (Standard: True)
        max_out_len: maximale Ausgabelänge (Standard: 10000 Bytes)

    Returns:
        dekomprimierte Bytes

    Raises:
        CompressionError bei Dekompressionsfehlern
    """

    global decompressor_err, decompressor_errAdr

    decompressor_err = 0
    decompressor_errAdr = 0

    out = bytearray()
    cs_calc = 0
    i = 0
    ende = False
    err = False

    length = len(data)

    while i < length and len(out) < max_out_len and not ende and not err:
        b = data[i]
        flag = b & 0xC0

        if flag == 0xC0:
            # Ende + 4-Byte Prüfsumme
            if i + 4 >= length:
                err = True
                decompressor_err = -3  # Zu kurze Daten für Prüfsumme
                break

            cs_rx = (data[i+1] << 24) | (data[i+2] << 16) | (data[i+3] << 8) | data[i+4]
            ende = True
            i += 5

            if use_cs and cs_rx != cs_calc:
                err = True
                decompressor_err = -100
                decompressor_errAdr = cs_rx - cs_calc
                break

        elif flag == 0x00:
            # Unkomprimierter Block (Store)
            if i + 1 >= length:
                err = True
                decompressor_err = -3
                break
            in_block = (data[i] << 8) | data[i+1]
            i += 2

            if i + in_block > length:
                err = True
                decompressor_err = -4
                break

            for _ in range(in_block):
                val = data[i]
                out.append(val)
                cs_calc = (cs_calc + val) & 0xFFFFFFFF
                i += 1

        elif flag == 0x40:
            # Komprimierter Block (CopyChar)
            if i + 2 >= length:
                err = True
                decompressor_err = -3
                break

            in_block = ((data[i] << 8) | data[i+1]) & 0x3FFF  # 14 bit Länge
            val = data[i+2]
            i += 3

            for _ in range(in_block):
                out.append(val)
                cs_calc = (cs_calc + val) & 0xFFFFFFFF

        elif flag == 0x80:
            # Fehler
            err = True
            decompressor_err = -2
            i += 1

        else:
            # Unerwartetes Flag (sollte nicht passieren)
            err = True
            decompressor_err = -1
            i += 1

        decompressor_errAdr = i

    if err or not ende:
        raise CompressionError(f"Dekompressionsfehler {decompressor_err} bei Position {decompressor_errAdr}")

    if len(out) > max_out_len:
        raise CompressionError(f"Dekomprimierte Daten zu lang ({len(out)} Bytes, max {max_out_len})")

    return bytes(out)
