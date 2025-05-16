"""Async TCP client for net4home bus connector."""
import asyncio

from .const import DEFAULT_PORT, DEFAULT_MI, DEFAULT_OBJADR

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
        """Establish connection and perform handshake."""
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        # TODO: implement MD5 handshake and login

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
            # TODO: parse header and payload