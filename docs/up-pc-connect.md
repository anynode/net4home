# UP-PC-Connect - Serielle Schnittstelle

## Übersicht

UP-PC-Connect ermöglicht die Verbindung zum net4home Bus-System über eine serielle Schnittstelle (RS-232/RS-485). Das Modul fungiert als Gateway zwischen dem PC und dem Bus-System und ermöglicht das Lesen und Senden von Paketen über die serielle Schnittstelle.

## Hardware-Anforderungen

- **Serielle Schnittstelle**: RS-232 oder RS-485 (je nach Modul)
- **Port**: 
  - **Windows**: COM1 bis COM7
  - **Linux**: `/dev/ttyUSB*`, `/dev/ttyACM*` oder `/dev/ttyS*`
- **Kabel**: Serielles Kabel (je nach Modul RS-232 oder RS-485)

## Serielle Schnittstellen-Parameter

### Standard-Parameter

Die serielle Schnittstelle muss mit folgenden Parametern konfiguriert werden:

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| **Baudrate** | **19200** | Übertragungsgeschwindigkeit (Bits pro Sekunde) |
| **Datenbits** | **8** | Anzahl der Datenbits pro Byte |
| **Parität** | **None (N)** | Keine Paritätsprüfung |
| **Stop-Bits** | **1** | Anzahl der Stop-Bits |
| **Flow Control** | **None** | Keine Flusskontrolle |

**Kurzform:** `19200, 8, N, 1` oder `8N1` bei 19200 Baud

### Alternative Baudraten

Je nach Modul-Version und Konfiguration können auch folgende Baudraten verwendet werden:

- **9600 Baud**: Für langsamere Verbindungen oder ältere Module
- **38400 Baud**: Für schnellere Verbindungen (falls unterstützt)
- **57600 Baud**: Für sehr schnelle Verbindungen (falls unterstützt)
- **115200 Baud**: Für maximale Geschwindigkeit (falls unterstützt)

**Hinweis:** Die Standard-Baudrate ist **19200 Baud**. Bei Problemen sollte diese zuerst verwendet werden.

## Verbindungsaufbau

### 1. COM-Port auswählen

Im Konfigurator kann zwischen folgenden COM-Ports gewählt werden:

- **COM1** bis **COM7**: Lokale serielle Schnittstellen
- **USB**: USB-zu-Seriell-Adapter (wird als COM-Port erkannt)

**Code-Referenz:**
```pascal
// ConnectU.dfm, Zeile 75-83
Items.Strings = (
  'lokalen COM&1'
  'lokalen COM&2'
  'lokalen COM3'
  'lokalen COM4'
  'lokalen COM5'
  'lokalen COM6'
  'lokalen COM7'
  '&Netzwerk'
  'USB')
```

### 2. Verbindung herstellen

Die Verbindung wird über die DLL-Funktion `N4HL3_open3b` hergestellt:

```pascal
res := N4HL3_open3b(
  comport,                    // COM-Port (1-7) oder N4H_CONNECT_OVER_IP
  ipAdresse,                  // Nicht verwendet bei serieller Verbindung
  ip_Port,                    // Nicht verwendet bei serieller Verbindung
  cb_n4h_paket1,              // Callback für empfangene Pakete
  cb_n4h_info1,               // Callback für Info-Nachrichten
  cb_on_client_connecting,    // Callback für Verbindungsaufbau
  0,                          // Name-Request-Callback
  0,                          // Reserviert
  N4H_APP_TYPE_ALL_DATA or N4H_APP_TYPE_CALLER_SENDMESSAGE,
  passwortClient,            // Passwort-Hash (Client-Hash als Hex-String)
  self.Handle                 // Window-Handle
);
```

**Code-Referenz:**
```3126:3141:Unit1.pas
if rg_typ.ItemIndex in [0,1,2,3,4,5,6] then
begin
  comport := rg_typ.ItemIndex+1;
  if cbServer.Checked then  comport := comport + N4H_THIS_IS_A_IP_SERVER;
end
else
if  rg_typ.itemIndex = 7 then
begin
  comport := N4H_CONNECT_OVER_IP;
end
else
if  rg_typ.itemIndex = 8 then
begin
  comport := N4H_USE_LOCAL_UP_USB;
  if cbServer.Checked then  comport := comport + N4H_THIS_IS_A_IP_SERVER;
end;
```

### 3. Verbindungsstatus prüfen

Nach dem Verbindungsaufbau wird der Status geprüft:

```pascal
if (comport and 15) <> 0 then
begin
  sPort := ' COM' + IntToStr(comport and 15);
  if res <> 0 then
  begin
    d('ERROR COM res=' + IntToStr(res));
    sPort := sPort + ' ERROR';
  end
  else
  begin
    ConnectInfo.connected := 1;
    sPort := sPort + ' OK';
    result := true;
  end;
  sb1.Panels[0].text := sPort;
end;
```

**Code-Referenz:**
```3207:3222:Unit1.pas
if (comport and 15) <>0 then
begin
  sPort := ' COM'+IntToStr(comport and 15);
  if res<>0 then
  begin
    d('ERROR COM res='+IntToStr(res));
    sPort := sPort+' ERROR';
  end
  else
  begin
    ConnectInfo.connected := 1;
    sPort := sPort+' OK';
    result := true;
  end;
  sb1.Panels[0].text := sPort;
end;
```

## Paket-Übertragung

### Paket-Struktur

Die Pakete werden über die serielle Schnittstelle im gleichen Format wie über IP übertragen:

1. **4 Bytes**: Länge des komprimierten Payloads (Little Endian)
2. **N Bytes**: Komprimiertes Payload

**Siehe auch:** [Bus-Header Struktur](header.md)

### Paket empfangen

Empfangene Pakete werden über den Callback `cb_n4h_paket1` verarbeitet:

```pascal
procedure cb_n4h_paket1(p: TN4Hpaket);
begin
  // Paket verarbeiten
  // p.ipsrc: MI-Adresse des Senders
  // p.ipdest: MI-Adresse des Empfängers
  // p.objsrc: OBJ-Adresse des Senders
  // p.ddata: Paketdaten
  // p.ddataLen: Länge der Daten
  // p.len: Gesamtlänge
end;
```

### Paket senden

Pakete werden über `N4HL3_sendAll` gesendet:

```pascal
function N4HL3_sendAll(p: TN4Hpaket): integer;
// Sendet ein Paket über die serielle Schnittstelle
// Rückgabe: 0 = Erfolg, <0 = Fehler
```

## Konfiguration

### Windows: COM-Port-Einstellungen

Die seriellen Parameter können in Windows über die Geräte-Manager-Einstellungen konfiguriert werden:

1. **Geräte-Manager öffnen**
2. **Ports (COM & LPT)** erweitern
3. **COM-Port auswählen** (z.B. COM1)
4. **Eigenschaften** → **Erweitert**
5. **Parameter setzen:**
   - Bits pro Sekunde: **19200**
   - Datenbits: **8**
   - Parität: **Keine**
   - Stopbits: **1**
   - Flusssteuerung: **Keine**

### Linux: Serielle Port-Konfiguration

Unter Linux werden die seriellen Parameter programmgesteuert gesetzt. Die Ports sind typischerweise:

- `/dev/ttyUSB0`, `/dev/ttyUSB1`, ... - USB-zu-Seriell-Adapter
- `/dev/ttyACM0`, `/dev/ttyACM1`, ... - USB CDC ACM Geräte
- `/dev/ttyS0`, `/dev/ttyS1`, ... - Serielle Ports (onboard)

**Berechtigungen:** Der Benutzer muss Mitglied der `dialout`-Gruppe sein, um auf serielle Ports zugreifen zu können:

```bash
# Benutzer zur dialout-Gruppe hinzufügen
sudo usermod -a -G dialout $USER

# Nach der Änderung neu einloggen oder:
newgrp dialout
```

### Programmgesteuerte Konfiguration

Bei Verwendung einer seriellen Bibliothek (z.B. in Python mit `pyserial`):

```python
import serial

# Serielle Schnittstelle öffnen
ser = serial.Serial(
    port='COM1',           # COM-Port
    baudrate=19200,        # Baudrate
    bytesize=8,            # Datenbits
    parity=serial.PARITY_NONE,  # Parität
    stopbits=1,            # Stop-Bits
    timeout=1,             # Timeout (Sekunden)
    xonxoff=False,         # Software Flow Control
    rtscts=False,          # Hardware Flow Control
    dsrdtr=False           # DSR/DTR Flow Control
)

# Daten lesen
data = ser.read(1024)  # Maximal 1024 Bytes lesen

# Daten schreiben
ser.write(data)

# Verbindung schließen
ser.close()
```

## Beispiel-Implementierung

### Serielle Ports unter Linux ermitteln

Unter Linux werden serielle Ports typischerweise als `/dev/ttyUSB*`, `/dev/ttyACM*` oder `/dev/ttyS*` bezeichnet. Hier sind verschiedene Methoden, um verfügbare Ports zu finden:

```python
import serial
import serial.tools.list_ports
import glob
import os

def list_serial_ports():
    """Listet alle verfügbaren seriellen Ports auf."""
    ports = []
    
    # Methode 1: Mit pyserial (plattformübergreifend)
    ports_pyserial = serial.tools.list_ports.comports()
    for port in ports_pyserial:
        ports.append({
            'device': port.device,
            'description': port.description,
            'hwid': port.hwid
        })
        print(f"Port: {port.device} - {port.description}")
    
    # Methode 2: Linux-spezifisch - /dev/tty* durchsuchen
    if os.name == 'posix':  # Linux/Unix
        tty_patterns = [
            '/dev/ttyUSB*',  # USB-zu-Seriell-Adapter
            '/dev/ttyACM*',  # USB CDC ACM Geräte
            '/dev/ttyS*',    # Serielle Ports
        ]
        
        for pattern in tty_patterns:
            for port in glob.glob(pattern):
                if os.path.exists(port):
                    ports.append({'device': port, 'description': 'Linux serial port'})
                    print(f"Port: {port}")
    
    return ports

# Verfügbare Ports auflisten
available_ports = list_serial_ports()
```

**Alternative: Kommandozeile unter Linux**

```bash
# Alle USB-Seriell-Adapter auflisten
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Oder mit dmesg die letzten USB-Geräte anzeigen
dmesg | grep -i tty

# Oder mit udevadm Informationen anzeigen
udevadm info --name=/dev/ttyUSB0
```

### Python-Beispiel

```python
import serial
import serial.tools.list_ports
import struct
import sys
import os

def find_serial_port():
    """Findet automatisch einen verfügbaren seriellen Port."""
    # Unter Windows: COM1-COM7
    if sys.platform.startswith('win'):
        for i in range(1, 8):
            port = f'COM{i}'
            try:
                ser = serial.Serial(port)
                ser.close()
                return port
            except (OSError, serial.SerialException):
                continue
    
    # Unter Linux: /dev/ttyUSB*, /dev/ttyACM*, /dev/ttyS*
    elif sys.platform.startswith('linux'):
        # Versuche USB-zu-Seriell-Adapter zuerst
        for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']:
            import glob
            for port in sorted(glob.glob(pattern)):
                try:
                    ser = serial.Serial(port)
                    ser.close()
                    return port
                except (OSError, serial.SerialException):
                    continue
    
    return None

# Serielle Schnittstelle konfigurieren
port = find_serial_port()
if not port:
    print("Kein serieller Port gefunden!")
    sys.exit(1)

print(f"Verwende Port: {port}")

ser = serial.Serial(
    port=port,
    baudrate=19200,
    bytesize=8,
    parity=serial.PARITY_NONE,
    stopbits=1,
    timeout=1
)

def read_packet():
    """Liest ein Paket von der seriellen Schnittstelle."""
    # 1. Lese Länge des komprimierten Payloads (4 Bytes)
    length_bytes = ser.read(4)
    if len(length_bytes) < 4:
        return None
    
    payload_len = struct.unpack('<I', length_bytes)[0]
    
    # 2. Lese komprimiertes Payload
    compressed_payload = ser.read(payload_len)
    if len(compressed_payload) < payload_len:
        return None
    
    # 3. Dekomprimiere (siehe header.md für Details)
    # decompressed = decomp_section_c_exact(compressed_payload, ...)
    
    return compressed_payload

def send_packet(packet_data):
    """Sendet ein Paket über die serielle Schnittstelle."""
    # 1. Komprimiere Paket (siehe header.md für Details)
    # compressed = compress_section(packet_data)
    
    # 2. Sende Länge (4 Bytes, Little Endian)
    length = len(compressed)
    ser.write(struct.pack('<I', length))
    
    # 3. Sende komprimiertes Payload
    ser.write(compressed)

# Hauptschleife
try:
    while True:
        packet = read_packet()
        if packet:
            # Paket verarbeiten
            process_packet(packet)
except KeyboardInterrupt:
    pass
finally:
    ser.close()
```

## Fehlerbehandlung

### Häufige Fehler

1. **"ERROR COM res=X"**
   - **Ursache**: COM-Port konnte nicht geöffnet werden
   - **Lösung**: 
     - Prüfen, ob COM-Port existiert
     - Prüfen, ob COM-Port bereits von anderem Programm verwendet wird
     - Gerätetreiber prüfen

2. **Keine Daten empfangen**
   - **Ursache**: Falsche Baudrate oder Parameter
   - **Lösung**: 
     - Baudrate auf 19200 setzen
     - Parameter auf 8N1 prüfen
     - Kabelverbindung prüfen

3. **Fehlerhafte Daten**
   - **Ursache**: Falsche Parameter oder Störungen
   - **Lösung**: 
     - Parameter nochmals prüfen
     - Kabelqualität prüfen
     - Längere Kabel vermeiden (max. 15m bei RS-232)

### Debugging

Aktivieren Sie Debug-Ausgaben, um die Kommunikation zu überwachen:

```pascal
d('COM res=' + IntToStr(res));  // Verbindungsstatus
d('Read: ' + IntToHex(data));   // Empfangene Daten
d('Send: ' + IntToHex(data));   // Gesendete Daten
```

## Wichtige Hinweise

### Passwort-Authentifizierung

Auch bei serieller Verbindung kann eine Passwort-Authentifizierung erforderlich sein. Das Passwort wird als MD5-Hash übertragen.

**Siehe auch:** [Bus-Anmeldung (Passwort-Authentifizierung)](connect.md)

### Paket-Kompression

Alle Pakete werden komprimiert übertragen. Die Kompression erfolgt automatisch durch die DLL.

**Siehe auch:** [Bus-Header Struktur](header.md)

### Timeouts

- **Lese-Timeout**: 1 Sekunde (empfohlen)
- **Schreib-Timeout**: 1 Sekunde (empfohlen)
- **Paket-Timeout**: Abhängig von der Anwendung

### Maximale Paketgröße

- **Komprimiert**: Abhängig von der Kompression (typisch 64-512 Bytes)
- **Unkomprimiert**: Maximal 64 Bytes Nutzdaten (`MAX_N4H_PAKET_LEN`)

## Zusammenfassung

### Serielle Parameter

| Parameter | Wert |
|-----------|------|
| **Baudrate** | 19200 (Standard) |
| **Datenbits** | 8 |
| **Parität** | None (N) |
| **Stop-Bits** | 1 |
| **Flow Control** | None |

### Verbindungsaufbau

1. Seriellen Port auswählen:
   - **Windows**: COM1-COM7
   - **Linux**: `/dev/ttyUSB*`, `/dev/ttyACM*` oder `/dev/ttyS*`
2. Serielle Parameter konfigurieren (19200, 8N1)
3. Verbindung über `N4HL3_open3b` herstellen
4. Verbindungsstatus prüfen
5. Pakete empfangen/senden

### Code-Referenzen

- **COM-Port-Auswahl**: `ConnectU.dfm`, Zeile 67-86
- **Verbindungsaufbau**: `Unit1.pas`, Zeile 3172-3185
- **Status-Prüfung**: `Unit1.pas`, Zeile 3207-3222

## Weitere Informationen

- [Bus-Header Struktur](header.md) - Paket-Format und Kompression
- [Bus-Anmeldung](connect.md) - Passwort-Authentifizierung
- [Bus-Kommunikation](buscomm.md) - Protokoll-Details
