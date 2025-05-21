import asyncio
import asyncio
import struct
import logging
import binascii

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .compressor import decompress, CompressionError
from .n4htools import log_parsed_packet  # Deine existierende Funktion zur Paketverarbeitung

_LOGGER = logging.getLogger(__name__)

class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()
        self._marker = b'\xa1\x0f'  # Marker a10f
 
    def feed_data(self, data: bytes):
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 2:
                break  # Länge noch nicht da

            length_bytes = self._buffer[:2]
            length = (
                length_bytes[0]
            )
            
            # total_len = (length*2) - 8
            total_len = length - 4
            
            if len(self._buffer) < total_len:
                break  # Ganzes Paket noch nicht da
                
            # 2b 0000 0000 21 a10f 00000800000030000003ff7f63750565330604fa06210502202541000e1401403500c0000005b9 
            #   
            #  1    2    2  1    2 39
            #

            # Die ersten 8 Bytes nach Länge sind unkomprimiert (Header)
            header = self._buffer[2:12]
            
            ptype = struct.unpack('<i', self._buffer[12:16])[0]

            compressed_payload = self._buffer[16:(total_len*2)]
            _LOGGER.error(f"compressed_payload: {compressed_payload}")

            try:
                decompressed_payload = decompress(compressed_payload)
                _LOGGER.error(f"decompressed_payload: {decompressed_payload}")
            except CompressionError as e:
                _LOGGER.error(f"Dekomprimierungsfehler: {e}")
                del self._buffer[:total_len]
                continue

            full_payload = decompressed_payload
            _LOGGER.debug(f"full_payload: {full_payload.hex()}")            
            packets.append((ptype, full_payload))

            del self._buffer[:total_len]

        return packets



def n4hmodule_parse(msg_bytes: bytes):
    #if len(msg_bytes) < 17:
    #    _LOGGER.error("N4HMODULE_Parse: Payload zu kurz")
    #    return None

    try:
        type8 = msg_bytes[0]
        ipsrc = int.from_bytes(msg_bytes[2:4], 'little')
        ipdst = int.from_bytes(msg_bytes[6:8], 'little')
        objsrc = int.from_bytes(msg_bytes[10:12], 'little')
        datalen = msg_bytes[14]

        if len(msg_bytes) < 16 + datalen:
            _LOGGER.error("N4HMODULE_Parse: Payload unvollständig laut Länge")
            return None

        ddata = msg_bytes[16:16 + datalen]

        _LOGGER.debug(f"N4HMODULE_Parse: type8={type8}, ipsrc={ipsrc}, ipdst={ipdst}, "
                      f"objsrc={objsrc}, datalen={datalen}, ddata={ddata.hex()}")

        return (type8, ipsrc, ipdst, objsrc, ddata)

    except Exception as e:
        _LOGGER.error(f"N4HMODULE_Parse: Fehler beim Parsen: {e}")
        return None

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
                    
                    parse_result = n4hmodule_parse(payload)
                    if parse_result is None:
                        _LOGGER.warning("Payload konnte nicht geparst werden, überspringe")
                        continue

                    type8, ipsrc, ipdst, objsrc, ddata = parse_result
                    # Hier kannst du ddata weiterverarbeiten oder an deine Home Assistant States übergeben
                    log_parsed_packet(struct.pack("<ii", ptype, len(payload)), payload)

        except Exception as e:
            _LOGGER.error(f"Fehler im Listener: {e}")
