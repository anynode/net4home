"""Async TCP client for net4home bus connector with MD5 handshake and logging."""
import asyncio
import hashlib
import struct
import logging

from .const import (
    DEFAULT_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PASSWORT_REQ,
    N4H_IP_CLIENT_ACCEPTED,
    DLL_REQ_VER,
)

_LOGGER = logging.getLogger(__name__)

class Net4HomeClient:
    def __init__(
        self,
        hass,
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
        _LOGGER.debug("Initialized Net4HomeClient: host=%s, port=%s, MI=%s, OBJADR=%s", host, port, mi, objadr)

    async def async_connect(self) -> None:
        """Establish connection and perform MD5-based password handshake."""
        _LOGGER.info("Connecting to net4home bus at %s:%s", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        _LOGGER.debug("TCP connection established")

        md5_digest: bytes = hashlib.md5(self._password.encode()).digest()
        _LOGGER.debug("Computed MD5 digest: %s", md5_digest.hex())

        algotyp = 1
        result = 0
        length = len(md5_digest)
        pw_field = md5_digest + b"�" * (56 - length)
        application_typ = 0
        dll_ver = DLL_REQ_VER

        payload = (
            struct.pack("<iii", algotyp, result, length)
            + pw_field
            + struct.pack("<ii", application_typ, dll_ver)
        )
        _LOGGER.debug("Built handshake payload of length %d", len(payload))

        header = struct.pack("<ii", N4HIP_PT_PASSWORT_REQ, len(payload))
        _LOGGER.debug("Sending handshake header ptype=%s, length=%s", N4HIP_PT_PASSWORT_REQ, len(payload))
        self._writer.write(header + payload)
        await self._writer.drain()
        _LOGGER.info("Handshake request sent")

        data = await self._reader.readexactly(8)
        ptype, plen = struct.unpack("<ii", data)
        _LOGGER.debug("Received handshake response header ptype=%s, length=%s", ptype, plen)
        if ptype != N4HIP_PT_PASSWORT_REQ:
            _LOGGER.error("Unexpected response type %s", ptype)
            raise ConnectionError(f"Unexpected response type: {ptype}")

        resp = await self._reader.readexactly(plen)
        resp_result = struct.unpack("<i", resp[4:8])[0]
        _LOGGER.debug("Handshake result code: %s", resp_result)
        if resp_result != N4H_IP_CLIENT_ACCEPTED:
            _LOGGER.error("Handshake failed with result %s", resp_result)
            raise ConnectionError("Password handshake failed")
        _LOGGER.info("Password handshake successful")

    async def async_disconnect(self) -> None:
        """Close the connection."""
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("TCP connection closed")

    async def async_send_packet(self, data: bytes) -> None:
        """Send raw packet to the bus."""
        _LOGGER.debug("Sending packet of length %d", len(data))
        if not self._writer:
            _LOGGER.error("Send failed: not connected")
            raise ConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()
        _LOGGER.debug("Packet sent")

    async def async_listen(self) -> None:
        """Continuously listen for incoming messages."""
        _LOGGER.info("Listening for incoming bus messages")
        if not self._reader:
            _LOGGER.error("Listen failed: not connected")
            raise ConnectionError("Not connected")
        while True:
            header = await self._reader.readexactly(6)
            _LOGGER.debug("Received raw header: %s", header)
            # TODO: parse header/payload and dispatch