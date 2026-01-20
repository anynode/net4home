# Bus-Kommunikation: ENUM_ALL (Discover)

## Übersicht

Der `D0_ENUM_ALL` Befehl wird verwendet, um alle Module im System zu entdecken. Je nach Systemgröße wird die Enumeration in unterschiedlich viele Teile aufgeteilt, um die Netzwerkbelastung zu reduzieren und Timeouts zu vermeiden.

## Systemgrößen

Das System unterstützt drei verschiedene Größenkonfigurationen:

### Kleines System (≤250 Module)
- **EnumPartMax:** `0`
- **Anzahl Teile:** 1 (keine Aufteilung)
- **Anzahl Runden:** 3 (wie bei allen Systemgrößen)
- **Gesamtausführungen:** 3 Runden × 1 Teil = 3x ENUM_ALL
- **Paketgröße:** 1 Byte
- **Paketformat:** Nur `D0_ENUM_ALL` (Byte 0)

### Mittleres System (251-500 Module)
- **EnumPartMax:** `2`
- **Anzahl Teile:** 2
- **Anzahl Runden:** 3 pro Teil (wie bei allen Systemgrößen)
- **Gesamtausführungen:** 3 Runden × 2 Teile = 6x ENUM_ALL
- **Paketgröße:** 5 Bytes
- **Paketformat:** `D0_ENUM_ALL` + Parameter

### Großes System (>500 Module)
- **EnumPartMax:** `4`
- **Anzahl Teile:** 4
- **Anzahl Runden:** 3 pro Teil (wie bei allen Systemgrößen)
- **Gesamtausführungen:** 3 Runden × 4 Teile = 12x ENUM_ALL
- **Paketgröße:** 5 Bytes
- **Paketformat:** `D0_ENUM_ALL` + Parameter

## Paketformat

### Kleines System
```pascal
ddata[0] := D0_ENUM_ALL;  // Nur 1 Byte
sendH2Nc(BROADCASTIP, ddata, 1);
```

### Mittleres und Großes System
```pascal
ddata[0] := D0_ENUM_ALL;  // Byte 0: Befehl
ddata[1] := $00;           // Byte 1: Reserviert
ddata[2] := Mask;          // Byte 2: Maske ($01 für mittleres, $03 für großes System)
ddata[3] := $00;           // Byte 3: Reserviert
ddata[4] := PartNumber;    // Byte 4: Teilnummer (0, 1, 2, oder 3)
sendH2Nc(BROADCASTIP, ddata, 1+4);  // 5 Bytes gesamt
```

### Teilnummern und Masken

**Mittleres System (EnumPartMax = 2):**
- Teil 0: `ddata[2] = $01`, `ddata[4] = $00`
- Teil 1: `ddata[2] = $01`, `ddata[4] = $01`

**Großes System (EnumPartMax = 4):**
- Teil 0: `ddata[2] = $03`, `ddata[4] = $00`
- Teil 1: `ddata[2] = $03`, `ddata[4] = $01`
- Teil 2: `ddata[2] = $03`, `ddata[4] = $02`
- Teil 3: `ddata[2] = $03`, `ddata[4] = $03`

## Ablauf der Enumeration

### 1. Initialisierung
```pascal
enumPart := 0;  // Startet bei Teil 0
EnumLevel(EL_FULL_ERASE, olModulTypListeMain);
```

### 2. Senden des ENUM_ALL Befehls
```pascal
procedure TFhome2net.EnumSend;
begin
  enum_all_req := true;
  TimerEnumAllTimeOut.tag := 1;
  TimerEnumAllTimeOut.enabled := true;
  
  // Sendet entsprechend der Systemgröße
  if EnumPartMax <> 0 then
    sendH2Nc(BROADCASTIP, ddata, 1+4)  // 5 Bytes für mittlere/große Systeme
  else
    sendH2Nc(BROADCASTIP, ddata, 1);   // 1 Byte für kleine Systeme
end;
```

### 3. Antwortverarbeitung
Jedes Modul antwortet mit `D0_ACK_TYP`, das folgende Informationen enthält:
- Modul-IP (Quelladresse)
- Modultyp
- Konfigurationsstatus
- Zufallszahl (rnd_ip)

Bei jeder `D0_ACK_TYP` Antwort:
- Timer wird zurückgesetzt: `TimerEnumAllTimeOut.Enabled := true`
- Modul wird zur Liste hinzugefügt oder aktualisiert
- Fortschrittsbalken wird aktualisiert

### 4. Timeout und Wiederholung/Nächster Teil
Nach Ablauf des Timeouts (`TimerEnumAllTimeOutTimer`):
- `enum_all_req := false`
- `AfterF5Complete` wird aufgerufen
- **Wiederholungslogik (gilt für alle Systemgrößen):**
  - Wenn `EnumState < 3`: Nächste Runde wird gestartet (EnumState wird inkrementiert)
  - Wenn `EnumState = 3` und `EnumPartMax <> 0`: Nächster Teil wird gesendet
    - `enumPart` wird inkrementiert
    - `EnumState` wird auf 1 zurückgesetzt
    - Nächster Teil wird gesendet: `EnumLevel(EL_CHECK_EXISTING_REPEAT, ...)`
  - Wenn `EnumState = 3` und `EnumPartMax = 0`: Enumeration ist abgeschlossen

## Timeout-Verhalten

### Konfigurierbarer Timeout
Der Timeout für `ENUM_ALL` ist konfigurierbar über die Statistik-Dialogbox:
```pascal
TimerEnumAllTimeOut.interval := 1000 * StrToInt(ed_timeEnumall.text);  // in Sekunden
```

**Standardwert:** 500ms (wie in `Unit1.dfm` definiert)

### Timeout-Mechanismus
1. **Timer wird gestartet** beim Senden von `ENUM_ALL`
2. **Timer wird zurückgesetzt** bei jeder `D0_ACK_TYP` Antwort
3. **Timer läuft ab**, wenn keine weiteren Antworten mehr kommen
4. **Nach Timeout:** Enumeration wird als abgeschlossen betrachtet

Dieses Verhalten stellt sicher, dass:
- Genug Zeit für alle Module bleibt, um zu antworten
- Die Enumeration nicht zu früh beendet wird
- Große Systeme genug Zeit für alle Antworten haben

### Verzögerung zwischen Teilen
Nach Abschluss eines Teils (EnumState = 3):
- `enumPart` wird inkrementiert
- Nächster Teil wird sofort gesendet (keine zusätzliche Verzögerung)
- Der Timer wird für den neuen Teil neu gestartet

## Wiederholungsmechanismus

**Wichtig:** Die Wiederholungslogik gilt für **alle Systemgrößen**, auch für kleine Systeme!

Die Enumeration wird immer 3 Runden pro Teil durchgeführt, um sicherzustellen, dass alle Module erfasst werden:

1. **Erste Runde (EnumState = 1):** Initiale Enumeration
2. **Zweite Runde (EnumState = 2):** Wiederholung zur Erfassung verspäteter Antworten
3. **Dritte Runde (EnumState = 3):** Finale Wiederholung

**Bei kleinen Systemen (EnumPartMax = 0):**
- Nach 3 Runden ist die Enumeration abgeschlossen
- Keine weiteren Teile werden gesendet
- **Gesamt: 3x ENUM_ALL Befehl**

**Bei mittleren Systemen (EnumPartMax = 2):**
- Nach 3 Runden eines Teils wird zum nächsten Teil gewechselt
- Jeder Teil durchläuft wiederum 3 Runden
- **Gesamt: 2 Teile × 3 Runden = 6x ENUM_ALL Befehl**

**Bei großen Systemen (EnumPartMax = 4):**
- Nach 3 Runden eines Teils wird zum nächsten Teil gewechselt
- Jeder Teil durchläuft wiederum 3 Runden
- **Gesamt: 4 Teile × 3 Runden = 12x ENUM_ALL Befehl**

Die Wiederholung erfolgt unabhängig von der Systemgröße und ist in der Logik von `AfterF5Complete` implementiert (siehe Code-Referenzen).

## Code-Referenzen

### EnumSend (Unit1.pas, Zeile 8089-8161)
Hauptprozedur zum Senden des ENUM_ALL Befehls mit Systemgrößen-spezifischer Paketkonstruktion.

### TimerEnumAllTimeOutTimer (Unit1.pas, Zeile 4058-4065)
Timeout-Handler, der die Enumeration abschließt, wenn keine weiteren Antworten kommen.

### AfterF5Complete (Unit1.pas, Zeile 4086-4145)
Wird nach Abschluss eines Enumerationsteils aufgerufen und steuert:
- Fortsetzung mit nächstem Teil (bei mittleren/großen Systemen)
- Start der Namensabfrage (optional)
- Finale Anzeige der Ergebnisse

### D0_ACK_TYP Verarbeitung (Unit1.pas, Zeile 2686-2827)
Verarbeitet die Antworten der Module und:
- Fügt neue Module hinzu
- Aktualisiert bestehende Moduleinträge
- Setzt den Timeout-Timer zurück

## Zusammenfassung

- **Kleine Systeme:** 3 Runden Enumeration ohne Aufteilung (1 Teil × 3 Runden = **3x ENUM_ALL**)
- **Mittlere Systeme:** 2-teilige Enumeration mit Mask `$01` (2 Teile × 3 Runden = **6x ENUM_ALL**)
- **Große Systeme:** 4-teilige Enumeration mit Mask `$03` (4 Teile × 3 Runden = **12x ENUM_ALL**)
- **Timeout:** Konfigurierbar (Standard: 500ms), wird bei jeder Antwort zurückgesetzt
- **Wiederholung:** **Immer 3 Runden pro Teil**, unabhängig von der Systemgröße
- **Keine zusätzliche Verzögerung** zwischen den Runden oder Teilen - sie werden sequenziell abgearbeitet
