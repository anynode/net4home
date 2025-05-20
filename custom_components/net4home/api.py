import asyncio
import logging
import struct

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .n4htools import (
    n4hbus_compress_section,
    n4hbus_decomp_section,
    log_parsed_packet,
)

_LOGGER = logging.getLogger(__name__)

class Net4HomeApi:
    def __init__(self, hass, host, port=DEFAULT_PORT, password="", mi=DEFAULT_MI, objadr=DEFAULT_OBJADR):
        self._hass = hass
        self._host = host
        self._port = port
        self._password = password  # aktuell ungenutzt
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None

    async def async_connect(self):
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP connection established")

        # MI/OBJADR als Little Endian (2 bytes je Feld!)
        mi_hex = f"{self._mi & 0xFF:02x}{(self._mi >> 8) & 0xFF:02x}"
        objadr_hex = f"{self._objadr & 0xFF:02x}{(self._objadr >> 8) & 0xFF:02x}"

        # Zusammensetzen des unkomprimierten Payloads
        payload_uncompressed = (
            "ac0f400a"
            + mi_hex
            + "bc024046"
            + objadr_hex
            + "04870000"
            + "00c00000"
            + "0200"
        )

        compressed = n4hbus_compress_section(payload_uncompressed)
        packet = bytes.fromhex("19000000" + compressed)
        packet = bytes.fromhex("0008ac0f0000cd564c77400c000021203833393833394536384630433841303241463146424338314443423634303746401b0000080700000087000000c000000aaa")

        self._writer.write(packet)
        await self._writer.drain()
        _LOGGER.debug("Compressed init packet sent (hex): %s", packet.hex())

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
