import asyncio
import asyncio
import struct
import logging
import binascii

from .const import N4H_IP_PORT, DEFAULT_MI, DEFAULT_OBJADR, N4HIP_PT_PAKET, N4HIP_PT_PASSWORT_REQ, N4HIP_PT_OOB_DATA_RAW
from .n4htools import log_parsed_packet, interpret_n4h_sFkt, TN4Hpaket, n4h_parse, add_module_if_new

_LOGGER = logging.getLogger(__name__)

class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()
 
    def feed_data(self, data: bytes):
        self._buffer.extend(data)
        packets = []
        
        while True:
            if len(self._buffer) < 2:
                break  # Länge noch nicht da

            length_bytes = self._buffer[:1]
            total_len = length_bytes[0] - 4
            
            if len(self._buffer) < total_len:
                break  # Ganzes Paket noch nicht da
                
            # Die ersten 8 Bytes nach Länge sind unkomprimiert (Header)
            header = self._buffer[2:6]
            ptype = struct.unpack('<h', self._buffer[6:8])[0]

            # Wir verarbeiten hier nur N4HIP_PT_PAKET Daten
            if ptype == N4HIP_PT_PAKET:
                payload = self._buffer[8:total_len]
                packets.append((ptype, payload))
            else:
                _LOGGER.debug(f"Nicht verarbeiteter Pakettyp: {ptype}")
            
            del self._buffer[:total_len + 8]

        return packets



class Net4HomeApi:
    def __init__(self, hass, host, port=N4H_IP_PORT, password="", mi=DEFAULT_MI, objadr=DEFAULT_OBJADR):
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

                packets = self._packet_receiver.feed_data(data)
                for ptype, payload in packets:
                    ret, paket = n4h_parse(payload)
                    if paket is None:                    
                        _LOGGER.warning("Paketdaten konnte nicht geparst werden, überspringe")
                        continue

                    # Hier kannst du ddata weiterverarbeiten oder an deine Home Assistant States übergeben
        except Exception as e:
            _LOGGER.error(f"Fehler im Listener: {e}")
