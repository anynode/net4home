from .md5_custom import get_hash_for_server2
from .compressor import compress

class Net4HomeApi:
    # ... existing __init__ and other methods ...

    def _build_password_packet(self, password: str) -> bytes:
        """
        Build the password request packet (TN4Hpaket) with:
        - type8 = N4HIP_PT_PASSWORT_REQ & 0xFF (172)
        - ipsrc = 0 (default)
        - ipdest = 0 (default)
        - objsrc = configured objsrc (e.g., 32700)
        - ddatalen = 16
        - ddata = modified MD5 hash of the password
        - checksum = sum of all bytes modulo 256
        """
        type8 = N4HIP_PT_PASSWORT_REQ & 0xFF
        ipsrc = 0
        ipdest = 0
        objsrc = self._objsrc if hasattr(self, "_objsrc") else 0

        pwd_hash = get_hash_for_server2(password)
        ddatalen = len(pwd_hash)

        packet_without_checksum = struct.pack(
            "<BHHHB", type8, ipsrc, ipdest, objsrc, ddatalen
        ) + pwd_hash

        checksum = sum(packet_without_checksum) % 256

        packet = packet_without_checksum + struct.pack("<B", checksum)^
        return packet

    async def async_connect(self) -> None:
        """Connect to the Bus connector and send the password request."""
        self._logger.debug(f"Connecting to net4home Bus connector at {self._host}:{self._port}")
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        self._logger.debug("TCP connection established")

        # Build password packet using configured password and objsrc
        packet_bytes = self._build_password_packet(self._password)

        self._logger.debug(f"Password packet (uncompressed): {packet_bytes.hex()}")

        compressed_packet = compress(packet_bytes)

        self._logger.debug(f"Password packet (compressed): {compressed_packet.hex()}")

        self._writer.write(compressed_packet)
        await self._writer.drain()
        self._logger.debug("Password packet sent")

        # Receive response
        compressed_response = await self._reader.read(4096)
        self._logger.debug(f"Received compressed response: {compressed_response.hex()}")

        if not compressed_response:
            raise ConnectionError("No response from server")

        # Decompress response
        try:
            response = decompress(compressed_response)
        except Exception as e:
            self._logger.error(f"Failed to decompress server response: {e}")
            raise

        self._logger.debug(f"Decompressed server response: {response.hex()}")

        # Validate response type
        if len(response) < 1:
            raise ConnectionError("Empty response from server")

        response_type = response[0]
        if response_type != (N4HIP_PT_PASSWORT_REQ & 0xFF):
            raise ConnectionError(f"Unexpected response type from server: {response_type}")

        self._logger.info("Password accepted by server")
