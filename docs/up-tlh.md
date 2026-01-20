# UP-TLH und UP-T Modul Dokumentation

## Übersicht

Die Module **UP-TLH** (`PLATINE_HW_IS_TLH` = 25) und **UP-T** (`PLATINE_HW_IS_UP_T` = 84) sind Temperatur-/Licht-/Feuchte-Regler bzw. reine Temperatur-Regler für das net4home System. Sie messen Sensordaten, führen PID-Regelung durch und können bei Schwellenwerten Ereignisse auslösen.

## Modultypen

- **UP-TLH:** `PLATINE_HW_IS_TLH` (25) - Temperatur, Licht, Feuchte Sensor + Regler
- **UP-T:** `PLATINE_HW_IS_UP_T` (84) - Temperatur Sensor + Regler
- **Modultyp:** `MODUL_IS_M` (Master-Modul)
- **Datenstruktur:** Verwendet `D0_RD_MODULSPEC_DATA` / `D0_RD_MODULSPEC_DATA_ACK` für Konfiguration

## Datenstruktur

### Tabellen-Organisation

Das Modul verwendet mehrere Tabellen mit jeweils 16 Bytes pro Eintrag:

- **Tab0-2:** Sensor-Konfiguration (Kanäle 0-2)
- **Tab $F0:** Tag-/Nacht-Temperaturen
- **Tab $F1:** Allgemeine Konfiguration (Sollwert-Adresse, Aktor, Klima)
- **Tab $F2:** Regler-Parameter (PID, Anlauf, Klima)
- **Tab $F3:** Abgleichwert (Temperatur-Offset)
- **Tab $80-$8F:** Ereignis-Tabelle (16 Einträge, Index 0-15)

**Modul-Info (ddata[1] = $FF):**

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[3]` | `gSensorCount` | Anzahl Sensoren (3 für TLH, 1 für T) |
| `ddata[4]` | `gTabEntryCount` | Anzahl Tabelleneinträge (max. 16) |

## Status-Informationen

### D0_ACTOR_ACK - Sollwert und Regler-Status

Das Modul sendet `D0_ACTOR_ACK` (55) als Antwort auf `D0_REQ` (54) zur Abfrage des Sollwerts und Regler-Status.

**Datenstruktur:**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_ACTOR_ACK` (55) |
| `ddata[1]` | Sollwert Low | byte | Niedriges Byte des Sollwerts (Temperatur * 10, Little Endian) |
| `ddata[2]` | Sollwert High | byte | Hohes Byte des Sollwerts (Temperatur * 10, Little Endian) |
| `ddata[3]` | Status | byte | Bit-Flags für Regler-Status |

**Status-Bits in ddata[3]:**

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | Heizregler aktiv | 1 | Heizregler ist aktiv |
| 1 | Klimaregler aktiv | 2 | Kühlregler/Klimaregler ist aktiv |

**Sollwert-Berechnung:**
```pascal
Sollwert_Temperatur = (ddata[1] + ddata[2] * 256) / 10.0
```

**Beispiel:**
- `ddata[1] = 0xDC` (220), `ddata[2] = 0x00` → Sollwert = 22.0°C
- `ddata[1] = 0xBE` (190), `ddata[2] = 0x00` → Sollwert = 19.0°C

### D0_VALUE_ACK - Sensor-Messwerte

Das Modul sendet `D0_VALUE_ACK` (101) als Antwort auf `D0_VALUE_REQ` (102) oder automatisch bei Änderungen.

**Datenstruktur:**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_VALUE_ACK` (101) |
| `ddata[1]` | Hardware-Typ | byte | Sensor-Typ (siehe unten) |
| `ddata[2]` | Wert Low | byte | Niedriges Byte des Messwerts |
| `ddata[3]` | Wert High | byte | Hohes Byte des Messwerts |

**Sensor-Typen:**

| Wert | Konstante | Einheit | Beschreibung |
|------|-----------|----------|--------------|
| `9` | `IN_HW_NR_IS_TEMP` | °C | Temperatur |
| `5` | `IN_HW_NR_IS_LICHT_ANALOG` | - | Lichtwert (analog) |
| `11` | `IN_HW_NR_IS_HUMIDITY` | % | Luftfeuchte |

**Temperatur-Berechnung:**
```pascal
// Wert ist signed 16-bit, Little Endian
temp_raw = ddata[2] + ddata[3] * 256
if temp_raw > 0x7FFF then
  temp_raw = temp_raw - 0x10000  // Negative Werte
Temperatur = temp_raw / 16.0
```

**Beispiel:**
- `ddata[2] = 0xE0` (224), `ddata[3] = 0x01` (1) → `temp_raw = 480` → Temperatur = 30.0°C
- `ddata[2] = 0x20` (32), `ddata[3] = 0xFF` (255) → `temp_raw = -480` → Temperatur = -30.0°C

**Lichtwert:**
- Direkt als 16-bit unsigned Integer (Little Endian)
- `Lichtwert = ddata[2] + ddata[3] * 256`

**Luftfeuchte:**
- Direkt als 16-bit unsigned Integer (Little Endian)
- `Luftfeuchte = ddata[2] + ddata[3] * 256` (in Prozent)

### D0_RD_MODULSPEC_DATA_ACK - Konfigurationsdaten

#### Modul-Info (ddata[1] = $FF)

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[3]` | `gSensorCount` | Anzahl Sensoren (3 für TLH, 1 für T) |
| `ddata[4]` | `gTabEntryCount` | Anzahl Tabelleneinträge (max. 16) |

#### Tag-/Nacht-Temperaturen (ddata[1] = $F0)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Tagwert High | byte | Hohes Byte der Tagtemperatur (* 10) |
| `ddata[3]` | Tagwert Low | byte | Niedriges Byte der Tagtemperatur (* 10) |
| `ddata[4]` | Nachtwert High | byte | Hohes Byte der Nachttemperatur (* 10) |
| `ddata[5]` | Nachtwert Low | byte | Niedriges Byte der Nachttemperatur (* 10) |

**Berechnung:**
```pascal
Tagwert = (ddata[2] * 256 + ddata[3]) / 10.0
Nachtwert = (ddata[4] * 256 + ddata[5]) / 10.0
```

#### Allgemeine Konfiguration (ddata[1] = $F1)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Objektadresse High | byte | Hohes Byte der Sollwert-Objektadresse |
| `ddata[3]` | Objektadresse Low | byte | Niedriges Byte der Sollwert-Objektadresse |
| `ddata[4]` | Sollwert-Gruppe High | byte | Hohes Byte der Sollwert-Gruppenadresse (Bit 15 = 0) |
| `ddata[5]` | Sollwert-Gruppe Low | byte | Niedriges Byte der Sollwert-Gruppenadresse |
| `ddata[6]` | Heizregler-Aktor High | byte | Hohes Byte der Aktor-Adresse für Heizung |
| `ddata[7]` | Heizregler-Aktor Low | byte | Niedriges Byte der Aktor-Adresse für Heizung |
| `ddata[8]` | Klimaregler-Objekt High | byte | Hohes Byte der Objektadresse für Kühlung |
| `ddata[9]` | Klimaregler-Objekt Low | byte | Niedriges Byte der Objektadresse für Kühlung |
| `ddata[10]` | HK-Konzept | byte | Bit 0: 0 = Heizung+Kühlung, 1 = Nur Heizung |

#### Regler-Parameter (ddata[1] = $F2)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Anlauf-Zeit High | byte | Hohes Byte der Anlaufzeit in Sekunden |
| `ddata[3]` | Anlauf-Zeit Low | byte | Niedriges Byte der Anlaufzeit in Sekunden |
| `ddata[4]` | Anlauf-Prozent | byte | Anlauf-Prozentsatz (0-100) |
| `ddata[5]` | TA | byte | TA-Regelzeit (0-255, tatsächlich = (ddata[5] + 1) * 8 Sekunden) |
| `ddata[6]` | Ki | byte | Integral-Anteil des PID-Reglers |
| `ddata[7]` | Kp | byte | Proportional-Anteil des PID-Reglers |
| `ddata[8]` | Klima-Hysterese High | byte | Hohes Byte der Klima-Hysterese (* 10) |
| `ddata[9]` | Klima-Hysterese Low | byte | Niedriges Byte der Klima-Hysterese (* 10) |
| `ddata[10]` | Klima-TA | byte | Klima-Regelzeit (0-255, tatsächlich = (ddata[10] + 1) * 8 Sekunden) |
| `ddata[11]` | Optionen | byte | Bit-Flags (siehe unten) |

**TA-Berechnung:**
```pascal
TA_Sekunden = (ddata[5] + 1) * 8
Klima_TA_Sekunden = (ddata[10] + 1) * 8
```

**Klima-Hysterese:**
```pascal
Klima_Hysterese = (ddata[8] * 256 + ddata[9]) / 10.0
```

**Optionen (ddata[11]):**

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | `TLH_OPT1_I_NOT_NEG` | 1 | I-Anteil nicht negativ (keine negative Integration) |
| 1 | `TLH_OPT1_UEBERSCHW_BEGR` | 2 | Überschwinger-Begrenzung aktiv |

#### Abgleichwert (ddata[1] = $F3)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Abgleich Low | byte | Niedriges Byte des Abgleichwerts (signed 16-bit) |
| `ddata[3]` | Abgleich High | byte | Hohes Byte des Abgleichwerts (signed 16-bit) |

**Berechnung:**
```pascal
abgleich_raw = smallInt(ddata[2] + ddata[3] * 256)
Abgleich_Temperatur = (abgleich_raw + 1) / 16.0
```

#### Sensor-Konfiguration (ddata[1] = 0, 1, 2)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Objektadresse High | byte | Hohes Byte der Sensor-Objektadresse (bei SW < 1.17) |
| `ddata[3]` | Objektadresse Low | byte | Niedriges Byte der Sensor-Objektadresse (bei SW < 1.17) |
| `ddata[4]` | Zeit-Index | byte | Zeit-Index für Sendezeitpunkt (`$FF` = sofort) |
| `ddata[5]` | Post-Typ | byte | Bits 2-3: Post-Typ (nur Kanal 0) |
| `ddata[6]` | Sensor-Typ | byte | `IN_HW_NR_IS_TEMP` (9), `IN_HW_NR_IS_LICHT_ANALOG` (5), `IN_HW_NR_IS_HUMIDITY` (11) |

**Hinweis:** Ab Software-Version 1.17 wird die Objektadresse automatisch berechnet:
```pascal
Sensor_Objektadresse = Basis_Objektadresse + 3 + Kanalnummer
```

#### Ereignis-Tabelle (ddata[1] = $80-$8F)

Jeder Tabelleneintrag (Index 0-15) hat folgende Struktur:

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Lock | byte | `0` = gesperrt, `$FF` = nicht gesperrt |
| `ddata[3]` | Sensor-Nr | byte | 0 = Temp, 1 = Licht, 2 = Feuchte |
| `ddata[4]` | Zieladresse High | byte | Hohes Byte der Ziel-Objektadresse |
| `ddata[5]` | Zieladresse Low | byte | Niedriges Byte der Ziel-Objektadresse |
| `ddata[6]` | Befehl 0 | byte | Erster Befehl-Byte |
| `ddata[7]` | Befehl 1 | byte | Zweiter Befehl-Byte |
| `ddata[8]` | Befehl 2 | byte | Dritter Befehl-Byte |
| `ddata[9]` | Flanke | byte | `$FF` = aus, `1` = unterschreiten, `2` = überschreiten, `3` = PIR-Controller, `4` = s.o. |
| `ddata[10]` | Schwellwert High | byte | Hohes Byte des Schwellwerts |
| `ddata[11]` | Schwellwert Low | byte | Niedriges Byte des Schwellwerts |
| `ddata[12]` | Hysterese High | byte | Hohes Byte der Hysterese |
| `ddata[13]` | Hysterese Low | byte | Niedriges Byte der Hysterese |

**Spezialfall Index 15 (ab SW 1.18):**
- **ROUTE wenn dunkel:** PIR-Routing bei Dunkelheit
- `ddata[9]` wird ignoriert, immer "unterschreiten"
- `ddata[3]` muss 1 (Licht) sein
- Zieladresse ist das Routing-Ziel für PIR-Befehle

## Befehle zum Modul

### D0_REQ - Sollwert und Status abfragen

**Befehl:** `D0_REQ` (54)

```
D0_REQ, 0, 0 → Sollwert-Objektadresse
```

**Antwort:** `D0_ACTOR_ACK` mit Sollwert und Regler-Status

### D0_SET - Sollwert setzen

**Befehl:** `D0_SET` (50)

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[0]` | Befehl | `D0_SET` (50) |
| `ddata[1]` | Sollwert High | Hohes Byte (Temperatur * 10) |
| `ddata[2]` | Sollwert Low | Niedriges Byte (Temperatur * 10) |

**Beispiel:**
```pascal
Sollwert = 22.5°C
w = round(22.5 * 10) = 225
ddata[1] = 225 shr 8 = 0
ddata[2] = 225 and $FF = 225
```

### D0_SET_N - Regler aktivieren/deaktivieren

**Befehl:** `D0_SET_N` (59)

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[0]` | Befehl | `D0_SET_N` (59) |
| `ddata[1]` | Status | Bit-Flags: Bit 0 = Heizregler, Bit 1 = Klimaregler |

**Status-Werte:**
- `0` = Beide Regler deaktiviert
- `1` = Heizregler aktiv
- `2` = Klimaregler aktiv
- `3` = Beide Regler aktiv

### D0_VALUE_REQ - Sensorwert abfragen

**Befehl:** `D0_VALUE_REQ` (102)

```
D0_VALUE_REQ, 0, 0 → Sensor-Objektadresse
```

**Antwort:** `D0_VALUE_ACK` mit Messwert

### D0_RD_MODULSPEC_DATA - Konfiguration lesen

**Befehl:** `D0_RD_MODULSPEC_DATA` (37)

| Parameter | Beschreibung |
|-----------|--------------|
| `ddata[1] = $FF` | Modul-Info lesen |
| `ddata[1] = $F0` | Tag-/Nacht-Temperaturen lesen |
| `ddata[1] = $F1` | Allgemeine Konfiguration lesen |
| `ddata[1] = $F2` | Regler-Parameter lesen |
| `ddata[1] = $F3` | Abgleichwert lesen |
| `ddata[1] = 0, 1, 2` | Sensor-Konfiguration lesen (Kanal 0-2) |
| `ddata[1] = $80-$8F` | Ereignis-Tabelle lesen (Index 0-15) |

### D0_WR_MODULSPEC_DATA - Konfiguration schreiben

**Befehl:** `D0_WR_MODULSPEC_DATA` (39)

Verwendet die gleichen Indizes wie `D0_RD_MODULSPEC_DATA`, sendet aber die Daten zum Schreiben.

## Ereignisse (Events)

Das Modul kann bei Schwellenwerten Ereignisse auslösen, die in der Ereignis-Tabelle (Index $80-$8F) konfiguriert werden.

### Flanken-Typen

| Wert | Name | Beschreibung |
|------|------|--------------|
| `$FF` | aus | Ereignis deaktiviert |
| `1` | unterschreiten | Ereignis bei Unterschreitung des Schwellwerts |
| `2` | überschreiten | Ereignis bei Überschreitung des Schwellwerts |
| `3` | PIR-Controller | PIR-Lichtsteuerung |
| `4` | s.o. | Nur Adress-Zeile (bei SW < 1.17) |

### Ereignis-Auslösung

Wenn ein Sensorwert den konfigurierten Schwellwert mit Hysterese überschreitet oder unterschreitet, sendet das Modul den konfigurierten Befehl an die Zieladresse.

**Schwellwert-Logik:**
- **Unterschreiten:** Ereignis wird ausgelöst, wenn `Messwert < (Schwellwert - Hysterese)`
- **Überschreiten:** Ereignis wird ausgelöst, wenn `Messwert > (Schwellwert + Hysterese)`

**Beispiel:**
- Schwellwert: 20.0°C
- Hysterese: 1.0°C
- Flanke: Unterschreiten
- → Ereignis wird ausgelöst, wenn Temperatur < 19.0°C fällt

### PIR-Routing (Index 15, ab SW 1.18)

Bei Dunkelheit (Lichtwert unterschreitet Schwellwert) werden PIR-Befehle an eine andere Adresse weitergeleitet:
- **Zieladresse:** Routing-Ziel für PIR-Befehle
- **Objektadresse + 22:** Empfängt die PIR-Befehle und leitet sie weiter

## Sollwert

### Lesen des Sollwerts

```
D0_REQ, 0, 0 → Sollwert-Objektadresse
```

**Antwort:** `D0_ACTOR_ACK`
- `ddata[1..2]`: Sollwert (Temperatur * 10, Little Endian)
- `ddata[3]`: Regler-Status (Bit 0 = Heizregler, Bit 1 = Klimaregler)

### Schreiben des Sollwerts

```
D0_SET, Sollwert_High, Sollwert_Low → Sollwert-Objektadresse
```

**Berechnung:**
```pascal
w = round(Sollwert_Temperatur * 10)
ddata[1] = w shr 8
ddata[2] = w and $FF
```

### Objektadressen

- **Sollwert:** `Basis_Objektadresse + 0` (z.B. `.Sollwert.Temperatur`)
- **Tagwert:** `Basis_Objektadresse + 1` (z.B. `.Tagwert`)
- **Nachtwert:** `Basis_Objektadresse + 2` (z.B. `.Nachtwert`)
- **Sensor Temp:** `Basis_Objektadresse + 3` (z.B. `.Messwert.Temperatur`)
- **Sensor Licht:** `Basis_Objektadresse + 4` (z.B. `.Messwert.Helligkeit`)
- **Sensor Feuchte:** `Basis_Objektadresse + 5` (z.B. `.Messwert.Feuchte`)
- **Tabellen-Einträge:** `Basis_Objektadresse + 6 + Index` (Index 0-15)

## Heizregler (PID-Regler)

### Regler-Parameter

| Parameter | Beschreibung | Einheit | Bereich |
|-----------|--------------|---------|---------|
| **Kp** | Proportional-Anteil | %/°K (ab SW 1.15) oder 10%/°K (vorher) | 0-255 |
| **Ki** | Integral-Anteil | - | 0-255 |
| **TA** | Regelzeit | Sekunden | 8-2048 (berechnet als (TA + 1) * 8) |
| **Anlauf-Zeit** | Anlaufzeit | Sekunden | 0-65535 |
| **Anlauf-Prozent** | Anlauf-Prozentsatz | % | 0-100 |

### Aktivierung

Der Heizregler wird über `D0_SET_N` aktiviert:
```
D0_SET_N, 1, 0 → Sollwert-Objektadresse
```

### Vorwahl-Parameter

**Fußbodenheizung:**
- Anlauf-Zeit: 900 Sekunden
- Anlauf-Prozent: 100%
- Kp: 200
- Ki: 64
- TA: 104 Sekunden

**Radiator:**
- Anlauf-Zeit: 100 Sekunden
- Anlauf-Prozent: 40%
- Kp: 1
- Ki: 16
- TA: 104 Sekunden

### PID-Debug (ddata[0] = $F1)

Das Modul kann PID-Debug-Informationen senden:

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `$F1` (Debug PID) |
| `ddata[1..2]` | P | signed 16-bit | Proportional-Anteil |
| `ddata[3..4]` | I | signed 16-bit | Integral-Anteil |
| `ddata[5..6]` | sum_e | signed 16-bit | Summe der Fehler |
| `ddata[7]` | Anlauf | byte | Anlauf-Status |
| `ddata[8]` | e | signed 8-bit | Aktueller Fehler (Sollwert - Istwert) |

## Kühlregler (Klimaregler)

### Regler-Parameter

| Parameter | Beschreibung | Einheit | Bereich |
|-----------|--------------|---------|---------|
| **Hysterese** | Hysterese | °C | 0.0-6553.5 (berechnet als Wert / 10) |
| **TA** | Regelzeit | Sekunden | 8-2048 (berechnet als (TA + 1) * 8) |

### Aktivierung

Der Klimaregler wird über `D0_SET_N` aktiviert:
```
D0_SET_N, 2, 0 → Sollwert-Objektadresse
```

### Funktionsweise

Der Klimaregler schaltet ein, wenn die Temperatur den Sollwert + Hysterese überschreitet, und schaltet aus, wenn die Temperatur den Sollwert - Hysterese unterschreitet.

**Beispiel:**
- Sollwert: 22.0°C
- Hysterese: 0.5°C
- → Ein bei > 22.5°C, Aus bei < 21.5°C

## Tagwert und Nachtwert

### Lesen

```
D0_RD_MODULSPEC_DATA, $F0, 0, 0 → Modul-Adresse
```

**Antwort:** `D0_RD_MODULSPEC_DATA_ACK` mit `ddata[1] = $F0`
- `ddata[2..3]`: Tagwert (Temperatur * 10)
- `ddata[4..5]`: Nachtwert (Temperatur * 10)

### Schreiben

```
D0_WR_MODULSPEC_DATA, $F0, Tag_High, Tag_Low, Nacht_High, Nacht_Low, ... → Modul-Adresse
```

**Berechnung:**
```pascal
tag_temp = round(Tagwert * 10)
nacht_temp = round(Nachtwert * 10)
ddata[2] = tag_temp shr 8
ddata[3] = tag_temp and $FF
ddata[4] = nacht_temp shr 8
ddata[5] = nacht_temp and $FF
```

### Verwendung

Tagwert und Nachtwert werden typischerweise von externen Modulen (z.B. HS-Time) gesetzt, um automatisch zwischen Tag- und Nachttemperatur umzuschalten.

## Objektadressen

Das Modul verwendet folgende Objektadressen (basierend auf `Basis_Objektadresse`):

| Offset | Objektadresse | Name | Beschreibung |
|--------|---------------|------|--------------|
| +0 | `obj_adr + 0` | Sollwert | Solltemperatur (lesen/schreiben) |
| +1 | `obj_adr + 1` | Tagwert | Tagtemperatur (lesen/schreiben) |
| +2 | `obj_adr + 2` | Nachtwert | Nachttemperatur (lesen/schreiben) |
| +3 | `obj_adr + 3` | Sensor Temp | Temperatur-Messwert (nur lesen) |
| +4 | `obj_adr + 4` | Sensor Licht | Lichtwert (nur lesen) |
| +5 | `obj_adr + 5` | Sensor Feuchte | Luftfeuchte (nur lesen) |
| +6 bis +21 | `obj_adr + 6 + i` | Tabellen-Einträge | Ereignis-Tabelleneinträge (i = 0-15) |
| +22 | `obj_adr + 22` | Dunkel-Zeit | Zeit für PIR-Routing (ab SW 1.18) |

**ADR_USAGE:** 22 Objektadressen werden benötigt.

## Software-Versionen

### Ab V1.09
- Basis-Funktionalität

### Ab V1.15
- Kp in %/°K statt 10%/°K
- `cbI_nichtNegativ` und `cdueberschwingerBegr` aktiviert

### Ab V1.17
- Automatische Objektadressen für Sensoren
- `cbLocked` sichtbar
- `ed_ObjAdr` und `edNameSensorObj` ausgeblendet

### Ab V1.18
- PIR-Routing (Index 15 in Ereignis-Tabelle)
- `gboxRoute` sichtbar

### Ab V1.19
- Dunkel-Zeit-Konfiguration (`obj_adr + 22`)

### Ab V1.22
- HK-Konzept (Heizung+Kühlung vs. Nur Heizung)
- `cbHKkonzept` aktiviert

## Kommunikationsprotokoll

### Sollwert lesen

```
1. D0_REQ, 0, 0 → Sollwert-Objektadresse
2. Antwort: D0_ACTOR_ACK mit Sollwert und Status
```

### Sollwert schreiben

```
1. D0_SET, Sollwert_High, Sollwert_Low → Sollwert-Objektadresse
```

### Regler aktivieren/deaktivieren

```
1. D0_SET_N, Status, 0 → Sollwert-Objektadresse
   Status: 0 = aus, 1 = Heizung, 2 = Kühlung, 3 = beide
```

### Sensorwert abfragen

```
1. D0_VALUE_REQ, 0, 0 → Sensor-Objektadresse
2. Antwort: D0_VALUE_ACK mit Messwert
```

### Konfiguration lesen

```
1. D0_RD_MODULSPEC_DATA, Index, 0, 0 → Modul-Adresse
2. Antwort: D0_RD_MODULSPEC_DATA_ACK mit Daten
```

### Konfiguration schreiben

```
1. D0_WR_MODULSPEC_DATA, Index, [Daten...], 0 → Modul-Adresse
```

## Zusammenfassung der Status-Informationen

### Vom Modul gesendet:

1. **D0_ACTOR_ACK** - Sollwert und Regler-Status
   - Sollwert (Temperatur * 10)
   - Heizregler aktiv (Bit 0)
   - Klimaregler aktiv (Bit 1)

2. **D0_VALUE_ACK** - Sensor-Messwerte
   - Temperatur (signed 16-bit / 16)
   - Lichtwert (unsigned 16-bit)
   - Luftfeuchte (unsigned 16-bit, Prozent)

3. **D0_RD_MODULSPEC_DATA_ACK** - Konfigurationsdaten
   - Modul-Info bei `ddata[1] = $FF`
   - Tag-/Nacht-Temperaturen bei `ddata[1] = $F0`
   - Allgemeine Konfiguration bei `ddata[1] = $F1`
   - Regler-Parameter bei `ddata[1] = $F2`
   - Abgleichwert bei `ddata[1] = $F3`
   - Sensor-Konfiguration bei `ddata[1] = 0, 1, 2`
   - Ereignis-Tabelle bei `ddata[1] = $80-$8F`

4. **$F1 (Debug PID)** - PID-Debug-Informationen
   - P, I, sum_e, Anlauf, e

### Vom Modul ausgelöste Ereignisse:

1. **Tabelleneinträge** senden Befehle bei Schwellenwert-Überschreitung/Unterschreitung
2. **PIR-Routing** (ab SW 1.18) leitet PIR-Befehle bei Dunkelheit weiter
3. **Regler-Aktionen** steuern Heizungs-/Kühlungs-Aktoren basierend auf PID-Regelung

## Wichtige Konstanten

```pascal
PLATINE_HW_IS_TLH = 25
PLATINE_HW_IS_UP_T = 84
D0_SET = 50
D0_REQ = 54
D0_SET_N = 59
D0_ACTOR_ACK = 55
D0_VALUE_ACK = 101
D0_VALUE_REQ = 102
D0_RD_MODULSPEC_DATA = 37
D0_RD_MODULSPEC_DATA_ACK = 38
D0_WR_MODULSPEC_DATA = 39
IN_HW_NR_IS_TEMP = 9
IN_HW_NR_IS_LICHT_ANALOG = 5
IN_HW_NR_IS_HUMIDITY = 11
TLH_OPT1_I_NOT_NEG = 1
TLH_OPT1_UEBERSCHW_BEGR = 2
GW_UNTERSCHREITUNG = 1
GW_UEBERSCHREITUNG = 2
GW_PIR_LIGHT_CONTROLER = 3
ADR_USAGE = 22
```
