import asyncio
import logging
import struct

from .const import (
    DEFAULT_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
)

_LOGGER = logging.getLogger(__name__)

class Net4HomeClient:
    def __init__(self, hass, host, port=DEFAULT_PORT, password="", mi=DEFAULT_MI, objadr=DEFAULT_OBJADR):
        self._hass = hass
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None
        _LOGGER.debug(
            "Initialized Net4HomeClient: host=%s port=%s MI=%s OBJADR=%s",
            host, port, mi, objadr,
        )

    async def async_connect(self):
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        _LOGGER.debug("TCP connection established")

        # Paket-Typ 25 (0x19)
        packet_type = 25
        # Beispiel für MI und OBJADR dynamisch gesetzt
        mi = self._mi
        objadr = self._objadr

        # Je nach Protokoll evtl. weitere Felder/Defaults ergänzen!
        # Hier: Baue analog zu deinem Perl-Paket, aber MI und OBJADR dynamisch
        # Du musst die genaue Struktur evtl. noch im Implementation Guide/Perl vergleichen.
        # Hier als Beispiel: (Restliche Felder ggf. noch anpassen!)
        payload = struct.pack(
            "<I H I H I I I H",
            packet_type,  # Paket-Typ (4B)
            mi,           # MI (2B)
            0x0facac0f,   # Dummy oder spezifisches Feld (4B) – anpassen!
            objadr,       # OBJADR (2B)
            0x4646bc02,   # Dummy oder weiteres Feld (4B) – anpassen!
            0x87000004,   # Dummy oder weiteres Feld (4B)
            0xc0000000,   # Dummy oder weiteres Feld (4B)
            0x2,          # Letztes Feld (2B)
        )
        self._writer.write(payload)
        await self._writer.drain()
        _LOGGER.warning("Dynamisches Init-Paket gesendet (hex): %s", payload.hex())

    async def async_disconnect(self):
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection closed")

    async def receive_packet(self):
        if not self._reader:
            raise ConnectionError("Not connected to bus")
        header = await self._reader.readexactly(8)
        ptype, length = struct.unpack("<ii", header)
        payload = await self._reader.readexactly(length)
        _LOGGER.info(
            "Empfangenes Paket: typ=%s, len=%s, header+payload (hex): %s",
            ptype, length, (header + payload).hex()
        )
        return ptype, payload

    async def async_listen(self):
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
                _LOGGER.debug("Received packet type=%s payload (hex)=%s", ptype, payload.hex())
            except Exception as e:
                _LOGGER.error("Exception in listener loop: %s", e)
                break
