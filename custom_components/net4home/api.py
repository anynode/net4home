import asyncio
import logging
from typing import Any, Tuple
from .const import (
    DEFAULT_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
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
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
        except Exception as e:
            _LOGGER.error("Could not open TCP connection: %s", e)
            raise

        _LOGGER.debug("TCP connection established")

        # Sende das identische Init-Paket wie in Perl
        init_hex = "190000000002ac0f400a000002bc02404600000487000000c000000200"
        init_bytes = bytes.fromhex(init_hex)
        self._writer.write(init_bytes)
        await self._writer.drain()
        _LOGGER.warning("Init-Paket wie Perl gesendet (hex): %s", init_bytes.hex())

    async def async_disconnect(self) -> None:
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection closed")

    async def receive_packet(self) -> Tuple[int, bytes]:
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

    async def async_listen(self) -> None:
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
                _LOGGER.debug("Received packet type=%s payload (hex)=%s", ptype, payload.hex())
            except Exception as e:
                _LOGGER.error("Exception in listener loop: %s", e)
                break
