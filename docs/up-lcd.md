# UP-LCD Modul

## Übersicht

UP-LCD ist ein **LCD-Display-Modul** für das net4home Bus-System. Das Modul bietet ein hierarchisches Menü-System mit bis zu 726 Menüpunkten (Nodes), 256 Text-Strings und 32 SetN-Strings für dynamische Textanzeigen. Es ermöglicht die Steuerung von Aktoren, das Anzeigen von Sensordaten und die Konfiguration komplexer Benutzeroberflächen.

## Modul-Informationen

| Eigenschaft | Wert |
|-------------|------|
| **Hardware-Typ** | `PLATINE_HW_IS_LCD3` (55) |
| **Software-Versionen** | 1.31, 1.33 |
| **Max. Nodes (Menüpunkte)** | 726 (`NODE_COUNT`) |
| **Max. Strings** | 256 (`STR_COUNT`) |
| **Max. SetN-Strings** | 32 (`STRN_COUNT`) |
| **String-Länge** | 16 Bytes (`STR_LEN`) |
| **SetN-String-Länge** | 15 Bytes (`STRN_LEN`) |
| **Gruppenadressen** | 3 (`GRP_COUNT`) |
| **ModulSpec-Datenlänge** | 32 Bytes pro Zeile (`MAX_RX_PER_ZEILE`) |
| **Gesamtgröße** | ~16 kB (508 Zeilen à 32 Bytes) |

## Datenstruktur

### TLCD3_data Record

Die komplette Konfiguration wird in einem `TLCD3_data` Record gespeichert:

```pascal
TLCD3_data = packed record
  cfg: TCfg_LCD3;                                    // Konfiguration (32 Bytes)
  strN: array[0..31] of TLCD3_StringN;              // SetN-Strings (32 * 16 = 512 Bytes)
  str: array[0..255] of TLCD3_String;                // Text-Strings (256 * 16 = 4096 Bytes)
  node: array[0..725] of TLCD3_Nodes;               // Menü-Nodes (726 * 16 = 11616 Bytes)
  node_dummy: array[0..15] of TLCD3_Nodes;          // Dummy-Nodes (16 * 16 = 256 Bytes)
end;
```

**Gesamtgröße:** ~16.512 Bytes

### TCfg_LCD3 (Konfiguration, 32 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `adrUK` | word | Basis-Objektadresse (UK = Unterklingel) |
| 2-5 | `password` | 4 bytes | Passwort (4 Zeichen) |
| 6 | `licht` | byte | Helligkeit (0-15) |
| 7 | `buzzer` | byte | Buzzer-Lautstärke (0-15) |
| 8 | `options` | byte | Optionen (Bit-Flags) |
| 9 | `options2` | byte | Zusätzliche Optionen (reserviert) |
| 10-15 | `adrGrp` | 3×word | Gruppenadressen (3 Stück) |
| 16 | `imodulBits` | byte | Interne Modul-Bits |
| 17 | `textIdAfterBoot` | byte | Text-ID nach Boot |
| 18-19 | `tlh_t` | word | TLH-Temperatur |
| 20-21 | `tlh_f` | word | TLH-Feuchte |
| 22-23 | `tlh_t2` | word | TLH-Temperatur 2 |
| 24-25 | `tlh_xx` | word | TLH-Reserviert |
| 26-31 | `res` | 6 bytes | Reserviert |

### TLCD3_String (Text-String, 16 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-15 | `s` | 16 bytes | Text-String (null-terminiert) |

**Hinweis:** Ein leerer String wird durch `s[0] = $FF` (`NO_TEXT_ID`) markiert.

### TLCD3_StringN (SetN-String, 16 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0 | `opt` | byte | Optionen (Bit-Flags) |
| 1-15 | `s` | 15 bytes | Text-String (null-terminiert) |

**Hinweis:** Ein leerer String wird durch `s[0] = $FF` (`NO_TEXT_ID`) markiert.

### TLCD3_Nodes (Menü-Node, 16 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0 | `text` | byte | Text-ID (Index in `str` Array, `$FF` = leer) |
| 1-2 | `prev` | word | Vorheriger Node (Pointer, `$FFFF` = keiner) |
| 3-4 | `next` | word | Nächster Node (Pointer, `$FFFF` = keiner) |
| 5-6 | `sub` | word | Erster Sub-Node (Pointer, `$FFFF` = keine) |
| 7-8 | `back` | word | Zurück-Node (Pointer, `$FFFF` = keiner) |
| 9-11 | `Befehl` | TBefehl | Befehl (3 Bytes: adr, cmd[0], cmd[1], cmd[2]) |
| 12 | `options` | byte | Node-Optionen (Bit-Flags) |
| 13 | `_unit` | byte | Einheit/Format (für Anzeige) |

**Hinweis:** Node 0 ist der Root-Node (Hauptmenü).

### TBefehl (Befehl, 5 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `adr` | word | Zieladresse (OBJ/GRP) |
| 2 | `cmd[0]` | byte | Befehl Byte 0 |
| 3 | `cmd[1]` | byte | Befehl Byte 1 |
| 4 | `cmd[2]` | byte | Befehl Byte 2 |

## Menü-Struktur

### Node-Navigation

Die Menü-Struktur basiert auf einer doppelt verketteten Liste:

- **prev/next**: Horizontale Navigation (gleiche Ebene)
- **sub**: Vertikale Navigation (Untermenü)
- **back**: Zurück-Navigation (übergeordnetes Menü)

**Beispiel-Struktur:**
```
Node 0 (Root)
  ├─ Node 1 (prev=0, next=2, sub=10, back=0)
  ├─ Node 2 (prev=1, next=3, sub=20, back=0)
  └─ Node 3 (prev=2, next=0, sub=$FFFF, back=0)
      │
      ├─ Node 10 (prev=10, next=11, sub=$FFFF, back=1)
      └─ Node 11 (prev=10, next=11, sub=$FFFF, back=1)
```

### Node-Pointer

- **`$FFFF`** (`NO_MORE_SUBNODES`): Kein weiterer Node
- **0**: Root-Node oder erster Node
- **1-725**: Gültige Node-Indizes

## Node-Optionen

### MEO_* Konstanten (options Byte)

| Bit | Konstante | Wert | Beschreibung |
|-----|-----------|------|--------------|
| 7 | `MEO_PASSWORD_REQ` | $80 | Passwort erforderlich |
| 6 | `MEO_REQ_VALUE` | $40 | Wert anfordern (D0_REQ) |
| 5 | `MEO_AFTER_EXEC_UP` | $20 | Nach Ausführung nach oben |
| 0-4 | `MEO_MASK_TYP` | $1F | Menü-Typ (siehe unten) |

### Menü-Typen (MEO_NODE_*)

| Wert | Konstante | Beschreibung |
|------|-----------|--------------|
| 0 | `MEO_NODE_SEND_CMD` | Befehl senden |
| 1 | `MEO_NODE_CHX_INTEGER` | Integer-Wert ändern |
| 2 | `MEO_NODE_CHX_TEMP10` | Temperatur ändern (×10) |
| 3 | `MEO_NODE_CHX_DIMMER` | Dimmer-Wert ändern |
| 4 | `MEO_NODE_DIMMER_WIE_TASTER` | Dimmer wie Taster |
| 5 | `MEO_NODE_CHX_TIME_24` | Zeit ändern (24h) |
| 6 | `MEO_NODE_INTERN_LICHTMODE` | Interner Lichtmodus |
| 7 | `MEO_NODE_INTERN_BUZZERMODE` | Interner Buzzer-Modus |
| 8 | `MEO_NODE_KEY_TRANSPARENTMODE` | Key Transparent-Modus |
| 9 | `MEO_NODE_ONLY` | Nur Untermenü-Halter |
| 10 | `MEO_TLH` | TLH-Modus |
| 11 | `MEO_READ_VAL` | Wert lesen |
| 12 | `MEO_NODE_CHX_TEXT` | Text ändern |
| 13 | `MEO_NODE_CHX_EIN_AUS` | Ein/Aus ändern |
| 14 | `MEO_NODE_CHX_MIN_BYTE` | Byte-Wert ändern (min) |
| 15 | `MEO_NODE_CHX_HSJAL_MODE_H` | HS-Jal Modus H |
| 16 | `MEO_NODE_CHX_HSJAL_MODE_R` | HS-Jal Modus R |
| 17 | `MEO_NODE_CHX_TIME_24_REL` | Zeit ändern (relativ) |
| 18 | `MEO_NODE_CHX_BYTE_15MIN` | Byte-Wert (15 Min) |
| 19 | `MEO_NODE_READ_TEMP10_HEIZ_KLIMA` | Temperatur lesen (Heiz/Klima) |
| 20 | `MEO_NODE_ACCESS_1` | Access 1 |
| 21 | `MEO_NODE_CHX_AUDIO_DB` | Audio dB ändern |
| 22 | `MEO_NODE_CHX_AUDIO_DB2` | Audio dB2 ändern |
| 23 | `MEO_NODE_CHX_TIME_WORD_SEC` | Zeit ändern (Word, Sekunden) |
| 24 | `MEO_NODE_CHX_TEMP16` | Temperatur ändern (×16) |
| 25 | `MEO_NODE_CHX_WORD_0_100` | Word-Wert ändern (0-100) |
| 26 | `MEO_NODE_CHX_ZWANG_BIN` | Zwang Binär |
| 27 | `MEO_NODE_CHX_EIN_AUS_DIREKT` | Ein/Aus direkt |
| 28 | `MEO_NODE_CHX_WORD` | Word-Wert ändern |
| 29 | `MEO_NODE_CHX_ZWANG_JAL_PERC` | Zwang Jalousie Prozent |
| 30 | `MEO_NODE_CHX_TIME_PROFIL` | Zeit-Profil ändern |

## LCD-Kommandos

### D0_SET_N - Text anzeigen

Zeigt einen Text auf dem LCD-Display an.

```pascal
ddata[0] := D0_SET_N;
ddata[1] := $F0;  // SetN-Kommando
ddata[2] := options;  // Optionen (Bit-Flags)
ddata[3] := freq;  // Frequenz (100 / Hz)
ddata[4] := (x shl 4) or y;  // X/Y-Position (nur wenn CI_LCD_OPT_USE_XY gesetzt)
move(text[1], ddata[5], LCD_STR_LEN_1);  // Text (24 Bytes)
Fhome2net.sendH2Nobj(adrLCD, ddata, lenTX);
```

**Optionen (ddata[2]):**

| Bit | Konstante | Wert | Beschreibung |
|-----|-----------|------|--------------|
| 0 | `CI_LCD_OPT_CLR_HOME` | $01 | Clear & Home |
| 1 | `CI_LCD_OPT_BLINK` | $02 | Blinken |
| 2 | `CI_LCD_OPT_LICHT_AUTO` | $04 | Licht automatisch |
| 3 | `CI_LCD_OPT_LICHT_LANG_EIN` | $08 | Licht lang ein |
| 4 | `CI_LCD_OPT_BUZZER_ON` | $10 | Buzzer an |
| 5 | `CI_LCD_OPT_LFCR` | $20 | Line Feed / Carriage Return |
| 6 | `CI_LCD_OPT_USE_XY` | $40 | X/Y-Position verwenden |

**Frequenz (ddata[3]):**
- `freq = 100 / Hz` (z.B. 1 Hz → 100, 0.5 Hz → 200)

**X/Y-Position (ddata[4]):**
- `x`: X-Koordinate (0-15, 4 Bits)
- `y`: Y-Koordinate (0-15, 4 Bits)
- Nur verwendet wenn `CI_LCD_OPT_USE_XY` gesetzt

**Text-Länge:**
- `LCD_STR_LEN_1 = 24` Bytes (Standard)
- `LCD_STR_LEN_1_M = 18` Bytes (für LCD-4x16M)

### ExtractLCDText - Text aus Paket extrahieren

Extrahiert LCD-Text aus einem empfangenen Paket.

```pascal
function ExtractLCDText(n4h_paket: TN4Hpaket): string;
// Extrahiert Text aus ddata[5..] (24 Bytes)
```

## ModulSpec-Daten lesen/schreiben

### Kapazität lesen

```pascal
ddata[0] := D0_RD_MODULSPEC_DATA;
ddata[1] := $FF;  // High-Byte der Adresse
ddata[2] := $FF;  // Low-Byte der Adresse ($FFFF = Kapazität)
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, $FF, $FF, adrModul);
```

**Antwort (`D0_RD_MODULSPEC_DATA_ACK`):**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| 0 | Befehl | byte | `D0_RD_MODULSPEC_DATA_ACK` |
| 1-2 | Adresse | word | `$FFFF` (Big Endian) |
| 3-4 | `SizeCfg` | word | Konfigurationsgröße (Big Endian) |
| 5-6 | `SizeStrN` | word | SetN-String-Größe (Big Endian) |
| 7-8 | `SizeStr` | word | String-Größe (Big Endian) |
| 9-10 | `SizeNODE` | word | NODE-Größe (Big Endian) |

### Zeile lesen

```pascal
ddata[0] := D0_RD_MODULSPEC_DATA;
ddata[1] := readPos shr 8;  // High-Byte der Adresse
ddata[2] := readPos;  // Low-Byte der Adresse
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos shr 8, readPos, adrModul);
```

**Antwort (`D0_RD_MODULSPEC_DATA_ACK`):**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| 0 | Befehl | byte | `D0_RD_MODULSPEC_DATA_ACK` |
| 1-2 | Adresse | word | Gelesene Adresse (Big Endian) |
| 3-34 | Daten | 32 bytes | Zeilendaten |

### Zeile schreiben

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := writePos shr 8;  // High-Byte der Adresse
ddata[2] := writePos;  // Low-Byte der Adresse
move(zeile32.d[0], ddata[3], 32);  // 32 Bytes Daten
Fhome2net.sendH2Nobj(adrModul, ddata, 35);
```

**Antwort (`D0_RD_MODULSPEC_DATA_ACK`):**
- Bestätigung mit gleicher Adresse (Checksumme)

### Sequenzielles Lesen/Schreiben

Das Modul unterstützt sequenzielles Lesen/Schreiben:

1. **Kapazität lesen** (`$FFFF`)
2. **Zeilen lesen/schreiben** (0 bis `ZEILEN_RX_COUNT-1`)
3. **Checksumme prüfen** (bei Schreiben)

**Zeilen-Organisation:**

| Bereich | Zeilen | Beschreibung |
|---------|--------|--------------|
| 0 | 1 | Konfiguration (`TCfg_LCD3`) |
| 1-16 | 16 | SetN-Strings (`strN[0..31]`) |
| 17-272 | 256 | Text-Strings (`str[0..255]`) |
| 273-508 | 236 | Menü-Nodes (`node[0..725]`) |

**Berechnung:**
```
ZEILEN_RX_COUNT = (
  (STRN_COUNT * 16) +      // 32 * 16 = 512 Bytes = 16 Zeilen
  (NODE_COUNT * 16) +      // 726 * 16 = 11616 Bytes = 363 Zeilen
  (STR_COUNT * STR_LEN) +  // 256 * 16 = 4096 Bytes = 128 Zeilen
  32                       // Konfiguration = 1 Zeile
) div 32 = 508 Zeilen
```

## Gruppenadressen

Das Modul unterstützt 3 Gruppenadressen:

| Gruppe | Feld | Beschreibung |
|--------|------|--------------|
| Gruppe 0 | `adrGrp[0]` | Standard-Gruppenadresse |
| Gruppe 1 | `adrGrp[1]` | Zusätzliche Gruppenadresse |
| Gruppe 2 | `adrGrp[2]` | Zusätzliche Gruppenadresse |

**Hinweis:** Gruppenadressen müssen Bit 15 = 1 haben (GRP-Adressen).

## Passwort-Schutz

Das Modul unterstützt Passwort-Schutz für einzelne Menüpunkte:

- **Passwort:** 4 Zeichen (in `TCfg_LCD3.password`)
- **Node-Option:** `MEO_PASSWORD_REQ` ($80) setzen
- **Verhalten:** Node ist nur nach Passwort-Eingabe zugänglich

## Beispiel-Workflow

### 1. Modul konfigurieren

```pascal
// Adressen setzen
LCD3_data.cfg.adrUK := 0x1234;
LCD3_data.cfg.adrGrp[0] := 0x8001;  // Gruppenadresse
LCD3_data.cfg.licht := 10;
LCD3_data.cfg.buzzer := 5;
LCD3_data.cfg.password := '1234';

// Text-String hinzufügen
move('Hauptmenü'[1], LCD3_data.str[0].s[0], 16);

// Root-Node konfigurieren
LCD3_data.node[0].text := 0;  // Text-ID 0
LCD3_data.node[0].prev := 0;
LCD3_data.node[0].next := 0;
LCD3_data.node[0].sub := 1;  // Erster Sub-Node
LCD3_data.node[0].back := $FFFF;
LCD3_data.node[0].Befehl.adr := 0;
LCD3_data.node[0].options := MEO_NODE_ONLY;  // Nur Untermenü-Halter
LCD3_data.node[0]._unit := 0;
```

### 2. Menüpunkt hinzufügen

```pascal
// Neuen Node erstellen
LCD3_data.node[1].text := 1;  // Text-ID 1
LCD3_data.node[1].prev := 1;  // Erster in Liste
LCD3_data.node[1].next := 1;  // Letzter in Liste
LCD3_data.node[1].sub := $FFFF;  // Keine Sub-Nodes
LCD3_data.node[1].back := 0;  // Zurück zu Root
LCD3_data.node[1].Befehl.adr := 0x5678;  // Zieladresse
LCD3_data.node[1].Befehl.cmd[0] := D0_SET;
LCD3_data.node[1].Befehl.cmd[1] := 101;  // EIN
LCD3_data.node[1].Befehl.cmd[2] := 0;
LCD3_data.node[1].options := MEO_NODE_SEND_CMD;
LCD3_data.node[1]._unit := 0;
```

### 3. Text anzeigen (SetN)

```pascal
// Text auf LCD anzeigen
ddata[0] := D0_SET_N;
ddata[1] := $F0;
ddata[2] := CI_LCD_OPT_CLR_HOME or CI_LCD_OPT_LICHT_AUTO;
ddata[3] := 100;  // 1 Hz
ddata[4] := 0;  // Keine X/Y-Position
s := 'Hallo Welt' + #0 + '                ';
move(s[1], ddata[5], 24);
Fhome2net.sendH2Nobj(adrLCD, ddata, 29);
```

### 4. ModulSpec schreiben

```pascal
// Daten in Zeilen aufteilen
ZeileToTypisiertData;  // LCD3_data → Modul512

// Sequenziell schreiben
for i := 0 to ZEILEN_RX_COUNT-1 do
begin
  ddata[0] := D0_WR_MODULSPEC_DATA;
  ddata[1] := i shr 8;
  ddata[2] := i;
  move(Modul512.z[i].d[0], ddata[3], 32);
  Fhome2net.sendH2Nobj(adrModul, ddata, 35);
  // Warten auf Bestätigung
end;
```

## Menü-Editor

Der Konfigurator bietet einen visuellen Menü-Editor:

- **TreeView**: Hierarchische Menü-Struktur
- **Drag & Drop**: Nodes verschieben
- **Kontext-Menü**: Nodes hinzufügen/löschen
- **Vorschau**: LCD-Simulation
- **Text-Editor**: Strings verwalten
- **Befehl-Editor**: Befehle konfigurieren

## Technische Details

### Byte-Swapping

Bei der Übertragung werden Adressen und Word-Werte byte-geswappt (Big Endian):

```pascal
procedure swapAdr;
begin
  kswap(LCD3_data.cfg.adrUK);
  kswap(LCD3_data.cfg.adrGrp[0]);
  kswap(LCD3_data.cfg.adrGrp[1]);
  kswap(LCD3_data.cfg.adrGrp[2]);
  // ... weitere Word-Werte
end;
```

### Dirty-List

Das Modul verwendet eine "Dirty-List" zum Tracking geänderter Zeilen:

```pascal
dirtyList: array[0..DIRTY_LIST_LEN-1] of integer;
// DIRTY_LIST_LEN = STRN_COUNT + NODE_COUNT + STR_COUNT + 1
```

Nur geänderte Zeilen werden beim Schreiben übertragen.

### Checksumme

Beim Schreiben wird eine Checksumme übertragen und geprüft:

```pascal
cs_write := (ddata[1] shl 8) or ddata[2];  // Adresse als Checksumme
// Antwort muss gleiche Adresse enthalten
```

## Zusammenfassung

Das UP-LCD-Modul bietet:

- ✅ **726 Menüpunkte** für komplexe Navigation
- ✅ **256 Text-Strings** für Menü-Texte
- ✅ **32 SetN-Strings** für dynamische Anzeigen
- ✅ **Hierarchische Menü-Struktur** mit Untermenüs
- ✅ **Passwort-Schutz** für einzelne Menüpunkte
- ✅ **Verschiedene Menü-Typen** (Befehl, Wert ändern, etc.)
- ✅ **Gruppenadressen** für zentrale Steuerung
- ✅ **Visueller Editor** im Konfigurator

Das Modul ist ideal für:
- Zentrale Steuerung von Aktoren
- Anzeige von Sensordaten
- Konfiguration komplexer Systeme
- Benutzerfreundliche Bedienoberflächen
- Zugriffskontrolle mit Passwort-Schutz
