import asyncio
import asyncio
import struct
import logging
import binascii

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .compressor import decompress, CompressionError
from .n4htools import log_parsed_packet, adr_to_text_obj_grp 

_LOGGER = logging.getLogger(__name__)

N4HIP_PT_PAKET = 4001
N4HIP_PT_PASSWORT_REQ = 4012
N4HIP_PT_OOB_DATA_RAW = 4010

class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()
 
    def feed_data(self, data: bytes):
        self._buffer.extend(data)
        packets = []
        # 19 0000000002 ac0f 400a000002bc02404600000487000000c000000200
        # Len 25 - total len 21 - 
        
        while True:
            if len(self._buffer) < 2:
                break  # Länge noch nicht da

            length_bytes = self._buffer[:1]
            total_len = length_bytes[0] - 4
            
            if len(self._buffer) < total_len:
                break  # Ganzes Paket noch nicht da
                
            # 2b 0000 0000 21 a10f 00000800000030000003ff7f63750565330604fa06210502202541000e1401403500c0000005b9 
            #   
            #  1    2    2  1    2 39
            #
            # 30 0000 0000 05 a10f 000004400500001c8102ff7fc96d056505060dd54d617263656c20476f6572747a6b6175403000c000000b72
            
            # Die ersten 8 Bytes nach Länge sind unkomprimiert (Header)
            _LOGGER.debug(f"Len:     {total_len}")
            header = self._buffer[2:6]
            ptype = struct.unpack('<h', self._buffer[6:8])[0]
            _LOGGER.debug(f"Header:  {self._buffer[2:6].hex()}")
            _LOGGER.debug(f"PType:   {self._buffer[6:8].hex()}")
            _LOGGER.debug(f"Payload: {self._buffer[8:total_len].hex()}")
            
            # Wir verarbeiten hier nur N4HIP_PT_PAKET Daten
            if ptype == N4HIP_PT_PAKET:
                payload = self._buffer[8:total_len]
                _LOGGER.debug(f"Pakettyp: {ptype}")
                _LOGGER.debug(f"Payload:  {payload.hex()}")
                packets.append((ptype, payload))
            else:
                _LOGGER.debug(f"Nicht verarbeiteter Pakettyp: {ptype}")
            
            del self._buffer[:total_len + 8]

        return packets


def n4h_parse(payload_bytes: bytes) -> tuple[str, int, int, int]:
    """
    Parsen des N4H-Payloads (als Bytes).
    Gibt zurück:
      - lesbaren String mit den Feldern,
      - ipsrc (int),
      - ipdst (int),
      - objsrc (int).
    Erwartet nur den Payload ab 'ip'-Feld (entspricht original Offset 20).
    """
    payload = payload_bytes.hex()
    ret = ""

    if len(payload) < 40:
        return ("Payload zu kurz für Parsing", 0, 0, 0)

    ip = int(payload[2:4] + payload[0:2], 16)
    ret += f"IP={ip}\t"

    unknown = payload[4:16]
    ret += f"({unknown})\t"

    type8 = int(payload[16:18], 16)
    ret += f"type8={type8}\t"

    # MI = ipsrc
    mi_str = payload[18:20] + payload[16:18]
    ipsrc = int(mi_str, 16)
    ret += f"MI={mi_str}\t"

    ipdst = int(payload[22:24] + payload[20:22], 16)
    ret += f"ipdst={ipdst}\t"

    objsrc = int(payload[26:28] + payload[24:26], 16)
    ret += f"objsrc={objsrc}\t"

    datalen = int(payload[28:30], 16)
    ret += f"datalen={datalen}\t"

    ddata_end = 30 + datalen * 2
    if len(payload) < ddata_end + 8:
        return ("Payload zu kurz für ddata und Checkbytes", ipsrc, ipdst, objsrc)

    ddata = payload[30:ddata_end]
    ret += f"ddata={ddata}\t"

    pos = ddata_end

    csRX = int(payload[pos:pos+2], 16)
    csCalc = int(payload[pos+2:pos+4], 16)
    length = int(payload[pos+4:pos+6], 16)
    posb = int(payload[pos+6:pos+8], 16)
    ret += f"({csRX}/{csCalc}/{length}/{posb})"

    _LOGGER.debug(f"n4h_parse output: {ret}")
    return ret, ipsrc, ipdst, objsrc

class Net4HomeApi:
    def __init__(self, hass, host, port=DEFAULT_PORT, password="", mi=DEFAULT_MI, objadr=DEFAULT_OBJADR):
        self._hass = hass
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None
        self._packet_receiver = N4HPacketReceiver()

    async def async_connect(self):
        _LOGGER.info(f"Verbinde zu net4home Bus bei {self._host}:{self._port}")
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP-Verbindung aufgebaut")

        try:
            packet_bytes = binascii.unhexlify(self._password)
        except binascii.Error as e:
            _LOGGER.error(f"Ungültiger Hex-String für Passwort: {e}")
            raise

        _LOGGER.debug(f"Passwortpaket senden (hex): {self._password}")
        self._writer.write(packet_bytes)
        await self._writer.drain()
        _LOGGER.debug("Passwortpaket gesendet")

    async def async_disconnect(self):
        _LOGGER.info("Verbindung zum net4home Bus trennen")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Verbindung geschlossen")

    async def async_listen(self):
        _LOGGER.info("Starte Listener für Busnachrichten")
        try:
            while True:
                data = await self._reader.read(4096)
                if not data:
                    _LOGGER.info("Verbindung wurde vom Server geschlossen")
                    break
                _LOGGER.debug(f"Empfangene Rohdaten ({len(data)} Bytes): {data.hex()}")

                packets = self._packet_receiver.feed_data(data)
                for ptype, payload in packets:
                    _LOGGER.debug(f"Paket empfangen: Typ={ptype}, Länge={len(payload)}")
                    # parse_result = n4h_parse(payload) 
                    parse_result, ipsrc, ipdst, objsrc = n4h_parse(payload)
                    _LOGGER.warning(f" -> {adr_to_text_obj_grp(ipdst)}")
                    
                    if parse_result is None:
                        _LOGGER.warning("Payload konnte nicht geparst werden, überspringe")
                        continue

                    # type8, ipsrc, ipdst, objsrc, ddata = parse_result
                    # Hier kannst du ddata weiterverarbeiten oder an deine Home Assistant States übergeben
                    # log_parsed_packet(struct.pack("<ii", ptype, len(payload)), payload)

        except Exception as e:
            _LOGGER.error(f"Fehler im Listener: {e}")
