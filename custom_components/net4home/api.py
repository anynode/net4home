"""Async TCP client for net4home bus connector with MD5 handshake."""
import asyncio
import hashlib
import struct

from .const import (
    DEFAULT_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    N4HIP_PT_PASSWORT_REQ,
    N4H_IP_CLIENT_ACCEPTED,
    DLL_REQ_VER,
)

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

    async def async_connect(self) -> None:
        """Establish connection and perform MD5-based password handshake."""
        # 1. Open TCP connection
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )

        # 2. Compute MD5 of the password
        md5_digest: bytes = hashlib.md5(self._password.encode()).digest()

        # 3. Build the TN4H_security payload
        algotyp = 1                    # MD5 algorithm
        result = 0                     # reserved
        length = len(md5_digest)      # should be 16
        # Password field is 56 bytes: our digest + zero-padding
        pw_field = md5_digest.ljust(56, bytes([0]))
        application_typ = 0            # per spec
        dll_ver = DLL_REQ_VER         # client DLL version constant

        payload = (
            struct.pack("<iii", algotyp, result, length)
            + pw_field
            + struct.pack("<ii", application_typ, dll_ver)
        )

        # 4. Prepend header (packet type + payload length)
        header = struct.pack("<ii", N4HIP_PT_PASSWORT_REQ, len(payload))
        self._writer.write(header + payload)
        await self._writer.drain()

        # 5. Read response header (type + length)
        data = await self._reader.readexactly(8)
        ptype, plen = struct.unpack("<ii", data)
        if ptype != N4HIP_PT_PASSWORT_REQ:
            raise ConnectionError(f"Unexpected response type: {ptype}")

        # 6. Read response payload and check Result field
        resp = await self._reader.readexactly(plen)
        # The Result int is at offset 4 (after Algotyp), 4 bytes long
        resp_result = struct.unpack("<i", resp[4:8])[0]
        if resp_result != N4H_IP_CLIENT_ACCEPTED:
            raise ConnectionError("Password handshake failed")

    async def async_disconnect(self) -> None:
        """Close the connection."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    async def async_send_packet(self, data: bytes) -> None:
        """Send raw packet to the bus."""
        if not self._writer:
            raise ConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def async_listen(self) -> None:
        """Continuously listen for incoming messages."""
        if not self._reader:
            raise ConnectionError("Not connected")
        while True:
            header = await self._reader.readexactly(6)
            # TODO: parse header (e.g. packet type + length) and then payload
            # length = parse_length_from_header(header)
            # payload = await self._reader.readexactly(length)
            # ...dispatch to handlers...
