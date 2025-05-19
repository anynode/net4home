import asyncio
import struct
import logging
from typing import Optional

from .md5_custom import get_hash_for_server2
from .compressor import compress, decompress, CompressionError

N4HIP_PT_PASSWORT_REQ = 4012

class Net4HomeApi:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        mi: Optional[int],
        objsrc: Optional[int],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objsrc = objsrc or 0
        self._logger = logger or logging.getLogger(__name__)

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    def _build_password_packet(self, password: str) -> bytes:
        type8 = N4HIP_PT_PASSWORT_REQ & 0xFF
        ipsrc = 0
        ipdest = 0
        objsrc = self._objsrc

        pwd_hash = get_hash_for_server2(password)
        ddatalen = len(pwd_hash)

        packet_without_checksum = struct.pack(
            "<BHHHB", type8, ipsrc, ipdest, objsrc, ddatalen
        ) + pwd_hash

        checksum = sum(packet_without_checksum) % 256

        packet = packet_without_checksum + struct.pack("<B", checksum)
        return packet

    async def async_connect(self) -> None:
        self._logger.debug(f"Verbinde mit net4home Busconnector bei {self._host}:{self._port}")
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        self._logger.debug("TCP-Verbindung hergestellt")

        packet_bytes = self._build_password_packet(self._password)
        self._logger.debug(f"Passwortpaket (unkomprimiert): {packet_bytes.hex()}")

        compressed_packet = compress(packet_bytes)
        self._logger.debug(f"Passwortpaket (komprimiert): {compressed_packet.hex()}")

        # 4-Byte Länge voranstellen (Little-Endian uint32)
        packet_len = len(compressed_packet)
        packet_with_len = struct.pack("<I", packet_len) + compressed_packet

        self._logger.debug(f"Länge komprimiertes Paket: {packet_len}")
        self._logger.debug(f"Gesendetes Paket mit Länge (hex): {packet_with_len[:4].hex()}")
        self._logger.debug(f"Gesendetes Paket komplett (hex): {packet_with_len.hex()}")

        # self._writer.write(packet_with_len)
        hex_string = "190000000002ac0f400a000002bc02404600000487000000c000000200"
        packet_bytes = bytes.fromhex(hex_string)
        self._writer.write(packet_bytes)        
        await self._writer.drain()
        self._logger.debug("Fake Passwortpaket gesendet")

        await self._read_packets(self._reader)

    async def _read_packets(self, reader: asyncio.StreamReader) -> None:
        while True:
            try:
                length_bytes = await reader.readexactly(4)
            except asyncio.IncompleteReadError:
                self._logger.warning("Verbindung geschlossen (IncompleteReadError)")
                break

            payload_len = struct.unpack("<I", length_bytes)[0]
            self._logger.debug(f"Erwarte Payload mit Länge {payload_len} Bytes")

            try:
                payload_compressed = await reader.readexactly(payload_len)
            except asyncio.IncompleteReadError:
                self._logger.warning("Verbindung geschlossen beim Lesen der Payload")
                break

            self._logger.debug(f"Empfangene komprimierte Payload: {payload_compressed.hex()}")

            try:
                payload = decompress(payload_compressed)
                self._logger.debug(f"Dekomprimierte Payload: {payload.hex()}")
            except CompressionError as err:
                self._logger.error(f"Dekompression fehlgeschlagen: {err}")
                continue

            self._process_packet(payload)

    def _process_packet(self, packet: bytes) -> None:
        if len(packet) < 8:
            self._logger.warning("Empfangenes Paket zu kurz")
            return

        type8 = packet[0]
        ipsrc, ipdest, objsrc = struct.unpack("<HHH", packet[1:7])
        ddatalen = packet[7]

        self._logger.debug(
            f"Paket empfangen: type8=0x{type8:02X}, ipsrc={ipsrc}, ipdest={ipdest}, objsrc={objsrc}, ddatalen={ddatalen}"
        )

        if len(packet) < 8 + ddatalen + 1:
            self._logger.warning("Paket zu kurz für Payload + Checksumme")
            return

        ddata = packet[8 : 8 + ddatalen]
        checksum = packet[8 + ddatalen]

        calc_checksum = sum(packet[:8 + ddatalen]) % 256
        if checksum != calc_checksum:
            self._logger.warning(f"Ungültige Checksumme: erhalten=0x{checksum:02X}, berechnet=0x{calc_checksum:02X}")

        if type8 == (N4HIP_PT_PASSWORT_REQ & 0xFF):
            self._logger.info("Passwort-Response empfangen")
        else:
            self._logger.info(f"Unbekannter Pakettyp empfangen: 0x{type8:02X}")

    async def async_disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._logger.debug("TCP-Verbindung geschlossen")
