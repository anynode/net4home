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
    N4H_IP_CLIENT_ACCEPTED,
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
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        _LOGGER.debug("TCP connection established")

        # MD5-based security handshake
        md5_digest = hashlib.md5(self._password.encode()).digest()
        _LOGGER.debug("Computed MD5 digest: %s", md5_digest.hex())

        # Build security payload: algo, result, length, digest + padding, applicationtyp, dllver
        algotyp = 1
        result = 0
        length = len(md5_digest)
        # Use bytes([0]) for null byte padding
        pw_field = md5_digest + bytes([0]) * (56 - len(md5_digest))

        application_typ = 0
        dll_ver = DLL_REQ_VER

        payload = (
            struct.pack("<iii", algotyp, result, length)
            + pw_field
            + struct.pack("<ii", application_typ, dll_ver)
        )
        header = struct.pack("<ii", N4HIP_PT_PASSWORT_REQ, len(payload))
        _LOGGER.debug(
            "Sending handshake: ptype=%s length=%s",
            N4HIP_PT_PASSWORT_REQ,
            len(payload),
        )
        self._writer.write(header + payload)
        await self._writer.drain()

        # Await response
        resp_header = await self._reader.readexactly(8)
        ptype, plen = struct.unpack("<ii", resp_header)
        _LOGGER.debug("Received handshake response header: ptype=%s plen=%s", ptype, plen)
        if ptype != N4HIP_PT_PASSWORT_REQ:
            raise ConnectionError(f"Unexpected handshake response type: {ptype}")

        resp_payload = await self._reader.readexactly(plen)
        resp_result = struct.unpack("<i", resp_payload[4:8])[0]
        if resp_result != N4H_IP_CLIENT_ACCEPTED:
            raise ConnectionError("Password handshake failed with code %s" % resp_result)
        _LOGGER.info("Password handshake successful")
        # Register with bus connector
        await self.async_register()  # send MI/OBJADR registration

    async def async_register(self) -> None:
        """Register this client at the Bus Connector using MI and OBJADR."""
        _LOGGER.info("Registering client on bus: MI=%s OBJADR=%s", self._mi, self._objadr)
        # Build minimal registration payload: MI (2 bytes), OBJADR (2 bytes), no data
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

from homeassistant.helpers.dispatcher import async_dispatcher_send

    async def async_listen(self) -> None:
        """Continuously listen for incoming messages and dispatch updates."""
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
            except Exception as exc:
                _LOGGER.error("Error reading packet: %s", exc)
                break

            if ptype == N4HIP_PT_OOB_DATA_RAW:
                _LOGGER.debug("Received OOB data: %s", payload.hex())
                # Example: first 2 bytes = OBJADR, next = value (adjust based on protocol!)
                if len(payload) >= 3:
                    objadr, value = struct.unpack("<HB", payload[:3])
                    async_dispatcher_send(
                        self._hass, f"net4home_update_{objadr}", value
                    )
                    _LOGGER.debug("Dispatched update for OBJADR %s: value %s", objadr, value)
                else:
                    _LOGGER.warning("OOB payload too short: %s", payload.hex())
            else:
                _LOGGER.warning("Unhandled packet type: %s", ptype)
