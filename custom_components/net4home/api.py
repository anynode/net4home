"""Async TCP client for net4home bus connector with MD5 handshake and packet framing."""
import asyncio
import hashlib
import struct
import logging
from typing import Any, Tuple

from .const import (
    DEFAULT_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PASSWORT_REQ,
    N4HIP_PT_PAKET,
    N4HIP_PT_OOB_DATA_RAW,
    DLL_REQ_VER,
)

_LOGGER = logging.getLogger(__name__)

class Net4HomeClient:
    def __init__(
        self,
        hass: Any,
        host: str,
        port: int = DEFAULT_PORT,
        password: str = "",
        mi: int = DEFAULT_MI,
        objadr: int = DEFAULT_OBJADR,
    ) -> None:
        self._hass = hass
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        _LOGGER.debug(
            "Initialized Net4HomeClient: host=%s port=%s MI=%s OBJADR=%s",
            host, port, mi, objadr,
        )

    async def async_connect(self) -> None:
        """Connect to the bus and perform MD5-based password handshake."""
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
        except Exception as e:
            _LOGGER.error("Could not open TCP connection: %s", e)
            raise

        _LOGGER.debug("TCP connection established")

        try:
            md5_digest = hashlib.md5(self._password.encode("utf-8")).digest()
            _LOGGER.debug("Computed MD5 digest: %s", md5_digest.hex())

            algotyp = 1
            result = 0
            length = len(md5_digest)
            pw_field = md5_digest + bytes([0]) * (56 - length)
            application_typ = 0
            dll_ver = DLL_REQ_VER

            payload = (
                struct.pack("<iii", algotyp, result, length)
                + pw_field
                + struct.pack("<ii", application_typ, dll_ver)
            )
            header = struct.pack("<ii", N4HIP_PT_PASSWORT_REQ, len(payload))
            _LOGGER.warning("Handshake-Header+Payload (hex): %s", (header + payload).hex())
            self._writer.write(header + payload)
            await self._writer.drain()
            _LOGGER.info("Handshake-Paket gesendet, warte **nicht** auf Antwort!")
            # NICHT auf Antwort warten! Gleich weiter machen.
        except Exception as e:
            _LOGGER.error("Handshake with bus connector failed: %s", e)
            raise

        # Registrierung nach erfolgreichem Handshake
        await self.async_register()  # send MI/OBJADR registration

    async def async_register(self) -> None:
        """Register this client at the Bus Connector using MI and OBJADR."""
        _LOGGER.info("Registering client on bus: MI=%s OBJADR=%s", self._mi, self._objadr)
        payload = struct.pack("<HH", self._mi, self._objadr)
        await self.send_packet(N4HIP_PT_PAKET, payload)
        _LOGGER.debug("Registration packet sent: %s", payload.hex())

    async def async_disconnect(self) -> None:
        """Close the connection to the bus."""
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection closed")

    def _build_header(self, ptype: int, length: int) -> bytes:
        """Pack packet header with type and length."""
        return struct.pack("<ii", ptype, length)

    async def send_packet(self, ptype: int, payload: bytes) -> None:
        """Send a framed packet to the bus."""
        if not self._writer:
            raise ConnectionError("Not connected to bus")
        header = self._build_header(ptype, len(payload))
        _LOGGER.debug("Sending packet type=%s length=%s", ptype, len(payload))
        self._writer.write(header + payload)
        await self._writer.drain()

    async def receive_packet(self) -> Tuple[int, bytes]:
        """Receive and parse a framed packet from the bus."""
        if not self._reader:
            raise ConnectionError("Not connected to bus")
        header = await self._reader.readexactly(8)
        ptype, length = struct.unpack("<ii", header)
        payload = await self._reader.readexactly(length)
        _LOGGER.debug("Received packet type=%s length=%s", ptype, length)
        return ptype, payload

    async def async_listen(self) -> None:
        """Continuously listen for incoming messages and dispatch."""
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
                if ptype == N4HIP_PT_OOB_DATA_RAW:
                    _LOGGER.debug("Received raw OOB data: %s", payload)
                    # TODO: parse out-of-band data and notify entities
                else:
                    _LOGGER.warning("Unhandled packet type: %s", ptype)
            except Exception as e:
                _LOGGER.error("Exception in listener loop: %s", e)
                break
