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
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
        except Exception as e:
            _LOGGER.error("Could not open TCP connection: %s", e)
            raise

        _LOGGER.debug("TCP connection established")

        try:
            # MD5-Hash des Passworts (UTF-8 wie in Perl)
            md5_digest = hashlib.md5(self._password.encode("utf-8")).digest()
            _LOGGER.debug("Computed MD5 digest: %s", md5_digest.hex())

            algotyp = 1
            result = 0
            length = len(md5_digest)
            pw_field = md5_digest + bytes([0]) * (56 - length)
            application_typ = 0
            dll_ver = DLL_REQ_VER

            # Alles exakt wie im Perl pack():
            # struct pack("iii", algotyp, result, length) + pw_field + struct pack("ii", application_typ, dllver)
            payload = (
                struct.pack("<iii", algotyp, result, length)
                + pw_field
                + struct.pack("<ii", application_typ, dll_ver)
            )
            header = struct.pack("<ii", N4HIP_PT_PASSWORT_REQ, len(payload))

            # Hexdump wie Perl ausgeben
            _LOGGER.warning("Handshake-Header+Payload (hex): %s", (header + payload).hex())
            self._writer.write(header + payload)
            await self._writer.drain()
            _LOGGER.debug("Handshake-Paket gesendet, warte auf Antwort...")

            try:
                resp_header = await asyncio.wait_for(self._reader.readexactly(8), timeout=5)
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout beim Warten auf Handshake-Antwort vom Busconnector!")
                raise
            except Exception as exc:
                _LOGGER.error("Fehler beim Empfangen der Handshake-Antwort: %s", exc)
                raise

            _LOGGER.debug("Handshake response header erhalten: %s", resp_header.hex())
            ptype, plen = struct.unpack("<ii", resp_header)
            _LOGGER.debug("Response unpacked: ptype=%s plen=%s", ptype, plen)
            if ptype != N4HIP_PT_PASSWORT_REQ:
                _LOGGER.error("Unexpected handshake response type: %s", ptype)
                raise ConnectionError(f"Unexpected handshake response type: {ptype}")

            resp_payload = await self._reader.readexactly(plen)
            _LOGGER.debug("Handshake response payload: %s", resp_payload.hex())
            resp_result = struct.unpack("<i", resp_payload[4:8])[0]
            _LOGGER.debug("Handshake result code: %s", resp_result)
            if resp_result != N4H_IP_CLIENT_ACCEPTED:
                _LOGGER.error("Password handshake failed with code %s", resp_result)
                raise ConnectionError(f"Password handshake failed with code {resp_result}")
            _LOGGER.info("Password handshake successful")
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
            raise Conne
