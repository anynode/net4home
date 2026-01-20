# WAV-Bell Modul

## Übersicht

WAV-Bell ist ein **Klingel-Modul** für die Wiedergabe von WAV-Audiodateien über das net4home Bus-System. Das Modul ermöglicht das Hochladen und Abspielen von bis zu 32 verschiedenen WAV-Tracks aus dem internen Flash-Speicher.

## Modul-Informationen

| Eigenschaft | Wert |
|-------------|------|
| **Hardware-Typ** | `PLATINE_HW_IS_BELL2` (63) |
| **Objektadressen** | 3 (ADR_USAGE = 3) |
| **Max. Tracks** | 32 (`MAX_TRACK_COUNT`) |
| **Nutzbarer Flash-Speicher** | 0x00000 - 0xF9FFF (999.999 Bytes ≈ 976 kB) |
| **ModulSpec-Datenlänge** | 32 Bytes pro Zeile (`MSP_DATA_LEN`) |
| **Track-Name-Länge** | 16 Bytes (`TNAME16_LEN`) |

## Objektadressen

Das WAV-Bell-Modul verwendet **3 aufeinanderfolgende Objektadressen**:

| Objektadresse | Objekttyp | Beschreibung |
|---------------|-----------|--------------|
| `adr+0` | `OT_WAV_BELL` (220) | Basis-Objektadresse (Hauptfunktion) |
| `adr+1` | `OT_WAV_BELL_NOT` (221) | Alarm-Lautstärke (für Notfall-Szenarien) |
| `adr+2` | `OT_WAV_BELL_LCD` (222) | Nur für UP-LCD Anzeige (kein Empfänger) |

**Beispiel:**
- Basis-Adresse: `0x1234`
- Adresse 1: `0x1234` (OT_WAV_BELL)
- Adresse 2: `0x1235` (OT_WAV_BELL_NOT)
- Adresse 3: `0x1236` (OT_WAV_BELL_LCD)

## Konfigurationsdatenstruktur

### TDBELL2 Record

Die komplette Konfiguration wird in einem `TDBELL2` Record gespeichert:

```pascal
TDBELL2 = packed record
  cfg: TCFG;                                    // Konfiguration (32 Bytes)
  tracks: packed array[0..31] of TDTRACK;      // Track-Liste (32 * 24 = 768 Bytes)
end;
```

**Gesamtgröße:** 800 Bytes

### TCFG (Konfiguration, 32 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `AdrUK` | word | Basis-Objektadresse (UK = Unterklingel) |
| 2-3 | `AdrGrp0` | word | Gruppenadresse 0 |
| 4-5 | `AdrGrp1` | word | Gruppenadresse 1 |
| 6-7 | `AdrGrp2` | word | Gruppenadresse 2 |
| 8 | `vol` | byte | Lautstärke (0-15) |
| 9 | `vol_alarm` | byte | Alarm-Lautstärke (0-15) |
| 10 | `onoff` | byte | Ein/Aus: `$FF` = Ein, `1` = Aus |
| 11-12 | `AdrLCD` | word | LCD-Anzeigeadresse |
| 13 | `TrackForToggle` | byte | Track-Nummer für Toggle-Befehl |
| 14-31 | `res` | 18 bytes | Reserviert |

### TDTRACK (Track-Information, 24 Bytes)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-2 | `adr_start` | word24 | Startadresse im Flash (3 Bytes, Big Endian) |
| 3-5 | `len` | word24 | Länge des Tracks (3 Bytes, Big Endian) |
| 6-7 | `SampleRateT2` | word | Sample-Rate als T2-Reload-Wert |
| 8-23 | `name` | 16 bytes | Track-Name (null-terminiert) |

**Hinweis:** Ein leerer Track wird durch `name[0] = $FF` markiert.

## WAV-Datei-Format

### Unterstützte Formate

Das Modul unterstützt folgende WAV-Formate:

| Format | Kanäle | Bit-Tiefe | Block-Align | Status |
|--------|--------|-----------|-------------|--------|
| Mono | 1 | 8-bit | 1 | ✅ Unterstützt |
| Mono | 1 | 16-bit | 2 | ✅ Unterstützt |
| Stereo | 2 | 8-bit | 2 | ✅ Unterstützt |
| Stereo | 2 | 16-bit | 4 | ✅ Unterstützt |

**Wichtig:** Nur PCM-Format (`WAVE_FORMAT_PCM = 1`) wird unterstützt. ADPCM und andere komprimierte Formate werden nicht unterstützt.

### Sample-Rate

- **Gültiger Bereich:** 100-700 (T2-Reload-Wert)
- **Berechnung:** `T2_Reload = 5529600 / SampleRate_Hz`
- **Beispiele:**
  - 8 kHz → T2 = 691
  - 11.025 kHz → T2 = 501
  - 16 kHz → T2 = 345
  - 22.05 kHz → T2 = 250
  - 44.1 kHz → T2 = 125
  - 48 kHz → T2 = 115

### Konvertierung

Die WAV-Datei wird beim Upload automatisch konvertiert:

1. **Stereo → Mono:** Stereo-Signale werden zu Mono gemischt (Durchschnitt beider Kanäle)
2. **16-bit → 8-bit (optional):** Bei 8-bit Quellen wird im 8-bit Modus gespeichert
3. **16-bit Ausgabe:** Standard-Ausgabe ist immer 16-bit Mono
4. **FIFO-Alignment:** Daten werden auf 1024 Sample-Grenzen ausgerichtet

### 8-bit Modus

Wenn die Quelle 8-bit ist (Mono 8-bit oder Stereo 8-bit), wird der Track im 8-bit Modus gespeichert:
- **Speicherbedarf:** `track_size_in_flash = downloadstream_size * 2` (doppelte Größe im Flash)
- **Flag:** `mode8bit = 1` im Track-Header

## Flash-Speicher-Organisation

### Sektoren

Der Flash-Speicher ist in 10 Sektoren unterteilt:

| Sektor | Adressbereich | Größe |
|--------|--------------|-------|
| 0 | 0x00000 - 0x01FFF | 8 kB |
| 1 | 0x02000 - 0x03FFF | 8 kB |
| 2 | 0x04000 - 0x05FFF | 8 kB |
| 3 | 0x06000 - 0x07FFF | 8 kB |
| 4 | 0x08000 - 0x7FFFF | 480 kB |
| 5 | 0xA0000 - 0xBFFFF | 128 kB |
| 6 | 0xC0000 - 0xDFFFF | 128 kB |
| 7 | 0xE0000 - 0xF7FFF | 96 kB |
| 8 | 0xF8000 - 0xF9FFF | 8 kB |
| 9 | 0xFA000 - 0xFFFFF | 24 kB (nicht nutzbar) |

**Nutzbarer Bereich:** 0x00000 - 0xF9FFF (999.999 Bytes)

### Track-Platzierung

Tracks werden sequenziell im Flash gespeichert:
- **Erster Track:** Startet bei Adresse 0x00000
- **Weitere Tracks:** Starten direkt nach dem Ende des vorherigen Tracks
- **Lücken:** Werden nicht verwendet (keine Fragmentierung)

## Kommandos

### D0_SET - Ein/Aus

**Ein:**
```pascal
ddata[0] := D0_SET;
ddata[1] := 101;  // EIN
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

**Aus:**
```pascal
ddata[0] := D0_SET;
ddata[1] := 102;  // AUS
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

### D0_SET_N - Track abspielen

```pascal
ddata[0] := D0_SET_N;
ddata[1] := track_nr;  // Track-Nummer (0-31)
ddata[2] := (repeat_count - 1) and $0F;  // Wiederholungen (0-15)
// Optionen:
if do_not_repeat then
  ddata[2] := ddata[2] + D2_OPT_DNR;      // $40: Nicht wiederholen
if interrupt then
  ddata[2] := ddata[2] + D2_OPT_INTERRUPT; // $80: Unterbrechen
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

**Optionen:**
- `D2_OPT_DNR` ($40): Do Not Repeat - Track wird nicht wiederholt
- `D2_OPT_INTERRUPT` ($80): Interrupt - Laufender Track wird unterbrochen

**Wiederholungen:**
- `ddata[2] & $0F`: Anzahl Wiederholungen - 1 (0 = 1x, 15 = 16x)

### D0_INC / D0_DEC - Lautstärke

```pascal
// Lautstärke erhöhen
ddata[0] := D0_INC;
ddata[1] := 0;
ddata[2] := 0;
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);

// Lautstärke verringern
ddata[0] := D0_DEC;
ddata[1] := 0;
ddata[2] := 0;
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

### D0_WR_MODULSPEC_DATA - WAV-Upload

#### Header schreiben (ddata[1] = 1)

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := 1;  // Header
ddata[2] := track_start_adr_in_flash shr 16;  // Flash-Adresse (3 Bytes)
ddata[3] := track_start_adr_in_flash shr 8;
ddata[4] := track_start_adr_in_flash;
ddata[5] := track_dest_nr;  // Track-Nummer (0-31)
ddata[6] := track_size_in_flash shr 16;  // Größe (3 Bytes)
ddata[7] := track_size_in_flash shr 8;
ddata[8] := track_size_in_flash;
ddata[9] := (rate div 2) shr 8;  // Sample-Rate T2 (2 Bytes)
ddata[10] := (rate div 2);
ddata[11] := mode8bit;  // 1 = 8-bit Modus
move(cn16, ddata[12], 16);  // Track-Name (16 Bytes)
Fhome2net.sendH2Nobj(adr_dld, ddata, 12 + 16);
```

#### Daten schreiben (ddata[1] = 2)

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := 2;  // Daten
move((pfile + write_pos)^, ddata[2], 32);  // 32 Bytes Daten
inc(write_pos, 32);
Fhome2net.sendH2Nobj(adr_dld, ddata, 34);
```

**Upload-Prozess:**
1. Header senden (ddata[1] = 1)
2. Warten auf `D0_ACK`
3. Daten in 32-Byte-Blöcken senden (ddata[1] = 2)
4. Nach jedem Block auf `D0_ACK` warten
5. Wiederholen bis alle Daten übertragen sind

**Timeout/Retry:**
- Timeout: 1000 ms
- Retry-Counter: 3 Versuche
- Bei Timeout: Position um 32 Bytes zurücksetzen und erneut senden

### D0_WR_MODULSPEC_DATA - Flash-Verwaltung

#### Erase All (ddata[1] = 4)

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := 4;  // Erase All
Fhome2net.sendH2Nc(adr_dld, ddata, 3);
```

**Antwort:**
- `D0_ACK` mit `ddata[1] = $FF`: Erase läuft (Timeout: 30 s)
- `D0_ACK` mit `ddata[1] = $01`: Erase erfolgreich
- `D0_ACK` mit `ddata[1] = andere`: Fehler

#### Blankcheck (ddata[1] = 3)

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := 3;  // Blankcheck
Fhome2net.sendH2Nc(adr_dld, ddata, 3);
```

**Antwort:**
- `D0_ACK` mit `ddata[1] = $FF`: Blankcheck läuft (Timeout: 20 s)
- `D0_ACK` mit `ddata[1] = 100`: Flash ist leer
- `D0_ACK` mit `ddata[1] = andere`: Flash ist nicht leer

#### Erase Sektor (ddata[1] = 5)

```pascal
ddata[0] := D0_WR_MODULSPEC_DATA;
ddata[1] := 5;  // Erase Sektor
ddata[2] := sektor_nr;  // Sektor-Nummer (0-9)
Fhome2net.sendH2Nc(adr_dld, ddata, 3);
```

## ModulSpec-Daten lesen/schreiben

Das Modul verwendet die Standard-ModulSpec-Mechanismen über `ASbaseObj`:

### Lesen

```pascal
// Über ASbaseObj
fnaModulLesenBegin;
// Nach erfolgreichem Lesen wird AfterLoadFile aufgerufen
```

### Schreiben

```pascal
// Über ASbaseObj
if EditToZeilen then
  fnaModulSchreibenBegin;
// Vor dem Schreiben wird FOnBeforWriteModul aufgerufen
```

**Datenformat:**
- Daten werden in Zeilen à 32 Bytes (`MSP_DATA_LEN`) gespeichert
- `TDBELL2` Record wird in Zeilen aufgeteilt
- Byte-Swapping (Little/Big Endian) wird automatisch durchgeführt

## Gruppenadressen

Das Modul unterstützt 3 Gruppenadressen:

| Gruppe | Feld | Beschreibung |
|--------|------|--------------|
| Gruppe 0 | `AdrGrp0` | Standard-Gruppenadresse |
| Gruppe 1 | `AdrGrp1` | Zusätzliche Gruppenadresse |
| Gruppe 2 | `AdrGrp2` | Zusätzliche Gruppenadresse |

**Hinweis:** Gruppenadressen müssen Bit 15 = 1 haben (GRP-Adressen).

## Lautstärke

Das Modul unterstützt zwei separate Lautstärke-Einstellungen:

| Einstellung | Feld | Beschreibung |
|------------|------|--------------|
| Normal | `vol` | Standard-Lautstärke (0-15) |
| Alarm | `vol_alarm` | Alarm-Lautstärke für Notfall-Szenarien (0-15) |

Die Alarm-Lautstärke wird verwendet, wenn Befehle an `OT_WAV_BELL_NOT` (adr+1) gesendet werden.

## Track-Verwaltung

### Track-Liste

Die Track-Liste wird in der `LVTracks` ListView angezeigt:

| Spalte | Beschreibung |
|--------|--------------|
| Nr. | Track-Nummer (1-32) |
| Name | Track-Name (16 Bytes) |
| Größe | Dateigröße in kB und Dauer in Sekunden |
| Sample-Rate | Sample-Rate in Hz |
| Start | Startadresse im Flash (Hex) |
| Sektor | Sektor-Nummer(n) |

### Track hinzufügen

1. WAV-Datei öffnen (Drag & Drop oder Datei-Dialog)
2. WAV-Datei wird analysiert (Sample-Rate, Format, Größe)
3. Download-Button aktivieren
4. Track wird automatisch in den nächsten freien Slot eingefügt
5. Flash-Adresse wird automatisch berechnet (nach dem letzten Track)

### Track löschen

- **Einzelner Track:** Track-Name auf `$FF` setzen (manuell oder über Konfiguration)
- **Alle Tracks:** "Erase All" Befehl senden

### Track testen

Doppelklick auf Track in der Liste oder "Test"-Button:
- Sendet `D0_SET_N` mit Track-Nummer
- Konfigurierbare Wiederholungen
- Optionen: DNR (Do Not Repeat), Interrupt

## Adressierung

### adr_dld Funktion

```pascal
function TFBell2.adr_dld:word;
begin
  result := ad.cfg.AdrUK;  // Basis-Objektadresse
end;
```

Alle Kommandos werden an `adr_dld` (Basis-Objektadresse) gesendet.

### type8 Parameter

- **OBJ/GRP-Adressen:** `type8 = 0` (`SEND_AS_OBJ_GRP`)
- **MI-Adressen:** `type8 = 1` (`SEND_AS_IP`) - nur bei Flash-Verwaltung (Erase, Blankcheck)

**Standard:** `sendH2Nobj` verwendet `type8 = 0` (OBJ-Adressierung)

## Beispiel-Workflow

### 1. Modul konfigurieren

```pascal
// Adressen setzen
ad.cfg.AdrUK := 0x1234;
ad.cfg.AdrGrp0 := 0x8001;  // Gruppenadresse
ad.cfg.AdrLCD := 0x1236;
ad.cfg.vol := 10;
ad.cfg.vol_alarm := 15;
ad.cfg.onoff := $FF;  // Ein
ad.cfg.TrackForToggle := 0;  // Track 0 für Toggle

// ModulSpec schreiben
EditToZeilen;
fnaModulSchreibenBegin;
```

### 2. WAV-Datei hochladen

```pascal
// 1. WAV-Datei laden
load_wav;  // Analysiert Datei, berechnet Parameter

// 2. Download starten
bDownloadClick(nil);  // Findet freien Slot, berechnet Flash-Adresse

// 3. Upload-Prozess läuft automatisch:
//    - writeFirst: Header senden
//    - writeNext: Daten in 32-Byte-Blöcken senden
//    - Nach jedem Block auf D0_ACK warten
```

### 3. Track abspielen

```pascal
// Track 0 abspielen, 3x wiederholen
ddata[0] := D0_SET_N;
ddata[1] := 0;  // Track 0
ddata[2] := 2;  // 3x (2 + 1)
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);

// Track 1 abspielen, unterbrechen wenn nötig
ddata[0] := D0_SET_N;
ddata[1] := 1;  // Track 1
ddata[2] := D2_OPT_INTERRUPT;  // Unterbrechen
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

### 4. Lautstärke steuern

```pascal
// Lautstärke erhöhen
ddata[0] := D0_INC;
ddata[1] := 0;
ddata[2] := 0;
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);

// Lautstärke verringern
ddata[0] := D0_DEC;
ddata[1] := 0;
ddata[2] := 0;
Fhome2net.sendH2Nobj(adr_dld, ddata, 3);
```

## Fehlerbehandlung

### WAV-Datei-Fehler

- **"no RIFF"**: Datei ist keine WAV-Datei
- **"no WAVE"**: WAV-Header fehlt
- **"no fmt"**: Format-Chunk fehlt
- **"WAVE_FORMAT_PCM not supported"**: Nur PCM wird unterstützt
- **"Channelcount not supported"**: Nur Mono (1) und Stereo (2) werden unterstützt
- **"Samplingrate nicht gültig"**: T2-Reload-Wert außerhalb 100-700

### Upload-Fehler

- **"Speicher voll"**: Kein freier Track-Slot verfügbar
- **"Passt nicht mehr rein"**: Track würde über 0xF9FFF hinausgehen
- **"Timeout"**: Keine Antwort vom Modul (3 Retries)
- **"Erase error"**: Flash-Löschung fehlgeschlagen

## Export-Funktionen

### Track-Liste exportieren

```pascal
racklistefrVisualOneexportieren1Click(nil);
// Exportiert Track-Namen in Textdatei:
// WavBellFiles{adr+2}.txt im Projektverzeichnis
```

## Technische Details

### T2-Reload-Berechnung

```pascal
T2_Reload = 5529600 / SampleRate_Hz
// Beispiel: 44100 Hz → 5529600 / 44100 = 125.39 ≈ 125
```

### Flash-Adress-Berechnung

```pascal
// Erster Track
if track_dest_nr = 0 then
  track_start_adr_in_flash := 0
else
  // Nach dem vorherigen Track
  track_start_adr_in_flash := 
    w24_to_dword(ad.tracks[track_dest_nr-1].adr_start) +
    w24_to_dword(ad.tracks[track_dest_nr-1].len);
```

### FIFO-Alignment

```pascal
nSample := (ms + 1023) and ($fffffff - 1023);
// Rundet auf 1024 Sample-Grenze auf
```

### Byte-Swapping

Bei der Konvertierung von 16-bit Samples:
```pascal
w := si + $800;  // Offset für 12-bit Bereich
w := swap(w);    // Byte-Swap für Little Endian
```

## Zusammenfassung

Das WAV-Bell-Modul bietet:

- ✅ **32 Tracks** im Flash-Speicher
- ✅ **976 kB** nutzbarer Speicher
- ✅ **Verschiedene WAV-Formate** (Mono/Stereo, 8/16-bit)
- ✅ **Automatische Konvertierung** (Stereo→Mono, Format-Anpassung)
- ✅ **Flexible Steuerung** (Wiederholungen, Interrupt, Lautstärke)
- ✅ **Gruppenadressen** für zentrale Steuerung
- ✅ **Separate Alarm-Lautstärke** für Notfall-Szenarien

Das Modul ist ideal für:
- Türklingeln
- Alarme und Warnsignale
- Hintergrundmusik
- Sprachansagen
- Benachrichtigungstöne
