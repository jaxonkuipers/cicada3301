"""512-bit hash functions `hashlib` does not ship, in pure Python.

This module contains functions that can be gated against published vectors and
omits implementations without an independent known answer.

**`keccak3-512` is not `sha3_512`.** SHA-3 was standardised in August 2015 and
changed the domain-separation padding from Keccak's `0x01` to `0x06`; LP2 was
published January 2014, so ORIGINAL Keccak is the period-correct function and
`hashlib.sha3_512` is a different function that did not exist when page-56 was
printed. Both are carried here, separately named.

Every function in `ALL` is gated by `gate.py` against a published test vector
or against `hashlib`. Nothing enters `ALL` ungated: a silently wrong hash
function turns a negative result into a lie about coverage.
"""

from __future__ import annotations

import hashlib

# --------------------------------------------------------------------------
# Keccak-f[1600], the sponge under both original Keccak and SHA-3
# --------------------------------------------------------------------------

_M64 = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    n &= 63
    return ((x << n) | (x >> (64 - n))) & _M64


def _rho_offsets() -> list[list[int]]:
    """Generated from the (x,y) walk rather than transcribed."""
    off = [[0] * 5 for _ in range(5)]
    x, y = 1, 0
    for t in range(24):
        off[x][y] = ((t + 1) * (t + 2) // 2) % 64
        x, y = y, (2 * x + 3 * y) % 5
    return off


def _round_constants() -> list[int]:
    """Generated from the rc(t) LFSR rather than transcribed."""
    rc, r = [], 1
    for _ in range(24):
        c = 0
        for j in range(7):
            r = ((r << 1) ^ ((r >> 7) * 0x71)) % 256
            if r & 2:
                c ^= 1 << ((1 << j) - 1)
        rc.append(c)
    return rc


_OFF = _rho_offsets()
_RC = _round_constants()


def _keccak_f(a: list[list[int]]) -> None:
    for rnd in range(24):
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x][y] ^= d[x]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _OFF[x][y])
        for x in range(5):
            for y in range(5):
                a[x][y] = b[x][y] ^ ((b[(x + 1) % 5][y] ^ _M64) & b[(x + 2) % 5][y])
        a[0][0] ^= _RC[rnd]


def keccak(rate: int, data: bytes, dsbyte: int, outlen: int) -> bytes:
    """Sponge over Keccak-f[1600]. `rate` in bytes, `dsbyte` the pad prefix."""
    a = [[0] * 5 for _ in range(5)]
    p = bytearray(data)
    p.append(dsbyte)
    while len(p) % rate:
        p.append(0)
    p[-1] ^= 0x80
    for off in range(0, len(p), rate):
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(p[off + 8 * i:off + 8 * i + 8], "little")
        _keccak_f(a)
    out = bytearray()
    while True:
        for i in range(rate // 8):
            out += a[i % 5][i // 5].to_bytes(8, "little")
        if len(out) >= outlen:
            return bytes(out[:outlen])
        _keccak_f(a)


def keccak512(b: bytes) -> bytes:
    """Original Keccak-512 -- the pre-standardisation function of 2014."""
    return keccak(72, b, 0x01, 64)


def keccak256(b: bytes) -> bytes:
    return keccak(136, b, 0x01, 32)


def _sha3_512_ours(b: bytes) -> bytes:
    return keccak(72, b, 0x06, 64)


def _shake256_ours(b: bytes, n: int) -> bytes:
    return keccak(136, b, 0x1F, n)


# --------------------------------------------------------------------------
# Whirlpool
# --------------------------------------------------------------------------

_E = [0x1, 0xB, 0x9, 0xC, 0xD, 0x6, 0xF, 0x3, 0xE, 0x8, 0x7, 0x4, 0xA, 0x2, 0x5, 0x0]
_R = [0x7, 0xC, 0xB, 0xD, 0xE, 0x4, 0x9, 0xF, 0x6, 0x3, 0x8, 0xA, 0x2, 0x5, 0x1, 0x0]


def _whirlpool_sbox() -> list[int]:
    """From the E and R mini-boxes; the spec's construction, not a table dump."""
    einv = [0] * 16
    for i, v in enumerate(_E):
        einv[v] = i
    s = []
    for u in range(16):
        for lo in range(16):
            y1, y2 = _E[u], einv[lo]
            r = _R[y1 ^ y2]
            s.append((_E[y1 ^ r] << 4) | einv[y2 ^ r])
    return s


def _gf(a: int, b: int) -> int:
    """GF(2^8) multiply, reduction polynomial 0x11D."""
    p = 0
    while b:
        if b & 1:
            p ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
        b >>= 1
    return p


_SBOX = _whirlpool_sbox()
_CIR = (1, 1, 4, 1, 8, 5, 2, 9)


def _whirlpool_tables() -> tuple[list[list[int]], list[int]]:
    c0 = []
    for x in range(256):
        v = 0
        for k in _CIR:
            v = (v << 8) | _gf(_SBOX[x], k)
        c0.append(v)
    ct = [c0]
    for t in range(1, 8):
        ct.append([((v >> (8 * t)) | (v << (64 - 8 * t))) & _M64 for v in c0])
    rc = [0]
    for r in range(1, 11):
        rc.append(int.from_bytes(bytes(_SBOX[8 * (r - 1) + j] for j in range(8)), "big"))
    return ct, rc


_CT, _RCW = _whirlpool_tables()


def _wround(st: list[int], k: int) -> list[int]:
    out = []
    for i in range(8):
        v = k if i == 0 else 0
        for t in range(8):
            v ^= _CT[t][(st[(i - t) % 8] >> (56 - 8 * t)) & 0xFF]
        out.append(v)
    return out


def whirlpool(data: bytes) -> bytes:
    """Whirlpool (the final 2003 revision). Miyaguchi-Preneel over W."""
    p = bytearray(data)
    p.append(0x80)
    while len(p) % 64 != 32:
        p.append(0)
    p += (len(data) * 8).to_bytes(32, "big")
    h = [0] * 8
    for off in range(0, len(p), 64):
        blk = [int.from_bytes(p[off + 8 * i:off + 8 * i + 8], "big") for i in range(8)]
        k = list(h)
        st = [blk[i] ^ k[i] for i in range(8)]
        for r in range(1, 11):
            k = _wround(k, _RCW[r])
            st = _wround(st, 0)
            st = [st[i] ^ k[i] for i in range(8)]
        h = [h[i] ^ st[i] ^ blk[i] for i in range(8)]
    return b"".join(x.to_bytes(8, "big") for x in h)


# --------------------------------------------------------------------------
# FNV-512. Parameters DERIVED, not transcribed: the offset basis is FNV-0 of
# Landon Curt Noll's signature string, and deriving it at 32 and 64 bits
# reproduces the published constants exactly (gate.py).
# --------------------------------------------------------------------------

_FNV_SIG = b"chongo <Landon Curt Noll> /\\../\\"
_FNV_PRIME = {32: (1 << 24) + (1 << 8) + 0x93,
              64: (1 << 40) + (1 << 8) + 0xB3,
              512: (1 << 344) + (1 << 8) + 0x57}


def fnv0(data: bytes, bits: int) -> int:
    h, p, m = 0, _FNV_PRIME[bits], (1 << bits) - 1
    for b in data:
        h = (h * p) & m
        h ^= b
    return h


def _basis(bits: int) -> int:
    return fnv0(_FNV_SIG, bits)


def fnv1(data: bytes, bits: int) -> int:
    h, p, m = _basis(bits), _FNV_PRIME[bits], (1 << bits) - 1
    for b in data:
        h = (h * p) & m
        h ^= b
    return h


def fnv1a(data: bytes, bits: int) -> int:
    h, p, m = _basis(bits), _FNV_PRIME[bits], (1 << bits) - 1
    for b in data:
        h ^= b
        h = (h * p) & m
    return h


def fnv512_0(b: bytes) -> bytes:
    return fnv0(b, 512).to_bytes(64, "big")


def fnv512_1(b: bytes) -> bytes:
    return fnv1(b, 512).to_bytes(64, "big")


def fnv512_1a(b: bytes) -> bytes:
    return fnv1a(b, 512).to_bytes(64, "big")


# --------------------------------------------------------------------------
# BLAKE-512 (the SHA-3 finalist, NOT BLAKE2b)
# --------------------------------------------------------------------------

_BLAKE_IV = [0x6A09E667F3BCC908, 0xBB67AE8584CAA73B, 0x3C6EF372FE94F82B,
             0xA54FF53A5F1D36F1, 0x510E527FADE682D1, 0x9B05688C2B3E6C1F,
             0x1F83D9ABFB41BD6B, 0x5BE0CD19137E2179]
_BLAKE_U = [0x243F6A8885A308D3, 0x13198A2E03707344, 0xA4093822299F31D0,
            0x082EFA98EC4E6C89, 0x452821E638D01377, 0xBE5466CF34E90C6C,
            0xC0AC29B7C97C50DD, 0x3F84D5B5B5470917, 0x9216D5D98979FB1B,
            0xD1310BA698DFB5AC, 0x2FFD72DBD01ADFB7, 0xB8E1AFED6A267E96,
            0xBA7C9045F12C7F99, 0x24A19947B3916CF7, 0x0801F2E2858EFC16,
            0x636920D871574E69]
_SIGMA = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
    [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
    [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
    [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
    [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
    [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
    [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
    [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
    [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
]


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (64 - n))) & _M64


def _blake_compress(h: list[int], blk: bytes, t: int) -> None:
    m = [int.from_bytes(blk[8 * i:8 * i + 8], "big") for i in range(16)]
    v = h[:] + _BLAKE_U[:8]
    v[12] ^= t & _M64
    v[13] ^= t & _M64
    v[14] ^= (t >> 64) & _M64
    v[15] ^= (t >> 64) & _M64
    for r in range(16):
        s = _SIGMA[r % 10]
        for i, (a, b, c, d) in enumerate(((0, 4, 8, 12), (1, 5, 9, 13), (2, 6, 10, 14),
                                          (3, 7, 11, 15), (0, 5, 10, 15), (1, 6, 11, 12),
                                          (2, 7, 8, 13), (3, 4, 9, 14))):
            p, q = s[2 * i], s[2 * i + 1]
            v[a] = (v[a] + v[b] + (m[p] ^ _BLAKE_U[q])) & _M64
            v[d] = _rotr(v[d] ^ v[a], 32)
            v[c] = (v[c] + v[d]) & _M64
            v[b] = _rotr(v[b] ^ v[c], 25)
            v[a] = (v[a] + v[b] + (m[q] ^ _BLAKE_U[p])) & _M64
            v[d] = _rotr(v[d] ^ v[a], 16)
            v[c] = (v[c] + v[d]) & _M64
            v[b] = _rotr(v[b] ^ v[c], 11)
    for i in range(8):
        h[i] ^= v[i] ^ v[i + 8]


def blake512(data: bytes) -> bytes:
    """BLAKE-512, the SHA-3 finalist. Salt zero."""
    h = _BLAKE_IV[:]
    bitlen = len(data) * 8
    # pad: 0x80, zeros to 112 mod 128, OR 0x01 into that last byte, 128-bit
    # big-endian bit length. When only one byte fits, it is 0x81.
    p = bytearray(data)
    p.append(0x80)
    while len(p) % 128 != 112:
        p.append(0)
    p[-1] |= 0x01
    p += bitlen.to_bytes(16, "big")
    for i in range(len(p) // 128):
        start = i * 1024
        inblock = max(0, min(1024, bitlen - start))
        # t counts message bits through this block; a block of pure padding
        # carries t = 0.
        t = 0 if inblock == 0 else start + inblock
        _blake_compress(h, bytes(p[128 * i:128 * i + 128]), t)
    return b"".join(x.to_bytes(8, "big") for x in h)


# --------------------------------------------------------------------------
# The catalogue. Populated by gate.py, which refuses to add an ungated function.
# --------------------------------------------------------------------------

STDLIB = {
    "sha512": lambda b: hashlib.sha512(b).digest(),
    "sha3_512": lambda b: hashlib.sha3_512(b).digest(),
    "blake2b": lambda b: hashlib.blake2b(b).digest(),
    "shake_256": lambda b: hashlib.shake_256(b).digest(64),
    "shake_128": lambda b: hashlib.shake_128(b).digest(64),
}

PUREPY = {
    "keccak512": keccak512,
    "whirlpool": whirlpool,
    "fnv512_0": fnv512_0,
    "fnv512_1": fnv512_1,
    "fnv512_1a": fnv512_1a,
    "blake512": blake512,
}
