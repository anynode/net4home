# Adressierung im net4home Bus-System

## Übersicht

Das net4home System verwendet verschiedene Adresstypen für die Kommunikation auf dem Bus:
- **MI** (Modul-IP): Direkte Adressierung von Modulen über ihre IP-Adresse
- **OBJ** (Objekt): Adressierung über Objektadressen
- **GRP** (Gruppe): Adressierung von Gruppen
- **Broadcast**: Broadcast-Adresse für alle Module

## Broadcast-Adresse

Die Broadcast-Adresse ist **`$FFFF`** und wird verwendet, um Nachrichten an alle Module im System zu senden.

```pascal
MI_BRC      = $ffff;
BROADCASTIP = $ffff;
```

**Verwendung:**
```pascal
sendH2Nc(BROADCASTIP, ddata, 1);
```

## Adresstypen im Detail

### 1. MI (Modul-IP)

**Adressbereich:** `1` bis `$FFFE`

**Kennzeichnung:**
- `type8 = sa2_T8_IP` (Wert `1`)
- Adresse wird direkt als IP-Adresse interpretiert

**Verwendung:**
- Direkte Kommunikation mit Modulen über deren IP-Adresse
- Wird für Konfigurationsbefehle verwendet
- Beispiel: `sendH2Nc(ipDest, ddata, datalen)` → sendet mit `SEND_AS_IP`

**Code-Beispiel:**
```pascal
function TFhome2net.sendH2Nc(ipDest:word; ddata:Tddata; datalen:byte):boolean;
begin
  result := sendH2Nb(gPCipSrc, ipDest, gPCobjSrc, ddata, datalen, SEND_AS_IP);
end;
```

### 2. OBJ (Objekt)

**Adressbereich:** `1` bis `$7FFE` (Bit 15 = 0)

**Kennzeichnung:**
- `type8 = 0` (kein IP-Flag)
- Adresse hat Bit 15 = 0 (niedrige Adressen)
- `MIN_OBJ_ADR = 1`
- `MAX_OBJ_ADR = $7FFE`

**Verwendung:**
- Kommunikation über Objektadressen
- Wird für logische Objekte im System verwendet
- Beispiel: `sendH2Nobj(ObjDest, ddata, datalen)` → sendet mit `type8 = 0`

**Code-Beispiel:**
```pascal
function TFhome2net.sendH2Nobj(ObjDest:word; ddata:Tddata; datalen:byte):boolean;
begin
  result := sendH2Nb(gPCipSrc, ObjDest, gPCobjSrc, ddata, datalen, 0);
end;
```

### 3. GRP (Gruppe)

**Adressbereich:** `$8001` bis `$FFFE - 500` (Bit 15 = 1)

**Kennzeichnung:**
- `type8 = 0` (kein IP-Flag)
- Adresse hat Bit 15 = 1 (`sa2_ADR_GRUPPE = $8000`)
- `MIN_GRP_ADR = $8001`
- `MAX_GRP_ADR = $FFFE - 500`

**Verwendung:**
- Gruppenkommunikation
- Ermöglicht das Senden an mehrere Module gleichzeitig
- Die Unterscheidung zwischen OBJ und GRP erfolgt über Bit 15 der Adresse

**Code-Beispiel:**
```pascal
function type8AsText(t:byte; adr:word):string;
begin
  if (t and sa2_T8_IP) <> 0 then result:= 'IP'
  else
  begin
    if adr and sa2_ADR_TYP_MASK = sa2_ADR_GRUPPE then
      result:= 'GRP'
    else
      result:= 'OBJ';
  end;
end;
```

## Entscheidungslogik in sendH2Nb

Die zentrale Funktion `sendH2Nb` setzt das `type8`-Flag basierend auf dem `sendAs`-Parameter:

```pascal
function TFhome2net.sendH2Nb(lipSrc,lipDest, lobjSrc:word; lddata:Tddata; 
                              ldatalen, lsendAs:byte):boolean;
var p:TN4Hpaket; 
    res:integer;
begin
   with p do
   begin
     ipSrc := lipsrc;
     ipDest := lipDest;
     objSrc := lobjSrc;
     move (lddata, ddata, sizeof(ddata));
     ddatalen := ldatalen;
     type8 := lsendAs;       // ObjGrp
     if lsendAs = SEND_AS_IP then
      type8 := sa2_T8_IP;
   end;
   // ...
end;
```

## Konstanten und Definitionen

### Adressbereiche
```pascal
MIN_OBJ_ADR = 1;         // kleinste gültige Objektadresse
MIN_OBJ_ADR_REQ = 1000;  // kleinste vergebene Objektadresse
MAX_OBJ_ADR = $7FFE;

MIN_GRP_ADR = $8001;
MAX_GRP_ADR = $FFFE - 500;  // reservierte feste Adressen

MI_EMPTY = 0;
MI_BRC   = $ffff;  // Broadcast-Adresse
```

### type8 Flags
```pascal
sa2_ADR_OBJ    = 0;
sa2_T8_IP      = 1;
sa2_T8_IP_ON_BUS = 2;
saCYCLIC       = 4;
saACK_REQ      = 8;
saPNR_MASK     = $F0;

sa2_ADR_GRUPPE = $8000;
sa2_ADR_TYP_MASK = $8000;
sa2_ADR_MASK   = $7FFF;

SEND_AS_OBJ_GRP = 0;
SEND_AS_IP     = sa2_T8_IP;  // = 1
```

## Zusammenfassungstabelle

| Typ | Adressbereich | type8 | Bit 15 der Adresse | Verwendung |
|-----|---------------|-------|-------------------|-----------|
| **MI** | 1 - $FFFE | `1` (sa2_T8_IP) | beliebig | Modul-IP-Adresse |
| **OBJ** | 1 - $7FFE | `0` | `0` | Objektadresse |
| **GRP** | $8001 - $FFFE-500 | `0` | `1` ($8000) | Gruppenadresse |
| **Broadcast** | `$FFFF` | `1` | - | Broadcast an alle |

## Unterscheidung zwischen OBJ und GRP

Die Unterscheidung zwischen Objekt- und Gruppenadressen erfolgt über **Bit 15** der Adresse:

- **OBJ**: Bit 15 = 0 → Adresse im Bereich 1 bis $7FFE
- **GRP**: Bit 15 = 1 → Adresse im Bereich $8001 bis $FFFE-500

Dies wird durch die Maske `sa2_ADR_TYP_MASK = $8000` geprüft:
```pascal
if adr and sa2_ADR_TYP_MASK = sa2_ADR_GRUPPE then
  // Es ist eine Gruppenadresse
else
  // Es ist eine Objektadresse
```

## Praktische Beispiele

### Broadcast senden
```pascal
ddata[0] := D0_ENUM_ALL;
sendH2Nc(BROADCASTIP, ddata, 1);
```

### An Modul-IP senden
```pascal
ddata[0] := D0_GET_TYP;
sendH2Nc(adrModul, ddata, 1);  // sendet mit SEND_AS_IP
```

### An Objektadresse senden
```pascal
ddata[0] := D0_SET_N;
sendH2Nobj(objDest, ddata, lenTX);  // sendet mit type8 = 0
```

### Gruppenadresse erkennen
```pascal
if (adr >= MIN_GRP_ADR) and (adr <= MAX_GRP_ADR) then
  // Es ist eine Gruppenadresse
```
