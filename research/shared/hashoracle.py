"""page-56's SHA-512 digest as a decision procedure for candidate plaintext.

Shared but NOT load-bearing: `lib/` is held to a higher bar. Import from an
attack, never from `lib/` or `tools/`.

page-56 prints 128 hex characters. If that digest is a hash of the book's
plaintext, then it makes a candidate DECIDABLE -- no fitness score, no judgement
call, one bit. What has been missing is the other half of the oracle: the byte
string. A rune stream is not bytes until somebody says which bytes, and "the
plaintext" admits dozens of renderings that hash to dozens of unrelated digests.

So this module does not guess. It enumerates the renderings explicitly
(`encodings`), crosses them with the 512-bit hash functions (`HASHES`), and
`identify` reports WHICH pair fired. The value is that the space is written down
and reusable: a future candidate is checked against all of it in one call, and
the conventions this repo has ruled out are the ones listed here.

    from research.shared import hashoracle as ho
    ho.verify(candidate_runetext)          # -> bool, against page-56
    ho.identify(candidate_runetext)        # -> 'translit.upper/sha512' or None

Two conventions are measured directly from Cicada's authenticated carriers:

  * what Cicada SIGNS is RFC 4880 canonical text -- CRLF line endings, trailing
    whitespace stripped per line, dash-escaping removed, and NO terminator after
    the last line. 36 of 36 signed communications verify under exactly that and
    0 of 36 under LF or with a trailing CRLF.
  * what Cicada HEX-ENCODES AND XORS is the raw file as stored -- LF endings,
    trailing newline present. Proven by the three 991-byte blocks of
    2014-01-liber-primus-hash-block, whose XOR is the 991-byte armored file
    2014-01-signed-ciphertext.asc byte for byte.

Those are different byte strings, so both line-ending conventions are carried
here rather than one being assumed.

Nothing here proves page-56 hashes the plaintext at all. The community's
standing reading is that it hashes a hidden-service address; `verify` is
agnostic and takes any bytes via `identify_bytes`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable

from lib.corpus import RuneText
from research.shared import hashes512

# --------------------------------------------------------------------------
# The 512-bit hash functions. Only 64-byte outputs can match page-56's 128 hex
# characters, which is what excludes sha256 and friends from the family.
# --------------------------------------------------------------------------

# 11 functions, every one gated against a published vector or against hashlib
# in tests/test_shared_hashoracle.py. `hashes512` supplies the seven `hashlib`
# does not ship. NOTHING enters this map ungated: a silently wrong hash turns a
# negative result into a lie about coverage.
#
# `keccak512` is NOT `sha3_512`. SHA-3 was standardised in August 2015 and
# changed Keccak's domain-separation padding from 0x01 to 0x06; LP2 was printed
# in January 2014, so original Keccak is the period-correct function. Both are
# carried, separately named.
#
# The community's own tool tried 18 (`discord.db` message 53158). The
# nine still missing -- JH, Skein, Grostl, CubeHash, Streebog-512, MD6-512, LSH,
# Whirlpool-0, Whirlpool-T -- each need a constant table that cannot be derived
# from the spec, so no gate here would catch a transcription slip. Left out on
# purpose rather than added unverified.
HASHES: dict[str, Callable[[bytes], bytes]] = {
    "sha512": lambda b: hashlib.sha512(b).digest(),
    "sha3_512": lambda b: hashlib.sha3_512(b).digest(),
    "blake2b": lambda b: hashlib.blake2b(b).digest(),
    "shake_256": lambda b: hashlib.shake_256(b).digest(64),
    "shake_128": lambda b: hashlib.shake_128(b).digest(64),
    "keccak512": hashes512.keccak512,
    "whirlpool": hashes512.whirlpool,
    "blake512": hashes512.blake512,
    "fnv512_0": hashes512.fnv512_0,
    "fnv512_1": hashes512.fnv512_1,
    "fnv512_1a": hashes512.fnv512_1a,
}


def page56_digest(c) -> str:
    """The 128 hex characters printed on page-56, from the corpus.

    Held in `RuneText.other` split across five `/`-delimited runs, which is how
    the transcription preserves the line breaks. Derived here rather than
    written down so it cannot drift away from the corpus.
    """
    runs = [s for _, s in c.page("page-56").text().other if len(s) > 2]
    if len(runs) != 1:
        raise ValueError(f"expected one long run on page-56, got {len(runs)}")
    digest = runs[0].replace("/", "")
    if len(digest) != 128 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"page-56 run is not 128 hex chars: {digest!r}")
    return digest


# --------------------------------------------------------------------------
# Renderings of a rune stream as bytes
# --------------------------------------------------------------------------

# The transcription's marks, by what they separate. `-` is a word break and `/`
# a printed line break; the rest are clause and paragraph structure.
_WORD, _LINE = "-", "/"


def _segments(t: RuneText, mark: str) -> list[list[int]]:
    out: list[list[int]] = [[]]
    for i, ix in enumerate(t.indices):
        out[-1].append(ix)
        if mark in t.marks_after[i]:
            out.append([])
    return [s for s in out if s]


def _translit(gp, ixs: Iterable[int]) -> str:
    return gp.unspell(list(ixs))


def encodings(t: RuneText) -> dict[str, bytes]:
    """Every byte rendering of `t` this repo considers plausible.

    Named `family.detail`, and the name is the deliverable: a candidate that
    fails against all of these has been excluded from exactly this list and no
    more. Add to it rather than testing a convention privately.
    """
    gp = t.gp
    ix = list(t.indices)
    runes = gp.to_runes(ix)
    words = _segments(t, _WORD)
    lines = _segments(t, _LINE)
    tr = _translit(gp, ix)
    primes = [gp.primes[i] for i in ix]

    out: dict[str, bytes] = {}

    # -- rune glyphs, as Unicode ------------------------------------------
    for enc, tag in (("utf-8", "utf8"), ("utf-16-le", "utf16le"),
                     ("utf-16-be", "utf16be"), ("utf-32-le", "utf32le"),
                     ("utf-32-be", "utf32be")):
        out[f"runes.{tag}"] = runes.encode(enc)
    out["runes.utf8.words.space"] = " ".join(
        gp.to_runes(w) for w in words).encode()
    out["runes.utf8.lines.lf"] = "\n".join(
        gp.to_runes(ln) for ln in lines).encode()
    out["runes.utf8.lines.crlf"] = "\r\n".join(
        gp.to_runes(ln) for ln in lines).encode()

    # -- Latin transliteration ---------------------------------------------
    out["translit.upper"] = tr.encode()
    out["translit.lower"] = tr.lower().encode()
    out["translit.words.space"] = " ".join(
        _translit(gp, w) for w in words).encode()
    out["translit.words.space.lower"] = " ".join(
        _translit(gp, w) for w in words).lower().encode()
    out["translit.lines.lf"] = "\n".join(
        _translit(gp, ln) for ln in lines).encode()
    out["translit.lines.crlf"] = "\r\n".join(
        _translit(gp, ln) for ln in lines).encode()

    # -- rune indices -------------------------------------------------------
    out["index.bytes"] = bytes(ix)
    out["index.dec.space"] = " ".join(map(str, ix)).encode()
    out["index.dec.lf"] = "\n".join(map(str, ix)).encode()
    out["index.dec.comma"] = ",".join(map(str, ix)).encode()
    out["index.hex"] = bytes(ix).hex().encode()
    out["index1.bytes"] = bytes(i + 1 for i in ix)
    out["index1.dec.space"] = " ".join(str(i + 1) for i in ix).encode()

    # -- gematria primes ----------------------------------------------------
    out["prime.bytes"] = bytes(primes)
    out["prime.dec.space"] = " ".join(map(str, primes)).encode()
    out["prime.dec.lf"] = "\n".join(map(str, primes)).encode()

    # -- hex-of-text, the form Cicada actually published blobs in -----------
    out["hex.runes.utf8"] = runes.encode().hex().encode()
    out["hex.translit.upper"] = tr.encode().hex().encode()

    # -- trailing-newline variants -----------------------------------------
    # Cicada's own hex-encoded object kept its trailing newline; its signed
    # object did not. Both are live, so carry both for every text rendering.
    for name in [k for k in out if not k.startswith(("index.b", "index1.b",
                                                     "prime.b", "runes.utf16",
                                                     "runes.utf32"))]:
        out[f"{name}+lf"] = out[name] + b"\n"
        out[f"{name}+crlf"] = out[name] + b"\r\n"
    return out


# --------------------------------------------------------------------------
# The oracle
# --------------------------------------------------------------------------

def identify_bytes(data: bytes, digest: str) -> str | None:
    """Which hash function takes `data` to `digest`, if any."""
    want = bytes.fromhex(digest)
    for hname, fn in HASHES.items():
        if fn(data) == want:
            return hname
    return None


_TABLE_CACHE: dict[tuple, dict[str, str]] = {}


def digest_table(t: RuneText) -> dict[str, str]:
    """`{'encoding/hash': hexdigest}` over the whole family, memoised.

    One call is `len(encodings(t)) * len(HASHES)` hashes, and seven of the
    eleven functions are pure Python. A caller checking MANY digests against
    ONE candidate -- which is exactly what a planted-digest control does --
    must build this once rather than call `identify` per digest, or the work
    is quadratic in the family size.
    """
    key = (t.indices, t.marks_after)
    table = _TABLE_CACHE.get(key)
    if table is None:
        table = {
            f"{ename}/{hname}": fn(data).hex()
            for ename, data in encodings(t).items()
            for hname, fn in HASHES.items()
        }
        _TABLE_CACHE[key] = table
    return table


def identify(t: RuneText, digest: str) -> str | None:
    """`'encoding/hash'` if some pair in the family takes `t` to `digest`.

    None means excluded from THIS family -- `len(encodings(t)) *
    len(HASHES)` renderings -- and says nothing beyond it.
    """
    want = digest.lower()
    for pair, hexdigest in digest_table(t).items():
        if hexdigest == want:
            return pair
    return None


def verify(t: RuneText, digest: str) -> bool:
    return identify(t, digest) is not None


def coverage(t: RuneText) -> int:
    """How many (encoding, hash) pairs a single `verify` call tests."""
    return len(encodings(t)) * len(HASHES)


# --------------------------------------------------------------------------
# Cicada's measured signing convention, for hashing a text the way Cicada did
# --------------------------------------------------------------------------

def rfc4880_canonical(text: str) -> bytes:
    """The bytes Cicada's signatures actually cover, from a plain LF string.

    36 of 36 signed communications verify under this and 0 of 36 under LF or
    with a trailing terminator. Dash-escaping is a clearsign transport artifact
    and is assumed already removed here.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    return "\r\n".join(ln.rstrip(" \t") for ln in lines).encode("utf-8")
