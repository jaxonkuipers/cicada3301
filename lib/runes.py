"""One canonical form for rune text, whatever notation it was written in.

People write the same rune sequence three ways -- as runic codepoints, as
Gematria Primus transliterations, and as index numbers -- so a grep in one
notation misses every message that used another. Everything here collapses to
the same canonical string, one character per rune index, and that is what the
Discord index stores and searches.

The alphabet and the transliteration table come from `lib.corpus`. Nothing here
keeps a private copy of the Gematria Primus.
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable, Iterator
from typing import NamedTuple

from lib import corpus

_GP = corpus.load().gp

RUNE_TO_INDEX = {r: i for i, r in enumerate(_GP.runes)}
TRANSLIT = _GP.spellings
MULTI_TOKENS = frozenset(t for t in TRANSLIT if len(t) > 1)
LAST_INDEX = _GP.N - 1

# One symbol per rune index. Any single-character alphabet works; these survive
# FTS5's trigram tokenizer without being split or folded.
_ALPHABET = string.ascii_lowercase + string.digits
if _GP.N > len(_ALPHABET):
    raise RuntimeError(f"no single-character alphabet for {_GP.N} runes")
CANON = _ALPHABET[: _GP.N]

_RUNE = f"[{corpus.RUNIC_FIRST}-{corpus.RUNIC_LAST}]"
RUNE_RUN = re.compile(_RUNE + "+")
# Rune text is normally printed with separators -- `-` between words, `.`
# between clauses, `/` at a line end -- so a contiguous-run index misses any
# query that spans one. Both forms are indexed.
RUNE_JOINED = re.compile(f"{_RUNE}+(?:[-./|\\s]+{_RUNE}+)+")
_WORDS = re.compile(r"[A-Za-z]+")
_TRANSLIT_SEP = frozenset("-. /")
_DIGIT_SPLIT = re.compile(r"[0-9]+|[^0-9]+")
_NUMERIC_SEP = re.compile(r"[\s,;:\[\]()\-|/]+")

# Below these lengths the notation is guesswork rather than rune text.
MIN_RUNIC = 2
MIN_JOINED = 3
MIN_NUMERIC = 4
MIN_TRANSLIT = 4


class Run(NamedTuple):
    """A stretch of rune text found in prose."""

    notation: str  # runic | runic-joined | numeric | translit
    raw: str  # as written
    canon: str  # one character per rune index


def canon_of(indices: Iterable[int]) -> str:
    return "".join(CANON[i] for i in indices)


def _runic(text: str) -> Iterator[Run]:
    for m in RUNE_RUN.finditer(text):
        run = m.group(0)
        idx = [RUNE_TO_INDEX[c] for c in run if c in RUNE_TO_INDEX]
        if len(idx) >= MIN_RUNIC:
            yield Run("runic", run, canon_of(idx))


def _runic_joined(text: str) -> Iterator[Run]:
    """Rune runs broken only by separators, rejoined: ᛋᚻᛖᚩᚷᛗᛡᚠ-ᛋᚣᛖᛝᚳ -> one run."""
    for m in RUNE_JOINED.finditer(text):
        span = m.group(0)
        idx = [RUNE_TO_INDEX[c] for c in span if c in RUNE_TO_INDEX]
        if len(idx) >= MIN_JOINED:
            yield Run("runic-joined", span, canon_of(idx))


def _numeric(text: str) -> Iterator[Run]:
    """Runs of >=4 integers all in 0..28, e.g. '[19, 21, 23, 27, 2, 14]'.

    ASCII digits only: `\\d` also matches superscripts and other scripts'
    digits, which int() then refuses.
    """
    run: list[int] = []
    raw: list[str] = []

    def take() -> Iterator[Run]:
        if len(run) >= MIN_NUMERIC:
            yield Run("numeric", " ".join(raw), canon_of(run))
        run.clear()
        raw.clear()

    for m in _DIGIT_SPLIT.finditer(text):
        tok = m.group(0)
        if tok[0] in string.digits:  # not .isdigit(): '⁶' passes that
            if len(tok) <= 2 and int(tok) <= LAST_INDEX:
                run.append(int(tok))
                raw.append(tok)
                continue
        elif _NUMERIC_SEP.fullmatch(tok):
            continue
        yield from take()  # anything else ends the run
    yield from take()


def _translit(text: str) -> Iterator[Run]:
    """Runs of >=4 explicitly separated GP transliterations, e.g. 'F-U-TH-O-R-C'.

    Scanned token by token rather than as one regex match, so a run reads out of
    the middle of a sentence: `so F-U-TH-O-R-C then` is a hit on six tokens, not
    a miss on eight.

    Requires real digraphs present, otherwise ordinary prose full of single
    letters produces constant false hits.
    """
    stretch: list[re.Match[str]] = []

    def take() -> Iterator[Run]:
        toks = [m.group(0).upper() for m in stretch]
        multi = sum(t in MULTI_TOKENS for t in toks)
        if len(toks) >= MIN_TRANSLIT and (multi >= 2 or (len(toks) >= 6 and multi >= 1)):
            raw = text[stretch[0].start() : stretch[-1].end()]
            yield Run("translit", raw, canon_of(TRANSLIT[t] for t in toks))
        stretch.clear()

    prev_end = -1
    for m in _WORDS.finditer(text):
        # One separator character and nothing else keeps the run going.
        adjacent = (
            bool(stretch)
            and m.start() - prev_end == 1
            and text[prev_end] in _TRANSLIT_SEP
        )
        prev_end = m.end()
        if m.group(0).upper() not in TRANSLIT:
            yield from take()
            continue
        if not adjacent:
            yield from take()
        stretch.append(m)
    yield from take()


def extract(text: str) -> Iterator[Run]:
    """Every rune sequence in `text`, in each notation it might be written in."""
    yield from _runic(text)
    yield from _runic_joined(text)
    yield from _numeric(text)
    yield from _translit(text)


def canonicalise_query(q: str) -> tuple[str, str]:
    """Rune query in any notation -> (canonical string, notation detected).

    Raises ValueError if it reads as none of them.
    """
    runes = [RUNE_TO_INDEX[c] for c in q if c in RUNE_TO_INDEX]
    if runes:
        return canon_of(runes), "runic"

    nums = re.findall(r"[0-9]{1,2}", q)
    if len(nums) >= 2 and all(int(n) <= LAST_INDEX for n in nums):
        return canon_of(int(n) for n in nums), "numeric"

    toks = [t for t in re.split(r"[^A-Za-z]+", q.upper()) if t]
    if toks and all(t in TRANSLIT for t in toks):
        return canon_of(TRANSLIT[t] for t in toks), "translit"

    raise ValueError(
        f"cannot read {q!r} as runes.\n"
        "  give runic codepoints (ᚠᚢᚦ), indices (0 1 2), or "
        "transliterations (F-U-TH)."
    )
