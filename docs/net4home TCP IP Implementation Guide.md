# net4home TCP/IP Implementation Guide

## Introduction

### Objectives

The objective of this document is to present the net4home service over
TCP/IP , in order to provide reference information that helps software developers to
implement this service. 

This document gives accurate and comprehensive description of a net4home 
service implementation. Its purpose is to facilitate the interoperability between the
devices using the net4home service.

### Client / Server Model

The net4home service provides a Client/Server communication between
devices connected on an Ethernet TCP/IP network.

**Following this procedure:**

1. Client connects to Bus connector and sends the password
2. Server accepts connection if allowed in the configuration of the server 
3. Now the clients receives and can send n4h packets

The file “uh2nApi.pas” contains many of the used constants and functions within the net4home eco system.

All IP data runs through a RLL Compressor. Before sending, use the compress function and before analyzing a received packet, the data must be decompressed.

### 

## Definitions

```pascal
const
	 // Definition of the packet type (ptye)
   // There are only three different types of a packet the client can send.
   N4HIP_PT_PAKET            = 4001; // n4hPacket
   N4HIP_PT_PASSWORT_REQ     = 4012; // Password
   N4HIP_PT_OOB_DATA_RAW     = 4010; // OOB
   
   TN4h_ANY_TYP_MMS = 11220011;
	 SYM_DATA_STR_LEN = 255;
	 MAX_N4H_PAKET_LEN = 64;
   Tddata = array[0..MAX_N4H_PAKET_LEN-1] of byte;

   // record of a packet
   TN4Hpaket = record
             type8 : byte;                    
             ipsrc,ipdest,objsrc : word;     
             ddatalen : byte;               
             ddata : Tddata;               
             csRX,
             csCalc,
             len,
             posb : byte;
           end;

  TN4H_security = record 
             Algotyp,
             Result,
             Len : integer;
             password: string[56];
             ApplicationTyp : integer;
             dll_ver : integer;
           end;

 TUDP_CS = ( TUDP_IS_CLIENT, TUDP_IS_SERVER );

  TSymData = record
    len:dword;
    dataType:dword;
    symVersion:dword;
    id1,id2:dword;
    n4h_paket : TN4Hpaket;
    infoStr : String[SYM_DATA_STR_LEN];
  end;

  TANY_HEADER = record
    ptype, payloadlen : integer;
  end;

  TANY_USER_BIN = record
            anyData:array[0..MAX_IP_DATA_LEN-1] of byte;
           end;

  TANY_USER_MMS = record
            anyType, udpRaumNr : dword;
            SymData : TSymData;
           end;

  TN4H_IP_UNI = packed record
            case integer of
              0: (bin :  TANY_USER_BIN);
              1: (mms : TANY_USER_MMS);
            end;

  TN4H_IP_ANY = packed record
            h : TANY_HEADER;
            u : TN4H_IP_UNI;      // -> payloadlen = size(u) variabel
            end;

  pTN4H_IP_ANY = ^TN4H_IP_ANY;
```

### Server side implementation

This implementation only shows how the communication works and how a received packet is processed. 

```pascal
// Sever (net4home Busconnector) implementation of receiving data from the client

procedure Tkips.OnN4hAny( pany : pTN4H_IP_ANY ; Socket: TCustomWinSocket);
var
    ClientApplicationTyp : integer;
    n4h_paket  : TN4Hpaket;
    n4hsec:TN4H_security;
    n4h_ip_anyOut: TN4H_IP_ANY;
begin
      if pany^.h.ptype = N4HIP_PT_PASSWORT_REQ  then
      begin
        move(pany^.u.bin.anyData , n4hsec, sizeof(n4hsec));
        // hier die DLL-Version des gerade connectenden clients auswerten
        if n4hsec.dll_ver <> DLL_REQ_VER then
        begin
          n4hsec.Result  := N4H_IP_CLIENT_DENIED_WRONG_SW_VERSION;     // Software des Clients passt nicht
          n4hsec.dll_ver := DLL_REQ_VER;
          move(n4hsec, n4h_ip_anyOut.u.bin.anyData, sizeof(n4hsec));
          n4h_ip_anyOut.h.ptype := N4HIP_PT_PASSWORT_REQ;
          SendToSocket(Socket, @n4h_ip_anyOut, sizeof(n4hsec) + sizeof(TANY_HEADER));
			    Socket.Data := ptr(N4H_APP_TYPE_CLOSED);  //     nix Routen
        end
      else
        if (assigned(OnPassword)) and (OnPassword(n4hsec.password ) = N4H_IP_CLIENT_ACCEPTED) then // würde hier z.B. der Busconnector weiter prüfen, dort ist auch der MD5-Kram
        begin
          ClientApplicationTyp := n4hsec.ApplicationTyp and N4H_APP_TYPE_MASK; // noch nicht inUse ! -> local verworfen
          n4hsec.Result:= N4H_IP_CLIENT_ACCEPTED;
          n4hsec.dll_ver := DLL_REQ_VER;
          move(n4hsec, n4h_ip_anyOut.u.bin.anyData, sizeof(n4hsec));
          n4h_ip_anyOut.h.ptype := N4HIP_PT_PASSWORT_REQ;
          SendToSocket(Socket, @n4h_ip_anyOut, sizeof(n4hsec) + sizeof(TANY_HEADER));
          Socket.Data := ptr(N4H_APP_TYPE_OPEN or ClientApplicationTyp);  //     ab jetzt erst Daten Routen
        end
      else
        begin
          n4hsec.Result := N4H_IP_CLIENT_DENIED_WRONG_PASSWORD;
          n4hsec.dll_ver := DLL_REQ_VER;
          move(n4hsec, n4h_ip_anyOut.u.bin.anyData, sizeof(n4hsec));
          n4h_ip_anyOut.h.ptype := N4HIP_PT_PASSWORT_REQ;
          SendToSocket(Socket, @n4h_ip_anyOut, sizeof(n4hsec) + sizeof(TANY_HEADER));
          Socket.Data := ptr(N4H_APP_TYPE_CLOSED);  // nix Routen
       end;
      end // end of password packet
     else
      if pany^.h.ptype = N4HIP_PT_PAKET  then
      begin
        if (integer(Socket.Data) and N4H_APP_TYPE_OC_MASK ) = N4H_APP_TYPE_OPEN then
        begin
          move(pany^.u.bin.anyData , n4h_paket, sizeof(n4h_paket));
          sendPaketToBus(n4h_paket);
        end;
      end // end of packet packet
     else
      if pany^.h.ptype = N4HIP_PT_OOB_DATA_RAW  then
      begin
        if (integer(Socket.Data) and N4H_APP_TYPE_OC_MASK ) = N4H_APP_TYPE_OPEN then
        begin
          // verteilen an alle ausser den sendenden
          SendToAllClientsOOB(pany, Socket);
        end;
      end;
end;
```

## Client side

```pascal
   
procedure Tkipc.OnN4hAny( pany : pTN4H_IP_ANY ; Socket: TCustomWinSocket);
var
  n4h_paket : TN4Hpaket;
  n4hsec : TN4H_security;
begin
    // wait for confirmation before the client can send any packets
    // Client sent a passwort request and can only proceed when server agrees
    if not client_socket_can_send  then 
    begin
      if pany^.h.ptype = N4HIP_PT_PASSWORT_REQ then
      begin
        move(pany^.u.bin.anyData,  n4hsec,  sizeof(n4hsec));
        if (n4hsec.Result = N4H_IP_CLIENT_ACCEPTED) then
        begin
          n4hL2nc_tripRoundDelay := getTickCOunt - n4hL2nc_tripRoundDelay;
          client_socket_can_send := true;
          ConnectionErrorCode := N4H_IP_CLIENT_ACCEPTED;
        end
      else
        begin
          ConnectionErrorCode := N4H_IP_CLIENT_DENIED;
          OnInfo(N4H_IP_CLIENT_DENIED, n4hsec.Result);         // ok -700
          exit;
        end;
    end
    else
       exit;
    end      
    else
    // dies ist Client der auf Antwort wartet
    if pany^.h.ptype = N4HIP_PT_PAKET then
    begin
      if assigned (tTxTimeout) then            // wird erst am Ende von .create erstellt....
      begin
        move (pany^.u.bin.anyData, n4h_paket, sizeof(TN4Hpaket));
        OnPaket(n4h_paket);           // Netz -> App
        if tTxTimeout.Enabled then
        begin
          if comparePaket(lastTXpaket, n4h_paket) then
          begin
            tTxTimeout.Enabled := false;
            OnInfo(N4H_TX_OK, 0);         // eigenes Paket real gesendet (BusEcho via IP)
          end;
        end;
      end;
    end
    else
    if pany^.h.ptype = N4HIP_PT_OOB_DATA_RAW then // MMS only
    begin
        OnOOBdata(hConnection, pany^);
    end;
end;
 
```

```pascal
// Compresseor and Decompressor implementation
// Data received and send are compressed to save resources

unit compressor;
interface
uses windows, sysUtils;

var
  decompressor_err:integer;
  decompressor_errAdr:integer;
  compressor_err:integer;
  compressor_errAdr:integer;

type
  TAdrSet = record
    start,ende : dword;
  end;

function CompressSection(pUnCompressed:pbyte; sizeRaw:dword; pCompressed:pbyte; MaxOutLen:dword):dword;
function decompSection(p2:pbyte; offset, fs:dword; p2out:pbyte; MaxOutLen:dword; useCS:boolean):dword;

implementation

function CompressSection(pUnCompressed:pbyte; sizeRaw:dword; pCompressed:pbyte; MaxOutLen:dword):dword;
var
  lenThisAZG, nextAZG4 : integer;
  cs, lenAZG, storeLen, lenCompressed, i : dword;
  bypeCompress : byte;
  csSaved : boolean;

  // 00 00 33 44 55 -> 2
  function getLenOfAZG(p:pbyte; count:integer):integer;
  var b:byte;
  begin
    result := 0;
    b := byte( p^ );
    while (b = byte( (p+result)^ )) and (result < count) do
      inc(result);
  end;

  function getPosOfNextAZG4(p:pbyte; count:integer):integer;
  var
     i:integer;
     b,c,d,e:byte;
  begin
     i:= 0;
     while (i<count -3) do
     begin
        b := byte( (p+i)^ );
        c := byte( (p+i+1)^ );
        d := byte( (p+i+2)^ );
        e := byte( (p+i+3)^ );
        if (b=c) and (b=d) and (b=e) then
        begin
          result := i;
          exit;
        end;
        inc(i);
     end;
     result := -1; // nix gefunden -> Store rest
  end;

  procedure AddComp(b:byte);
  begin
    pbyte(pCompressed+ lenCompressed) ^ := b;
      if lenCompressed < MaxOutLen then
        inc(lenCompressed)
      else
        compressor_err:= 1;
  end;

  procedure store(p:pbyte; len:word);
  begin
    if len = 0 then exit;
    if len > $3fff then begin compressor_err:= 2; exit; end;
    AddComp(hi(len));    AddComp(lo(len));
    while len>0 do
    begin
      AddComp( byte(p^) ); inc(p); dec(len);
    end;
  end;

  procedure storeBig(p:pbyte; storeLen:dword);
  begin
      while storeLen > $3fff do
      begin
        store(p, $3fff);
        inc(p,$3fff);
        dec(storeLen, $3fff);
      end;
      store(p, storeLen);

  end;

  procedure addCs(Acs:dword);
  begin
      AddComp($c0);// Ende Sign, CS?
      AddComp(Acs shr 24);
      AddComp(Acs shr 16);
      AddComp(Acs shr 8);
      AddComp(Acs shr 0);
      csSaved := true;
  end;

begin
  cs := 0;
  for i:= 0 to sizeRaw-1 do
    cs := cs + byte(  ( pUnCompressed + i)^ );

  csSaved := false;
  result := 0;
  lenCompressed:= 0;
  i:= 0;
  compressor_err := 0;

  while (compressor_err=0) and (i<sizeRaw) do
  begin
    nextAZG4 := getPosOfNextAZG4(pUnCompressed+i, sizeRaw -i);  // wo steht der nächste block an dem alle 4 Zeichen gleich sind  01 02 03 00 00 00 00 -> 3
    if nextAZG4 = -1 then // store rest
    begin
      storeLen := sizeRaw - i;
      storeBig(pUnCompressed+i, storeLen);
      inc(i, storeLen);
      addCs(cs);
    end
    else // es existiert ein Block mit AZG mehr als 4... -> Compress
    begin
      if nextAZG4 > 0 then
      begin
        storeBig(pUnCompressed+i, nextAZG4);
        inc(i, nextAZG4);
      end;

      lenAZG := getLenOfAZG(pUnCompressed+i, sizeRaw -i);
      if lenAZG >= 4 then
      begin
        bypeCompress := byte( (pUnCompressed+i)^ );
        while lenAZG > 0 do
        begin
          lenThisAZG := lenAZG; if lenThisAZG > $3fff then lenThisAZG := $3fff;
          AddComp($40 or hi(lenThisAZG)); AddComp(lo(lenThisAZG));  AddComp(bypeCompress);  // Compress 4000 or len
          inc(i, lenThisAZG);
          dec(lenAZG, lenThisAZG);
        end;
      end
      else
      begin
        compressor_err := 8;
      end;
    end;
  end;

  if compressor_err = 0 then
  begin
    if not csSaved then
      addCs(cs);
    result := lenCompressed;
  end;
end;

function decompSection(p2:pbyte; offset, fs:dword; p2out:pbyte; MaxOutLen:dword; useCS:boolean):dword;
var
  inBlock : integer;
  gPoutPos, i : dword;
  err,
  ende : boolean;
  gPout : pbyte;
  b : byte;
  csCalc, csRx : dword;
  ar2k:array[0..10000] of byte;

  procedure AddOut(b:byte; gPout:pbyte);
  begin
    pbyte(gPout+gPoutPos)^  := b;
    csCalc := csCalc + b;
    inc(gPoutPos);
  end;

begin
  csCalc := 0;
  result := 0;

  if MaxOutLen > sizeof(ar2k) then
  begin
    result := 0;
    exit;
  end;
  gPout := @ar2k;
  decompressor_err := -4;
  decompressor_errAdr := 0;
  i := offset;             // 289 - BB59
  gPoutPos := 0;
  ende := false;
  err := false;
  while (i<fs) and (gPoutPos < MaxOutLen) and (not ende) and (not err) do
  begin
      b := byte( (p2+i)^ );
      if (b and $C0) = $C0 then // Ende  C0 4 byte Checksumme über RawData Add32
      begin
        csRx :=        byte( (p2+i+1)^ ) shl 24;
        csRx := csRx + byte( (p2+i+2)^ ) shl 16;
        csRx := csRx + byte( (p2+i+3)^ ) shl 8;
        csRx := csRx + byte( (p2+i+4)^ );
        ende := true;
        inc(i,4);
        if useCS and  (csRx <> csCalc) then
        begin
          err := true;          decompressor_err:= -100;          decompressor_errAdr := csRx - csCalc;
        end;
      end
      else
      if (b and $C0) = 0 then //Store no Compression   0XXX + len
      begin
        inBlock := byte((p2+i)^) *256 + byte((p2+i+1)^);
        inc(i,2);
        while(inBlock > 0) do
        begin
          dec(inBlock);
          AddOut(byte((p2+i)^) ,gPout);
          inc(i);
        end;
      end
      else
     if (b and $C0) = $40 then // Compression   4XXX + len + byte ->  3 byte -> lohnt also erst ab 4 gleichen Byte
      begin                     // CopyChar
        inBlock := (byte((p2+i)^) *256 + byte((p2+i+1)^)) and $3fff; // copyLen
        b := byte((p2+i+2)^); // copy this byte
        inc(i,3);
        while(inBlock > 0) do
        begin
          dec(inBlock);
          AddOut(b ,gPout);
        end;
      end
      else
      if (b and $C0) = $80 then
      begin
        err := true;
        decompressor_err:= -2;
        inc(i);
      end;
      decompressor_errAdr := i;
  end;

  if (not err) and ende then
  begin
    if MaxOutLen >= gPoutPos then
    begin
      result := gPoutPos;
      move(gPout^, p2out^, gPoutPos);
    end
    else
    begin
      decompressor_err:= -220;
      decompressor_errAdr := i;
    end;
  end;
end;
end.

```

```pascal
// Daten vom IP-Server (kein local-Comport!)

procedure Tkipc.ClientSocket1Read(Sender: TObject;  Socket: TCustomWinSocket);
begin
  SocketReadToN4hAny(Socket, OnN4hAny, ring_buffer);
end;

procedure SocketReadToN4hAny(Socket: TCustomWinSocket; OnN4hAny: TOnN4hAny; ring:TRing_buffer);
var
  lastByteCount, payloadCount : integer;
  lenOut, lenByteInRing  : integer;
  n4h_ip_any : TN4H_IP_ANY;
  dummyRxBuf: array[0..MAX_TX_BUF_SIZE-1] of byte;
begin
  if not add_to_ring(ring, Socket, lastByteCount) then
  begin
    OnInfo(N4H_IM_DEV_CLIENT_RX_BUFF_FULL, lastByteCount );
  end;

  while True do
  begin
    // hat Ring mehr als 4 byte ?
    lenByteInRing := get_ring_bytecount(ring);
    if lenByteInRing <= 4 then
      exit;

    // 4 byte Längenbyte vorhanden...
    if not get_i4_from_ring(ring, payloadCount ) then
      exit;

    // genug für ein ganzes Paket?
    if  (lenByteInRing-4) < payloadCount then
      exit;

    if not get_bytes_from_ring(ring, @dummyRxBuf, payloadCount+4 ) then
      exit;

    if not packOut(@dummyRxBuf, payloadCount+4, @n4h_ip_any, lenOut, sizeof(n4h_ip_any) ) then
      exit;

    OnN4hAny(@n4h_ip_any, Socket);
    invalidate_bytes_from_ring(ring, payloadCount+4);
  end;
end;

 
function packOut(pIn:pbyte; lenIn:integer; pOut:pbyte; var lenOut:integer; maxLenOut:integer):boolean;
var
  payloadLen : integer;
begin
  result := false;

  if lenIn < 4 then   // ohne Länge geht nichts
    exit;

  move((pIn+0)^, payloadLen, 4);  // länge in Daten ermitteln

  // genug Daten IN übergeben?
  if (lenIn-4) < payloadLen then
    exit;

  // enpackte Daten passen in OutBuf?
  if maxLenOut >= payloadLen then
  begin
    lenOut := decompSection(pIn+4, 0, payloadLen, pout, maxLenOut, false);
    result := true;
  end;
end;
```

```pascal
// Unit to send a packet to the serial port
procedure TL2com.sendNextQueued;
var
    i:integer;
    cs,cs2:byte;
    paket : TN4Hpaket;

  procedure TX_addStream(Ac:ansichar);
  begin
    cs := cs + byte(Ac);
    if Ac = #$55 then gRawtx := gRawtx+#$54+#$01 else
    if Ac = #$54 then gRawtx := gRawtx+#$54+#$00 else
    gRawtx := gRawtx + Ac;
  end;

begin
  gTxRetryCount := MAX_RETRY_TX_PAKET;
  gRawtx := #$55;
  cs := $55;

  with paket do
  begin
    inc(ctpt.RXcyclicNr);
    type8:=  (type8 and $0F) or (ctpt.RXcyclicNr shl 4);
    TX_addStream(ansichar( type8));     // type

    if (type8 and saACK_REQ) <> 0 then
    begin
      ctpt.wait_for_req_ackChar:= true;
      retry_tx_ackReq := MAX_RETRY_TX_PAKET;
    end
    else
      ctpt.wait_for_req_ackChar:= false;
      
    TX_addStream(ansichar( hi(ipSrc)));
    TX_addStream(ansichar( lo(ipSrc)));
    TX_addStream(ansichar( hi(ipDest)));
    TX_addStream(ansichar( lo(ipDest)));
    TX_addStream(ansichar( hi(objSrc)));
    TX_addStream(ansichar( lo(objSrc)));
    TX_addStream(ansichar( ddataLen));

    for i:=0 to ddatalen-1 do
      TX_addStream( ansichar( ddata[i]));
 
    cs2 := cs;
    TX_addStream(ansichar( cs2));
  end;

  ctpt.lastTXpaket := paket;
  if (paket.type8 and saCYCLIC) <>0 then
  begin
     // kann Pegelwandler nicht
  end;
  TX_Try_RawPaket;
end;
```

## Initial communication

To register as a client at the Bus connector, the following message needs to be send as a password request.

- The password must be hashed with the modified md5 implementation below.
- Before sending, the data must be compressed
- The type8 of the TN4Hpaket must be a N4HIP_PT_PASSWORT_REQ request

Example with password 123:

- $sendmsg = "190000000002ac0f400a000002bc02404600000487000000c000000200";

The client needs to send the password after hashing with the following example with the modified MD5. Details about the modified MD5 are in the files “md5.pas” and “md5User.pas”

```pascal
function GetHashForServer2(password:ansistring):ansistring;
var
	asStr:ansistring;
	clientHash:TarHashMD5;

begin
	clientHash :=  GetStrHash(password, asStr);
	result := HashToStr( GetHashForServer(clientHash, asStr));
end;

function GetHashForClient(PlainPassword:ShortString):shortstring;
var
	asStr  : ansistring;
	clientHash : TarHashMD5;
begin
	clientHash := GetStrHash(PlainPassword, asStr);
	result := asStr;
end;
```