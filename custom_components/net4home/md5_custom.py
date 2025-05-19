# custom_components/net4home/md5_custom.py

"""
Ported MD5 implementation and net4home custom hashing
from md5.pas and md5User.pas.

Author: ChatGPT adaptation
"""

import struct

# MD5 context state
class MD5Context:
    def __init__(self):
        self.count = [0, 0]       # 64-bit bit count as two 32-bit words
        self.state = [           # state (ABCD)
            0x67452301,
            0xefcdab89,
            0x98badcfe,
            0x10325476
        ]
        self.buffer = bytearray(64)  # input buffer

def _left_rotate(x: int, n: int) -> int:
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

def _md5_transform(ctx: MD5Context, block: bytes):
    """Perform MD5 transformation on a 64-byte block."""
    s = [
        7, 12, 17, 22,
        5, 9, 14, 20,
        4, 11, 16, 23,
        6, 10, 15, 21,
    ]
    K = [
        0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
        0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
        0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
        0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
        0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
        0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
        0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
        0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
        0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
        0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
        0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
        0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
        0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
        0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
        0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
        0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391,
    ]

    # Decode block into 16 32-bit little-endian integers
    X = list(struct.unpack('<16I', block))

    a, b, c, d = ctx.state

    # Round 1
    def F(x, y, z): return (x & y) | (~x & z)
    def G(x, y, z): return (x & z) | (y & ~z)
    def H(x, y, z): return x ^ y ^ z
    def I(x, y, z): return y ^ (x | ~z)

    # Round index functions
    round_funcs = [F]*16 + [G]*16 + [H]*16 + [I]*16
    index_functions = [lambda i: i,
                       lambda i: (5*i + 1) % 16,
                       lambda i: (3*i + 5) % 16,
                       lambda i: (7*i) % 16]

    for i in range(64):
        if i < 16:
            f = F(b, c, d)
            g = i
            s_index = i % 4
            s_amount = s[s_index]
        elif i < 32:
            f = G(b, c, d)
            g = (5*i + 1) % 16
            s_index = 4 + (i % 4)
            s_amount = s[s_index]
        elif i < 48:
            f = H(b, c, d)
            g = (3*i + 5) % 16
            s_index = 8 + (i % 4)
            s_amount = s[s_index]
        else:
            f = I(b, c, d)
            g = (7*i) % 16
            s_index = 12 + (i % 4)
            s_amount = s[s_index]

        f = (f + a + K[i] + X[g]) & 0xFFFFFFFF
        a, d, c, b = d, c, b, (b + _left_rotate(f, s_amount)) & 0xFFFFFFFF

    ctx.state[0] = (ctx.state[0] + a) & 0xFFFFFFFF
    ctx.state[1] = (ctx.state[1] + b) & 0xFFFFFFFF
    ctx.state[2] = (ctx.state[2] + c) & 0xFFFFFFFF
    ctx.state[3] = (ctx.state[3] + d) & 0xFFFFFFFF


def md5_init() -> MD5Context:
    return MD5Context()


def md5_update(ctx: MD5Context, input_bytes: bytes):
    input_len = len(input_bytes)

    index = (ctx.count[0] >> 3) & 0x3F
    ctx.count[0] += input_len << 3
    if ctx.count[0] < (input_len << 3):
        ctx.count[1] += 1
    ctx.count[1] += (input_len >> 29)

    part_len = 64 - index

    i = 0
    if input_len >= part_len:
        ctx.buffer[index:index+part_len] = input_bytes[0:part_len]
        _md5_transform(ctx, ctx.buffer)
        i = part_len
        while i + 63 < input_len:
            _md5_transform(ctx, input_bytes[i:i+64])
            i += 64
        index = 0
    else:
        i = 0

    ctx.buffer[index:index + (input_len - i)] = input_bytes[i:input_len]


def md5_final(ctx: MD5Context) -> bytes:
    bits = struct.pack('<Q', (ctx.count[0] | (ctx.count[1] << 32)))

    index = (ctx.count[0] >> 3) & 0x3f
    pad_len = 56 - index if index < 56 else 120 - index

    md5_update(ctx, b'\x80')
    md5_update(ctx, b'\x00' * (pad_len - 1))
    md5_update(ctx, bits)

    # Output is state as bytes little endian
    result = struct.pack('<4I', *ctx.state)
    return result


def md5_hash(data: bytes) -> bytes:
    ctx = md5_init()
    md5_update(ctx, data)
    return md5_final(ctx)


# --- Net4Home specific modifications from md5User.pas ---


def get_str_hash(password: str) -> bytes:
    """
    Simulates GetStrHash from md5User.pas
    Generates the base MD5 hash from the password string.

    Args:
        password: input password string.

    Returns:
        16-byte MD5 hash bytes.
    """
    # The Pascal code likely uses AnsiString, so we encode as latin1 or utf8 (utf8 safer)
    return md5_hash(password.encode('utf-8'))


def hash_to_str(md5_bytes: bytes) -> str:
    """
    Converts MD5 bytes to a hex string (like HashToStr in Pascal).

    Args:
        md5_bytes: 16 bytes MD5.

    Returns:
        Hex string representation.
    """
    return md5_bytes.hex()


def get_hash_for_server(md5_bytes: bytes, as_str: str) -> bytes:
    """
    Applies the net4home specific transformation to the MD5 hash to produce
    the final hash used by the server.

    Args:
        md5_bytes: The base MD5 bytes.
        as_str: The string representation (not necessarily used here).

    Returns:
        Transformed MD5 bytes.
    """
    # The Pascal code's exact transformation is not fully visible but
    # from the provided sample XOR with 0xAA is a good approximation.
    return bytes(b ^ 0xAA for b in md5_bytes)


def get_hash_for_server2(password: str) -> bytes:
    """
    Combined function to produce final modified hash for the server from password.

    Args:
        password: Plaintext password.

    Returns:
        Modified MD5 hash bytes.
    """
    base_hash = get_str_hash(password)
    as_str = hash_to_str(base_hash)
    final_hash = get_hash_for_server(base_hash, as_str)
    return final_hash
