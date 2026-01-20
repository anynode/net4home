# Bus-Anmeldung (Passwort-Authentifizierung)

## Übersicht

Bei der Verbindung zum net4home Bus muss ein Passwort zur Authentifizierung gesendet werden. Das Passwort wird als MD5-Hash übertragen, um die Sicherheit zu gewährleisten. Die Anmeldung erfolgt über ein spezielles Paket mit einer besonderen Pakettyp-Kennung.

## Pakettyp-Kennung

Es gibt zwei Pakettypen für die Passwort-Authentifizierung:

| Konstante | Wert | Beschreibung |
|-----------|------|--------------|
| `N4HIP_PT_PASSWORT_REQ_ALT` | 4002 | Altes Format (bis V1.27) |
| `N4HIP_PT_PASSWORT_REQ` | 4012 | Neues Format (ab V1.27, mit MD5) |

**Hinweis:** Ab Version 1.27 wurde das Format geändert, um MD5 Passwort-Sicherheit zu gewährleisten. Das neue Format (`4012`) sollte verwendet werden.

## Paketstruktur

### TN4H_IP_SEC Record

Das Passwort-Paket verwendet die Struktur `TN4H_IP_SEC`:

```pascal
TN4H_IP_SEC = record
  ptype: integer;              // Pakettyp: 4012 (N4HIP_PT_PASSWORT_REQ)
  N4H_security: TN4H_security; // Sicherheitsdaten
end;
```

### TN4H_security Record

```pascal
TN4H_security = record
  Algotyp: integer;        // Algorithmus-Typ
  Result: integer;         // Ergebnis (wird vom Server gesetzt)
  Len: integer;            // Länge
  password: string[56];    // Passwort-Hash als Hex-String (32 Zeichen = 16 Bytes MD5)
  ApplicationTyp: integer; // Anwendungstyp
  dll_ver: integer;        // DLL-Version
end;
```

**Wichtig:** Das `password`-Feld enthält den MD5-Hash des Passworts als Hex-String (32 Zeichen für 16 Bytes MD5-Hash).

## Passwort-Hashing

### Client-Seite

Der Client muss das Passwort in einen MD5-Hash umwandeln:

**Funktion:** `GetStrHash(password: string, var asStr: string): TarHashMD5`

**Prozess:**
1. Das Passwort wird mit einem Padding-String auf 32 Zeichen aufgefüllt
2. Ein MD5-Hash wird berechnet (16 Bytes)
3. Der Hash wird als Hex-String (32 Zeichen) zurückgegeben

**Beispiel:**
```pascal
var
  password: string;
  hashStr: string;
  hash: TarHashMD5;
begin
  password := 'meinPasswort';
  hash := GetStrHash(password, hashStr);
  // hashStr enthält jetzt den 32-stelligen Hex-String
end;
```

### Server-Seite

Der Server erwartet einen Server-Hash, der aus dem Client-Hash berechnet wird:

**Funktion:** `GetHashForServer2(password: string): string`

**Prozess:**
1. Client-Hash wird aus dem Passwort berechnet: `clientHash = GetStrHash(password)`
2. Server-Hash wird berechnet: `serverHash = clientHash + c1`
3. Der Server-Hash wird als Hex-String zurückgegeben

**Konstante c1:**
```pascal
c1: TarHashMD5 = ($61,$12,$81,$39,
                   $51,$3a,$4b,$8c,
                   $1d,$52,$9f,$11,
                   $b1,$a7,$53,$3d);
```

### Verifikation auf dem Server

**Funktion:** `VerifyHashs(sClientHash, sServerHash: string): boolean`

**Prozess:**
1. Client-Hash wird aus dem empfangenen Paket extrahiert
2. Erwarteter Server-Hash wird berechnet: `expectedServerHash = clientHash + c1`
3. Vergleich: `expectedServerHash == sServerHash`

**Rückgabewerte:**
- `N4H_IP_CLIENT_ACCEPTED` (0): Passwort korrekt, Verbindung akzeptiert
- `N4H_IP_CLIENT_DENIED` (-700): Passwort falsch, Verbindung abgelehnt
- `N4H_IP_CLIENT_DENIED_WRONG_PASSWORD` (-703): Falsches Passwort

## Paket-Aufbau

### Unkomprimiertes Paket (vor Kompression)

Das Passwort-Paket folgt der gleichen Struktur wie normale Pakete:

```
[8 Bytes Header] [TN4H_IP_SEC Daten]
```

**Header (8 Bytes):**
- Bytes 0-1: `ptype` = `4012` (Little Endian: `0C 0F`)
- Bytes 2-3: `reserved1` = `0x0000`
- Bytes 4-7: `reserved2` = Länge des unkomprimierten Payloads (Little Endian)

**TN4H_IP_SEC Daten:**
- 4 Bytes: `ptype` = `4012` (integer, Little Endian)
- 4 Bytes: `Algotyp` (integer, Little Endian)
- 4 Bytes: `Result` (integer, Little Endian)
- 4 Bytes: `Len` (integer, Little Endian)
- 56 Bytes: `password` (string[56], null-terminiert)
- 4 Bytes: `ApplicationTyp` (integer, Little Endian)
- 4 Bytes: `dll_ver` (integer, Little Endian)

**Gesamtgröße:** 8 (Header) + 80 (TN4H_IP_SEC) = 88 Bytes (unkomprimiert)

### Komprimiertes Paket (übertragen)

Das Paket wird komprimiert übertragen:

```
[4 Bytes: Länge des komprimierten Payloads] [N Bytes: Komprimiertes Payload]
```

## Verbindungsablauf

### 1. Client verbindet sich

Der Client öffnet eine Verbindung über:
- `N4HL3_open3b` (altes Format)
- `N4HL3_open6` (neues Format, ab V6)

**Parameter:**
```pascal
N4HL3_open6(
  @hBusConnection,           // Verbindungs-Handle (aus)
  ipAdresse,                 // IP-Adresse des Servers
  ip_Port,                   // Port (typischerweise 4001)
  cb_n4h_paket2,             // Callback für empfangene Pakete
  cb_n4h_info2,              // Callback für Info-Nachrichten
  0,                         // Name-Request-Callback
  N4H_APP_TYPE_ALL_DATA or N4H_APP_TYPE_CALLER_SENDMESSAGE,
  passwortClient,           // Passwort-Hash (Client-Hash als Hex-String)
  0,                         // Reserviert
  self.Handle                // Window-Handle
);
```

### 2. Passwort-Paket senden

Das Passwort-Paket wird automatisch vom Client gesendet, wenn die Verbindung hergestellt wird. Der Client sendet:

```
ptype = 4012 (N4HIP_PT_PASSWORT_REQ)
password = Client-Hash als Hex-String (32 Zeichen)
```

### 3. Server verifiziert Passwort

Der Server empfängt das Passwort-Paket und ruft den Callback `cb_on_client_connecting` auf:

```pascal
function cb_on_client_connecting(pw: shortString): integer;
begin
  // pw enthält den Client-Hash als Hex-String
  result := N4H_IP_CLIENT_DENIED;
  
  if VerifyHashs(pw, Fhome2net.connectInfo.passwortServer) then
  begin
    result := N4H_IP_CLIENT_ACCEPTED;
    // Verbindung akzeptiert
  end
  else
  begin
    // Verbindung abgelehnt
  end;
end;
```

### 4. Antwort vom Server

Der Server setzt das `Result`-Feld in `TN4H_security`:
- `0` oder `N4H_IP_CLIENT_ACCEPTED`: Verbindung akzeptiert
- `N4H_IP_CLIENT_DENIED` oder `N4H_IP_CLIENT_DENIED_WRONG_PASSWORD`: Verbindung abgelehnt

## Beispiel-Implementierung

### Python-Beispiel

```python
import hashlib
import struct

# Konstante c1 (für Server-Hash)
C1 = bytes([
    0x61, 0x12, 0x81, 0x39,
    0x51, 0x3a, 0x4b, 0x8c,
    0x1d, 0x52, 0x9f, 0x11,
    0xb1, 0xa7, 0x53, 0x3d
])

def get_str_hash(password: str) -> bytes:
    """Berechnet den Client-Hash aus dem Passwort."""
    # Padding-String (wie in md5User.pas)
    s_pad = 'f239uhrnvioj3944z5olqw0e9u4tlekrg09345092hjo340gt3094z203r92eif09u23f9828'
    
    # Passwort mit Länge voranstellen
    s = chr(len(password)) + password
    
    # Auf 32 Zeichen auffüllen
    i = 0
    while len(s) < 32:
        s += s_pad[i % len(s_pad)]
        i += 1
    
    # MD5-Hash berechnen (WICHTIG: net4home verwendet eine modifizierte MD5!)
    # Für eine vollständige Implementierung müsste die modifizierte MD5 aus md5.pas
    # nachimplementiert werden (siehe NON_DEFAULT_MD5 Kommentar)
    md5_hash = hashlib.md5(s.encode('latin1')).digest()
    
    return md5_hash

def get_hash_for_server(password: str) -> str:
    """Berechnet den Server-Hash aus dem Passwort."""
    client_hash = get_str_hash(password)
    
    # Server-Hash = Client-Hash + c1
    server_hash = bytes([(a + b) & 0xFF for a, b in zip(client_hash, C1)])
    
    # Als Hex-String zurückgeben
    return server_hash.hex().upper()

def build_password_packet(password: str) -> bytes:
    """Erstellt ein Passwort-Paket für die Bus-Anmeldung."""
    # Client-Hash berechnen
    client_hash = get_str_hash(password)
    hash_str = client_hash.hex().upper()
    
    # TN4H_IP_SEC Struktur aufbauen
    ptype = 4012  # N4HIP_PT_PASSWORT_REQ
    algotyp = 0
    result = 0
    length = 0
    application_typ = 0
    dll_ver = 0
    
    # password als string[56] (null-terminiert, mit Nullen aufgefüllt)
    password_bytes = hash_str.encode('ascii')[:55]  # Max 55 Zeichen + null
    password_padded = password_bytes + b'\x00' * (56 - len(password_bytes))
    
    # Paket zusammenbauen
    packet = struct.pack('<i', ptype)           # 4 Bytes: ptype
    packet += struct.pack('<i', algotyp)        # 4 Bytes: Algotyp
    packet += struct.pack('<i', result)         # 4 Bytes: Result
    packet += struct.pack('<i', length)         # 4 Bytes: Len
    packet += password_padded                    # 56 Bytes: password
    packet += struct.pack('<i', application_typ) # 4 Bytes: ApplicationTyp
    packet += struct.pack('<i', dll_ver)        # 4 Bytes: dll_ver
    
    # Header hinzufügen
    header = struct.pack('<H', ptype)            # 2 Bytes: ptype (Little Endian)
    header += struct.pack('<H', 0)               # 2 Bytes: reserved1
    header += struct.pack('<I', len(packet))     # 4 Bytes: Payload-Länge
    
    return header + packet
```

### Delphi-Beispiel

```pascal
procedure SendPasswordPacket(password: string);
var
  ip_sec: TN4H_IP_SEC;
  clientHash: TarHashMD5;
  hashStr: string;
begin
  // Client-Hash berechnen
  clientHash := GetStrHash(password, hashStr);
  
  // TN4H_IP_SEC initialisieren
  FillChar(ip_sec, sizeof(ip_sec), 0);
  ip_sec.ptype := N4HIP_PT_PASSWORT_REQ;
  ip_sec.N4H_security.Algotyp := 0;
  ip_sec.N4H_security.Result := 0;
  ip_sec.N4H_security.Len := 0;
  ip_sec.N4H_security.password := hashStr;  // 32-stelliger Hex-String
  ip_sec.N4H_security.ApplicationTyp := 0;
  ip_sec.N4H_security.dll_ver := 0;
  
  // Paket senden (wird automatisch komprimiert)
  // ... über N4HL3_open6 oder ähnliche Funktion
end;
```

## Wichtige Hinweise

### MD5-Modifikation

**WICHTIG:** net4home verwendet eine modifizierte MD5-Implementierung! In `md5.pas` gibt es Kommentare zu `NON_DEFAULT_MD5`, die auf Abweichungen vom Standard-MD5-Algorithmus hinweisen. Für eine korrekte Implementierung muss die MD5-Funktion aus `md5.pas` nachimplementiert werden.

### Passwort-Speicherung

- **Client:** Speichert den Client-Hash (`GetStrHash`)
- **Server:** Speichert den Server-Hash (`GetHashForServer2`)
- **Verifikation:** Server prüft, ob `Client-Hash + c1 == Server-Hash`

### Verschlüsselung in der Registry

Wenn das Passwort in der Registry gespeichert wird, wird es zusätzlich verschlüsselt:

```pascal
// Verschlüsseln
encodedHash := encodeHashToReg(originalHash);
// encodedHash = originalHash + cReg

// Entschlüsseln
decodedHash := decodeHashFromReg(encodedHash);
// decodedHash = encodedHash - cReg
```

**Konstante cReg:**
```pascal
cReg: TarHashMD5 = ($31,$12,$e1,$39,
                     $41,$3a,$fb,$ac,
                     $5d,$52,$1f,$31,
                     $71,$a7,$93,$dd);
```

## Fehlerbehandlung

### Falsches Passwort

Wenn das Passwort falsch ist, sendet der Server:
- `Result = N4H_IP_CLIENT_DENIED` (-700) oder
- `Result = N4H_IP_CLIENT_DENIED_WRONG_PASSWORD` (-703)

Die Verbindung wird getrennt.

### Verbindungsfehler

Mögliche Fehlercodes:
- `N4H_IP_CLIENT_DENIED`: Verbindung abgelehnt (allgemein)
- `N4H_IP_CLIENT_DENIED_WRONG_PASSWORD`: Falsches Passwort
- Andere Fehlercodes je nach Implementierung

## Zusammenfassung

1. **Pakettyp:** `N4HIP_PT_PASSWORT_REQ` = 4012
2. **Struktur:** `TN4H_IP_SEC` mit `TN4H_security`
3. **Passwort-Format:** MD5-Hash als Hex-String (32 Zeichen)
4. **Client-Hash:** `GetStrHash(password)` → MD5-Hash
5. **Server-Hash:** `Client-Hash + c1`
6. **Verifikation:** `VerifyHashs(clientHash, serverHash)`
7. **Ergebnis:** `N4H_IP_CLIENT_ACCEPTED` (0) oder `N4H_IP_CLIENT_DENIED` (-700)

## Wichtige Konstanten

```pascal
N4HIP_PT_PASSWORT_REQ_ALT = 4002  // Alt (bis V1.27)
N4HIP_PT_PASSWORT_REQ = 4012     // Neu (ab V1.27, mit MD5)
N4H_IP_CLIENT_ACCEPTED = 0
N4H_IP_CLIENT_DENIED = -700
N4H_IP_CLIENT_DENIED_WRONG_PASSWORD = -703
```

## Implementierungshinweise

1. **MD5-Modifikation beachten:** Die MD5-Implementierung in `md5.pas` weicht vom Standard ab
2. **Padding-String:** Der exakte Padding-String aus `md5User.pas` muss verwendet werden
3. **Hex-Format:** Der Hash muss als Großbuchstaben-Hex-String (32 Zeichen) übertragen werden
4. **String-Länge:** Das `password`-Feld ist `string[56]`, aber der Hash ist nur 32 Zeichen lang
5. **Null-Terminierung:** Der String sollte null-terminiert sein
6. **Little Endian:** Alle Integer-Werte müssen in Little Endian übertragen werden
7. **Kompression:** Das Paket wird wie normale Pakete komprimiert übertragen
