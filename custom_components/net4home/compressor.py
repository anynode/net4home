# custom_components/net4home/compressor.py

"""
Run-Length-Like (RLL) Compressor and Decompressor for net4home packets.

Ported from the Pascal 'compressor' unit.

Implements compression scheme that encodes runs of 4+ identical bytes
and decompresses accordingly.

Includes checksum calculation and verification.

Author: ChatGPT adaptation
"""

from typing import Optional

class CompressionError(Exception):
    pass

def compress(data: bytes) -> bytes:
    """
    Compress the input data using net4home RLL compression.

    Args:
        data: Raw bytes to compress.

    Returns:
        Compressed bytes including checksum.

    Raises:
        CompressionError on failure.
    """
    MAX_BLOCK_LEN = 0x3FFF  # max block size (16383)

    def get_run_length(buf: bytes, start: int, max_len: int) -> int:
        byte_val = buf[start]
        length = 0
        while start + length < len(buf) and length < max_len and buf[start + length] == byte_val:
            length += 1
        return length

    def find_next_run_of_4(buf: bytes, start: int) -> int:
        limit = len(buf) - 3
        for i in range(start, limit):
            b = buf[i]
            if b == buf[i + 1] == buf[i + 2] == buf[i + 3]:
                return i
        return -1

    compressed = bytearray()
    cs = sum(data) & 0xFFFFFFFF  # 32-bit checksum

    pos = 0
    cs_saved = False

    while pos < len(data):
        next_run_pos = find_next_run_of_4(data, pos)

        if next_run_pos == -1:
            # No more runs, store rest as raw blocks
            rest_len = len(data) - pos
            while rest_len > 0:
                block_len = min(rest_len, MAX_BLOCK_LEN)
                # Store raw block: two bytes length, then data
                compressed.append((block_len >> 8) & 0xFF)
                compressed.append(block_len & 0xFF)
                compressed.extend(data[pos:pos + block_len])
                pos += block_len
                rest_len -= block_len
            # Append checksum marker and checksum
            compressed.append(0xC0)
            compressed.append((cs >> 24) & 0xFF)
            compressed.append((cs >> 16) & 0xFF)
            compressed.append((cs >> 8) & 0xFF)
            compressed.append(cs & 0xFF)
            cs_saved = True
            break

        # Store raw data before the run
        if next_run_pos > pos:
            raw_len = next_run_pos - pos
            while raw_len > 0:
                block_len = min(raw_len, MAX_BLOCK_LEN)
                compressed.append((block_len >> 8) & 0xFF)
                compressed.append(block_len & 0xFF)
                compressed.extend(data[pos:pos + block_len])
                pos += block_len
                raw_len -= block_len

        # Now compress the run of repeated bytes
        run_len = get_run_length(data, pos, MAX_BLOCK_LEN)
        if run_len < 4:
            raise CompressionError("Run length less than 4 where compression expected")

        while run_len > 0:
            chunk_len = min(run_len, MAX_BLOCK_LEN)
            # Compression block: 2 bytes length with high bits set to 0x40, then 1 byte value
            length_encoded = chunk_len & 0x3FFF  # 14 bits length
            compressed.append(0x40 | ((length_encoded >> 8) & 0x3F))
            compressed.append(length_encoded & 0xFF)
            compressed.append(data[pos])
            pos += chunk_len
            run_len -= chunk_len

    if not cs_saved:
        # Append checksum if not already appended
        compressed.append(0xC0)
        compressed.append((cs >> 24) & 0xFF)
        compressed.append((cs >> 16) & 0xFF)
        compressed.append((cs >> 8) & 0xFF)
        compressed.append(cs & 0xFF)

    return bytes(compressed)


def decompress(data: bytes, use_checksum: bool = True) -> bytes:
    """
    Decompress net4home RLL compressed data.

    Args:
        data: Compressed data bytes.
        use_checksum: Whether to verify checksum.

    Returns:
        Decompressed raw bytes.

    Raises:
        CompressionError on failure or checksum mismatch.
    """
    MAX_OUTPUT_SIZE = 10000  # arbitrary large buffer size

    output = bytearray()
    cs_calc = 0
    pos = 0
    ended = False

    def add_out_byte(b: int):
        nonlocal cs_calc
        output.append(b)
        cs_calc = (cs_calc + b) & 0xFFFFFFFF

    while pos < len(data) and not ended:
        b = data[pos]
        pos += 1
        prefix = b & 0xC0

        if prefix == 0xC0:
            # End marker + 4 byte checksum follows
            if pos + 4 > len(data):
                raise CompressionError("Incomplete checksum data")
            cs_rx = (data[pos] << 24) | (data[pos+1] << 16) | (data[pos+2] << 8) | data[pos+3]
            pos += 4
            ended = True
            if use_checksum and cs_rx != cs_calc:
                raise CompressionError(f"Checksum mismatch: expected {cs_rx}, calculated {cs_calc}")
        elif prefix == 0x00:
            # Raw data block
            if pos >= len(data):
                raise CompressionError("Unexpected end of data reading raw length")
            length = (b << 8) | data[pos]
            pos += 1
            if pos + length > len(data):
                raise CompressionError("Raw data length exceeds input")
            for i in range(length):
                add_out_byte(data[pos + i])
            pos += length
        elif prefix == 0x40:
            # Compressed run block
            if pos + 1 > len(data):
                raise CompressionError("Unexpected end of data reading compressed block length and byte")
            length = ((b & 0x3F) << 8) | data[pos]
            pos += 1
            if pos >= len(data):
                raise CompressionError("Unexpected end of data reading compressed byte")
            val = data[pos]
            pos += 1
            for _ in range(length):
                add_out_byte(val)
        else:
            raise CompressionError(f"Invalid prefix byte encountered: {b:#x}")

    if not ended:
        raise CompressionError("Did not find checksum end marker")

    return bytes(output)
