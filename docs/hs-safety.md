# HS-Safety Modul Dokumentation

## Übersicht

Das **HS-Safety** Modul (`PLATINE_HW_IS_ALARM1` = 35) ist eine Alarmanlage für das net4home System. Es überwacht Sensoren, verwaltet Scharf-/Unscharf-Zustände und löst bei Alarm verschiedene Aktionen aus.

## Modultyp

- **Hardware-Typ:** `PLATINE_HW_IS_ALARM1` (35)
- **Modultyp:** `MODUL_IS_M` (Master-Modul)
- **Datenstruktur:** Verwendet `D0_RD_MODULSPEC_DATA` / `D0_RD_MODULSPEC_DATA_ACK` für Konfiguration

## Datenstruktur

### Tabellen-Organisation

Das Modul verwendet mehrere Tabellen mit jeweils 16 Bytes (`EE_TAB_TX_LEN = 16`) pro Eintrag:

- **Tab0:** Basis-Konfiguration (Länge: `gTab0len`)
- **Tab1:** Auslöser-Liste (Länge: `gTab1len`)
- **Tab2:** Ausgänge/Aktionen (Länge: `gTab2len`)
- **Tab3:** RF-Keys (Länge: `gTab3len`)
- **Tab4:** Event-Log (Länge: `gTab4len`)

**Gesamtlänge:** `gTabEntryCount = gTab0len + gTab1len + gTab2len + gTab3len + ((gTab4len * 12) div 16)`

### Modul-Info (ddata[1] = $FF)

Bei `D0_RD_MODULSPEC_DATA_ACK` mit `ddata[1] = $FF`:

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[2]` | `gTab0len` | Länge Tabelle 0 |
| `ddata[3]` | `gTab1len` | Länge Tabelle 1 (Auslöser) |
| `ddata[4]` | `gTab2len` | Länge Tabelle 2 (Ausgänge) |
| `ddata[5]` | `gTab3len` | Länge Tabelle 3 (Keys) |
| `ddata[6]` | `gTab4len` | Länge Tabelle 4 (Event-Log) |

## Status-Informationen

### D0_SENSOR_ACK - Sensor-Status

Das Modul sendet `D0_SENSOR_ACK` (65) als Antwort auf `D0_REQ` (54) zur Statusabfrage eines Sensors.

**Datenstruktur:**

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[0]` | Befehl | `D0_SENSOR_ACK` (65) |
| `ddata[1]` | Wert Low | Niedriges Byte des Sensorwerts |
| `ddata[2]` | Status | Bit-Flags für Sensor-Status |
| `ddata[3]` | Wert High | Hohes Byte des Sensorwerts |
| `ddata[4]` | Sync | 0 = Sensor synchronisiert, sonst nicht synchronisiert |

**Status-Bits in ddata[2]:**

| Bit | Konstante | Bedeutung |
|-----|-----------|-----------|
| 0 | `EE_TAB_AI_EXTERN` (1) | Extern aktiv |
| 1 | `EE_TAB_AI_INTERN1` (2) | Intern 1 aktiv |
| 2 | `EE_TAB_AI_INTERN2` (4) | Intern 2 aktiv |
| 3 | `EE_TAB_AI_SABO` (8) | Sabotage aktiv |

**Status-Text-Format:**
- `ext/` - wenn `EE_TAB_AI_EXTERN` gesetzt
- `int1/` - wenn `EE_TAB_AI_INTERN1` gesetzt
- `int2/` - wenn `EE_TAB_AI_INTERN2` gesetzt
- `sab/` - wenn `EE_TAB_AI_SABO` gesetzt
- `sync...` - wenn `ddata[4] = 0` (Sensor synchronisiert)

### D0_VALUE_ACK - RF-Tag Reader

Bei Empfang eines RF-Tags sendet das Modul `D0_VALUE_ACK` (101):

| Byte | Name | Beschreibung |
|------|------|--------------|
| `ddata[0]` | Befehl | `D0_VALUE_ACK` (101) |
| `ddata[1]` | Hardware-Typ | `IN_HW_NR_IS_RF_TAG_READER` (7) |
| `ddata[2]` | Key-Typ | `USE_FROMEL_KEY_RFTAG` |
| `ddata[3..7]` | Key-Daten | 5 Bytes RF-Tag-Daten (`RF_PAKET_DATA_LEN = 5`) |
| `ddata[9]` | Short/Long | `RF_KEY_LONG` oder `RF_KEY_SHORT` |

## Befehle zum Modul

### D0_SET - Scharf/Unscharf schalten

**Befehl:** `D0_SET` (50)

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| `ddata[1]` | `1` | Extern Scharf |
| `ddata[1]` | `2` | Intern 2 Scharf |
| `ddata[1]` | `3` | Intern 1 Scharf |
| `ddata[1]` | `0` | Unscharf |
| `ddata[1]` | `11` | Test-Befehl 1 |
| `ddata[1]` | `12` | Test-Befehl 2 |
| `ddata[1]` | `13` | Test-Befehl 3 |

### D0_REQ - Sensor-Status abfragen

**Befehl:** `D0_REQ` (54)

Fragt den Status eines Sensors ab. Antwort: `D0_SENSOR_ACK`

## Ereignisse (Events)

Das Modul kann verschiedene Ereignisse auslösen, die in Tabelle 2 (Tab2) konfiguriert werden. Jedes Ereignis kann einen Befehl an eine Objektadresse senden.

### Event-Liste

| Index | Ereignis-Name | Beschreibung |
|-------|---------------|--------------|
| 0 | Extern Scharf geschaltet.1 | Erste Aktion bei Extern Scharf |
| 1 | Extern Scharf geschaltet.2 | Zweite Aktion bei Extern Scharf |
| 2 | Intern 2 Scharf geschaltet.1 | Erste Aktion bei Intern 2 Scharf |
| 3 | Intern 2 Scharf geschaltet.2 | Zweite Aktion bei Intern 2 Scharf |
| 4 | Intern 1 Scharf geschaltet.1 | Erste Aktion bei Intern 1 Scharf |
| 5 | Intern 1 Scharf geschaltet.2 | Zweite Aktion bei Intern 1 Scharf |
| 6 | Unscharf geschaltet.1 | Erste Aktion bei Unscharf |
| 7 | Unscharf geschaltet.2 | Zweite Aktion bei Unscharf |
| 8 | Reserviert | Reserviert |
| 9 | Alles geschlossen, Prüfung begonnen | Prüfung startet |
| 10 | Alles geschlossen, erfolgreich geprüft | Prüfung erfolgreich |
| 11 | Nicht alles geschlossen | Nicht alle Sensoren geschlossen |
| 12 | Ausgelöst, Quittieren eines Alarms anfordern | Alarm ausgelöst, Quittierung erforderlich |
| 13 | Ausgelöst bei Extern Scharf.1 | Alarm bei Extern Scharf (1) |
| 14 | Ausgelöst bei Extern Scharf.2 | Alarm bei Extern Scharf (2) |
| 15 | Ausgelöst bei Intern 2 Scharf.1 | Alarm bei Intern 2 Scharf (1) |
| 16 | Ausgelöst bei Intern 2 Scharf.2 | Alarm bei Intern 2 Scharf (2) |
| 17 | Ausgelöst bei Intern 1 Scharf.1 | Alarm bei Intern 1 Scharf (1) |
| 18 | Ausgelöst bei Intern 1 Scharf.2 | Alarm bei Intern 1 Scharf (2) |
| 19 | Ausgelöst bei Unscharf (Sabotage).1 | Alarm bei Unscharf/Sabotage (1) |
| 20 | Ausgelöst bei Unscharf (Sabotage).2 | Alarm bei Unscharf/Sabotage (2) |

**Hinweis:** Ab Software-Version 1.18 werden 13 Events unterstützt, ab Version 1.19 werden 21 Events unterstützt.

### Event-Konfiguration

Jedes Event speichert einen `TBefehl` (5 Bytes) mit:
- **Adresse** (2 Bytes, Little Endian, geswappt)
- **Befehl** (3 Bytes: `d[0]`, `d[1]`, `d[2]`)

Die Event-Adressen werden automatisch vergeben:
- Basis-Adresse: `ed_obj_main` (Haupt-Objektadresse)
- Event-Adressen: `Basis + 5 + EventIndex`

## Auslöser-Konfiguration (Tab1)

Jeder Auslöser ist ein Eintrag in Tabelle 1 mit folgender Struktur:

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB_ADR_MONITOR` | word | Objektadresse des zu überwachenden Sensors (Little Endian, geswappt) |
| 2 | `EE_TAB_ACTIVE_IN` | byte | Bit-Flags für Aktivierung |
| 3 | `EE_TAB_RX_MODE` | byte | Empfangsmodus |
| 4 | `EE_TAB_SENSORTYP` | byte | Sensor-Typ |
| 5-7 | `EE_TAB__2` bis `EE_TAB__4` | byte | Reserviert |
| 8-15 | `EE_TAB_TEXT` | string[8] | Name/Text des Auslösers |

### EE_TAB_ACTIVE_IN (Bit-Flags)

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | `EE_TAB_AI_EXTERN` | 1 | Bei "Extern Scharf" aktiv |
| 1 | `EE_TAB_AI_INTERN1` | 2 | Bei "Intern 1 Scharf" aktiv |
| 2 | `EE_TAB_AI_INTERN2` | 4 | Bei "Intern 2 Scharf" aktiv |
| 3 | `EE_TAB_AI_SABO` | 8 | Sabotage-Erkennung |
| 4 | `EE_TAB_AI_EX_DELAY` | $10 | Extern mit Verzögerung |

**Kombinationen:**
- `EE_TAB_AI_INTERN1` (2): Intern 1+2+Ext aktiv
- `EE_TAB_AI_INTERN2` (4): Intern 2+Ext aktiv
- `EE_TAB_AI_EXTERN` (1): Nur Extern aktiv

### EE_TAB_RX_MODE

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | `EE_TAB_RXM_DEST` | 1 | Empfang über Zieladresse |
| 1 | `EE_TAB_RXM_SRC` | 2 | Empfang über Absenderadresse |

### EE_TAB_SENSORTYP

| Bit | Konstante | Wert | Bedeutung |
|-----|-----------|------|-----------|
| 0 | `EE_TAB_ST_REED_N0` | 1 | Reed-Kontakt NO (Normal Open) |
| 1 | `EE_TAB_ST_REED_N1` | 2 | Reed-Kontakt N1 (Normal Closed) |

## Ausgänge-Konfiguration (Tab2)

### Zeile 0: Sirene 1

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_ADR_SIRENE1` | word | Objektadresse der Sirene (Little Endian, geswappt) |
| 2-3 | `EE_TAB2_ADR_SIRENE1_TIME` | word | Zeit in Sekunden (Little Endian, geswappt, signed) |

### Zeile 1: Rundumleuchte 1

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_ADR_RUNDUM1` | word | Objektadresse der Rundumleuchte |
| 2-3 | `EE_TAB2_ADR_RUNDUM1_TIME` | word | Zeit in Sekunden (signed) |

### Zeile 2: Info-LED

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_ADR_ON_INFO` | word | Objektadresse für LED-Status |
| 2 | LED-Invert | byte | `1` = LED invertiert, `$FF` = normal |
| 3-4 | Ext-LD Adresse | word | Adresse für Ext-LD (ab V1.15) |
| 5 | Ext-LD Optionen | byte | Bit-Flags: `EE_TAB_AI_INTERN1`, `EE_TAB_AI_INTERN2`, `EE_TAB_AI_EXTERN` |

### Zeile 3: Info-LCD

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_ADR_LCD_INFO` | word | Objektadresse für LCD-Text |
| 2 | RF nur Ext | byte | `1` = RF nur bei Extern, `$FF` = immer |
| 3 | Always Poll | byte | `1` = Sensoren immer abfragen, `$FF` = nur bei Scharf |
| 4 | Poll-Timer | byte | Intervall in Sekunden (5-60) |
| 5 | New Detect | byte | `$A5` = Neue Erkennung (ab V1.18) |
| 6 | IP to Alarm | byte | `1` = IP bei Alarm, `$FF` = deaktiviert (ab V1.11) |

### Zeile 4: Pre-Alarm

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_ADR_PRE_ALARM` | word | Objektadresse für Pre-Alarm |
| 2-3 | `EE_TAB2_ADR_PRE_ALARM_TIME` | word | Zeit in Sekunden (signed) |

### Zeile 5: RF-Reader

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-1 | `EE_TAB2_RF_READER` | word | Objektadresse des RF-Readers |
| 2 | Wrong Key to Alarm | byte | `1` = Falscher Key löst Alarm aus, `0` = nicht |

## RF-Keys (Tab3)

Jeder Key ist 5 Bytes lang (`RF_PAKET_DATA_LEN = 5`) und wird in einem 16-Byte-Eintrag gespeichert:

| Offset | Beschreibung |
|--------|--------------|
| 0-4 | RF-Tag-Daten (5 Bytes) |
| 5-15 | Reserviert |

Ein leerer Key ist mit `$FF` gefüllt.

## Event-Log (Tab4)

Das Event-Log speichert bis zu 20 Ereignisse (`T_Safety_Evt`):

```pascal
T_Safety_Evt = record
  nr: word;          // Event-Nummer
  zeile: byte;       // Auslöser-Zeile (oder $F0/$F1/$F2 für spezielle Events)
  std, min, sec: byte;  // Zeit
  day, month, year: byte;  // Datum
  add: byte;         // 1 = nicht gemeldet
  res1, res2: byte;  // Reserviert
end;
```

**Spezielle Event-Zeilen:**
- `$F0`: 3x falscher Key
- `$F1`: Uhr gestellt
- `$F2`: Konfigbefehl erkannt

## Basis-Konfiguration (Tab0)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0 | - | byte | `8` = Sabo, nicht aus |
| 3-4 | `EE_LC_ADR` | word | Basis-Objektadresse (Little Endian, geswappt) |
| 5 | Event 11 Adresse | byte | Adresse für Event 11 |
| 10 | Status an VisualOne | byte | `1` = Status an VisualOne senden |
| 11 | Event 12 Adresse | byte | Adresse für Event 12 |

## Software-Versionen

### Ab V1.10
- Basis-Funktionalität

### Ab V1.11
- `cbIPtoAlarm` aktiviert (IP bei Alarm)

### Ab V1.15
- Ext-LD Unterstützung (`ed_ExtLD`, `ebLD_i1`, `ebLD_i2`, `ebLD_ext`)

### Ab V1.18
- 13 Events unterstützt
- `gOnEventCount = 13`
- Neue Erkennung (`$A5` in Tab2 Zeile 3, Offset 5)

### Ab V1.19
- 21 Events unterstützt
- `gOnEventCount = 13+8 = 21`
- `ADR_USAGE = 18+8 = 26`

## Kommunikationsprotokoll

### Lesen der Konfiguration

1. **Modul-Info lesen:**
   ```
   D0_RD_MODULSPEC_DATA, $FF, 0, 0 → Modul-Adresse
   ```
   Antwort: `D0_RD_MODULSPEC_DATA_ACK` mit Tabellen-Längen

2. **Tabellen lesen:**
   ```
   D0_RD_MODULSPEC_DATA, Index, 0, 0 → Modul-Adresse
   ```
   Antwort: `D0_RD_MODULSPEC_DATA_ACK` mit 16 Bytes Daten

### Schreiben der Konfiguration

1. **Tabellen schreiben:**
   ```
   D0_WR_MODULSPEC_DATA, Index, [16 Bytes Daten], 0 → Modul-Adresse
   ```

### Sensor-Status abfragen

```
D0_REQ, 0, 0 → Sensor-Objektadresse
```
Antwort: `D0_SENSOR_ACK` mit Status-Informationen

### Scharf/Unscharf schalten

```
D0_SET, Modus, 0 → Modul-Objektadresse
```
- Modus: `1` = Extern, `2` = Intern 2, `3` = Intern 1, `0` = Unscharf

## Zusammenfassung der Status-Informationen

### Vom Modul gesendet:

1. **D0_SENSOR_ACK** - Sensor-Status bei Abfrage
   - Status-Bits: extern, intern1, intern2, sabotage
   - Sync-Status

2. **D0_VALUE_ACK** - RF-Tag erkannt
   - RF-Tag-Daten (5 Bytes)

3. **D0_RD_MODULSPEC_DATA_ACK** - Konfigurationsdaten
   - Tabellen-Längen bei `ddata[1] = $FF`
   - Tabellen-Daten bei normalem Index

### Vom Modul ausgelöste Ereignisse:

1. **21 verschiedene Events** können Befehle an konfigurierte Objektadressen senden
2. **Event-Log** speichert alle wichtigen Ereignisse mit Zeitstempel
3. **Ausgänge** (Sirene, Rundumleuchte, LED, LCD, Pre-Alarm) werden bei Alarm aktiviert

## Wichtige Konstanten

```pascal
PLATINE_HW_IS_ALARM1 = 35
D0_SET = 50
D0_REQ = 54
D0_SENSOR_ACK = 65
D0_VALUE_ACK = 101
IN_HW_NR_IS_RF_TAG_READER = 7
EE_TAB_TX_LEN = 16
RF_PAKET_DATA_LEN = 5
EE_TAB_AI_EXTERN = 1
EE_TAB_AI_INTERN1 = 2
EE_TAB_AI_INTERN2 = 4
EE_TAB_AI_SABO = 8
EE_TAB_AI_EX_DELAY = $10
```
