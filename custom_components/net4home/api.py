import asyncio
import logging
import struct
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
    Port der zentralen Hashfunktion aus md5User.pas/md5.pas:
    - Latin1-Encoding (wie Delphi-Ansicht von AnsiString)
    - auf 16 Bytes mit Nullbytes gepadded
    - klassischer MD5-Hash drüber
    - 16 Byte Digest
    """
    pw_bytes = password.encode('latin1')
    pw_buf = pw_bytes.ljust(16, b'\0')
    md5_digest = hashlib.md5(pw_buf).digest()
    return md5_digest

def build_login_handshake(password: str, algotyp: int = 1, dll_ver: int = 1, application_typ: int = 0):
    """
    Baut das vollständige Login-Handshake-Paket für den Busconnector.
    - Nutzt die modifizierte Hashfunktion wie in md5User.pas.
    """
    md5_digest = get_hash_for_server2(password)
    password_field = md5_digest.ljust(56, b'\0')
    payload = struct.pack(
        "<iii56sii",
        algotyp,
        0,
        16,
        password_field,
        application_typ,
        dll_ver
    )
    header = struct.pack("<ii", 4012, len(payload))
    handshake = header + payload
    return handshake

def n4hbus_compress_section(p_uncompressed: str) -> str:
    """
    Port von N4HBUS_CompressSection aus Perl/Pascal nach Python.
    """
    cs = sum(int(p_uncompressed[i*2:i*2+2], 16) for i in range(len(p_uncompressed)//2))
    length = len(p_uncompressed) // 2
    hi = length >> 8
    lo = length & 0xFF
    p_compressed = f"{hi:02X}{lo:02X}"
    p = 0
    while p < length:
        p_compressed += p_uncompressed[p*2:p*2+2]
        p += 1
    p_compressed += "C0"
    p_compressed += f"{(cs>>24)&0xFF:02X}{(cs>>16)&0xFF:02X}{(cs>>8)&0xFF:02X}{cs&0xFF:02X}"
    plen = len(p_compressed) // 2
    p_compressed = f"{plen:02X}000000" + p_compressed
    return p_compressed

def n4hbus_decomp_section(p2: str, fs: int) -> str:
    """
    Port von N4HBUS_decompSection aus Perl/Pascal nach Python.
    """
    ret = ''
    zaehler = 0
    ende = False
    err = False
    gPout = ''
    maxoutlen = 372
    while (zaehler < fs) and (len(gPout) < maxoutlen*2) and not ende and not err:
        bb = p2[zaehler*2:zaehler*2+2]
        bbval = int(bb, 16)
        if (bbval & 192) == 192:
            ende = True
            zaehler += 1
        elif (bbval & 192) == 0:
            bc = p2[(zaehler+1)*2:(zaehler+1)*2+2]
            inBlock = (int(bb, 16) << 8) + int(bc, 16)
            zaehler += 2
            while inBlock > 0:
                gPout += p2[zaehler*2:zaehler*2+2]
                zaehler += 1
                inBlock -= 1
        elif (bbval & 192) == 64:
            bc = p2[(zaehler+1)*2:(zaehler+1)*2+2]
            inBlock = ((int(bb, 16) << 8) + int(bc, 16)) & 16383
            bbval_next = p2[(zaehler+2)*2:(zaehler+2)*2+2]
            zaehler += 3
            while inBlock > 0:
                gPout += bbval_next
                inBlock -= 1
        elif (bbval & 0xC0) == 0x80:
            err = True
            zaehler += 1
    if (not err) and ende:
        ret = gPout
    return ret

class Net4HomeClient:
    def __init__(
        self,
        hass,
        host,
        port=DEFAULT_PORT,
        password="",
        mi=DEFAULT_MI,
        objadr=DEFAULT_OBJADR
    ):
        self._hass = hass
        self._host = host
        self._port = port
        self._password = password
        self._mi = mi
        self._objadr = objadr
        self._reader = None
        self._writer = None
 
    async def async_connect(self):
        _LOGGER.info("Connecting to net4home bus at %s:%d", self._host, self._port)
        self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        _LOGGER.debug("TCP connection established")

        handshake = build_login_handshake(self._password)
        self._writer.write(handshake)
        await self._writer.drain()
        _LOGGER.info("Login-Handshake gesendet (hex): %s", handshake.hex())

    async def async_disconnect(self):
        _LOGGER.info("Disconnecting from net4home bus")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            _LOGGER.debug("Connection closed")

    async def receive_packet(self):
        if not self._reader:
            raise ConnectionError("Not connected to bus")
        header = await self._reader.readexactly(8)
        ptype, length = struct.unpack("<ii", header)
        payload = await self._reader.readexactly(length)
        hex_payload = (header + payload).hex()
        _LOGGER.info(
            "Empfangenes Paket: typ=%s, len=%s, header+payload (hex): %s",
            ptype, length, hex_payload
        )
        # Dekompression falls notwendig:
        try:
            decompressed = n4hbus_decomp_section(payload.hex(), len(payload))
            _LOGGER.info("Dekomprimierter Payload: %s", decompressed)
        except Exception as ex:
            _LOGGER.error("Fehler bei der Dekomprimierung: %s", ex)
        return ptype, payload

    async def async_listen(self):
        _LOGGER.info("Starting listener for bus messages")
        while True:
            try:
                ptype, payload = await self.receive_packet()
                _LOGGER.debug("Received packet type=%s payload (hex)=%s", ptype, payload.hex())
            except Exception as e:
                _LOGGER.error("Exception in listener loop: %s", e)
                break
