# Verbesserungsvorschläge für Python send_raw_command

## Analyse der aktuellen Implementierung

Die aktuelle Python-Implementierung verwendet mehrere feste Werte, die verbessert werden können:

### Aktuelle feste Werte:
1. `"A10F"` - Pakettyp `N4HIP_PT_PAKET` (4001)
2. `"0000"` - Reserviertes Feld (2 Bytes)
3. `"4E000000"` - Feste Payload-Länge (78 Bytes)
4. `"00"` - Platzhalter nach type8 (1 Byte)
5. `"00000000"` - Abschluss-Bytes (csRX, csCalc, len, posb)

## Verbesserungsvorschläge

### 1. Konstanten definieren

```python
# Pakettypen
N4HIP_PT_PAKET = 4001  # 0x0FA1

# Adresstypen
SEND_AS_OBJ_GRP = 0
SEND_AS_IP = 1  # sa2_T8_IP

# Paketstruktur-Konstanten
MAX_N4H_PAKET_LEN = 64  # Maximale ddata-Länge
HEADER_SIZE = 8  # Header-Größe in Bytes
RESERVED1_DEFAULT = 0  # Standardwert für reserved1

# TN4Hpaket Struktur-Größen
TYPE8_SIZE = 1
SKIP_BYTE_SIZE = 1  # Byte nach type8 wird übersprungen
ADDRESS_SIZE = 2  # word = 2 Bytes
DDATALEN_SIZE = 1
DDATA_SIZE = MAX_N4H_PAKET_LEN
TRAILER_SIZE = 4  # csRX, csCalc, len, posb

# Berechnete Payload-Länge (ohne Header)
# type8(1) + skip(1) + ipsrc(2) + ipdest(2) + objsrc(2) + ddatalen(1) + ddata(64) + trailer(4) = 77
# Aber: Die tatsächliche Payload-Länge kann variieren je nach ddatalen!
# Standard-Payload-Länge für maximale Pakete:
STANDARD_PAYLOAD_LEN = (
    TYPE8_SIZE + SKIP_BYTE_SIZE + 
    ADDRESS_SIZE * 3 +  # ipsrc, ipdest, objsrc
    DDATALEN_SIZE + 
    DDATA_SIZE + 
    TRAILER_SIZE
)  # = 77 Bytes

# Aber die Dokumentation zeigt 78 Bytes - möglicherweise wird ein zusätzliches Byte benötigt
# oder die Berechnung berücksichtigt etwas anderes
```

### 2. Dynamische Payload-Längenberechnung

Die feste Länge `"4E000000"` (78) sollte dynamisch berechnet werden:

```python
def calculate_payload_length(ddata_len: int) -> int:
    """
    Berechnet die unkomprimierte Payload-Länge basierend auf der ddata-Länge.
    
    Args:
        ddata_len: Länge der tatsächlichen Daten (ddatalen)
    
    Returns:
        Länge des unkomprimierten Payloads in Bytes
    """
    # TN4Hpaket Struktur:
    # type8: 1 Byte
    # skip: 1 Byte (wird übersprungen beim Parsing)
    # ipsrc: 2 Bytes
    # ipdest: 2 Bytes
    # objsrc: 2 Bytes
    # ddatalen: 1 Byte
    # ddata: ddata_len Bytes (max 64)
    # trailer (csRX, csCalc, len, posb): 4 Bytes
    
    payload_len = (
        TYPE8_SIZE +           # 1
        SKIP_BYTE_SIZE +       # 1
        ADDRESS_SIZE * 3 +     # 6 (ipsrc, ipdest, objsrc)
        DDATALEN_SIZE +        # 1
        min(ddata_len, DDATA_SIZE) +  # ddata (max 64)
        TRAILER_SIZE           # 4
    )
    
    return payload_len
```

### 3. Verbesserte send_raw_command Implementierung

**WICHTIG:** `type8` ist entscheidend für die korrekte Interpretation von `ipdst`:
- `type8 = 1` (SEND_AS_IP): `ipdst` wird als **MI-Adresse** interpretiert
- `type8 = 0` (SEND_AS_OBJ_GRP): `ipdst` wird als **OBJ/GRP-Adresse** interpretiert

Die Unterscheidung zwischen OBJ und GRP erfolgt über Bit 15 der Adresse (siehe `adressen.md`).

```python
def determine_type8(ipdst: int, explicit_type8: int | None = None) -> int:
    """
    Bestimmt den type8-Wert basierend auf der Zieladresse.
    
    Args:
        ipdst: Zieladresse
        explicit_type8: Explizit gesetzter type8 (wenn None, wird automatisch bestimmt)
    
    Returns:
        type8-Wert (1 für MI, 0 für OBJ/GRP)
    """
    if explicit_type8 is not None:
        return explicit_type8
    
    # Spezialadressen: Broadcast und ENUM_ALL sind immer MI
    if ipdst == 0x7FFF or ipdst == 0xFFFF:
        return SEND_AS_IP
    
    # Adressen < 0x8000 können sowohl MI als auch OBJ sein
    # Standard: Wenn < 0x8000, annehmen es ist MI (konservativ)
    # Besser: type8 sollte explizit übergeben werden!
    if ipdst < 0x8000:
        # Warnung: Dies ist eine Annahme! type8 sollte explizit gesetzt werden
        return SEND_AS_IP
    else:
        # Adressen >= 0x8000 sind GRP-Adressen
        return SEND_AS_OBJ_GRP

async def send_raw_command(
    self, 
    ipdst: int, 
    ddata: bytes, 
    objsource: int = 0, 
    mi: int = 65281, 
    type8: int | None = None  # None = automatisch bestimmen
):
    """
    Send a command to the bus.
    
    Args:
        ipdst: Target address (can be MI or OBJ address)
          * MI address: < 0x8000 (32768), e.g. 0x0099 for module MI0099
          * OBJ address: 1 - 0x7FFE (Bit 15 = 0)
          * GRP address: 0x8001 - 0xFFFE-500 (Bit 15 = 1)
          * Special values: 0x7FFF (32767) = Broadcast, 0xFFFF (65535) = ENUM_ALL
        mi: MI address of sender (always MI address, < 0x8000)
        objsource: OBJ address of sender (can be 0 for module commands)
        type8: Address type (None = auto-detect, SEND_AS_IP=1 for MI, SEND_AS_OBJ_GRP=0 for OBJ/GRP)
          **WICHTIG:** type8 bestimmt, ob ipdst als MI oder OBJ/GRP interpretiert wird!
        ddata: Command data (max 64 bytes)
    
    Raises:
        ValueError: Wenn type8 und ipdst nicht zusammenpassen
    """
    try:
        # Validierung
        if len(ddata) > MAX_N4H_PAKET_LEN:
            raise ValueError(f"ddata too long: {len(ddata)} > {MAX_N4H_PAKET_LEN}")
        
        # Bestimme type8 (automatisch oder explizit)
        if type8 is None:
            type8 = determine_type8(ipdst)
        else:
            # Validierung: type8 sollte zur Adresse passen
            if type8 == SEND_AS_IP:
                # MI-Adresse: sollte < 0x8000 sein (außer Broadcast/ENUM_ALL)
                if ipdst >= 0x8000 and ipdst not in (0x7FFF, 0xFFFF):
                    _LOGGER.warning(
                        f"type8=SEND_AS_IP but ipdst=0x{ipdst:04X} >= 0x8000 "
                        f"(might be GRP address, should use type8=0)"
                    )
            else:  # type8 == SEND_AS_OBJ_GRP
                # OBJ/GRP-Adresse: Broadcast/ENUM_ALL sollten type8=1 haben
                if ipdst in (0x7FFF, 0xFFFF):
                    _LOGGER.warning(
                        f"type8=SEND_AS_OBJ_GRP but ipdst=0x{ipdst:04X} is special "
                        f"(should use type8=SEND_AS_IP)"
                    )
        
        # Berechne Payload-Länge dynamisch
        payload_len = calculate_payload_length(len(ddata))
        
        # === Paketaufbau im Hexstring
        # Header: 8 Bytes
        sendbus = struct.pack('<H', N4HIP_PT_PAKET).hex().upper()  # 2 Bytes: ptype (0x0FA1)
        sendbus += struct.pack('<H', RESERVED1_DEFAULT).hex().upper()  # 2 Bytes: reserved1
        sendbus += struct.pack('<I', payload_len).hex().upper()  # 4 Bytes: Payload-Länge (Little Endian)
        # Header Ende (8 Bytes total)
        
        # === Packet data after header (TN4Hpaket structure)
        # type8: First byte after header
        sendbus += f"{type8:02X}"  # type8 (1 byte)
        sendbus += "00"  # Skip byte (1 byte, result[1] is skipped in n4h_parse)
        
        # === Encode addresses (Little Endian)
        sendbus += decode_d2b(mi)  # ipsrc (2 Bytes, little endian)
        sendbus += decode_d2b(ipdst)  # ipdest (2 Bytes, little endian)
        sendbus += decode_d2b(objsource)  # objsrc (2 Bytes, little endian)
        
        # === Prepare DDATA: first byte = length, then the actual payload
        ddatalen = len(ddata)
        full_ddata = bytes([ddatalen]) + ddata
        
        # === Pad ddata to MAX_N4H_PAKET_LEN (64 bytes) = 128 hex characters
        ddata_padded = full_ddata.ljust(MAX_N4H_PAKET_LEN + 1, b'\x00')  # +1 for ddatalen byte
        ddata_hex = ddata_padded.hex().upper()
        sendbus += ddata_hex
        
        # === Abschluss mit csRX, csCalc, len, posb (4 Bytes)
        # Diese Werte werden normalerweise vom Parser gesetzt, hier mit 0 initialisiert
        sendbus += "00000000"
        
        # === Kompression & Verpackung
        compressed = compress_section(sendbus)
        compressed_bytes = bytes.fromhex(compressed)
        
        # === Finales Paket: [4 Bytes Länge] + [Komprimiertes Payload]
        final_packet = struct.pack('<I', len(compressed_bytes))  # 4 Bytes: Länge des komprimierten Payloads
        final_packet += compressed_bytes
        
        # === Logging
        ddata_list = " ".join(ddata.hex()[i:i+2].upper() for i in range(0, len(ddata.hex()), 2))
        log_line = (
            f"SEND: ipsrc=0x{mi:04X}, ipdst=0x{ipdst:04X}, objsrc={objsource}, "
            f"type8={type8}, datalen={ddatalen}, ddata=[{ddata_list}], "
            f"payload_len={payload_len}, compressed_len={len(compressed_bytes)}"
        )
        # _LOGGER.debug(log_line)
        
        # === Senden
        self._writer.write(final_packet)
        await self._writer.drain()
        
    except Exception as e:
        _LOGGER.error(f"Error sending data (raw): {e}")
        raise
```

### 4. Zusätzliche Verbesserungen

#### a) Validierung der Adressen

```python
def validate_address(addr: int, addr_type: str = "any") -> bool:
    """
    Validiert eine Adresse basierend auf ihrem Typ.
    
    Args:
        addr: Die zu validierende Adresse
        addr_type: "mi", "obj", "grp", oder "any"
    
    Returns:
        True wenn gültig, sonst False
    """
    if addr_type == "mi":
        return 1 <= addr < 0x8000 or addr == 0xFFFF  # MI oder ENUM_ALL
    elif addr_type == "obj":
        return 1 <= addr <= 0x7FFE
    elif addr_type == "grp":
        return 0x8001 <= addr <= 0xFFFE
    else:  # any
        return 1 <= addr <= 0xFFFF or addr == 0x7FFF  # Broadcast
```

#### b) Helper-Funktion für Paketaufbau

```python
def build_tn4h_paket(
    type8: int,
    ipsrc: int,
    ipdest: int,
    objsrc: int,
    ddata: bytes
) -> bytes:
    """
    Baut die TN4Hpaket-Struktur auf.
    
    Returns:
        Bytes der TN4Hpaket-Struktur
    """
    ddatalen = len(ddata)
    if ddatalen > MAX_N4H_PAKET_LEN:
        raise ValueError(f"ddata too long: {ddatalen} > {MAX_N4H_PAKET_LEN}")
    
    # type8
    packet = bytes([type8])
    # skip byte
    packet += b'\x00'
    # Adressen (Little Endian)
    packet += struct.pack('<H', ipsrc)
    packet += struct.pack('<H', ipdest)
    packet += struct.pack('<H', objsrc)
    # ddatalen
    packet += bytes([ddatalen])
    # ddata (gepaddet auf 64 Bytes)
    packet += ddata.ljust(MAX_N4H_PAKET_LEN, b'\x00')
    # Trailer (csRX, csCalc, len, posb)
    packet += b'\x00\x00\x00\x00'
    
    return packet
```

#### c) Verwendung von struct statt String-Manipulation

```python
# Statt String-Manipulation:
sendbus = "A10F" + "0000" + "4E000000" + ...

# Besser: Direktes Packen:
header = struct.pack('<HHI', N4HIP_PT_PAKET, RESERVED1_DEFAULT, payload_len)
paket_data = build_tn4h_paket(type8, mi, ipdst, objsource, ddata)
uncompressed = header + paket_data
```

## Zusammenfassung der wichtigsten Verbesserungen

2. **Dynamische Längenberechnung**: Payload-Länge basierend auf tatsächlicher ddata-Länge
3. **Validierung**: Prüfung von Adressen und Datenlängen
4. **type8-Automatik oder Validierung**: 
   - **KRITISCH**: `type8` bestimmt, ob `ipdst` als MI oder OBJ/GRP interpretiert wird
   - Automatische Bestimmung von `type8` basierend auf `ipdst` (mit Warnung)
   - Validierung, dass `type8` zur Adresse passt
   - Explizite Übergabe von `type8` wird empfohlen
5. **Strukturierte Paket-Erstellung**: Helper-Funktionen für bessere Wartbarkeit
6. **Bessere Fehlerbehandlung**: Explizite Exceptions statt stillem Fehlschlagen
7. **Dokumentation**: Klarere Kommentare und Docstrings

## Wichtige Erkenntnis: type8 und Adress-Interpretation

**`type8` ist entscheidend** für die korrekte Interpretation von `ipdst`:

| type8 | Wert | ipdst-Interpretation | Beispiel |
|-------|------|----------------------|----------|
| `SEND_AS_IP` | `1` | **MI-Adresse** (Modul-IP) | `0x0099` = Modul MI0099 |
| `SEND_AS_OBJ_GRP` | `0` | **OBJ/GRP-Adresse** | `0x1234` = Objekt, `0x8001` = Gruppe |

**Problem in aktueller Implementierung:**
- Default `type8 = SEND_AS_OBJ_GRP` (0) ist problematisch
- Wenn `ipdst` eine MI-Adresse ist, wird sie falsch interpretiert
- Wenn `ipdst` eine OBJ-Adresse ist, aber `type8=1` verwendet wird, wird sie auch falsch interpretiert

**Lösung:**
- `type8` sollte **immer explizit** übergeben werden
- Oder automatisch basierend auf `ipdst` bestimmt werden (mit Validierung)
- Validierung, dass `type8` zur Adresse passt

## Vergleich mit Pascal-Implementierung

Die Pascal-Implementierung (`sendH2Nb` in `Unit1.pas`):
- Verwendet `TN4Hpaket` Record-Struktur
- Ruft `N4HL3_sendAll(p)` auf, das die Paket-Erstellung und Kompression übernimmt
- Die tatsächliche Paket-Erstellung erfolgt in der DLL (`n4h_du2.dll`)

Die Python-Implementierung muss diese Funktionalität selbst implementieren, daher ist es wichtig:
- Die exakte Struktur zu befolgen
- Die Längen korrekt zu berechnen
- Die Kompression korrekt anzuwenden

## Kritischer Punkt: type8 und Adress-Interpretation

### Warum type8 wichtig ist

Das `type8`-Flag bestimmt, wie die `ipdest`-Adresse im Paket interpretiert wird:

1. **`type8 = 1` (SEND_AS_IP)**: 
   - `ipdest` wird als **MI-Adresse** (Modul-IP) interpretiert
   - Das Paket wird direkt an das Modul mit dieser IP-Adresse gesendet
   - Beispiel: `ipdest = 0x0099` → Modul MI0099

2. **`type8 = 0` (SEND_AS_OBJ_GRP)**:
   - `ipdest` wird als **OBJ- oder GRP-Adresse** interpretiert
   - Die Unterscheidung zwischen OBJ und GRP erfolgt über Bit 15:
     - Bit 15 = 0 → OBJ-Adresse (1 - 0x7FFE)
     - Bit 15 = 1 → GRP-Adresse (0x8001 - 0xFFFE-500)
   - Das Paket wird über die Objekt-/Gruppenadressierung geroutet

## Wann welcher type8-Wert verwendet werden soll

### Entscheidungstabelle

| Zieladresse (ipdst) | Adresstyp | type8-Wert | Begründung |
|---------------------|-----------|------------|------------|
| `0x0001` - `0x7FFE` | **MI-Adresse** (Modul-IP) | `1` (SEND_AS_IP) | Direkte Kommunikation mit Modul über IP-Adresse |
| `0x0001` - `0x7FFE` | **OBJ-Adresse** (Objekt) | `0` (SEND_AS_OBJ_GRP) | Kommunikation über Objektadresse (logisches Objekt) |
| `0x7FFF` | **Broadcast** | `1` (SEND_AS_IP) | Broadcast an alle Module (immer als IP) |
| `0x8001` - `0xFFFE-500` | **GRP-Adresse** (Gruppe) | `0` (SEND_AS_OBJ_GRP) | Gruppenkommunikation (Bit 15 = 1) |
| `0xFFFF` | **ENUM_ALL** | `1` (SEND_AS_IP) | Enumeration aller Module (immer als IP) |

### Entscheidungsregeln

#### 1. **type8 = 1 (SEND_AS_IP) verwenden, wenn:**

- **Modul-IP-Adressen**: Direkte Kommunikation mit einem Modul über dessen IP-Adresse
  ```python
  # Beispiel: Kommunikation mit Modul MI0099
  await send_raw_command(
      ipdst=0x0099,  # Modul MI0099
      ddata=ddata,
      type8=SEND_AS_IP  # = 1
  )
  ```

- **Broadcast-Adressen**: Senden an alle Module
  ```python
  # Beispiel: ENUM_ALL
  await send_raw_command(
      ipdst=0xFFFF,  # ENUM_ALL
      ddata=ddata,
      type8=SEND_AS_IP  # = 1
  )
  
  # Beispiel: Broadcast
  await send_raw_command(
      ipdst=0x7FFF,  # Broadcast
      ddata=ddata,
      type8=SEND_AS_IP  # = 1
  )
  ```

- **Konfigurationsbefehle**: Befehle, die direkt an Module gerichtet sind
  ```python
  # Beispiel: D0_GET_TYP an Modul senden
  ddata = bytes([D0_GET_TYP])
  await send_raw_command(
      ipdst=0x0123,  # Modul MI0123
      ddata=ddata,
      type8=SEND_AS_IP  # = 1
  )
  ```

#### 2. **type8 = 0 (SEND_AS_OBJ_GRP) verwenden, wenn:**

- **Objektadressen**: Kommunikation über logische Objektadressen (1 - 0x7FFE, Bit 15 = 0)
  ```python
  # Beispiel: Objektadresse 0x1234
  await send_raw_command(
      ipdst=0x1234,  # OBJ-Adresse
      ddata=ddata,
      type8=SEND_AS_OBJ_GRP  # = 0
  )
  ```

- **Gruppenadressen**: Senden an eine Gruppe von Modulen (0x8001 - 0xFFFE-500, Bit 15 = 1)
  ```python
  # Beispiel: Gruppenadresse 0x8001
  await send_raw_command(
      ipdst=0x8001,  # GRP-Adresse
      ddata=ddata,
      type8=SEND_AS_OBJ_GRP  # = 0
  )
  ```

- **Objekt-Befehle**: Befehle, die an logische Objekte gerichtet sind
  ```python
  # Beispiel: D0_SET an Objekt senden
  ddata = bytes([D0_SET, 100, 0])
  await send_raw_command(
      ipdst=0x1234,  # OBJ-Adresse
      ddata=ddata,
      type8=SEND_AS_OBJ_GRP  # = 0
  )
  ```

### Problem: Adressbereichs-Überschneidung

**WICHTIG**: Adressen im Bereich `0x0001` - `0x7FFE` können sowohl MI- als auch OBJ-Adressen sein!

Die Unterscheidung erfolgt **nur** über `type8`:
- `type8 = 1` → MI-Adresse (Modul-IP)
- `type8 = 0` → OBJ-Adresse (Objekt)

**Beispiel:**
```python
# Gleiche Adresse, unterschiedliche Interpretation:
ipdst = 0x1234

# Als MI-Adresse (Modul MI1234)
await send_raw_command(ipdst=0x1234, ddata=ddata, type8=SEND_AS_IP)

# Als OBJ-Adresse (Objekt 0x1234)
await send_raw_command(ipdst=0x1234, ddata=ddata, type8=SEND_AS_OBJ_GRP)
```

### Entscheidungshilfe: Wie bestimme ich type8?

1. **Ist es eine Modul-IP-Adresse?**
   - Ja → `type8 = SEND_AS_IP` (1)
   - Nein → Weiter zu Schritt 2

2. **Ist es eine Broadcast- oder ENUM_ALL-Adresse?**
   - `0x7FFF` (Broadcast) → `type8 = SEND_AS_IP` (1)
   - `0xFFFF` (ENUM_ALL) → `type8 = SEND_AS_IP` (1)
   - Nein → Weiter zu Schritt 3

3. **Ist es eine Gruppenadresse?**
   - `0x8001` - `0xFFFE-500` (Bit 15 = 1) → `type8 = SEND_AS_OBJ_GRP` (0)
   - Nein → Weiter zu Schritt 4

4. **Ist es eine Objektadresse?**
   - `0x0001` - `0x7FFE` (Bit 15 = 0) → `type8 = SEND_AS_OBJ_GRP` (0)

### Praktische Beispiele aus dem Pascal-Code

#### Beispiel 1: Modul-Konfiguration (MI-Adresse)
```pascal
// Pascal: sendH2Nc() → automatisch SEND_AS_IP
ddata[0] := D0_GET_TYP;
sendH2Nc(adrModul, ddata, 1);  // adrModul ist MI-Adresse
```

```python
# Python: Explizit type8=SEND_AS_IP
ddata = bytes([D0_GET_TYP])
await send_raw_command(
    ipdst=adr_modul,  # z.B. 0x0099
    ddata=ddata,
    type8=SEND_AS_IP  # = 1
)
```

#### Beispiel 2: Objekt-Befehl (OBJ-Adresse)
```pascal
// Pascal: sendH2Nobj() → automatisch type8=0
ddata[0] := D0_SET;
ddata[1] := 100;
sendH2Nobj(objDest, ddata, 2);  // objDest ist OBJ-Adresse
```

```python
# Python: Explizit type8=SEND_AS_OBJ_GRP
ddata = bytes([D0_SET, 100, 0])
await send_raw_command(
    ipdst=obj_dest,  # z.B. 0x1234
    ddata=ddata,
    type8=SEND_AS_OBJ_GRP  # = 0
)
```

#### Beispiel 3: ENUM_ALL (Broadcast)
```pascal
// Pascal: sendH2Nc() mit BROADCASTIP → automatisch SEND_AS_IP
ddata[0] := D0_ENUM_ALL;
sendH2Nc(BROADCASTIP, ddata, 1);  // BROADCASTIP = 0xFFFF
```

```python
# Python: Explizit type8=SEND_AS_IP
ddata = bytes([D0_ENUM_ALL])
await send_raw_command(
    ipdst=0xFFFF,  # ENUM_ALL
    ddata=ddata,
    type8=SEND_AS_IP  # = 1
)
```

### Zusammenfassung: type8-Werte

| type8 | Wert | Verwendung | Adressbereich |
|-------|------|------------|---------------|
| `SEND_AS_IP` | `1` | Modul-IP-Adressen, Broadcast, ENUM_ALL | `0x0001` - `0x7FFE` (MI), `0x7FFF`, `0xFFFF` |
| `SEND_AS_OBJ_GRP` | `0` | Objekt- und Gruppenadressen | `0x0001` - `0x7FFE` (OBJ), `0x8001` - `0xFFFE-500` (GRP) |

**Goldene Regel:**
- **Modul-Kommunikation** → `type8 = 1` (SEND_AS_IP)
- **Objekt/Gruppen-Kommunikation** → `type8 = 0` (SEND_AS_OBJ_GRP)
- **Im Zweifel**: Prüfe den Kontext - ist es eine Modul-IP oder eine logische Objektadresse?

### Problem in der aktuellen Implementierung

Die aktuelle Python-Implementierung hat:
```python
type8: int = SEND_AS_OBJ_GRP  # Default = 0
```

**Das ist problematisch**, weil:
- Wenn `ipdst` eine MI-Adresse ist (z.B. `0x0099`), wird sie fälschlicherweise als OBJ-Adresse interpretiert
- Das Paket wird nicht korrekt geroutet
- **Lösung**: `type8` sollte basierend auf `ipdst` automatisch bestimmt werden, oder explizit übergeben werden

### Empfohlene Implementierung

```python
# Option 1: Automatische Bestimmung (mit Validierung)
type8 = determine_type8(ipdst)  # Automatisch basierend auf Adresse

# Option 2: Explizite Übergabe (empfohlen für Klarheit)
await send_raw_command(
    ipdst=0x0099,  # MI-Adresse
    ddata=ddata,
    type8=SEND_AS_IP  # Explizit: Es ist eine MI-Adresse
)

await send_raw_command(
    ipdst=0x1234,  # OBJ-Adresse
    ddata=ddata,
    type8=SEND_AS_OBJ_GRP  # Explizit: Es ist eine OBJ-Adresse
)
```

### Vergleich mit Pascal

In Pascal wird `type8` explizit über die Funktion bestimmt:
- `sendH2Nc()` → setzt automatisch `SEND_AS_IP`
- `sendH2Nobj()` → setzt automatisch `0` (OBJ/GRP)

Die Python-Implementierung sollte ähnlich vorgehen oder zumindest validieren.

## Offene Fragen

1. **Payload-Länge 78 vs. 77**: Die Dokumentation zeigt 78 Bytes, aber die Berechnung ergibt 77. Möglicherweise:
   - Ein zusätzliches Padding-Byte?
   - Die Berechnung berücksichtigt etwas anderes?
   - Die 78 ist für ein spezielles Paket-Format?

2. **Trailer-Bytes**: Die Werte für `csRX`, `csCalc`, `len`, `posb` werden normalerweise vom Parser gesetzt. Beim Senden sollten diese 0 sein, aber es wäre gut zu verifizieren, ob sie berechnet werden müssen.

3. **Skip-Byte**: Das Byte nach `type8` wird beim Parsing übersprungen (`result[1]`). Beim Senden sollte es 0 sein, aber es wäre gut zu bestätigen, ob es eine spezielle Bedeutung hat.
