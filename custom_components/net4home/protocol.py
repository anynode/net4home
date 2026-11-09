"""TCP packets between Home Assistant and the bus connector."""
import asyncio
import logging
import struct
from typing import Tuple

from .const import (
    MAX_N4H_PAKET_LEN,
    N4HIP_PT_OOB_DATA_RAW,
    N4HIP_PT_PAKET,
    N4HIP_PT_PASSWORT_REQ,
    RESERVED1_DEFAULT,
    SEND_AS_OBJ_GRP,
    STANDARD_PAYLOAD_LEN,
    TRAILER_SIZE,
)
from .n4htools import (
    compress_section,
    decode_d2b,
)

_LOGGER = logging.getLogger(__name__)

def pwm_status_to_ha(hi: int, lo: int) -> tuple[bool, int]:
    """Map a PWM actor status to Home Assistant on/off and brightness.

    A 16-bit status word of 0..100 is the percent (TLH and ACTOR_ACK).
    D0_SET from the konfigurator puts that percent in the high byte and
    leaves the low byte at 0, so an echoed word of percent*256 is the
    same value.
    """
    word = ((hi & 0xFF) << 8) | (lo & 0xFF)
    if word <= 100:
        percent = word
    elif (lo & 0xFF) == 0 and (hi & 0xFF) <= 100:
        percent = hi & 0xFF
    else:
        percent = min(word, 100)
    return percent > 0, round(percent * 255 / 100)

class N4HPacketReceiver:
    """Receive and parse packets from the bus connector."""
    
    def __init__(self):
        """Initialize the packet receiver."""
        self._buffer = bytearray()

    def receive_raw_command(self, data: bytes):
        """Receive raw command data and parse into packets."""
        self._buffer.extend(data)
        packets = []

        while True:
            if len(self._buffer) < 4:
                break  # Not enough data for length header

            payload_len = int.from_bytes(self._buffer[:4], 'little')

            if len(self._buffer) < payload_len + 4:
                break  # Not yet full packet received

            full_packet = self._buffer[:payload_len + 4]
            compressed_payload = full_packet[4:4 + payload_len]

            try:
                decompressed, length = decomp_section_c_exact(
                    compressed_payload,
                    offset=0,
                    length=len(compressed_payload),
                    max_out_len=2048,
                    use_cs=False
                )

                if len(decompressed) >= 2:
                    ptype = struct.unpack('<h', decompressed[0:2])[0]

                    if ptype == N4HIP_PT_PAKET:
                        packets.append((ptype, decompressed))
                    elif ptype == N4HIP_PT_OOB_DATA_RAW:
                        _LOGGER.debug("Raw OOB data packets received.")
                        
                    elif ptype == N4HIP_PT_PASSWORT_REQ:
                        _LOGGER.debug(f"Password ACK empfangen")
                    else:
                        _LOGGER.debug(f"Ignored packet type: {ptype}")

                else:
                    _LOGGER.warning("Dekomprimierter Block zu kurz (< 8 Byte)")

            except Exception as e:
                _LOGGER.error(f"Dekomprimierung fehlgeschlagen: {e}")

            del self._buffer[:payload_len + 4]

        return packets

class DecompressionError(Exception):
    """Exception raised when decompression fails."""
    
    def __init__(self, code: int, detail: int):
        """Initialize decompression error."""
        super().__init__(f"Decompression error {code}, detail: {detail}")
        self.code = code
        self.detail = detail

def decomp_section_c_exact(data: bytes, offset: int, length: int, max_out_len: int, use_cs: bool) -> Tuple[bytes, int]:
    """Decompress a section using the C exact algorithm."""
    result = bytearray()
    cs_calc = 0
    i = offset
    g_pout_pos = 0
    ende = False
    err = False

    while i < length and g_pout_pos < max_out_len and not ende and not err:
        b = data[i]

        if (b & 0xC0) == 0xC0:
            if i + 4 >= length:
                raise DecompressionError(-98, i)
            cs_rx = (
                (data[i + 1] << 24)
                | (data[i + 2] << 16)
                | (data[i + 3] << 8)
                | data[i + 4]
            )
            i += 5
            ende = True
            if use_cs and cs_rx != cs_calc:
                raise DecompressionError(-100, cs_rx - cs_calc)

        elif (b & 0xC0) == 0x00:
            if i + 1 >= length:
                raise DecompressionError(-97, i)
            cclen = ((data[i] << 8) | data[i + 1]) & 0x3FFF
            i += 2
            for j in range(cclen):
                if i < length:
                    val = data[i]
                    result.append(val)
                    cs_calc += val
                    g_pout_pos += 1
                    i += 1
                else:
                    raise DecompressionError(-11, i)

        elif (b & 0xC0) == 0x40:
            if i + 2 >= length:
                raise DecompressionError(-95, i)
            cclen = ((data[i] << 8) | data[i + 1]) & 0x3FFF
            val = data[i + 2]
            i += 3
            for _ in range(cclen):
                result.append(val)
                cs_calc += val
                g_pout_pos += 1

        elif (b & 0xC0) == 0x80:
            raise DecompressionError(-2, i)

        else:
            raise DecompressionError(-5, i)

    if not err and ende and len(result) <= max_out_len:
        return bytes(result), len(result)

    raise DecompressionError(-220, i)

class N4HPacketSender:
    """Send packets to the bus connector."""
    
    def __init__(self, writer: asyncio.StreamWriter):
        """Initialize the packet sender with a stream writer."""
        self._writer = writer

    async def send_raw_command(self, ipdst: int, ddata: bytes, objsource: int = 0, mi: int = 65281, type8: int = SEND_AS_OBJ_GRP):
        """
        Send a command to the bus.
        
        Addressing:
        - ipdst: Target address (can be MI or OBJ address)
          * MI address: < 0x8000 (32768), e.g. 0x0099 for module MI0099
          * OBJ address: Can be < 0x8000 (e.g. 27232) or >= 0x8000 for groups
          * Special values: 0x7FFF (32767) = Broadcast, 0xFFFF (65535) = ENUM_ALL
        - mi: MI address of sender (always MI address, < 0x8000)
        - objsource: OBJ address of sender (can be 0 for module commands)
        - type8: Address type (SEND_AS_IP=1 for MI addresses, 0 for OBJ addresses)
        """
        _LOGGER.debug(
            f"[IP] Sending command: "
            f"ipsrc=0x{mi:04X}, ipdst=0x{ipdst:04X}, objsrc={objsource}, "
            f"datalen={len(ddata)}, type8={type8}"
        )
        
        try:
            # === Paketaufbau im Hexstring
            # Header: 8 Bytes
            sendbus = struct.pack('<H', N4HIP_PT_PAKET).hex().upper()  # N4HIP_PT_PAKET (2 Bytes, little endian: 0x0FA1)
            sendbus += struct.pack('<H', RESERVED1_DEFAULT).hex().upper()  # Reserved1 (2 Bytes)
            sendbus += struct.pack('<I', STANDARD_PAYLOAD_LEN).hex().upper()  # Payload-Länge (4 Bytes, little endian)
            # Header Ende (HEADER_SIZE Bytes total)
            
            # === Packet data after header (as expected in n4h_parse)
            # type8: First byte after header (sa2_T8_IP=1 for MI addresses)
            sendbus += f"{type8:02X}"    # type8 (TYPE8_SIZE byte)
            sendbus += "00"              # Skip byte (SKIP_BYTE_SIZE byte, result[1] is skipped)
            
            # === Encode addresses (as expected in n4h_parse: result[2:4], result[4:6], result[6:8])
            sendbus += decode_d2b(mi)    # ipsrc (ADDRESS_SIZE Bytes, little endian)
            sendbus += decode_d2b(ipdst) # ipdest (ADDRESS_SIZE Bytes, little endian)
            sendbus += decode_d2b(objsource) # objsrc (ADDRESS_SIZE Bytes, little endian)

            # === Prepare DDATA: first byte = length, then the actual payload
            full_ddata = bytes([len(ddata)]) + ddata

            # === Pad to MAX_N4H_PAKET_LEN bytes (MAX_N4H_PAKET_LEN * 2 hex characters)
            ddata_hex = full_ddata.hex().upper().ljust(MAX_N4H_PAKET_LEN * 2, "0")
            sendbus += ddata_hex

            # === Abschluss mit csRX, csCalc, length, posb (TRAILER_SIZE bytes)
            sendbus += "00" * TRAILER_SIZE

            # === Kompression & Verpackung
            compressed = compress_section(sendbus)
            final_bytes = bytes.fromhex(compressed)
            # === Senden
            self._writer.write(final_bytes)
            await self._writer.drain()

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            _LOGGER.warning("[IP] Send dropped, bus connection is down: %s", e)
        except Exception as e:
            _LOGGER.error(f"[IP] Error sending data (raw): {e}", exc_info=True)
