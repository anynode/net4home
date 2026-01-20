# Powerup-Status bei Aktoren

## Übersicht

Der Powerup-Status bestimmt das Verhalten eines Aktors nach einem Stromausfall oder Neustart. Dieser Status wird über den Befehl `D0_RD_ACTOR_DATA_ACK` ausgelesen und über `D0_WR_ACTOR_DATA` geschrieben.

## Befehl zum Auslesen

### D0_RD_ACTOR_DATA_ACK

**Befehlscode:** `31` (definiert in `uh2nApi.pas` als `D0_RD_ACTOR_DATA_ACK`)

**Antwort auf:** `D0_RD_ACTOR_DATA` (26)

## Datenstruktur in D0_RD_ACTOR_DATA_ACK

Das `D0_RD_ACTOR_DATA_ACK` Paket enthält die Konfigurationsdaten für einen einzelnen Aktor-Kanal:

| Byte-Index | Name | Typ | Beschreibung |
|------------|------|-----|--------------|
| `ddata[0]` | Befehl | byte | Immer `D0_RD_ACTOR_DATA_ACK` (31) |
| `ddata[1]` | Kanal | byte | Kanalnummer (0..n) |
| `ddata[2]` | Typ | byte | Aktor-Typ (z.B. `OUT_HW_NR_IS_ONOFF`, `OUT_HW_NR_IS_TIMER`, `OUT_HW_NR_IS_DIMMER`) |
| `ddata[3]` | Zeit1 Low | byte | Niedriges Byte von Zeitwert 1 (signed, Little Endian) |
| `ddata[4]` | Zeit1 High | byte | Hohes Byte von Zeitwert 1 (signed, Little Endian) |
| `ddata[5]` | **PowerUp** | **byte** | **Powerup-Status (Index 0-4)** |
| `ddata[6]` | MinHell | byte | Minimale Helligkeit (bei Dimmern) |
| `ddata[7]` | StatusInfoPost | byte | Status-Info senden (0 = nein, 1 = ja) |
| `ddata[8]` | ObjAdr Low | byte | Niedriges Byte der Objektadresse (Little Endian) |
| `ddata[9]` | ObjAdr High | byte | Hohes Byte der Objektadresse (Little Endian) |
| `ddata[10]` | Zeit2 Low | byte | Niedriges Byte von Zeitwert 2 (signed, Little Endian) |
| `ddata[11]` | Zeit2 High | byte | Hohes Byte von Zeitwert 2 (signed, Little Endian) |
| `ddata[12]` | Optionen | byte | Optionen (Bit-Flags, z.B. `OUT_OPTION_2_MOTOR_ANLAUF`, `OUT_OPTION_2_INV_OUT`) |
| `ddata[13]` | Art | byte | Aktor-Art (bei bestimmten Modultypen) |
| `ddata[14]` | MotorVal | byte | Motoranlauf in % (bei Dimmern) |
| `ddata[15]` | MotorTime | byte | Motoranlauf in Sekunden (bei Dimmern) |
| `ddata[16..33]` | - | byte | Weitere Daten (abhängig vom Modultyp) |

## Powerup-Status Werte

Der Powerup-Status wird in `ddata[5]` gespeichert und ist ein Index (0-4), der auf folgende Werte verweist:

| Index | Wert | Beschreibung |
|-------|------|--------------|
| `0` | `AUS` | Aktor bleibt nach Powerup ausgeschaltet |
| `1` | `EIN` | Aktor wird nach Powerup eingeschaltet |
| `2` | `wie vor Stromausfall` | Aktor nimmt den Zustand wieder ein, den er vor dem Stromausfall hatte |
| `3` | `keine Änderung` | Keine Änderung am aktuellen Zustand |
| `4` | `EIN mit 100%` | Aktor wird nach Powerup mit 100% eingeschaltet (bei Dimmern) |

**Quelle:** Diese Werte sind in `AktorKonfigU.dfm` für die ComboBoxen `cbPowerUpAR` und `cbPowerUpAD` definiert:

```pascal
Items.Strings = (
  'AUS'                    // Index 0
  'EIN'                    // Index 1
  'wie vor Stromausfall'  // Index 2
  'keine Änderung'         // Index 3
  'EIN mit 100%')          // Index 4
```

## Auswertung im Code

### Lesen aus D0_RD_ACTOR_DATA_ACK

Die Auswertung erfolgt in `AktorKonfigU.pas` in der Funktion `setData`:

```pascal
if ddata[0] = D0_RD_ACTOR_DATA_ACK then
begin
  posTab := ddata[1];
  
  if posTab < 32 then
    move (ddata[2], md.zeilen[posTab].d[0], 32);
  
  AxZeileToLV(posTab);
  
  // Powerup-Status wird aus ddata[5] gelesen
  // (in auskommentiertem Code: sg1.Cells[3,posTab+1]:= cbPowerUp.items[ ddata[5] ];)
end;
```

### Speicherung in ModulASx

Die Daten werden in der Struktur `ModulASx.z[kanal].d[2+3]` gespeichert:

- **Offset im ddata-Array:** `5` (direkt als `ddata[5]`)
- **Offset in ModulASx:** `2+3` (die ersten 2 Bytes sind für Schicht 2 reserviert)

**Beispiele aus dem Code:**

```pascal
// Für Dimmer (AD)
lvAD.Items[kanal].SubItems[5] := cbPowerUpAD.items[ oASbase.ModulASx.z[kanal].d[2+3] ];

// Für Relais (AR)
lvAR.Items[kanal].SubItems[6] := cbPowerUpAD.items[ oASbase.ModulASx.z[kanal].d[2+3] ];
```

### Schreiben des Powerup-Status

Beim Schreiben wird der Wert in `ddata[5]` gesetzt:

```pascal
// In EditToRecAR, EditToRecAD, etc.
ddata[5] := cbPowerUp.itemIndex;
```

## Modul-Unterstützung

**Nicht alle Module unterstützen Powerup!**

Die Funktion `ModulKannPowerUp(mtyp:byte):boolean` in `uh2nApi.pas` prüft, ob ein Modultyp Powerup unterstützt.

**Beispiel aus `AktorKonfigU.pas`:**

```pascal
if not ModulKannPowerUp(oASbase.ModulASx.typModul.typ) then
begin
  cbPowerUpAR.Visible := false;
  LabelARPowerUp.Visible := false;
end;
```

Wenn ein Modul Powerup nicht unterstützt, wird das Powerup-Combobox in der UI ausgeblendet.

## Verwendung in verschiedenen Aktor-Typen

### Relais (AR)

- Powerup-Status wird in `lvAR.Items[kanal].SubItems[6]` angezeigt
- ComboBox: `cbPowerUpAR`
- Speicherung: `oASbase.ModulASx.z[kanal].d[2+3]`

### Dimmer (AD)

- Powerup-Status wird in `lvAD.Items[kanal].SubItems[5]` angezeigt
- ComboBox: `cbPowerUpAD`
- Speicherung: `oASbase.ModulASx.z[kanal].d[2+3]`
- **Besonderheit:** Bei Dimmern kann auch "EIN mit 100%" (Index 4) verwendet werden

### Jalousie (AJ)

- **Powerup wird nicht unterstützt** für Jalousien
- In `AktorKonfigU.pas` Zeile 847: `cbPowerup.visible := false;` für Jalousien

## Standardwerte

Wenn Powerup nicht sichtbar/verfügbar ist, wird standardmäßig `0` (AUS) gesetzt:

```pascal
if cbPowerUpAR.Visible then
  oASbase.ModulASx.z[kanal].d[2+3] := cbPowerUpAR.itemIndex
else
  oASbase.ModulASx.z[kanal].d[2+3] := 0;
```

## Verwandte Befehle

- **Lesen:** `D0_RD_ACTOR_DATA` (26) → Antwort: `D0_RD_ACTOR_DATA_ACK` (31)
- **Schreiben:** `D0_WR_ACTOR_DATA` (30) → verwendet die gleiche Datenstruktur

## Zusammenfassung

- **Befehl:** `D0_RD_ACTOR_DATA_ACK` (31)
- **Position:** `ddata[5]` (Index 0-4)
- **Werte:**
  - `0` = AUS
  - `1` = EIN
  - `2` = wie vor Stromausfall
  - `3` = keine Änderung
  - `4` = EIN mit 100% (nur Dimmer)
- **Speicherung:** `ModulASx.z[kanal].d[2+3]` (Offset 5 im ddata-Array)
- **Einschränkung:** Nicht alle Module unterstützen Powerup (prüfen mit `ModulKannPowerUp`)
