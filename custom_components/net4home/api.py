import asyncio
import logging
import struct

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .md5_custom import get_hash_for_server2
from .n4htools import (
    n4hbus_decomp_section,
    log_parsed_packet,
)

_LOGGER = logging.getLogger(__name__)

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

    async def async_connect(self):
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP connection established")
        packet = self._password
        _LOGGER.debug("Password packet sent before (hex): %s", packet.hex())
        self._writer.write(packet.hex())
        await self._writer.drain()
        _LOGGER.debug("Password packet sent after (hex): %s", packet.hex())

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
        hex_payload = (header + payload).hex()
        log_parsed_packet(header, payload)
        _LOGGER.debug(
            "Empfangenes Paket: typ=%s, len=%s, header+payload (hex): %s",
            ptype, length, hex_payload
        )
        try:
            decompressed = n4hbus_decomp_section(payload.hex(), len(payload))
            _LOGGER.debug("Dekomprimierter Payload: %s", decompressed)
        except Exception as ex:
            _LOGGER.error("Fehler bei der Dekomprimierung: %s", ex)
        return ptype, payload

    async def async_listen(self):
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
            except Exception as e:
                _LOGGER.error("Exception in listener loop: %s", e)
                break
