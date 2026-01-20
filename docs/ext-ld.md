# EXT-LD (Motorriegel) Modul

## Übersicht

EXT-LD ist ein **Motorriegel-Modul** für die Steuerung von Türschlössern mit Motorantrieb. Das Modul ermöglicht die elektrische Ver- und Entriegelung von Türen über das net4home Bus-System.

## Modul-Informationen

| Eigenschaft | Wert |
|-------------|------|
| **Hardware-Typ** | `PLATINE_HW_IS_EXT_LD` (39) |
| **Software-Versionen** | 1.20, 1.21 |
| **Min. Software-Version** | 1.10 (für Konfigurator) |
| **ModulSpec-Tabellen** | 6 (ab V1.16), 4 (bis V1.15) |
| **Objektadressen** | 3 (ADR_USAGE = 3) |
| **Stromverbrauch** | 40 mA |
| **IPK-Version** | 4.4 |

## Objektadressen

Das EXT-LD-Modul verwendet **3 aufeinanderfolgende Objektadressen**:

| Objektadresse | Objekttyp | Beschreibung |
|---------------|-----------|--------------|
| `adr+0` | `OT_EXT_LD_BASE` (90) | Basis-Objektadresse (Hauptfunktion) |
| `adr+1` | `OT_EXT_LD_BASE_1` (91) | Zeit "Tür offen" ändern |
| `adr+2` | `OT_EXT_LD_BASE_2` (92) | Türkontaktabfrage |

**Beispiel:**
- Basis-Adresse: `0x1234`
- Adresse 1: `0x1234` (OT_EXT_LD_BASE)
- Adresse 2: `0x1235` (OT_EXT_LD_BASE_1)
- Adresse 3: `0x1236` (OT_EXT_LD_BASE_2)

## Software-Versionen und Kompatibilität

### Version 1.10 (Minimum)
- Basis-Funktionalität
- Konfigurator erfordert mindestens Version 1.10

### Version 1.11
- ModulSpec-Datenlänge: 24 Bytes pro Zeile (`MSP_DATA_LEN_BIS_V111`)
- Timer-Faktor für Rücklauf: 5ms

### Version 1.12
- ModulSpec-Datenlänge: 12 Bytes pro Zeile (`MSP_DATA_LEN_AB_V112`)
- Timer-Faktor für Rücklauf: 25ms (ab V1.12)

### Version 1.15
- Momentensperre während Entriegeln+Entspannen (`cbMomentenSperreONwhileEntrPlus`)
- Ext-LD Integration in HS-Safety

### Version 1.16
- ModulSpec-Tabellen: 6 Zeilen (statt 4)
- Neue Events:
  - "Tür wurde geschlossen"
  - "Tür steht offen"

### Version 1.19
- Schnelles Verdrehen erkennen (`cbSchnellesVerdrehenErkennen`)
- Referenzfahrt auf nach unbekannt (`cbReferenzfahrtAufNachUnbekannt`)
- UniSend-Info senden (`cbSendUniSendInfo`)

## Konfigurationsdatenstruktur

### ModulSpec-Daten (72 Bytes)

Die Konfigurationsdaten werden in 3 Blöcken à 24 Bytes gespeichert (bis V1.11) oder in 6 Blöcken à 12 Bytes (ab V1.12).

#### Block 1 (Zeile 0-1, bis V1.11) / (Zeile 0-5, ab V1.12)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0-2 | `EE_CMD_TX_1` | 3 bytes | Befehl für Event 1 (Taster betätigt) |
| 3-4 | `EE_ADR_TX_1` | word | Zieladresse für Event 1 |
| 5-7 | `EE_CMD_TX_2` | 3 bytes | Befehl für Event 2 (Motor-Endstellung "verriegelt") |
| 8-9 | `EE_ADR_TX_2` | word | Zieladresse für Event 2 |
| 10-12 | `EE_CMD_TX_3` | 3 bytes | Befehl für Event 3 (Motor-Endstellung "entriegelt") |
| 13-14 | `EE_ADR_TX_3` | word | Zieladresse für Event 3 |
| 15-17 | `EE_CMD_TX_4` | 3 bytes | Befehl für Event 4 (Tür wurde geöffnet) |
| 18-19 | `EE_ADR_TX_4` | word | Zieladresse für Event 4 |
| 5 | `EE_ADR_LOCAL_ADR` | word | Lokale Objektadresse (Basis) |
| 7 | `EE_T_MAX_MOTOR_EIN` | byte | Maximale Motorlaufzeit (Sekunden) |
| 8 | `EE_T_MOTOR_RUECK_ZU` | byte | Motor-Rücklaufzeit zu (in Einheiten von timer_factor_rueck) |
| 9 | `EE_IST_AUF_ZU` | byte | Status: Auf/Zu |
| 10 | `EE_T_IGNORE_STROM_BEGRENZUNG` | byte | Zeit zum Ignorieren der Strombegrenzung (in 5ms-Einheiten) |
| 11-12 | `EE_ADR_GRUPPE` | word | Gruppenadresse (Bit 15 = 1) |
| 13 | `EE_T_MOTOR_RUECK_AUF` | byte | Motor-Rücklaufzeit auf (in Einheiten von timer_factor_rueck) |
| 14 | `EE_T_MOTOR_RUECK_AUF_SUMMEN` | byte | Motor-Rücklaufzeit auf für Summen (in Einheiten von timer_factor_rueck) |
| ? | `EE_ADR_ZU_PULSE` | byte | Anzahl Pulse für "Zu"-Position (2, 4, 6, ...) |

#### Block 2 (Zeile 2-3, bis V1.11) / (Zeile 6-11, ab V1.12)

| Offset | Name | Typ | Beschreibung |
|--------|------|-----|--------------|
| 0 | `EE_IST_AUF_ZU` | byte | Status: Auf/Zu |
| 1 | `EE_TUERSTEHT_OFFEN_TIMER_SEC` | byte | Zeitverzögerung für "Tür steht offen" (Sekunden) |
| 5-7 | `EE_CMD_TX_5` | 3 bytes | Befehl für Event 5 (Manuell verdreht) |
| 8-9 | `EE_ADR_TX_5` | word | Zieladresse für Event 5 |
| 10-12 | `EE_CMD_TX_6` | 3 bytes | Befehl für Event 6 (Tür wurde geschlossen) |
| 13-14 | `EE_ADR_TX_6` | word | Zieladresse für Event 6 |
| 15-17 | `EE_CMD_TX_7` | 3 bytes | Befehl für Event 7 (Tür steht offen) |
| 18-19 | `EE_ADR_TX_7` | word | Zieladresse für Event 7 |

#### Optionen (EE_OPT_BITS_0)

| Bit | Konstante | Beschreibung |
|-----|-----------|--------------|
| 0 | `EE_OPT_0_MOTOR_INV` (1) | Motorrichtung invertiert (Tür rechts) |
| 1 | `EE_OPT_0_USE_TASTE` (2) | Taster erlauben |
| 2 | `EE_OPT_0_NACHT` (4) | Nachtschaltung aktiv |
| 5 | `EE_OPT_0_BEIDE_RICHT_ENTSPANNEN` (0x20) | Beide Richtungen entspannen |
| 6 | `EE_OPT_0_MS_BEI_ENTRIEGELN_PLUS_ENTSPANNEN` (0x40) | Momentensperre bei Entriegeln+Entspannen (ab V1.15) |
| ? | `EE_OPT_0_NACHT_IMMERZU` | Immer zu in Nachtschaltung |

#### Optionen (EE_OPT_BITS_1) - ab V1.19

| Bit | Konstante | Beschreibung |
|-----|-----------|--------------|
| 0 | `EE_OPT_1_SCHNELL_MAN_DREH_ERKENN` (1) | Schnelles Verdrehen erkennen |
| 1 | `EE_OPT_1_REF_AUF_NACH_UNBEKANNT` (2) | Referenzfahrt auf nach unbekannt |
| 2 | `EE_OPT_1_SENDE_UNISEND_INFO` (4) | UniSend-Info senden |

## Befehle

### D0_SET - Motor steuern

**Senden:**
```pascal
ddata[0] := D0_SET;
ddata[1] := Wert;  // 1 = Zu, 3 = Auf, 4 = Entriegeln und Summen
sendH2N_3byteCmdObj(D0_SET, Wert, 0, objAdr);
```

**Werte:**
- `1`: Motor zu (verriegeln)
- `3`: Motor auf (entriegeln)
- `4`: Entriegeln und Summen

**Beispiel:**
```pascal
// Tür verriegeln
ddata[0] := D0_SET;
ddata[1] := 1;
Fhome2net.sendH2N(Fhome2net.gPCipSrc, getLocalObjAdr, ddata, 2, 0);

// Tür entriegeln
ddata[0] := D0_SET;
ddata[1] := 3;
Fhome2net.sendH2N(Fhome2net.gPCipSrc, getLocalObjAdr, ddata, 2, 0);
```

### D0_REQ - Status abfragen

**Senden:**
```pascal
ddata[0] := D0_REQ;
Fhome2net.sendH2N(Fhome2net.gPCipSrc, getLocalObjAdr, ddata, 1, 0);
```

**Antwort:** `D0_ACTOR_ACK` (siehe unten)

### D0_TOGGLE - Toggle (Umschalten)

**Senden:**
```pascal
ddata[0] := D0_TOGGLE;
Fhome2net.sendH2N(Fhome2net.gPCipSrc, getLocalObjAdr, ddata, 1, 0);
```

### D0_LOCK - Verriegelung/Zwangsführung

**Senden:**
```pascal
ddata[0] := D0_LOCK;
ddata[1] := Flags;  // Bit-Flags
ddata[2] := 0;
Fhome2net.sendH2N_3byteCmdObj(D0_LOCK, Flags, 0, objAdr);
```

**Flags (ddata[1]):**
- Bit 7 (`$80`): Zwangsführung aktiv
- Bit 0 (`$01`): Verriegeln
- Bit 1 (`$02`): Entriegeln
- Bit 6 (`$40`): Momentensperre aktiv

**Kombinationen:**
- `$80 + $01 = $81`: Zwangsgeführt verriegeln
- `$80 + $03 = $83`: Zwangsgeführt entriegeln
- `$C0 + $01 = $C1`: Zwangsgeführt verriegeln + Momentensperre
- `$C0 + $03 = $C3`: Zwangsgeführt entriegeln + Momentensperre
- `$00`: Zwangsführung aus

**Beispiel:**
```pascal
// Zwangsgeführt verriegeln
Fhome2net.sendH2N_3byteCmdObj(D0_LOCK, $80 or $01, 0, getLocalObjAdr);

// Zwangsgeführt entriegeln
Fhome2net.sendH2N_3byteCmdObj(D0_LOCK, $80 or $03, 0, getLocalObjAdr);

// Zwangsführung aus
Fhome2net.sendH2N_3byteCmdObj(D0_LOCK, 0, 0, getLocalObjAdr);
```

### D0_LOCK_STATE_REQ - Verriegelungsstatus abfragen

**Senden:**
```pascal
Fhome2net.sendH2Nb_3byteCmdObj(D0_LOCK_STATE_REQ, 0, 0, getLocalObjAdr, gPCObjSrc);
```

**Antwort:** `D0_LOCK_STATE_ACK` (siehe unten)

### D0_SET_N - Spezielle Funktionen

**Senden:**
```pascal
ddata[0] := D0_SET_N;
ddata[1] := Funktion;  // 20 oder 21
Fhome2net.sendH2N(Fhome2net.gPCipSrc, getLocalObjAdr, ddata, 2, 0);
```

**Funktionen:**
- `20`: Funktion 20 (Referenzfahrt?)
- `21`: Funktion 21 (Referenzfahrt?)

## Antworten

### D0_ACTOR_ACK - Status-Information

**Empfangen:** Als Antwort auf `D0_REQ`

**Datenstruktur:**
```pascal
ddata[0] = D0_ACTOR_ACK;  // 55
ddata[1] = ?;             // Unbekannt
ddata[2] = StatusFlags;   // Bit-Flags
```

**Status-Flags (ddata[2]):**

| Bit | Konstante | Beschreibung |
|-----|-----------|--------------|
| 0 | `GOR_VERRIEGELT` (1) | Verriegelt |
| 1 | `GOR_DIR_A` (2) | Richtung A (>) |
| 2 | `GOR_DIR_B` (4) | Richtung B (<) |
| 3 | `GOR_NACHTBETRIEB` (8) | Nachtschaltung aktiv |
| 4 | `GOR_TUER_IST_GESCHLOSSEN` ($10) | Tür ist geschlossen |
| 5 | `GOR_TASTE_ERLAUBT` ($20) | Taster erlaubt |
| 6 | `GOR_MANUELL_VERDREHT` ($40) | Manuell verdreht |

**Beispiel-Auswertung:**
```pascal
if p.ddata[0] = D0_ACTOR_ACK then
begin
  s := 'GOA=';
  if (p.ddata[2] and GOR_DIR_A) <> 0 then s := s + '>/';
  if (p.ddata[2] and GOR_DIR_B) <> 0 then s := s + '</';
  if (p.ddata[2] and GOR_NACHTBETRIEB) <> 0 then s := s + 'Nacht/' else s := s + 'Tag/';
  if (p.ddata[2] and GOR_TUER_IST_GESCHLOSSEN) <> 0 then s := s + 'TürZu/' else s := s + 'TürAuf/';
  if (p.ddata[2] and GOR_TASTE_ERLAUBT) <> 0 then s := s + 'TasteErlaubt/' else s := s + 'TasteAus/';
  if (p.ddata[2] and GOR_MANUELL_VERDREHT) <> 0 then
    s := s + 'man.gedreht/'
  else
  begin
    if (p.ddata[2] and GOR_VERRIEGELT) <> 0 then s := s + 'Verriegelt/' else s := s + 'Entriegelt/';
  end;
end;
```

### D0_LOCK_STATE_ACK - Verriegelungsstatus

**Empfangen:** Als Antwort auf `D0_LOCK_STATE_REQ`

**Datenstruktur:**
```pascal
ddata[0] = D0_LOCK_STATE_ACK;  // 68
ddata[1] = StatusFlags;        // Bit-Flags
```

**Status-Flags (ddata[1]):**
- Bit 7 (`$80`): Zwangsführung aktiv
- Bit 6 (`$40`): Momentensperre aktiv
- Bit 0 (`$01`): Verriegeln
- Bit 1 (`$02`): Entriegeln

**Beispiel-Auswertung:**
```pascal
if p.ddata[0] = D0_LOCK_STATE_ACK then
begin
  cbZwang.Checked := ((p.ddata[1] and $80) <> 0);
  cbZWMomentensperre.Checked := ((p.ddata[1] and $40) <> 0);
  cbentriegeln.State := cbGrayed;
  cbverriegeln.State := cbGrayed;
end;
```

### D0_MODUL_SPECIFIC_INFO - Referenzfahrt-Status

**Empfangen:** Während Referenzfahrt

**Datenstruktur:**
```pascal
ddata[0] = D0_MODUL_SPECIFIC_INFO;  // 72
ddata[1] = MSI_Code;                // Referenzfahrt-Status
ddata[2] = Wert;                    // Zusätzlicher Wert
```

**MSI-Codes:**
- `MSI_REFERENZFAHRT_FAHRE_1` (1): Fahre in Startposition...
- `MSI_REFERENZFAHRT_FAHRE_2` (2): Referenzfahrt...
- `MSI_REFERENZFAHRT_BEENDET_OK` (3): Referenzfahrt erfolgreich, neuer Wert gespeichert
- `MSI_REFERENZFAHRT_BEENDET_ERROR` (4): Fehler: max. Laufzeit überschritten
- `MSI_REFERENZFAHRT_BEENDET_ERROR_TUER_OFFEN` (5): Fehler: Tür erst schließen!
- `MSI_REFERENZFAHRT_BEENDET_ERROR_MAX_PULSE_ERREICHT` (6): Fehler: zu viele Umdrehungen

**Beispiel-Auswertung:**
```pascal
if p.ddata[0] = D0_MODUL_SPECIFIC_INFO then
begin
  case p.ddata[1] of
    MSI_REFERENZFAHRT_FAHRE_1:     sb1.Panels[2].text := 'fahre in Startposition...';
    MSI_REFERENZFAHRT_FAHRE_2:     sb1.Panels[2].text := 'Referenzfahrt...';
    MSI_REFERENZFAHRT_BEENDET_OK:  sb1.Panels[2].text := 'Neuen Wert gespeichert: '+IntToStr(p.ddata[2]);
    MSI_REFERENZFAHRT_BEENDET_ERROR: msge('Fehler: max. Laufzeit überschritten');
    MSI_REFERENZFAHRT_BEENDET_ERROR_TUER_OFFEN: msge('Tür erst schließen !');
    MSI_REFERENZFAHRT_BEENDET_ERROR_MAX_PULSE_ERREICHT: msge('Fehler: zuviele Umdrehungen.');
  end;
end;
```

## Event-System

Das EXT-LD-Modul unterstützt **7 Events**, die bei bestimmten Zuständen ausgelöst werden:

| Event | Beschreibung | Adresse | Befehl |
|-------|--------------|---------|--------|
| 0 | "Taster betätigt" | `EE_ADR_TX_1` | `EE_CMD_TX_1` |
| 1 | Motor-Endstellung "verriegelt" | `EE_ADR_TX_2` | `EE_CMD_TX_2` |
| 2 | Motor-Endstellung "entriegelt" | `EE_ADR_TX_3` | `EE_CMD_TX_3` |
| 3 | "Tür wurde geöffnet" | `EE_ADR_TX_4` | `EE_CMD_TX_4` |
| 4 | "Manuell verdreht" | `EE_ADR_TX_5` | `EE_CMD_TX_5` |
| 5 | "Tür wurde geschlossen" | `EE_ADR_TX_6` | `EE_CMD_TX_6` |
| 6 | "Tür steht offen" | `EE_ADR_TX_7` | `EE_CMD_TX_7` |

**Hinweis:** Event 6 ("Tür steht offen") hat eine zusätzliche Zeitverzögerung (`EE_TUERSTEHT_OFFEN_TIMER_SEC`).

## Konfigurationsparameter

### Zeitparameter

| Parameter | Offset | Typ | Einheit | Beschreibung |
|-----------|--------|-----|---------|--------------|
| `EE_T_MAX_MOTOR_EIN` | 7 | byte | Sekunden | Maximale Motorlaufzeit |
| `EE_T_MOTOR_RUECK_ZU` | 8 | byte | timer_factor_rueck ms | Motor-Rücklaufzeit zu |
| `EE_T_MOTOR_RUECK_AUF` | 13 | byte | timer_factor_rueck ms | Motor-Rücklaufzeit auf |
| `EE_T_MOTOR_RUECK_AUF_SUMMEN` | 14 | byte | timer_factor_rueck ms | Motor-Rücklaufzeit auf für Summen |
| `EE_T_IGNORE_STROM_BEGRENZUNG` | 10 | byte | 5ms | Zeit zum Ignorieren der Strombegrenzung |
| `EE_T_WIEDERVERRIEGELN` | ? | byte | Sekunden | Wiederverriegelung nach X Sekunden (Nachtschaltung) |
| `EE_TUERSTEHT_OFFEN_TIMER_SEC` | 1 | byte | Sekunden | Zeitverzögerung für "Tür steht offen" Event |

**Timer-Faktoren:**
- Bis V1.12: `timer_factor_rueck = 5` (5ms pro Einheit)
- Ab V1.12: `timer_factor_rueck = 25` (25ms pro Einheit)

**Beispiel:**
```pascal
// Bis V1.12: 100ms = 20 Einheiten (100 / 5)
// Ab V1.12: 100ms = 4 Einheiten (100 / 25)
ad[EE_T_MOTOR_RUECK_ZU] := StrToInt(ed_EE_T_MOTOR_RUECK.text) div timer_factor_rueck;
```

### Adressparameter

| Parameter | Offset | Typ | Beschreibung |
|-----------|--------|-----|--------------|
| `EE_ADR_LOCAL_ADR` | 5-6 | word | Lokale Objektadresse (Basis) |
| `EE_ADR_GRUPPE` | 11-12 | word | Gruppenadresse (Bit 15 = 1) |
| `EE_ADR_ZU_PULSE` | ? | byte | Anzahl Pulse für "Zu"-Position (2, 4, 6, ...) |

## Integration mit HS-Safety

Das EXT-LD-Modul kann in die HS-Safety (Alarmanlage) integriert werden:

**Konfiguration in HS-Safety (ab V1.15):**
- Ext-LD Adresse: Objektadresse des EXT-LD-Moduls
- Ext-LD Optionen:
  - `EE_TAB_AI_INTERN1`: Intern 1
  - `EE_TAB_AI_INTERN2`: Intern 2
  - `EE_TAB_AI_EXTERN`: Extern

**Verwendung:**
- Ext-LD kann beim Scharfschalten verriegelt werden
- Ext-LD kann bei Alarm ausgelöst werden

## Besondere Funktionen

### Referenzfahrt

Die Referenzfahrt dient zur Kalibrierung der Motorpositionen:

1. **Start:** `D0_SET_N` mit Wert `20` oder `21`
2. **Status:** `D0_MODUL_SPECIFIC_INFO` mit MSI-Codes
3. **Ergebnis:** Neuer Wert wird in `ddata[2]` zurückgegeben

**Voraussetzungen:**
- Tür muss geschlossen sein
- Max. Laufzeit darf nicht überschritten werden
- Max. Pulse dürfen nicht erreicht werden

### Schnelles Verdrehen erkennen

**Ab V1.19:** Option `EE_OPT_1_SCHNELL_MAN_DREH_ERKENN`

Erkennt, wenn die Tür manuell schnell verdreht wird (ohne Motor).

**Warnung:** Diese Option sollte nur in Absprache mit net4home GmbH verwendet werden.

### Motorrichtung invertieren

**Option:** `EE_OPT_0_MOTOR_INV`

Invertiert die Motorrichtung (für Türen, die rechts montiert sind).

**Code-Logik:**
```c
bit realDir = DIR_AUF;
if (cfg_inv_motor_dir)
  realDir = !realDir;

if (realDir == DIR_AUF)
  OUT_MOTOR_A = 0;
  OUT_MOTOR_B = 1;
else
  OUT_MOTOR_A = 1;
  OUT_MOTOR_B = 0;
```

## Code-Referenzen

### Hauptdateien
- `Ext_LDu.pas`: Haupt-Implementierung des EXT-LD-Konfigurators
- `Ext_LDu.dfm`: Formular-Definition
- `uh2nApi.pas`: Konstanten und Definitionen (Zeilen 720-790)

### Wichtige Funktionen
- `TfExt_LD.setData()`: Verarbeitung eingehender Pakete
- `TfExt_LD.ad_to_edit()`: Konvertierung Daten → UI
- `TfExt_LD.edit_to_ad()`: Konvertierung UI → Daten
- `TfExt_LD.FOnBeforWriteModul()`: Vorbereitung zum Schreiben

### Integration in Unit1.pas
```pascal
// Zeile 2268: Paket-Verteilung
if assigned(fExt_LD) then
  if fExt_LD.visible then
    fExt_LD.setData(paket);

// Zeile 4659-4663: Modul-Auswahl
PLATINE_HW_IS_EXT_LD:
  bExtLDClick(nil);
  result := fExt_LD;
```

## Changelog

### V1.20
- Änderung für spezielle Türen, die mechanisch kein Entriegeln in die Strombegrenzung vertragen
- Schnelle Erkennung für manuelles Verdrehen
- UniSend-Option zum ständigen Update der Visualisierung
- K1 bleibt abwärtskompatibel für ältere EXT-LD

### V1.21
- Anpassung an den 53er Atmelprozessor

## Zusammenfassung

EXT-LD ist ein Motorriegel-Modul für die Steuerung von Türschlössern:
- **3 Objektadressen** für verschiedene Funktionen
- **7 Events** für Zustandsänderungen
- **Zwangsführung** und **Momentensperre** für Sicherheit
- **Referenzfahrt** zur Kalibrierung
- **Integration** mit HS-Safety möglich
- **Verschiedene Software-Versionen** mit unterschiedlichen Features
