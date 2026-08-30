"""Minimal OpenPGP (RFC 4880) reader: armor, packets, RSA clearsign verify.

Written because gpg is not installed here and because the point of the exercise
is to see the EXACT byte string Cicada hashed, which `gpg --verify` hides.

Verification of a clearsigned message recovers three things an attack can use:
  * the canonicalised bytes that went into the hash (RFC 4880 s7.1: dash-escaping
    removed, trailing whitespace per line removed, lines joined with CRLF, no
    trailing line ending),
  * the hash algorithm Cicada chose, and
  * proof, from the 3301 key, that those exact bytes are what was signed.

No corpus parsing here. Callers hand in `Communication.raw` from solver.corpus.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass

# RFC 4880 s9.4
HASH_ALGOS = {1: "MD5", 2: "SHA1", 3: "RIPEMD160", 8: "SHA256",
              9: "SHA384", 10: "SHA512", 11: "SHA224"}
_HASHLIB = {1: "md5", 2: "sha1", 8: "sha256", 9: "sha384", 10: "sha512",
            11: "sha224"}
# RFC 8017 A.2.4 DigestInfo DER prefixes
_DER = {
    1: bytes.fromhex("3020300c06082a864886f70d020505000410"),
    2: bytes.fromhex("3021300906052b0e03021a05000414"),
    8: bytes.fromhex("3031300d060960864801650304020105000420"),
    9: bytes.fromhex("3041300d060960864801650304020205000430"),
    10: bytes.fromhex("3051300d060960864801650304020305000440"),
    11: bytes.fromhex("302d300d06096086480165030402040500041c"),
}

_ARMOR_HEADER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: ")
_ARMOR = re.compile(
    r"-----BEGIN PGP ([A-Z ]+)-----\r?\n(.*?)\r?\n-----END PGP \1-----",
    re.S,
)


def dearmor(text: str, want: str) -> bytes:
    """Return the binary body of the first `-----BEGIN PGP <want>-----` block."""
    for m in _ARMOR.finditer(text):
        if m.group(1).strip() != want:
            continue
        lines = m.group(2).replace("\r\n", "\n").split("\n")
        # Armor headers run to the first blank line -- blank meaning
        # whitespace-only, which 2012-01-location-numbers relies on.
        for i, ln in enumerate(lines):
            if _ARMOR_HEADER.match(ln):
                continue
            lines = lines[i + 1:] if not ln.strip() else lines[i:]
            break
        lines = [ln for ln in lines if ln.strip()]
        if lines and lines[-1].startswith("="):
            lines = lines[:-1]          # CRC24 checksum line
        return base64.b64decode("".join(lines))
    raise KeyError(f"no PGP {want} block")


@dataclass(frozen=True)
class Packet:
    tag: int
    body: bytes


def packets(data: bytes) -> list[Packet]:
    """Parse old- and new-format packet headers. Partial lengths unsupported."""
    out, i = [], 0
    while i < len(data):
        h = data[i]
        if not h & 0x80:
            raise ValueError(f"bad packet header {h:#x} at {i}")
        i += 1
        if h & 0x40:                                   # new format
            tag = h & 0x3F
            o = data[i]
            if o < 192:
                ln, i = o, i + 1
            elif o < 224:
                ln, i = ((o - 192) << 8) + data[i + 1] + 192, i + 2
            elif o == 255:
                ln, i = int.from_bytes(data[i + 1:i + 5], "big"), i + 5
            else:
                raise ValueError("partial body lengths unsupported")
        else:                                          # old format
            tag, lt = (h >> 2) & 0x0F, h & 0x03
            nbytes = (1, 2, 4)[lt] if lt < 3 else None
            if nbytes is None:
                ln, i = len(data) - i, i
            else:
                ln = int.from_bytes(data[i:i + nbytes], "big")
                i += nbytes
        out.append(Packet(tag, data[i:i + ln]))
        i += ln
    return out


def _mpi(b: bytes, i: int) -> tuple[int, int]:
    bits = int.from_bytes(b[i:i + 2], "big")
    n = (bits + 7) // 8
    return int.from_bytes(b[i + 2:i + 2 + n], "big"), i + 2 + n


@dataclass(frozen=True)
class PublicKey:
    n: int
    e: int
    created: int
    algo: int
    fingerprint: str
    keyid: str
    nbits: int


def parse_public_key(armored: str) -> PublicKey:
    pkts = packets(dearmor(armored, "PUBLIC KEY BLOCK"))
    body = next(p.body for p in pkts if p.tag == 6)
    if body[0] != 4:
        raise ValueError(f"only v4 keys handled, got v{body[0]}")
    created = int.from_bytes(body[1:5], "big")
    algo = body[5]
    n, i = _mpi(body, 6)
    e, _ = _mpi(body, i)
    fp = hashlib.sha1(b"\x99" + len(body).to_bytes(2, "big") + body).hexdigest()
    return PublicKey(n, e, created, algo, fp.upper(), fp[-16:].upper(),
                     n.bit_length())


@dataclass(frozen=True)
class Signature:
    version: int
    sigtype: int
    pubalgo: int
    hashalgo: int
    hashed: bytes
    unhashed: bytes
    left16: bytes
    sig: int
    issuer: str


def parse_signature(armored: str) -> Signature:
    pkts = packets(dearmor(armored, "SIGNATURE"))
    b = next(p.body for p in pkts if p.tag == 2)
    if b[0] != 4:
        raise ValueError(f"only v4 signatures handled, got v{b[0]}")
    sigtype, pubalgo, hashalgo = b[1], b[2], b[3]
    hlen = int.from_bytes(b[4:6], "big")
    hashed = b[6:6 + hlen]
    j = 6 + hlen
    ulen = int.from_bytes(b[j:j + 2], "big")
    unhashed = b[j + 2:j + 2 + ulen]
    j += 2 + ulen
    left16 = b[j:j + 2]
    sig, _ = _mpi(b, j + 2)
    issuer = ""
    for typ, data in _subpackets(unhashed) + _subpackets(hashed):
        if typ == 16 and len(data) == 8:
            issuer = data.hex().upper()
    return Signature(4, sigtype, pubalgo, hashalgo, hashed, unhashed,
                     left16, sig, issuer)


def _subpackets(area: bytes) -> list[tuple[int, bytes]]:
    out, i = [], 0
    while i < len(area):
        o = area[i]
        if o < 192:
            ln, i = o, i + 1
        elif o < 255:
            ln, i = ((o - 192) << 8) + area[i + 1] + 192, i + 2
        else:
            ln, i = int.from_bytes(area[i + 1:i + 5], "big"), i + 5
        out.append((area[i] & 0x7F, area[i + 1:i + ln]))
        i += ln
    return out


CLEARSIGNED_BEGIN = "-----BEGIN PGP SIGNED MESSAGE-----"
SIGNATURE_BEGIN = "-----BEGIN PGP SIGNATURE-----"


def clearsigned_body(raw: str) -> str:
    """Return a clearsigned message body with its source whitespace intact.

    OpenPGP permits the blank line after the ``Hash:`` headers to contain
    whitespace. Two preserved 2012 messages use a single space there, while
    the 2013 morse carrier begins its signed body with an additional empty
    line. Parse the envelope by lines so both cases remain distinguishable.

    The line ending immediately before the signature delimiter belongs to the
    clearsign framework and is removed. Every other body byte represented by
    the decoded string, including leading and trailing whitespace, is kept.
    """
    marker = raw.find(CLEARSIGNED_BEGIN)
    if marker < 0:
        raise ValueError("no PGP SIGNED MESSAGE block")
    cursor = marker + len(CLEARSIGNED_BEGIN)
    if raw.startswith("\r\n", cursor):
        cursor += 2
    elif raw.startswith("\n", cursor):
        cursor += 1
    else:
        raise ValueError("PGP SIGNED MESSAGE marker is not line terminated")

    while True:
        line_end = raw.find("\n", cursor)
        if line_end < 0:
            raise ValueError("clearsigned message has no body separator")
        line = raw[cursor:line_end]
        if line.endswith("\r"):
            line = line[:-1]
        cursor = line_end + 1
        if _ARMOR_HEADER.match(line):
            continue
        if not line.strip():
            break
        raise ValueError(f"unexpected clearsign header line: {line!r}")

    signature = re.search(
        rf"(?m)^{re.escape(SIGNATURE_BEGIN)}\r?$", raw[cursor:]
    )
    if signature is None:
        raise ValueError("no PGP SIGNATURE block")
    body = raw[cursor:cursor + signature.start()]
    if body.endswith("\r\n"):
        return body[:-2]
    if body.endswith("\n"):
        return body[:-1]
    if body:
        raise ValueError("PGP SIGNATURE marker is not on a new line")
    return body


def cleartext_signed_bytes(raw: str) -> bytes:
    """The exact bytes hashed for a clearsigned message (RFC 4880 s7.1).

    Dash-escaping removed, trailing whitespace stripped from every line, lines
    joined with CRLF, and NO line ending after the last line.
    """
    body = clearsigned_body(raw).replace("\r\n", "\n")
    lines = []
    for ln in body.split("\n"):
        if ln.startswith("- "):
            ln = ln[2:]
        elif ln == "-":
            ln = ""
        lines.append(ln.rstrip(" \t"))
    return "\r\n".join(lines).encode("utf-8")


def hash_input(signed: bytes, s: Signature) -> bytes:
    """signed data || hashed subpacket area || v4 trailer."""
    head = bytes([4, s.sigtype, s.pubalgo, s.hashalgo]) + \
        len(s.hashed).to_bytes(2, "big") + s.hashed
    return signed + head + b"\x04\xff" + len(head).to_bytes(4, "big")


def rsa_verify(key: PublicKey, digest: bytes, hashalgo: int, sig: int) -> bool:
    k = (key.nbits + 7) // 8
    m = pow(sig, key.e, key.n).to_bytes(k, "big")
    t = _DER[hashalgo] + digest
    expect = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return m == expect


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str
    hashalgo: str
    sigtype: int
    signed: bytes
    digest: str
    issuer: str


def verify_cleartext(raw: str, key: PublicKey) -> Verdict:
    s = parse_signature(raw)
    signed = cleartext_signed_bytes(raw)
    algo = _HASHLIB.get(s.hashalgo)
    if algo is None:
        return Verdict(False, f"unknown hash algo {s.hashalgo}", "?",
                       s.sigtype, signed, "", s.issuer)
    d = hashlib.new(algo, hash_input(signed, s)).digest()
    if d[:2] != s.left16:
        return Verdict(False, f"left16 {d[:2].hex()} != {s.left16.hex()}",
                       HASH_ALGOS[s.hashalgo], s.sigtype, signed, d.hex(),
                       s.issuer)
    if s.issuer and s.issuer != key.keyid:
        return Verdict(False, f"issuer {s.issuer} != key {key.keyid}",
                       HASH_ALGOS[s.hashalgo], s.sigtype, signed, d.hex(),
                       s.issuer)
    ok = rsa_verify(key, d, s.hashalgo, s.sig)
    return Verdict(ok, "GOOD" if ok else "RSA check failed",
                   HASH_ALGOS[s.hashalgo], s.sigtype, signed, d.hex(),
                   s.issuer)
