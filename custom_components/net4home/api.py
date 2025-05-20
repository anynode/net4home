import asyncio
import logging
import struct
import binascii

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .md5_custom import get_hash_for_server2
from .n4htools import (
    n4hbus_decomp_section,
    log_parsed_packet,
)

_LOGGER = logging.getLogger(__name__)

class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()

    def feed_data(self, data: bytes):
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 8:
                break

            try:
                ptype, length = struct.unpack("<ii", self._buffer[:8])
            except struct.error as e:
                _LOGGER.error("Error unpacking packet header: %s", e)
                break

            if len(self._buffer) < 8 + length:
                break

            payload = self._buffer[8:8 + length]
            packets.append((ptype, payload))
            del self._buffer[:8 + length]

        return packets


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
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP connection established")

        try:
            packet_bytes = binascii.unhexlify(self._password)
        except binascii.Error as e:
            _LOGGER.error("Invalid password hex string: %s", e)
            raise

        _LOGGER.debug("Password packet to send (hex): %s", self._password)
        self._writer.write(packet_bytes)
        await self._writer.drain()
        _LOGGER.debug("Password packet sent")

    async def async_disconnect(self):
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection closed")

    async def async_listen(self):
        _LOGGER.info("Starting listener for bus messages")
        try:
            while True:
                data = await self._reader.read(4096)
                if not data:
                    _LOGGER.info("Connection closed by remote")
                    break

                packets = self._packet_receiver.feed_data(data)

                for ptype, payload in packets:
                    _LOGGER.debug(f"Received packet type={ptype} length={len(payload)}")
                    try:
                        decompressed = n4hbus_decomp_section(payload.hex(), len(payload))
                        _LOGGER.debug(f"Decompressed payload: {decompressed}")
                        log_parsed_packet(struct.pack("<ii", ptype, len(payload)), payload)
                        # Hier weitere Verarbeitung ergänzen
                    except Exception as e:
                        _LOGGER.error(f"Decompression error: {e}")

        except Exception as e:
            _LOGGER.error(f"Listener exception: {e}")
