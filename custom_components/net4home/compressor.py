class CompressionError(Exception):
    pass

def compress(data: bytes) -> bytes:
    """
    Ein sehr einfacher RLL-Kompressor angelehnt an N4HBUS_CompressSection.
    Hier als Beispiel: fügt nur die Länge + Daten + Endmarkierung + Prüfsumme an.
    Für echte Kompression müsste man noch Runs codieren.
    """
    # Länge als 2 Bytes (HighByte, LowByte)
    length = len(data)
    hi = (length >> 8) & 0xFF
    lo = length & 0xFF
    cs = sum(data) & 0xFFFFFFFF

    # Header (Länge)
    compressed = bytes([hi, lo])
    compressed += data
    compressed += b'\xC0'  # Ende-Marker (gemäß Perl-Code)
    # Prüfsumme als 4 Bytes big endian (wie im Perl-Code)
    compressed += bytes([
        (cs >> 24) & 0xFF,
        (cs >> 16) & 0xFF,
        (cs >> 8) & 0xFF,
        cs & 0xFF,
    ])
    # Laut Perl wird noch ein Längenbyte + 3 Nullen vorangestellt:
    total_len = len(compressed)
    prefix = bytes([total_len]) + b'\x00\x00\x00'
    return prefix + compressed

def decompress(data: bytes) -> bytes:
    """
    Einfacher Dekompressor für die Daten nach dem Perl-Algorithmus.
    Hier simulieren wir nur die reine Rückgabe der Nutzdaten ohne Runs,
    da der Perl-Code eine einfache RLL-Variante mit speziellen Bitmasken nutzt.
    """

    if len(data) < 7:
        raise CompressionError("Daten zu kurz für Dekompression")

    # Laut Perl wird das erste Byte als Länge genutzt (prefix)
    len_prefix = data[0]
    # Die nächsten 3 Bytes sind Nullen (Padding)
    # Danach folgt der komprimierte Datenblock

    # Einfachheitshalber ignorieren wir hier die echte RLL-Dekompression und
    # extrahieren den Block anhand der Länge

    compressed_section = data[4:]  # Nach prefix + 3 Nullen

    # Nun interpretieren wir die 2 Bytes Länge als Länge der unkomprimierten Daten
    if len(compressed_section) < 2:
        raise CompressionError("Kein Längenfeld im komprimierten Block")

    length_hi = compressed_section[0]
    length_lo = compressed_section[1]
    uncompressed_len = (length_hi << 8) + length_lo

    # Datenbereich ohne Header + Prüfsumme + Endmarker
    # Endmarker 0xC0, Prüfsumme 4 Bytes am Ende
    # Daten liegen zwischen Byte 2 und (len-5)

    data_start = 2
    data_end = len(compressed_section) - 5  # 1 Endmarker + 4 Prüfsumme

    if data_end < data_start:
        raise CompressionError("Ungültige komprimierte Datenlänge")

    # Extrahiere Datenblock (unkomprimiert, da wir keine Runs verarbeiten)
    decompressed = compressed_section[data_start:data_end]

    if len(decompressed) != uncompressed_len:
        # Warnung, da Länge nicht passt
        # In der echten Dekompression würde man hier Runs expandieren
        pass

    return decompressed
