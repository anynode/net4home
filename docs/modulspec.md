# D0_RD_MODULSPEC_DATA_ACK Auswertung

## Übersicht

Der Befehl `D0_RD_MODULSPEC_DATA_ACK` (38) ist die Antwort auf einen `D0_RD_MODULSPEC_DATA` (37) Befehl und enthält modulspezifische Konfigurationsdaten. Die Auswertung variiert je nach Modultyp und verwendet unterschiedliche Datenstrukturen.

## Befehlscodes

```pascal
D0_RD_MODULSPEC_DATA      = 37;  // Anfrage
D0_RD_MODULSPEC_DATA_ACK  = 38;  // Antwort
D0_WR_MODULSPEC_DATA      = 39;  // Schreiben
```

## Allgemeine Datenstruktur

Das `D0_RD_MODULSPEC_DATA_ACK` Paket hat folgende Grundstruktur:

| Byte-Index | Name | Beschreibung |
|------------|------|--------------|
| `ddata[0]` | Befehl | Immer `D0_RD_MODULSPEC_DATA_ACK` (38) |
| `ddata[1]` | Kanal/Index | Kanalnummer, Tabellen-Index oder spezielle Adresse |
| `ddata[2..]` | Daten | Modulspezifische Daten (Länge variiert) |

## Modulspezifische Auswertungen

### 1. SensorConfig (SensorConfigU.pas)

**Verwendung:** Konfiguration von Sensormodulen

```pascal
if ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if ddata[1] = 0 then // kanal 0
  begin
    cbSicheres_Senden.Checked := (ddata[2] and SEND_WITH_ACKREQ) <> 0;
  end;
end;
```

**Datenstruktur:**
- `ddata[1] = 0`: Kanal 0 (Allgemeine Konfiguration)
- `ddata[2]`: Flags (Bit 0 = `SEND_WITH_ACKREQ` für sicheres Senden)

---

### 2. Vi4 (Vi4u.pas) - Videoumschalter

**Verwendung:** Konfiguration des Vi4 Videoumschalters

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  ed_obj.text := IntToStr(pTo16bit(@p.ddata[EE_OBJ_ADRw]));
  ed_grp.text := IntToStr(pTo16bit(@p.ddata[EE_GRP_ADRw]) and $7fff);
  cbSlaveCount.ItemIndex := p.ddata[EE_SLAVESb];
  cb_betriebsart.ItemIndex := p.ddata[EE_MODEb];
  ed_verweildauer.text := FloatToStr(p.ddata[EE_T100MS_HOLDb] / 10);
  ed_haltezeit.text := FloatToStr(p.ddata[EE_T100MS_CAMb] / 10);
  
  cam_used := pTo16bit(@p.ddata[EE_USED_CAMSw]);
  cb_cam_aktiv1.checked := boolean(cam_used and 1);
  cb_cam_aktiv2.checked := boolean(cam_used and 2);
  // ... bis cb_cam_aktiv10
end;
```

**Datenstruktur:**
- `ddata[1] = 0`: Hauptkonfiguration
- `EE_OBJ_ADRw`: Objektadresse (2 Bytes, Little Endian)
- `EE_GRP_ADRw`: Gruppenadresse (2 Bytes, Little Endian, Bit 15 = 0)
- `EE_SLAVESb`: Anzahl Slaves
- `EE_MODEb`: Betriebsart
- `EE_T100MS_HOLDb`: Verweildauer in 100ms-Schritten
- `EE_T100MS_CAMb`: Haltezeit in 100ms-Schritten
- `EE_USED_CAMSw`: Bitmask für aktive Kameras (16-bit)

**Anfrage:**
```pascal
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, 0, 0, adrModul);
```

---

### 3. Tuer (uTuer.pas) - Türöffner

**Verwendung:** Anzeige von Türöffner-Daten

```pascal
if ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  s := intToHex(ddata[2], 2) + '  ';
  for i := 0 to 4 do
    s := s + IntToHex(ddata[i+3], 2);
  s := s + ' Master=' + inttostr(ddata[8]);
  lb1.items.add(s);
end;
```

**Datenstruktur:**
- `ddata[1]`: Index (wird ignoriert)
- `ddata[2]`: Erste Daten-Byte (Hex)
- `ddata[3..7]`: Weitere 5 Bytes Daten (Hex)
- `ddata[8]`: Master-Status

**Anfrage:**
```pascal
send3byteCMD(D0_RD_MODULSPEC_DATA, 0, 0);
```

---

### 4. uniEEDownLoader (uniEEDownLoader.pas) - EEPROM Downloader

**Verwendung:** Generischer EEPROM-Downloader für alle Module

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if mode = UD_READ then
  begin
    // Copy compressed to all
    if allowFillCmd and (p.len = 3) then
    begin
      for i := 1 to zeilenLen-1 do
        p.ddata[2+i] := p.ddata[2];
    end;
    
    move(p.ddata[2], ud_ar[ar_pos], zeilenLen);
    inc(ar_pos, zeilenLen);
    readNext;
  end
  else
  if mode = UD_WRITE then
    writeNext;
end;
```

**Datenstruktur:**
- `ddata[1]`: Zeilen-Index (readPos)
- `ddata[2..]`: Zeilendaten (Länge = `zeilenLen`, typisch 32 Bytes)
- **Besonderheit:** Wenn `p.len = 3` und `allowFillCmd`, wird Byte 2 auf alle Positionen kopiert (Komprimierung)

**Anfrage:**
```pascal
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul);
```

---

### 5. ASbaseObj (ASbaseObj.pas) - Basisklasse für ModulSpec-Tabellen

**Verwendung:** Basis-Implementierung für alle Module mit ModulSpec-Tabellen

```pascal
if ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if isFFzeile then
  if ModulASx.optReadFF then
  begin
    OnCompleteRWx(R_FF_ZEILE_VALID);
    ReadInfoIndex := 0;
    reqZeile := ModulASx.ReadInfo[ReadInfoIndex].startZeile;
    ReadZeile(reqZeile);
    exit;
  end;
  
  inc(reqZeile);
  if reqZeile < ModulASx.ReadInfo[ReadInfoIndex].endZeile then
    ReadZeile(reqZeile)
  else
  begin
    inc(ReadInfoIndex);
    if ModulASx.ReadInfo[ReadInfoIndex].setUsed then
    begin
      reqZeile := ModulASx.ReadInfo[ReadInfoIndex].startZeile;
      ReadZeile(reqZeile);
    end
    else
      ReadComplete;
  end;
end;
```

**Datenstruktur:**
- `ddata[1]`: Zeilen-Index (reqZeile)
- `ddata[2..]`: Zeilendaten (32 Bytes typisch)
- **Sequenzielles Lesen:** Liest mehrere Zeilen nacheinander, bis alle Bereiche gelesen sind

---

### 6. LCD3 (LCD3u.pas) - LCD-Display Modul

**Verwendung:** Konfiguration von LCD3-Displays

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  adrInsert := p.ddata[1]*256 + p.ddata[2];
  if adrInsert = $ffff then
  begin
    move(p.ddata[3], capData, sizeof(capData));
    with capData do
    begin
      SizeCfg := swap(SizeCfg);
      SizeStrN := swap(SizeStrN);
      SizeStr := swap(SizeStr);
      SizeNODE := swap(SizeNODE);
      label28.caption := IntToStr(SizeCfg) + ' byte';
      label29.caption := IntToStr(SizeNODE div 16) + ' Menüs';
      label30.caption := IntToStr(SizeStr div 16) + ' Texte';
      label31.caption := IntToStr(SizeStrN div 16) + ' Texte';
    end;
  end;
  
  if rw = WRITE_DATA then
  begin
    readPos := getFirstDirty(true);
    if readPos <> -1 then
    begin
      if cs_write = (p.ddata[1]*256 + p.ddata[2]) then
      begin
        retryCount := 0;
        writeNext;
      end
      else
      begin
        rw := IDLE;
        ShowMessage('Error: Schreiben CS-Fehler...');
      end;
    end;
  end;
end;
```

**Datenstruktur:**
- `ddata[1..2]`: Adresse (2 Bytes, Big Endian) - `$FFFF` = Kapazitäts-Info
- `ddata[3..]`: Daten oder Kapazitäts-Struktur
- **Kapazitäts-Info (bei `$FFFF`):**
  - `SizeCfg`: Konfigurationsgröße (2 Bytes, Big Endian)
  - `SizeStrN`: String-Größe N (2 Bytes, Big Endian)
  - `SizeStr`: String-Größe (2 Bytes, Big Endian)
  - `SizeNODE`: NODE-Größe (2 Bytes, Big Endian)

**Anfrage:**
```pascal
// Kapazität lesen
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, $ff, $ff, adrModul);

// Zeile lesen
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos shr 8, readPos, adrModul);
```

---

### 7. GSM (gsmU.pas) - GSM-Modul

**Verwendung:** Konfiguration von GSM-Modulen

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if rw = READ_FREE_DATA then
  begin
    for i := 1 to p.ddatalen - 1 do
      s := s + chrX(p.ddata[i]);
    lb1.items.add(s);
  end;
  
  if rw = READ_SQ_DATA then
  begin
    s := 'SQ=';
    for i := 1 to p.ddatalen - 1 do
      s := s + chrX(p.ddata[i]);
    lb1.items.add(s);
    
    if pos('+CSQ:', s) <> 0 then
    begin
      s := copy(s, pos('+CSQ:', s) + 6, 20);  // "...+CSQ: 10,0" -> "10,0"
      delete(s, pos(',', s), 20);
      sq := StrToIntDef(s, 2);
      pb1.Position := sq;
      
      if sq in [0..31] then
        ed_info.Text := 'Signal ' + IntToStr(sq * 3) + '%'
      else
      if sq = 99 then
        ed_info.Text := 'Signal unbekannt.';
    end;
    rw := IDLE;
  end;
  
  if rw = WRITE_DATA then
  begin
    inc(readPos);
    if readPos < GSM_ZEILEN_RX_COUNT then
      writeNext
    else
    begin
      rw := IDLE;
      ShowMessage('Schreiben ok');
    end;
  end;
  
  if rw = READ_DATA then
  begin
    move(p.ddata[2], gsmAsArray[readPos].z[0], MAX_RX_PER_ZEILE);
    inc(readPos);
    if readPos < GSM_ZEILEN_RX_COUNT then
      Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul)
    else
    begin
      rw := IDLE;
      ZeileToTypisiertData;
      DataToLV;
    end;
  end;
end;
```

**Datenstruktur:**
- `ddata[1]`: Zeilen-Index (readPos)
- `ddata[2..]`: Zeilendaten oder AT-Befehl-Antwort (ASCII)
- **Modi:**
  - `READ_FREE_DATA`: Freie Daten (AT-Befehle)
  - `READ_SQ_DATA`: Signalqualität (`+CSQ:` Antwort)
  - `READ_DATA`: Konfigurationsdaten
  - `WRITE_DATA`: Schreibmodus

**Anfrage:**
```pascal
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul);
```

---

### 8. IR_TX (uIR_tx.pas) - IR-Sender

**Verwendung:** Konfiguration von IR-Sendern

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if p.ddata[1] = $ff then  // Modul Info
  begin
    gTabEntryCount := p.ddata[2];
    gTab2EntryCount := p.ddata[5];
    adrObj := p.ddata[3]*256 + p.ddata[4];
    ed_ob_lokal.text := IntToStr(adrObj);
    edName.Text := ExtractNamePart(Fhome2net.getNSCombinedP(adrObj));
    sb1.Panels[0].Text := 'Upload...';
    gTabPos := 0;
  end
  else
  if p.ddata[1] < $80 then  // Tabelle
  begin
    move(p.ddata[2], tab[p.ddata[1]], 24);
    if not getFullTab then
      tabToListBox_(p.ddata[1]);
  end
  else
  if p.ddata[1] >= $c0 then  // MaxPower
  begin
    move(p.ddata[2], tab2[p.ddata[1]-$c0], 32);
    if not getFullTab2 then
    begin
      tab2ToListBox_(p.ddata[1] - $c0);
      if updateLB2_folger then
      begin
        updateLB2_folger := true;
        lvFBtypSelectItem(nil, lvFBtyp.Selected, true);
      end;
    end;
  end;
end;
```

**Datenstruktur:**
- `ddata[1] = $FF`: Modul-Info
  - `ddata[2]`: Tabellen-Einträge (gTabEntryCount)
  - `ddata[3..4]`: Objektadresse (2 Bytes, Little Endian)
  - `ddata[5]`: Tabellen2-Einträge (gTab2EntryCount)
- `ddata[1] < $80`: Haupttabelle
  - `ddata[1]`: Tabellen-Index
  - `ddata[2..25]`: Tabellendaten (24 Bytes)
- `ddata[1] >= $C0`: MaxPower-Tabelle
  - `ddata[1] - $C0`: Tabellen-Index
  - `ddata[2..33]`: Tabellendaten (32 Bytes)

**Anfrage:**
```pascal
// Modul-Info
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, $ff, 0, adrModul);

// Tabelle
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, gTabPos, 0, adrModul);

// MaxPower
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, gTabPos + $c0, 0, adrModul);
```

---

### 9. HS_STe8 (hs_ste8U.pas) - HS Steuerung 8

**Verwendung:** Konfiguration von HS_STe8-Modulen

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if rw = WRITE_DATA then
  begin
    inc(readPos);
    if readPos < STe8ZEILEN_COUNT then
      writeNext
    else
    begin
      rw := IDLE;
      ShowMessage('Schreiben ok');
    end;
  end;
  
  if rw = READ_DATA then
  begin
    move(p.ddata[2], ST8_data[readPos].z[0], STe8ZEIL_LEN);
    inc(readPos);
    if readPos < STe8ZEILEN_COUNT then
      Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul)
    else
    begin
      rw := IDLE;
      ZeileToTypisiertData;
      DataToLV;
    end;
  end;
end;
```

**Datenstruktur:**
- `ddata[1]`: Zeilen-Index (readPos)
- `ddata[2..]`: Zeilendaten (STe8ZEIL_LEN Bytes)

**Anfrage:**
```pascal
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul);
```

---

### 10. PIR_LUX (uPirLux.pas) - PIR/Lux-Sensor

**Verwendung:** Konfiguration von PIR/Lux-Sensoren

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if p.ddata[1] = 0 then  // kanal 1,2
  begin
    ed_obj.text := IntToStr(p.ddata[2]*256 + p.ddata[3]);
    ed_t_dunkel.text := IntToStr(p.ddata[4]*256 + p.ddata[5]);
  end;
end;
```

**Datenstruktur:**
- `ddata[1] = 0`: Kanal 1,2 Konfiguration
- `ddata[2..3]`: Objektadresse (2 Bytes, Little Endian)
- `ddata[4..5]`: Dunkelschwellwert (2 Bytes, Little Endian)

**Anfrage:**
```pascal
Fhome2net.sendH2N_3byteCmdIP(D0_RD_MODULSPEC_DATA, 0, 0);
```

---

### 11. UP_IRRX (UP_IRRXu.pas) - IR-Empfänger

**Verwendung:** Konfiguration von IR-Empfängern

```pascal
if ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if ddata[1] = $fe then  // Lernen gestartet
    label3.Caption := 'Taste am Sender betätigen....'
  else
  if lernReq and (ddata[1] = aktNr) then
  begin
    lernReq := false;
    move(ddata[2], oASbase.ModulASx.z[aktNr].d[2], 32);
    ZeileToEdit(aktNr);
    fnaSetModified;
    label3.Caption := 'Erfolgreich angelernt!';
  end;
end;
```

**Datenstruktur:**
- `ddata[1] = $FE`: Lernmodus gestartet
- `ddata[1] = aktNr`: Gelernte Daten für Kanal aktNr
- `ddata[2..33]`: IR-Code-Daten (32 Bytes)

**Anfrage:**
```pascal
// Lernen starten
Fhome2net.sendH2N_3byteCmdIPa(D0_WR_MODULSPEC_DATA, $fe, aktNr, oASbase.adrModul);
```

---

### 12. HS_PaketRouter (HS_PaketRouter.pas)

**Verwendung:** Konfiguration von Paket-Routern

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  if p.ddata[1] = $fe then
  begin
    if p.ddata[2] = 1 then
      label13.Caption := 'EIN'
    else
      label13.Caption := 'AUS';
  end;
end;
```

**Datenstruktur:**
- `ddata[1] = $FE`: Status-Information
- `ddata[2]`: Status (1 = EIN, 0 = AUS)

---

### 13. Bell2 (Bell2U.pas) - Klingel-Modul

**Verwendung:** WAV-Datei-Upload für Klingel-Module

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  // Leere Auswertung - wird nur für Schreib-Bestätigung verwendet
end;
```

**Hinweis:** Bell2 verwendet `D0_RD_MODULSPEC_DATA_ACK` hauptsächlich als Bestätigung beim Schreiben von WAV-Daten.

---

### 14. Ext_LD (Ext_LDu.pas) - Externe LED

**Verwendung:** Konfiguration externer LED-Module

```pascal
if p.ddata[0] = D0_RD_MODULSPEC_DATA_ACK then
begin
  // Leere Auswertung - verwendet ASbaseObj-Basisklasse
end;
```

**Hinweis:** Ext_LD verwendet die Basis-Implementierung aus `ASbaseObj`.

---

## Spezielle Adressen/Indizes

Viele Module verwenden spezielle Werte für `ddata[1]`:

| Wert | Bedeutung | Verwendung |
|------|-----------|------------|
| `0x00` | Kanal 0 / Erste Zeile | Standard-Konfiguration |
| `0xFF` | Modul-Info | Kapazität, Tabellengrößen, Basis-Adressen |
| `0xFE` | Status / Lernmodus | Status-Abfrage, Lernmodus |
| `0xF0` | Spezielle Konfiguration | Modulspezifisch (z.B. TLH) |
| `0xF1` | Spezielle Konfiguration 2 | Modulspezifisch (z.B. TLH) |
| `0xF2` | Spezielle Konfiguration 3 | Modulspezifisch (z.B. TLH) |
| `0x80` | Tabellen-Bereich 2 | Zweite Tabelle (z.B. IR_TX) |
| `0xC0` | Tabellen-Bereich 3 | Dritte Tabelle / MaxPower (z.B. IR_TX) |

## Gemeinsame Muster

### Sequenzielles Lesen

Viele Module lesen mehrere Zeilen sequenziell:

```pascal
if rw = READ_DATA then
begin
  move(p.ddata[2], dataArray[readPos], dataLen);
  inc(readPos);
  if readPos < maxCount then
    Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos, 0, adrModul)
  else
  begin
    rw := IDLE;
    ProcessData();
  end;
end;
```

### Checksummen-Validierung

Einige Module (z.B. LCD3) validieren Checksummen:

```pascal
if cs_write = (p.ddata[1]*256 + p.ddata[2]) then
begin
  retryCount := 0;
  writeNext;
end
else
begin
  ShowMessage('Error: Schreiben CS-Fehler...');
end;
```

### 16-bit Adressierung

Module mit `rw16bitAdressing` verwenden 16-bit Indizes:

```pascal
// High-Byte, Low-Byte
Fhome2net.sendH2N_3byteCmdIPa(D0_RD_MODULSPEC_DATA, readPos shr 8, readPos, adrModul);
```

## Zusammenfassung

Die Auswertung von `D0_RD_MODULSPEC_DATA_ACK` ist stark modulspezifisch:

1. **Basis-Struktur:** `ddata[0]` = Befehl, `ddata[1]` = Index/Kanal, `ddata[2..]` = Daten
2. **Spezielle Indizes:** `$FF` = Info, `$FE` = Status, `$C0+` = Erweiterte Tabellen
3. **Sequenzielles Lesen:** Viele Module lesen mehrere Zeilen nacheinander
4. **Datenlängen:** Variieren von 1 Byte bis 32+ Bytes je nach Modul
5. **Endianness:** Meist Little Endian, manchmal Big Endian (z.B. LCD3 Kapazität)

Die genaue Interpretation hängt vom Modultyp und der Software-Version ab.
