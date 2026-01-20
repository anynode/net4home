# Modultypen-Verwaltung: addMod Funktion

## Übersicht

Die Funktion `addMod` wird verwendet, um Modultypen zur Auswahlliste im Dialog "Modul hinzufügen" hinzuzufügen. Sie wird beim Erstellen des Dialogs (`FormCreate`) aufgerufen, um alle verfügbaren Modultypen zu registrieren.

## Funktionssignatur

```pascal
procedure TfModulNeuAdd.addMod(
  typ:byte;           // Modultyp (z.B. PLATINE_HW_IS_S4)
  desc:string;        // Beschreibungstext für die Anzeige
  ns:integer;         // Anzahl Sensoren
  na:integer;         // Anzahl Aktoren
  ng:integer;         // Länge der Gruppentabelle
  nm:integer;         // Länge der ModulSpec-Tabelle
  sw1:integer;        // Software-Version USER1 (Hauptversion)
  sw2:integer;        // Software-Version USER2 (Unterversion)
  swIPK1:integer;     // IPK-Version 1
  swIPK2:integer;     // IPK-Version 2
  i0:integer;         // Stromverbrauch in mA
  DlgIdx:integer      // Dialog-Index für Konfiguration
);
```

## Funktionsweise

Die Funktion erstellt ein `ToModul`-Objekt, füllt es mit den übergebenen Parametern und fügt es zur internen Liste `olModule` hinzu. Diese Liste wird später verwendet, um die Modultypen im ListView des Dialogs anzuzeigen.

```pascal
procedure TfModulNeuAdd.addMod(typ:byte; desc:string; ns,na,ng,nm, sw1,sw2,swIPK1,swIPK2, i0, DlgIdx:integer);
var
  om:ToModul;
begin
  om := ToModul.create;
  om.typModul.typ := typ;
  om.typModul.ns := ns;
  om.typModul.na := na;
  om.typModul.ModulSpecTabLen := nm;
  om.typModul.grpTabLen := ng;
  om.typModul.swvUSER1 := sw1;
  om.typModul.swvUSER2 := sw2;
  om.typModul.svwIPK := swIPK1;
  om.typModul.svwIPK_sub := swIPK2;
  om.typModul.DlgIdx := DlgIdx;
  om.I0 := i0;  // Stromverbrauch
  om.desc := desc;
  olModule.add(om);
end;
```

## Parameter-Erklärung

| Parameter | Typ | Beschreibung | Beispiel |
|-----------|-----|--------------|----------|
| `typ` | byte | Modultyp-Konstante (Hardware-Typ) | `PLATINE_HW_IS_S4` |
| `desc` | string | Anzeigename/Beschreibung | `'Sensor, 4fach'` |
| `ns` | integer | Anzahl Sensoren | `4` |
| `na` | integer | Anzahl Aktoren | `6` |
| `ng` | integer | Länge der Gruppentabelle | `80` |
| `nm` | integer | Länge der ModulSpec-Tabelle | `0` |
| `sw1` | integer | Software-Version USER1 (Hauptversion) | `1` |
| `sw2` | integer | Software-Version USER2 (Unterversion) | `15` |
| `swIPK1` | integer | IPK-Version 1 | `4` |
| `swIPK2` | integer | IPK-Version 2 | `4` |
| `i0` | integer | Stromverbrauch in Milliampere (mA) | `18` |
| `DlgIdx` | integer | Dialog-Index für Konfiguration | `DEF_IDX` (0) |

### Software-Version

Die Software-Version wird durch `sw1` und `sw2` dargestellt:
- `sw1 = 1, sw2 = 15` → Software-Version **1.15**
- `sw1 = 2, sw2 = 0` → Software-Version **2.00**

### IPK-Version

Die IPK-Version wird durch `swIPK1` und `swIPK2` dargestellt:
- `swIPK1 = 4, swIPK2 = 4` → IPK-Version **4.4**

## Verfügbare Modultypen

Die folgende Liste zeigt alle Modultypen, die über die `addMod`-Funktion registriert werden:

### Sensoren

| Typ | Beschreibung | Sensoren | Aktoren | Gruppen | ModulSpec | Software | IPK | Strom (mA) |
|-----|--------------|----------|---------|---------|-----------|----------|-----|------------|
| `PLATINE_HW_IS_S4` | Sensor, 4fach | 4 | 0 | 0 | 0 | 1.15 | 4.4 | 18 |
| `PLATINE_HW_IS_S32` | Sensor, 32fach (beta) | 32 | 0 | 0 | 0 | 1.02 | 4.4 | 50 |
| `PLATINE_HW_IS_UP_GL` | Sensor, Glasbruch | 1 | 0 | 0 | 0 | 1.10 | 4.3 | 55 |

### Aktoren

| Typ | Beschreibung | Sensoren | Aktoren | Gruppen | ModulSpec | Software | IPK | Strom (mA) |
|-----|--------------|----------|---------|---------|-----------|----------|-----|------------|
| `PLATINE_HW_IS_AR6` | Aktor, Relais, 6A 6fach | 0 | 6 | 80 | 0 | 2.00 | 4.4 | 125 |
| `PLATINE_HW_IS_AJ3` | Aktor, Jalousie, 3A 3fach | 0 | 3 | 80 | 0 | 2.01 | 4.4 | 125 |
| `PLATINE_HW_IS_AD3` | Aktor, Dimmer, 575VA 3fach | 0 | 3 | 80 | 0 | 1.18 | 4.4 | 40 |
| `PLATINE_HW_IS_AD3e` | Aktor, Dimmer-E, 575VA 3fach | 0 | 3 | 80 | 0 | 1.18 | 4.4 | 40 |
| `PLATINE_HW_IS_AT8` | Aktor, Elektronik, 25VA 8fach | 0 | 8 | 80 | 0 | 2.00 | 4.4 | 50 |
| `PLATINE_HW_IS_AT2E` | Aktor, Elektronik, 25VA 2fach | 0 | 2 | 80 | 0 | 1.00 | 4.3 | 50 |
| `PLATINE_HW_IS_AR2` | Aktor, Relais, 6A 2fach | 0 | 2 | 80 | 0 | 1.02 | 4.4 | 50 |
| `PLATINE_HW_IS_AJ1` | Aktor, Jalousie, 3A 1fach | 0 | 1 | 30 | 0 | 1.02 | 4.4 | 50 |
| `PLATINE_HW_IS_A32` | Aktor, 32fach (beta) | 0 | 32 | 80 | 0 | 1.02 | 4.4 | 50 |

### Regler und Spezialmodule

| Typ | Beschreibung | Sensoren | Aktoren | Gruppen | ModulSpec | Software | IPK | Strom (mA) |
|-----|--------------|----------|---------|---------|-----------|----------|-----|------------|
| `PLATINE_HW_IS_TLH` | Modul, Regler, Temp./Licht/Feuchte Sensor, UP-TLH | 0 | 0 | 0 | 22 | 1.20 | 4.4 | 30 |
| `PLATINE_HW_IS_UP_T` | Modul, Regler, Temp.Sensor, UP-T | 0 | 0 | 0 | 22 | 1.21 | 4.4 | 30 |
| `PLATINE_HW_IS_ALARM1` | Alarmanlage | 0 | 0 | 0 | 107 | 1.20 | 4.4 | 40 |
| `PLATINE_HW_IS_EXT_LD` | Motorriegel 1.20 | 0 | 0 | 0 | 6 | 1.20 | 4.4 | 40 |
| `PLATINE_HW_IS_EXT_LD` | Motorriegel 1.21 | 0 | 0 | 0 | 6 | 1.21 | 4.4 | 40 |
| `PLATINE_HW_IS_HS_ACCESS` | Zutritts-Steuerung | 0 | 0 | 0 | 60 | 1.03 | 4.4 | 40 |
| `PLATINE_HW_IS_I2_PIR` | Bewegungsmelder-Schnittstelle | 0 | 0 | 0 | 2 | 3.06 | 4.4 | 40 |
| `PLATINE_HW_IS_LCD3` | LCD-Display 1.31 | 0 | 0 | 0 | 508 | 1.31 | 4.4 | 50 |
| `PLATINE_HW_IS_LCD3` | LCD-Display 1.33 | 0 | 0 | 0 | 508 | 1.33 | 4.4 | 50 |
| `PLATINE_HW_IS_HS_WZ` | Wetterstation | 0 | 0 | 0 | 47 | 1.01 | 4.4 | 110 |
| `PLATINE_HW_IS_GSM` | GSM-Modul | 0 | 0 | 0 | 188 | 2.07 | 4.4 | 250 |
| `PLATINE_HW_IS_GSM` | GSM-Modul (16-bit only) | 0 | 0 | 0 | 188 | 2.08 | 4.4 | 250 |
| `PLATINE_HW_IS_HS_CLIMATE` | HS-Climate | 0 | 0 | 128 | 62 | 2.00 | 4.4 | 50 |
| `PLATINE_HW_IS_HS_JAL` | HS-Jal | 0 | 0 | 128 | 24 | 1.27 | 4.4 | 50 |
| `PLATINE_HW_IS_HS_TIME` | Zeitsteuerung, Zeitgeber DCF, Astrokalender | 0 | 0 | 0 | 112 | 2.00 | 4.4 | 35 |

### Fernbedienungen und Sender

| Typ | Beschreibung | Sensoren | Aktoren | Gruppen | ModulSpec | Software | IPK | Strom (mA) |
|-----|--------------|----------|---------|---------|-----------|----------|-----|------------|
| `PLATINE_HW_IS_IRRX` | Fernbedienungsempfänger (IR) | 0 | 0 | 0 | 32 | 1.10 | 4.4 | 40 |
| `PLATINE_HW_IS_IR_TX16` | IR Universalsender V2 (16bit) | 0 | 0 | 0 | 404 | 1.00 | 4.4 | 40 |
| `PLATINE_HW_IS_HFRX` | Fernbedienungsempfänger (Funk) | 0 | 0 | 0 | 40 | 1.01 | 4.4 | 40 |
| `PLATINE_HW_IS_HFRXT` | Empfänger für AP-Taster (Funk) | 0 | 0 | 0 | 128 | 1.00 | 4.4 | 40 |
| `PLATINE_HW_IS_HFRX_ELV868` | Funkempfänger 868Mhz (KS300) | 0 | 0 | 0 | 2 | 1.00 | 4.4 | 40 |

### Weitere Module

| Typ | Beschreibung | Sensoren | Aktoren | Gruppen | ModulSpec | Software | IPK | Strom (mA) |
|-----|--------------|----------|---------|---------|-----------|----------|-----|------------|
| `PLATINE_HW_IS_BELL2` | Komfort-Klingel | 0 | 0 | 0 | 25 | 1.128 | 4.4 | 500 |
| `PLATINE_HW_IS_19_AMP4` | Verstärker 4-Kanal 50W | 0 | 0 | 32 | 4 | 1.06 | 4.4 | 25 |
| `PLATINE_HW_IS_HS_SI6` | Stromsensor 6fach, HS-SI6 | 0 | 0 | 0 | 24 | 1.00 | 4.4 | 100 |
| `PLATINE_HW_IS_UP_SI` | Stromsensor 1fach, UP-SI | 0 | 0 | 0 | 4 | 1.09 | 4.3 | 50 |
| `PLATINE_HW_IS_DALI` | DALI-Schnittstelle | 0 | 0 | 16 | 54 | 1.00 | 4.3 | 100 |
| `PLATINE_HW_IS_HS_COUNTER` | Zähler | 0 | 0 | 0 | 34 | 1.02 | 4.4 | 40 |
| `PLATINE_HW_IS_ACCESS2_MAIN` | Zutritt+Zeiterfassung | 0 | 0 | 0 | 61 | 3.05 | 4.4 | 40 |
| `PLATINE_HW_IS_PROUTE1` | Ablaufsteuerung, Lichtszenen | 0 | 0 | 0 | 160 | 1.10 | 4.4 | 35 |
| `PLATINE_HW_IS_EXT_AQV_PW` | Badewannensteuerung | 0 | 0 | 0 | 4 | 1.06 | 4.4 | 0 |
| `PLATINE_HW_IS_EXT_CBE` | Belüftungssteuerung | 0 | 0 | 0 | 4 | 1.05 | 4.4 | 0 |
| `PLATINE_HW_IS_PC_SOFTWARE` | PC-Software MMS | 0 | 0 | 0 | 0 | 1.05 | 0.0 | 0 |
| `PLATINE_HW_IS_UP_RF` | RF-Tag Leser V1 | 2 | 1 | 10 | 0 | 1.12 | 4.4 | 55 |
| `PLATINE_HW_IS_UP_RF` | RF-Tag Leser V1 (2009-08) | 2 | 1 | 10 | 0 | 1.13 | 4.4 | 55 |
| `PLATINE_HW_IS_UP_RF2` | RF-Tag Leser V2 | 0 | 0 | 0 | 10 | 2.00 | 4.4 | 55 |

## Verwendung

Die Funktion wird während der Initialisierung des Dialogs (`FormCreate`) aufgerufen, um alle verfügbaren Modultypen zu registrieren:

```pascal
procedure TfModulNeuAdd.FormCreate(Sender: TObject);
begin
  olModule := TObjectList.create;
  
  // Alle Modultypen registrieren
  addMod(PLATINE_HW_IS_S4, 'Sensor, 4fach', 4, 0, 0, 0, 1, 15, 4, 4, 18, DEF_IDX);
  // ... weitere Module
end;
```

Die registrierten Module werden dann im `FormShow`-Event im ListView angezeigt, wo der Benutzer einen Modultyp auswählen kann, um ein neues Modul zum Projekt hinzuzufügen.

## Beispiel

```pascal
addMod(
  PLATINE_HW_IS_S4,        // Typ: 4-fach Sensor
  'Sensor, 4fach',         // Beschreibung
  4,                       // 4 Sensoren
  0,                       // 0 Aktoren
  0,                       // 0 Gruppen
  0,                       // 0 ModulSpec-Tabellen
  1,                       // Software-Version 1
  15,                      // Software-Version .15
  4,                       // IPK-Version 4
  4,                       // IPK-Version .4
  18,                      // 18 mA Stromverbrauch
  DEF_IDX                  // Standard-Dialog-Index
);
```

Dieses Beispiel registriert einen 4-fach Sensor mit Software-Version 1.15, IPK-Version 4.4 und einem Stromverbrauch von 18 mA.

---

# D0_ACK_TYP Befehl

## Übersicht

Der `D0_ACK_TYP`-Befehl ist die Antwort auf einen `D0_GET_TYP`-Befehl und enthält alle wichtigen Informationen über ein Modul, einschließlich Modultyp, Software-Version, Konfigurationsstatus und Tabellen-Längen.

## Befehlscode

```pascal
D0_ACK_TYP = 3;
```

## Datenstruktur

Das `D0_ACK_TYP`-Paket enthält mindestens 15 Bytes (Index 0-14) mit folgenden Informationen:

| Byte-Index | Parameter | Typ | Beschreibung | Beispiel |
|------------|-----------|-----|--------------|----------|
| `ddata[0]` | Befehl | byte | Immer `D0_ACK_TYP` (3) | `3` |
| `ddata[1]` | `typ` | byte | Modultyp (Hardware-Typ) | `PLATINE_HW_IS_S4` |
| `ddata[2]` | `ns` | byte | Anzahl Sensoren | `4` |
| `ddata[3]` | `na` | byte | Anzahl Aktoren | `6` |
| `ddata[5]` | `svwIPK_sub` | byte | IPK-Unterversion | `4` |
| `ddata[7]` | `swvUSER1` | byte | Software-Version USER1 (Hauptversion) | `1` |
| `ddata[8]` | `swvUSER2` | byte | Software-Version USER2 (Unterversion) | `15` |
| `ddata[9]` | `svwIPK` | byte | IPK-Version | `4` |
| `ddata[10]` | Config-Flags | byte | Bit-Flags für Konfiguration | siehe unten |
| `ddata[11]` | Flags | byte | Zusätzliche Flags | siehe unten |
| `ddata[12]` | `grpTabLen` | byte | Länge der Gruppentabelle | `80` |
| `ddata[13]` | `ModulSpecTabLen` | byte | Länge der ModulSpec-Tabelle | `0` |
| `ddata[14]` | `rnd_ip` | byte | Zufallszahl für IP (ab NET4/IPK≥4) | `0-255` |

**Hinweis:** Die MI-Adresse (`adr`) wird nicht im Datenpaket übertragen, sondern aus `paket.ipsrc` übernommen.

## Bit-Flags in ddata[10]

```pascal
D10_CONFIG_ENABLE_BIT    = $1;  // Bit 0: Konfiguration aktiviert
D10_FCONFIG_ENABLE_BIT   = $2;  // Bit 1: Factory-Konfiguration aktiviert
```

- **Bit 0** (`D10_CONFIG_ENABLE_BIT`): `cfgEnabled` – Konfiguration aktiviert
- **Bit 1** (`D10_FCONFIG_ENABLE_BIT`): `fcfgEnabled` – Factory-Konfiguration aktiviert (nur wenn Bit 0 gesetzt)

### Auswertung der Config-Flags

```pascal
function GetLcfgEnabled(var ddata:Tddata):boolean;
begin
  result := false;
  if ddata[9] >= 2 then // NET2
  begin
    if (ddata[10] and D10_CONFIG_ENABLE_BIT) <> 0 then
      result := true;
  end;
end;

function GetFcfgEnabled(var ddata:Tddata):boolean;
begin
  result := false;
  if (ddata[10] and D10_CONFIG_ENABLE_BIT) <> 0 then
  begin
    if (ddata[10] and D10_FCONFIG_ENABLE_BIT) <> 0 then
      result := true;
  end;
end;
```

## Bit-Flags in ddata[11]

```pascal
D11_ACK_TYP_MS16BIT = $01;  // Bit 0: ModulSpec-Tabelle ist 16-bit
```

- **Bit 0** (`D11_ACK_TYP_MS16BIT`): Wenn gesetzt, wird `ModulSpecTabLen` mit 4 multipliziert (16-bit statt 8-bit)

### Auswertung

```pascal
if svwIPK >= 3 then  // ab NET3
begin
  if (ddata[11] and D11_ACK_TYP_MS16BIT) <> 0 then
    ModulSpecTabLen := ModulSpecTabLen * 4;
end;
```

## Datenverarbeitung

Die Daten werden in der Funktion `DDataToTModulTypAdresse` extrahiert:

```pascal
procedure DDataToTModulTypAdresse(var modul:TModulTypAdresse; mi:integer; ddata:Tddata);
begin
  with modul do
  begin
    cfgEnabled := GetLcfgEnabled(ddata);
    fcfgEnabled := GetFcfgEnabled(ddata);
    adr := mi;  // aus paket.ipsrc übernommen
    typ := ddata[1];
    ns := ddata[2];
    na := ddata[3];
    swvUSER1 := ddata[7];
    swvUSER2 := ddata[8];
    svwIPK := ddata[9];
    svwIPK_sub := ddata[5];
    grpTabLen := ddata[12];
    ModulSpecTabLen := ddata[13];
    
    rnd_ip := 0;
    if svwIPK >= 4 then  // ab NET4
      rnd_ip := ddata[14];
    
    if svwIPK >= 3 then  // ab NET3
    begin
      if (ddata[11] and D11_ACK_TYP_MS16BIT) <> 0 then
        ModulSpecTabLen := ModulSpecTabLen * 4;
    end;
  end;
end;
```

## Verwendung

Der `D0_ACK_TYP`-Befehl wird automatisch als Antwort auf `D0_GET_TYP` gesendet:

```pascal
// Anfrage senden
ddata[0] := D0_GET_TYP;
sendH2Nc(adrModul, ddata, 1);

// Antwort empfangen (in cb_n4h_paket)
if paket.ddata[0] = D0_ACK_TYP then
begin
  // Daten extrahieren
  DDataToTModulTypAdresse(o.modul, paket.ipsrc, paket.ddata);
  o.modul.rnd_ip := GetRndByDData(paket.ddata);
  o.SetCfgEnabledChanges(paket.ddata);
end;
```

## Abhängigkeiten von IPK-Version

- **NET2 (IPK ≥ 2)**: `cfgEnabled` wird aus `ddata[10]` ausgelesen
- **NET3 (IPK ≥ 3)**: `ModulSpecTabLen` kann 16-bit sein (Flag in `ddata[11]`)
- **NET4 (IPK ≥ 4)**: `rnd_ip` wird aus `ddata[14]` gelesen

## Zusammenfassung

Das `D0_ACK_TYP`-Paket enthält:
- **Modultyp und Hardware-Informationen**: typ, ns (Sensoren), na (Aktoren)
- **Software-Versionen**: swvUSER1, swvUSER2 (z.B. 1.15)
- **IPK-Versionen**: svwIPK, svwIPK_sub (z.B. 4.4)
- **Konfigurations-Status**: cfgEnabled, fcfgEnabled (aus ddata[10])
- **Tabellen-Längen**: grpTabLen, ModulSpecTabLen
- **Zufallszahl für IP**: rnd_ip (ab NET4)
- **Flags für erweiterte Funktionen**: ddata[11] (16-bit ModulSpec-Tabelle)
