import asyncio
import logging
import struct
from typing import Any, Tuple
import hashlib

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

def get_hash_for_server2(password: str) -> bytes:
    """
    Portiert die 'GetHashForServer2' aus md5User.pas/md5.pas nach Python.
    Gibt exakt denselben 16-Byte-Hash zurück, den der Server erwartet.
    """
    pw_bytes = password.encode('latin1')  # oft ist in Delphi Latin1 oder ASCII verwendet
    pw_buf = pw_bytes.ljust(16, b'\0')
    md5 = hashlib.md5()
    md5.update(pw_buf)
    digest = md5.digest()
    return digest  # 16 Bytes

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

        # Modifizierte MD5-User-Hash-Funktion anwenden
        md5_digest = get_hash_for_server2(self._password)
        _LOGGER.debug("MD5-User Digest: %s", md5_digest.hex())

        # Beispiel: Authentifizierungs-/Init-Paket mit Hash (Passe Struktur ggf. an!)
        # Falls dein Protokoll wie vorher Hex-Paket + Hash an festen Stellen erwartet:
        # → Hier muss das Paket exakt wie in Perl/FHEM aufgebaut werden
        # Für Testzwecke: Baue das Paket dynamisch zusammen, z.B. als Template

        # Beispiel für "Handshake"-Paket:
        packet_type = N4HIP_PT_PASSWORT_REQ  # z.B. 4012
        payload = md5_digest + bytes([0]) * (56 - len(md5_digest))  # ggf. anpassen!

        # Hier struct.pack anpassen je nach Protokoll (z.B. mit weiteren Feldern wie MI, OBJADR, DLL_VER)
        # Das ist ein Beispiel – siehe Implementation Guide für genaue Reihenfolge!
        algotyp = 1
        result = 0
        length = len(md5_digest)
        application_typ = 0
        dll_ver = DLL_REQ_VER

        packet = (
            struct.pack("<iii", algotyp, result, length)
            + payload
            + struct.pack("<ii", application_typ, dll_ver)
        )
        header = struct.pack("<ii", packet_type, len(packet))
        handshake = header + packet

        self._writer.write(handshake)
        await self._writer.drain()
        _LOGGER.info("Handshake-Paket mit modifiziertem Hash gesendet (hex): %s", handshake.hex())

        # → Optional auf Antwort warten, je nach Protokoll

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
