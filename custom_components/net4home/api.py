import asyncio
import logging
import struct
import binascii

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR
from .compressor import decompress, CompressionError
from .n4htools import log_parsed_packet

_LOGGER = logging.getLogger(__name__)

class N4HPacketReceiver:
    def __init__(self):
        self._buffer = bytearray()

    def feed_data(self, data: bytes):
        """Füttert neue Daten in den Puffer und gibt alle vollständigen Pakete zurück.

        Paketaufbau (Little Endian):
        - 4 Bytes: ptype (int)
        - 4 Bytes: Länge (int)
        - Länge Bytes: Payload (komprimiert)

        Rückgabe: Liste von (ptype, payload_bytes)
        """
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 8:
                # Header noch nicht vollständig
                break

            try:
                ptype, length = struct.unpack("<ii", self._buffer[:8])
            except struct.error as e:
                _LOGGER.error("Fehler beim Entpacken des Headers: %s", e)
                break

            if len(self._buffer) < 8 + length:
                # Payload noch nicht vollständig
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
            _LOGGER.error("Ungültiger Hex-String für Passwort: %s", e)
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

                for idx, (ptype, payload) in enumerate(packets, 1):
                    _LOGGER.debug(f"Packet #{idx}: Type={ptype}, Length={len(payload)}, Payload (hex)={payload.hex()}")

                for ptype, payload in packets:
                    _LOGGER.debug(f"Received packet type={ptype} length={len(payload)}")
                    try:
                        decompressed = decompress(payload)
                        _LOGGER.debug(f"Decompressed payload (hex): {decompressed.hex()}")
                        log_parsed_packet(struct.pack("<ii", ptype, len(payload)), decompressed)
                        # Hier kann weitere Paketverarbeitung erfolgen
                    except CompressionError as e:
                        _LOGGER.error(f"Fehler bei der Dekomprimierung: {e}")
                    except Exception as e:
                        _LOGGER.error(f"Unbekannter Fehler bei Paketverarbeitung: {e}")

        except Exception as e:
            _LOGGER.error(f"Listener exception: {e}")
