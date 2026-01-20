# HS-Time Modul Dokumentation

## Übersicht

Das **HS-Time** Modul (`PLATINE_HW_IS_HS_TIME` = 10) ist eine Zeitschaltuhr mit DCF77-Zeitgeber und Astrokalender für das net4home System. Es ermöglicht zeitgesteuerte Aktionen mit verschiedenen Zeitmodi, Profilen, Feiertagsunterstützung und Sonnenaufgang/Untergang-Berechnungen.

## Modultyp

- **Hardware-Typ:** `PLATINE_HW_IS_HS_TIME` (10)
- **Modultyp:** `MODUL_IS_M` (Master-Modul)
- **Datenstruktur:** Verwendet `D0_RD_MODULSPEC_DATA` / `D0_RD_MODULSPEC_DATA_ACK` für Konfiguration
- **Software-Version:** Ab V1.08 (mindestens erforderlich), V2.00 mit Sonnenfunktion

## Datenstruktur

### Tabellen-Organisation

Das Modul verwendet mehrere Tabellen mit jeweils 16 Bytes pro Eintrag:

- **Tab0-15:** Zeitsteuerungs-Einträge (max. 16 Einträge, Index 0-15)
- **Tab16-108:** Sonnenstand und Feiertage (93 Zeilen à 16 Bytes)
  - **Tab16-47:** Sonnenstand (32 Zeilen, 365 Tage)
  - **Tab48-108:** Feiertage (61 Zeilen, max. 240 Feiertage)
- **Tab $FF:** Modul-Info (Basis-Konfiguration)

**Gesamtlänge:** 
- V1.x: 16 Einträge (16 Zeilen)
- V2.00: 112 Einträge (112 Zeilen)

### Modul-Info (ddata[1] = $FF)

Bei `D0_RD_MODULSPEC_DATA_ACK` mit `ddata[1] = $FF`:

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Objektadresse High | byte | Hohes Byte der Basis-Objektadresse |
| `ddata[3]` | Objektadresse Low | byte | Niedriges Byte der Basis-Objektadresse |
| `ddata[4]` | Broadcast-Index | byte | Index für Broadcast-Intervall (0-7) |
| `ddata[5]` | Reserviert | byte | Reserviert |
| `ddata[6]` | Katholische Feiertage | byte | `1` = katholische Feiertage aktiv, `0` = deaktiviert |
| `ddata[7]` | Post-Typ | byte | Post-Typ (Bits 2-3) |
| `ddata[8]` | Reserviert | byte | Reserviert |
| `ddata[9]` | Tabellen-Einträge | byte | Anzahl aktiver Tabelleneinträge (max. 16) |

### Zeitsteuerungs-Eintrag (TsuTabEntry)

Jeder Eintrag in der Tabelle (Index 0-15) hat folgende Struktur:

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[2]` | Mode | byte | Zeitmodus (siehe Zeitmodi) |
| `ddata[3]` | Hour | byte | Stunde (BCD oder binär, je nach Mode) |
| `ddata[4]` | Min | byte | Minute (BCD oder binär, je nach Mode) |
| `ddata[5]` | Day | byte | Tag (BCD, nur bei MONTHLY/JAHRLICH) |
| `ddata[6]` | Month | byte | Monat (BCD, nur bei MONTHLY/JAHRLICH) |
| `ddata[7]` | Day of Week | byte | Wochentag-Bitmaske (siehe Wochentage) |
| `ddata[8]` | Zieladresse High | byte | Hohes Byte der Zieladresse |
| `ddata[9]` | Zieladresse Low | byte | Niedriges Byte der Zieladresse |
| `ddata[10]` | Befehl 1 | byte | Erster Befehl |
| `ddata[11]` | Befehl 2 | byte | Zweiter Befehl |
| `ddata[12]` | Befehl 3 | byte | Dritter Befehl |
| `ddata[13]` | Profil | byte | Profil-Bitmaske (siehe Profile) |

**Wochentag-Bitmaske (ddata[7]):**

| Bit | Wochentag | Wert |
|-----|-----------|------|
| 0 | Montag | `1` |
| 1 | Dienstag | `2` |
| 2 | Mittwoch | `4` |
| 3 | Donnerstag | `8` |
| 4 | Freitag | `$10` |
| 5 | Samstag | `$20` |
| 6 | Sonntag | `$40` |
| 7 | Feiertag | `$80` |

### Sonnenstand (TarSonnenStand)

Die Sonnenstand-Daten werden für 365 Tage gespeichert:

```pascal
TSaSu = packed record
  sa, su: byte;  // Sonnenaufgang, Sonnenuntergang
end;

TarSonnenStand = packed record
  SaSu: array[0..MAX_TAGE_PRO_JAHR-1] of TSaSu;  // 365 Tage
  dummy: array[0..37] of byte;
end;
```

**Berechnung der Zeit:**
- Sonnenaufgang: `(sa * 2 + 210) Minuten` (ab 3:30 Uhr)
- Sonnenuntergang: `(su * 2 + 900) Minuten` (ab 15:00 Uhr)

**Beispiel:**
- `sa = 0` → Sonnenaufgang: 3:30 Uhr (210 Minuten)
- `sa = 30` → Sonnenaufgang: 4:30 Uhr (270 Minuten)
- `su = 0` → Sonnenuntergang: 15:00 Uhr (900 Minuten)
- `su = 60` → Sonnenuntergang: 17:00 Uhr (1020 Minuten)

### Feiertage (TFeiertage)

Bis zu 240 Feiertage können gespeichert werden:

```pascal
TFeiertag = packed record
  jahr, monat, tag: byte;  // BCD-kodiert
end;

TFeiertage = packed record
  ft: array[0..MAX_FEIERTAGE-1] of TFeiertag;  // 240 Feiertage
end;
```

**Format:**
- Jahr: BCD, 0-99 (Jahr 2000-2099)
- Monat: BCD, 1-12
- Tag: BCD, 1-31

## Status-Informationen

### D0_ACTOR_ACK - Aktive Profil-Maske

Das Modul sendet `D0_ACTOR_ACK` (55) als Antwort auf `D0_REQ` (54) zur Abfrage der aktiven Profile.

**Datenstruktur:**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_ACTOR_ACK` (55) |
| `ddata[1]` | Reserviert | byte | Reserviert |
| `ddata[2]` | Profil-Maske | byte | Bit-Maske der aktiven Profile (siehe Profile) |

**Beispiel:**
- `ddata[2] = 1` → Profil 1 aktiv
- `ddata[2] = 3` → Profile 1 und 2 aktiv
- `ddata[2] = 255` → Alle 8 Profile aktiv

### D0_VALUE_ACK - DCF77-Zeit und Sonnenstand

Das Modul sendet `D0_VALUE_ACK` (101) als Antwort auf `D0_VALUE_REQ` (102) zur Abfrage der aktuellen Zeit oder des Sonnenstands.

#### DCF77-Zeit (ddata[1] = IN_HW_NR_IS_CLOCK = 6)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_VALUE_ACK` (101) |
| `ddata[1]` | Hardware-Typ | byte | `IN_HW_NR_IS_CLOCK` (6) |
| `ddata[2]` | Reserviert | byte | Reserviert |
| `ddata[3]` | Sekunde | byte | Sekunde (BCD) |
| `ddata[4]` | Minute | byte | Minute (BCD) |
| `ddata[5]` | Stunde | byte | Stunde (BCD) |
| `ddata[6]` | Tag | byte | Tag (BCD) |
| `ddata[7]` | Monat | byte | Monat (BCD) |
| `ddata[8]` | Wochentag | byte | Wochentag (0=Montag, 6=Sonntag) |
| `ddata[9]` | Jahr Low | byte | Niedriges Byte des Jahres (BCD) |
| `ddata[10]` | Jahr High | byte | Hohes Byte des Jahres (BCD) |
| `ddata[11]` | Status-Bits | byte | DCF77-Status (siehe Status-Bits) |
| `ddata[12]` | Minuten ohne Empfang | byte | Anzahl Minuten ohne DCF77-Empfang |

**Status-Bits in ddata[11]:**

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | `DCF77_SOMMERZEIT` | 1 | Sommerzeit aktiv |
| 1 | `DCF77_SOMMERZEIT_ANGUENDIGUNG` | 2 | Sommerzeit-Ankündigung |
| 2 | `DCF77_KEIN_EMPFANG` | 4 | Kein DCF77-Empfang |
| 3 | `DCT_FEIERTAG` | 8 | Feiertag erkannt |
| 4 | `DCF77_SYNC_PHASE` | $10 | Noch nicht synchronisiert |

**Status-Interpretation:**

- `ddata[12] = 0` und `(ddata[11] & DCF77_SYNC_PHASE) = 0`: Zeit synchron, DCF-Empfang aktiv
- `ddata[12] = 0` und `(ddata[11] & DCF77_SYNC_PHASE) != 0`: Zeit noch nicht synchron
- `ddata[12] != 0` und `(ddata[11] & DCF77_SYNC_PHASE) = 0`: Seit X Minuten ohne Empfang (vorher erfolgreich synchronisiert)
- `ddata[12] != 0` und `(ddata[11] & DCF77_SYNC_PHASE) != 0`: Seit X Minuten ohne Empfang (seit Powerup kein Empfang)

#### Sonnenaufgang (ddata[1] = VAL_IS_MIN_TAG_WORD_SA = 50)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_VALUE_ACK` (101) |
| `ddata[1]` | Wert-Typ | byte | `VAL_IS_MIN_TAG_WORD_SA` (50) |
| `ddata[2]` | Minuten Low | byte | Niedriges Byte der Minuten seit Mitternacht |
| `ddata[3]` | Minuten High | byte | Hohes Byte der Minuten seit Mitternacht |

**Berechnung:**
```
Sonnenaufgang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
```

#### Sonnenuntergang (ddata[1] = VAL_IS_MIN_TAG_WORD_SU = 51)

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_VALUE_ACK` (101) |
| `ddata[1]` | Wert-Typ | byte | `VAL_IS_MIN_TAG_WORD_SU` (51) |
| `ddata[2]` | Minuten Low | byte | Niedriges Byte der Minuten seit Mitternacht |
| `ddata[3]` | Minuten High | byte | Hohes Byte der Minuten seit Mitternacht |

**Berechnung:**
```
Sonnenuntergang_Zeit = (ddata[3] * 256 + ddata[2]) Minuten seit Mitternacht
```

### D0_RD_MODULSPEC_DATA_ACK - Konfigurationsdaten

#### Modul-Info (ddata[1] = $FF)

Siehe Abschnitt "Modul-Info (ddata[1] = $FF)" oben.

#### Zeitsteuerungs-Eintrag (ddata[1] = 0-15)

Siehe Abschnitt "Zeitsteuerungs-Eintrag (TsuTabEntry)" oben.

#### Sonnenstand/Feiertage (ddata[1] = 16-108)

Die Daten werden in 16-Byte-Blöcken übertragen. Die ersten 32 Zeilen (16-47) enthalten Sonnenstand-Daten, die restlichen 61 Zeilen (48-108) enthalten Feiertage.

## Befehle zum Modul

### D0_REQ - Aktive Profil-Maske abfragen

**Befehl:** `D0_REQ` (54)

```
D0_REQ, 0, 0 → Basis-Objektadresse
```

**Antwort:** `D0_ACTOR_ACK` mit Profil-Maske in `ddata[2]`

### D0_SET - Profil-Maske setzen

**Befehl:** `D0_SET` (50)

```
D0_SET, Profil_Maske, 0 → Basis-Objektadresse
```

**Parameter:**
- `ddata[1]`: Profil-Maske (Bit-Maske, siehe Profile)

**Beispiel:**
- `D0_SET, 1, 0` → Profil 1 aktivieren
- `D0_SET, 3, 0` → Profile 1 und 2 aktivieren
- `D0_SET, 255, 0` → Alle 8 Profile aktivieren

### D0_SET_N - Zeit setzen

**Befehl:** `D0_SET_N` (59)

```
D0_SET_N, 0, Sekunde, Minute, Stunde, Tag, Monat, Wochentag, 0, Jahr → Basis-Objektadresse
```

**Datenstruktur:**

| Byte | Name | Typ | Beschreibung |
|------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | `D0_SET_N` (59) |
| `ddata[1]` | Reserviert | byte | `0` |
| `ddata[2]` | Sekunde | byte | Sekunde (BCD) |
| `ddata[3]` | Minute | byte | Minute (BCD) |
| `ddata[4]` | Stunde | byte | Stunde (BCD) |
| `ddata[5]` | Tag | byte | Tag (BCD) |
| `ddata[6]` | Monat | byte | Monat (BCD) |
| `ddata[7]` | Wochentag | byte | Wochentag (0=Montag, 6=Sonntag) |
| `ddata[8]` | Hundert Jahre | byte | `0` (ignoriert) |
| `ddata[9]` | Jahr | byte | Jahr (binär, 0-99 für 2000-2099) |

**Wochentag-Berechnung:**
```pascal
dow := DayOfWeek(now) - 2;  // 0=Montag, 6=Sonntag
if dow = -1 then dow := 6;  // Sonntag
```

### D0_VALUE_REQ - Zeit oder Sonnenstand abfragen

**Befehl:** `D0_VALUE_REQ` (102)

#### DCF77-Zeit abfragen

```
D0_VALUE_REQ, 0, 0 → Basis-Objektadresse
```

**Antwort:** `D0_VALUE_ACK` mit `ddata[1] = IN_HW_NR_IS_CLOCK` (6)

#### Sonnenaufgang abfragen

```
D0_VALUE_REQ, 0, 0 → Basis-Objektadresse + 17
```

**Antwort:** `D0_VALUE_ACK` mit `ddata[1] = VAL_IS_MIN_TAG_WORD_SA` (50)

#### Sonnenuntergang abfragen

```
D0_VALUE_REQ, 0, 0 → Basis-Objektadresse + 18
```

**Antwort:** `D0_VALUE_ACK` mit `ddata[1] = VAL_IS_MIN_TAG_WORD_SU` (51)

### D0_RD_MODULSPEC_DATA - Konfiguration lesen

**Befehl:** `D0_RD_MODULSPEC_DATA` (37)

| Parameter | Beschreibung |
|-----------|--------------|
| `ddata[1] = $FF` | Modul-Info lesen |
| `ddata[1] = 0-15` | Zeitsteuerungs-Eintrag lesen (Index 0-15) |
| `ddata[1] = 16-108` | Sonnenstand/Feiertage lesen (Zeile 16-108) |

### D0_WR_MODULSPEC_DATA - Konfiguration schreiben

**Befehl:** `D0_WR_MODULSPEC_DATA` (39)

Verwendet die gleichen Indizes wie `D0_RD_MODULSPEC_DATA`, sendet aber die Daten zum Schreiben.

**Wichtig:** Bei V1.x ist die Zeilenlänge 14 Bytes, bei V2.00 ist sie 18 Bytes (16+2).

## Zeitmodi

Das Modul unterstützt verschiedene Zeitmodi für die Zeitsteuerung:

| Wert | Konstante | Name | Beschreibung |
|------|-----------|------|--------------|
| `0` | `STE_MODE_ENTRY_OFF` | Deaktiv | Eintrag ist deaktiviert |
| `1` | `STE_MODE_HOURLY` | Stündlich | Jede Stunde zur angegebenen Minute |
| `2` | `STE_MODE_DAILY` | Täglich | Täglich zur angegebenen Zeit, mit Wochentag-Filter |
| `3` | `STE_MODE_MONTHLY` | Monatlich | Monatlich am angegebenen Tag zur angegebenen Zeit |
| `4` | `STE_MODE_RANDOM` | Zufall | (Nicht verwendet) |
| `5` | `STE_MODE_JAHRLICH` | Jährlich | Jährlich am angegebenen Datum zur angegebenen Zeit |
| `7` | `STE_MODE_SA` | Relativ zum Sonnenaufgang | Relativ zum Sonnenaufgang (ab V2.00) |
| `8` | `STE_MODE_SU` | Relativ zum Sonnenuntergang | Relativ zum Sonnenuntergang (ab V2.00) |

### Zeitformat je nach Mode

**STE_MODE_DAILY, STE_MODE_MONTHLY, STE_MODE_JAHRLICH:**
- Stunde/Minute: BCD-Format (z.B. `$14` = 14 Uhr, `$30` = 30 Minuten)
- Format: `HH:MM` (Hex)

**STE_MODE_HOURLY:**
- Nur Minute relevant, Stunde wird ignoriert
- Format: `XX:MM` (Hex)

**STE_MODE_SA, STE_MODE_SU:**
- Zeit relativ zum Sonnenaufgang/Untergang in Minuten (Word, nicht BCD)
- Format: `MM:SS` (Dezimal) oder `-MM:SS` (negativ = vorher)
- Berechnung: `w = Minuten` (positiv) oder `w = $10000 - Minuten` (negativ)

**Beispiel für STE_MODE_SA:**
- `00:30` → 30 Minuten nach Sonnenaufgang
- `-01:00` → 1 Stunde vor Sonnenaufgang

## Profile

Das Modul unterstützt 8 Profile, die als Bit-Maske gespeichert werden:

| Bit | Profil | Wert | Beschreibung |
|-----|--------|------|--------------|
| 0 | Profil 1 | `1` | Erstes Profil |
| 1 | Profil 2 | `2` | Zweites Profil |
| 2 | Profil 3 | `4` | Drittes Profil |
| 3 | Profil 4 | `8` | Viertes Profil |
| 4 | Profil 5 | `$10` | Fünftes Profil |
| 5 | Profil 6 | `$20` | Sechstes Profil |
| 6 | Profil 7 | `$40` | Siebtes Profil |
| 7 | Profil 8 | `$80` | Achtes Profil |

**Aktive Profil-Maske:**
- Jeder Zeitsteuerungs-Eintrag kann mehreren Profilen zugeordnet werden
- Nur Einträge, deren Profil-Maske mit der aktiven Profil-Maske übereinstimmt, werden ausgeführt
- Beispiel: Wenn Profil-Maske `3` (Profil 1+2) aktiv ist, werden nur Einträge mit Profil `1`, `2` oder `3` ausgeführt

## Ereignisse (Events)

Das Modul löst bei Erreichen der konfigurierten Zeit ein Ereignis aus und sendet den konfigurierten Befehl an die Zieladresse.

### Ereignis-Auslösung

1. **Zeitprüfung:** Das Modul prüft kontinuierlich, ob die konfigurierte Zeit erreicht ist
2. **Profil-Prüfung:** Es wird geprüft, ob der Eintrag zur aktiven Profil-Maske passt
3. **Wochentag-Prüfung:** Bei `STE_MODE_DAILY` wird geprüft, ob der aktuelle Wochentag aktiviert ist
4. **Feiertag-Prüfung:** Wenn Feiertag-Bit gesetzt ist, wird geprüft, ob heute ein Feiertag ist
5. **Befehl senden:** Wenn alle Bedingungen erfüllt sind, wird der konfigurierte Befehl an die Zieladresse gesendet

### Befehle

Jeder Zeitsteuerungs-Eintrag kann bis zu 3 Befehle senden:
- `cmd1`, `cmd2`, `cmd3`: Drei Bytes für den Befehl (siehe `otBefehlDlg`)

**Typische Befehle:**
- `D0_SET` - Wert setzen
- `D0_SET_N` - Status setzen
- `D0_ACTOR` - Aktor steuern
- Kombinationen für komplexe Aktionen

## Feiertage

### Feiertage verwalten

Das Modul kann bis zu 240 Feiertage speichern. Feiertage werden im Format `TT.MM.JJ` gespeichert (BCD-kodiert).

**Einschränkungen:**
- Jahr muss >= 2005 (BCD: `5`) sein
- Nur zukünftige Feiertage werden gespeichert (>= heute - 1 Tag)

### Katholische Feiertage

Das Modul kann katholische Feiertage automatisch erkennen (nur bei Software < V2.00):
- `ddata[6] = 1`: Katholische Feiertage aktiv
- `ddata[6] = 0`: Katholische Feiertage deaktiviert

## Sonnenstand (Astrokalender)

### Berechnung

Der Sonnenstand wird für 365 Tage im Jahr berechnet basierend auf:
- Geographische Breite (46°-58° Nord)
- Geographische Länge (5°-15° Ost)
- Zeitgleichung
- Deklination

**Berechnungsformel:**
```pascal
Deklination := 0.40954 * sin(0.0172 * (TagNr - 79.35))
Zeitdifferenz := 12 * arccos((sin(-0.0145) - sin(Breite) * sin(Deklination)) / (cos(Breite) * cos(Deklination))) / pi
Zeitgleichung := -0.1752 * sin(0.033430 * TagNr + 0.5474) - 0.1340 * sin(0.018234 * TagNr - 0.1939)
Aufgang_Ortszeit := 12 - Zeitdifferenz - Zeitgleichung
Untergang_Ortszeit := 12 + Zeitdifferenz - Zeitgleichung
Aufgang := Aufgang_Ortszeit - Länge/15 + Zeitzone
Untergang := Untergang_Ortszeit - Länge/15 + Zeitzone
```

**Speicherung:**
- `sa := round(((Aufgang * 60) - 210) / 2)`  // Ab 3:30 Uhr
- `su := round(((Untergang * 60) - 900) / 2)`  // Ab 15:00 Uhr

### Vordefinierte Orte

Das Modul unterstützt folgende vordefinierte Orte:

| Index | Ort | Länge | Breite |
|-------|-----|-------|--------|
| 0 | Kiel | 10.0° | 54.4° |
| 1 | Hannover | 9.8° | 52.5° |
| 2 | Frankfurt | 8.6° | 49.9° |
| 3 | München | 11.6° | 48.2° |
| 4 | Benutzerdefiniert | - | - |

### Relativ-Zeiten (STE_MODE_SA, STE_MODE_SU)

Bei den Modi `STE_MODE_SA` und `STE_MODE_SU` wird die Zeit relativ zum Sonnenaufgang oder Sonnenuntergang angegeben:

- **Positiv:** Minuten nach Sonnenaufgang/Untergang
- **Negativ:** Minuten vor Sonnenaufgang/Untergang

**Beispiel:**
- `00:30` bei `STE_MODE_SA` → 30 Minuten nach Sonnenaufgang
- `-01:00` bei `STE_MODE_SU` → 1 Stunde vor Sonnenuntergang

## Objektadressen

Das Modul verwendet folgende Objektadressen (basierend auf `Basis_Objektadresse`):

| Offset | Objektadresse | Name | Beschreibung |
|--------|---------------|------|--------------|
| +0 | `obj_adr + 0` | Basis | Basis-Objektadresse (Profil-Maske, Zeit setzen) |
| +1 bis +16 | `obj_adr + 1` bis `obj_adr + 16` | Zeitsteuerungs-Einträge | Objektadressen für einzelne Einträge (Index 0-15) |
| +17 | `obj_adr + 17` | Sonnenaufgang | Sonnenaufgang abfragen |
| +18 | `obj_adr + 18` | Sonnenuntergang | Sonnenuntergang abfragen |

**ADR_USAGE:** `TabEntryCount + 3` Objektadressen werden benötigt (typischerweise 19).

## Broadcast-Intervall

Das Modul kann die Zeit in regelmäßigen Abständen an andere Module senden. Der Broadcast-Index (`ddata[4]`) bestimmt das Intervall:

| Index | Intervall | Beschreibung |
|-------|-----------|--------------|
| 0 | Nie | Kein Broadcast |
| 1 | 1 Minute | Jede Minute |
| 2 | 5 Minuten | Alle 5 Minuten |
| 3 | 15 Minuten | Alle 15 Minuten |
| 4 | 30 Minuten | Alle 30 Minuten |
| 5 | 60 Minuten | Alle 60 Minuten |
| 6 | 2 Stunde | Alle 2 Stunden |
| 7 | 4 Stunde | Alle 4 Stunden |
| 8 | 6 Stunde | Alle 6 Stunden |
| 9 | 8 Stunde | Alle 8 Stunden |
| 10 | 12 Stunde | Alle 12 Stunden |
| 11 | 24 Stunden | Alle 24 Stunden |

## Software-Versionen

### Ab V1.08
- Basis-Funktionalität
- Zeitsteuerung mit täglichen, monatlichen, jährlichen Modi
- Feiertagsunterstützung
- DCF77-Zeitgeber

### Ab V2.00
- Sonnenaufgang/Untergang-Berechnung
- `STE_MODE_SA` und `STE_MODE_SU` Modi
- Erweiterte Datenstruktur (112 Zeilen statt 16)
- Keine katholische Feiertags-Option mehr

## Kommunikationsprotokoll

### Lesen der Konfiguration

1. **Modul-Info lesen:**
   ```
   D0_RD_MODULSPEC_DATA, $FF, 0, 0 → Modul-Adresse
   ```
   Antwort: `D0_RD_MODULSPEC_DATA_ACK` mit Basis-Konfiguration

2. **Zeitsteuerungs-Einträge lesen:**
   ```
   D0_RD_MODULSPEC_DATA, Index, 0, 0 → Modul-Adresse
   ```
   Antwort: `D0_RD_MODULSPEC_DATA_ACK` mit 16 Bytes Daten (Index 0-15)

3. **Sonnenstand/Feiertage lesen:**
   ```
   D0_RD_MODULSPEC_DATA, Zeile, 0, 0 → Modul-Adresse
   ```
   Antwort: `D0_RD_MODULSPEC_DATA_ACK` mit 16 Bytes Daten (Zeile 16-108)

### Schreiben der Konfiguration

1. **Basis-Konfiguration schreiben:**
   ```
   D0_WR_MODULSPEC_DATA, $FF, [10 Bytes Daten], 0 → Modul-Adresse
   ```

2. **Zeitsteuerungs-Einträge schreiben:**
   ```
   D0_WR_MODULSPEC_DATA, Index, [14-18 Bytes Daten], 0 → Modul-Adresse
   ```
   - V1.x: 14 Bytes
   - V2.00: 18 Bytes (16+2)

3. **Sonnenstand/Feiertage schreiben:**
   ```
   D0_WR_MODULSPEC_DATA, Zeile, [16 Bytes Daten], 0 → Modul-Adresse
   ```

### Zeit abfragen

```
D0_VALUE_REQ, 0, 0 → Basis-Objektadresse
```

Antwort: `D0_VALUE_ACK` mit DCF77-Zeit

### Zeit setzen

```
D0_SET_N, 0, Sekunde, Minute, Stunde, Tag, Monat, Wochentag, 0, Jahr → Basis-Objektadresse
```

### Profil-Maske abfragen/setzen

**Abfragen:**
```
D0_REQ, 0, 0 → Basis-Objektadresse
```

**Setzen:**
```
D0_SET, Profil_Maske, 0 → Basis-Objektadresse
```

## Zusammenfassung der Status-Informationen

### Vom Modul gesendet:

1. **D0_ACTOR_ACK** - Aktive Profil-Maske
   - Profil-Bitmaske in `ddata[2]`

2. **D0_VALUE_ACK** - DCF77-Zeit, Sonnenaufgang/Untergang
   - DCF77-Zeit mit Status-Bits
   - Sonnenaufgang/Untergang als Minuten seit Mitternacht

3. **D0_RD_MODULSPEC_DATA_ACK** - Konfigurationsdaten
   - Modul-Info bei `ddata[1] = $FF`
   - Zeitsteuerungs-Einträge bei `ddata[1] = 0-15`
   - Sonnenstand/Feiertage bei `ddata[1] = 16-108`

### Vom Modul ausgelöste Ereignisse:

1. **Zeitgesteuerte Aktionen** werden bei Erreichen der konfigurierten Zeit ausgelöst
2. **Befehle** werden an die konfigurierte Zieladresse gesendet
3. **Broadcast** der Zeit in regelmäßigen Abständen (wenn konfiguriert)

## Wichtige Konstanten

```pascal
PLATINE_HW_IS_HS_TIME = 10
D0_SET = 50
D0_REQ = 54
D0_ACTOR_ACK = 55
D0_SET_N = 59
D0_VALUE_REQ = 102
D0_VALUE_ACK = 101
D0_RD_MODULSPEC_DATA = 37
D0_WR_MODULSPEC_DATA = 39
IN_HW_NR_IS_CLOCK = 6
VAL_IS_MIN_TAG_WORD_SA = 50
VAL_IS_MIN_TAG_WORD_SU = 51
STE_MODE_ENTRY_OFF = 0
STE_MODE_HOURLY = 1
STE_MODE_DAILY = 2
STE_MODE_MONTHLY = 3
STE_MODE_JAHRLICH = 5
STE_MODE_SA = 7
STE_MODE_SU = 8
DCF77_SOMMERZEIT = 1
DCF77_SOMMERZEIT_ANGUENDIGUNG = 2
DCF77_KEIN_EMPFANG = 4
DCT_FEIERTAG = 8
DCF77_SYNC_PHASE = $10
MAX_FEIERTAGE = 240
MAX_TAGE_PRO_JAHR = 365
```

## Beispiel-Konfiguration

### Zeitsteuerungs-Eintrag: Täglich um 18:00 Uhr

```
Mode: STE_MODE_DAILY (2)
Hour: $18 (24 = 18 Uhr)
Min: $00 (0 Minuten)
Day: $00 (nicht verwendet)
Month: $00 (nicht verwendet)
Dow: $3F (Mo-Sa, Bit 0-5)
Zieladresse: 0x0100
Befehl: D0_SET, 1, 0 (Ein)
Profil: 1
```

### Zeitsteuerungs-Eintrag: 30 Minuten nach Sonnenaufgang

```
Mode: STE_MODE_SA (7)
Hour: 0 (nicht verwendet)
Min: 30 (30 Minuten)
Day: $00 (nicht verwendet)
Month: $00 (nicht verwendet)
Dow: $FF (alle Wochentage)
Zieladresse: 0x0200
Befehl: D0_SET, 1, 0 (Ein)
Profil: 1
```

## Implementierungshinweise

1. **Zeilenlänge beachten:** V1.x verwendet 14 Bytes, V2.00 verwendet 18 Bytes (16+2)
2. **BCD-Format:** Zeitangaben (außer STE_MODE_SA/SU) sind im BCD-Format
3. **Wochentag-Berechnung:** Sonntag = 6 (nicht 0)
4. **Sonnenstand-Berechnung:** Nur für Breitengrade 46°-58° Nord und Längengrade 5°-15° Ost
5. **Feiertage:** Nur zukünftige Feiertage werden gespeichert
6. **Profil-Maske:** Logisches UND zwischen Eintrags-Profil und aktiver Profil-Maske
