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

import functools
import re
import string
from collections.abc import Iterable, Iterator
from typing import NamedTuple

from lib import corpus

# One symbol per rune index. Any single-character alphabet works; these survive
# FTS5's trigram tokenizer without being split or folded.
_ALPHABET = string.ascii_lowercase + string.digits


class _Tables(NamedTuple):
    rune_to_index: dict[str, int]
    translit: dict[str, int]
    multi_tokens: frozenset[str]
    last_index: int
    canon: str


@functools.cache
def _tables() -> _Tables:
    """The Gematria Primus, loaded on first use.

    Built lazily rather than at import: reading corpus/ as a side effect of
    `import lib.runes` makes every importer -- `dsearch --help` included --
    fail when the corpus is absent, for a table it may never touch.
    """
    gp = corpus.load().gp
    if gp.N > len(_ALPHABET):
        raise RuntimeError(f"no single-character alphabet for {gp.N} runes")
    translit = gp.spellings
    return _Tables(
        rune_to_index={r: i for i, r in enumerate(gp.runes)},
        translit=translit,
        multi_tokens=frozenset(t for t in translit if len(t) > 1),
        last_index=gp.N - 1,
        canon=_ALPHABET[: gp.N],
    )


_RUNE = f"[{corpus.RUNIC_FIRST}-{corpus.RUNIC_LAST}]"
RUNE_RUN = re.compile(_RUNE + "+")
# Rune text is normally printed with separators -- `-` between words, `.`
# between clauses, `/` at a line end -- so a contiguous-run index misses any
# query that spans one. Both forms are indexed.
#
# What does NOT join: a newline, or every row of a pasted rune grid would fuse
# into one sequence that never existed; and a `|`, which is that same grid's
# COLUMN separator, so `| ᚠᚢᚦ | ᚩᚱᚳ | ᚷᚹᚻ |` was reading three cells as nine
# adjacent runes. `_TRANSLIT_SEP` below always omitted `|`; the two extractors
# disagreed about the same character. Spaces and tabs still join -- a tab is
# whitespace between tokens exactly as a space is, and a space already joins.
RUNE_JOINED = re.compile(f"{_RUNE}+(?:[-./ \\t]+{_RUNE}+)+")
_WORDS = re.compile(r"[A-Za-z]+")
_TRANSLIT_SEP = frozenset("-. /")
_DIGIT_SPLIT = re.compile(r"[0-9]+|[^0-9]+")
_NUMERIC_SEP = re.compile(r"[\s,;:\[\]()\-|/]+")
# A `-` immediately before a digit but not immediately after one is a MINUS
# SIGN, not a separator: `8 -2`, `0,-1`, `-4 3`. `19-21-23` is index notation
# and stays. Without this the sign is eaten and a difference vector or a
# +/-1 matrix indexes as rune text that was never written.
_SIGNED = re.compile(r"(?<![0-9])-[0-9]")
_ROW_BREAK = frozenset("\n\r")
# A `|` is a column separator, and a closing bracket followed by an opening one
# is the boundary between two containers. Either means the digits on each side
# were printed as separate sequences: `[12, 18, 25] | [6, 7, 16]` is two
# vectors, and the shipped index had 19 rows fusing exactly that way.
_GROUP_BREAK = re.compile(r"\||[\])][^\[(]*[\[(]")

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
    canon = _tables().canon
    return "".join(canon[i] for i in indices)


def indices_of(canon: str) -> list[int]:
    """Canonical string -> rune indices. Inverse of `canon_of`.

    The canonical form is deliberately opaque (`abc`), so a caller that wants
    to SHOW what it searched -- and catch a query that was read as the wrong
    notation -- needs this to print it back as indices.
    """
    table = _tables().canon
    return [table.index(c) for c in canon]


def _gp_fragments(span: str, min_len: int) -> Iterator[tuple[str, list[int]]]:
    """GP-rune stretches of `span`, broken at any rune outside the GP 29.

    A non-GP rune (Younger Futhark kaun in a pasted comparison table, say) is a
    break, not a skip: skipping it would assert an adjacency the source text
    does not contain. Separator characters never break.
    """
    rune_to_index = _tables().rune_to_index
    start = end = None
    idx: list[int] = []
    for j, c in enumerate(span):
        if c in rune_to_index:
            if start is None:
                start = j
            idx.append(rune_to_index[c])
            end = j + 1
        elif corpus.is_rune(c):
            if len(idx) >= min_len:
                yield span[start:end], idx
            start = end = None
            idx = []
    if len(idx) >= min_len:
        yield span[start:end], idx


def _runic(text: str) -> Iterator[Run]:
    for m in RUNE_RUN.finditer(text):
        for raw, idx in _gp_fragments(m.group(0), MIN_RUNIC):
            yield Run("runic", raw, canon_of(idx))


def _runic_joined(text: str) -> Iterator[Run]:
    """Rune runs broken only by separators, rejoined: ᛋᚻᛖᚩᚷᛗᛡᚠ-ᛋᚣᛖᛝᚳ -> one run."""
    for m in RUNE_JOINED.finditer(text):
        for raw, idx in _gp_fragments(m.group(0), MIN_JOINED):
            yield Run("runic-joined", raw, canon_of(idx))


def _numeric_sep(tok: str) -> bool:
    """True if `tok` separates two indices rather than ending the run.

    A newline ends it. The rows of a pasted grid are separate sequences, the
    same rule `RUNE_JOINED` follows above -- `\\s` in `_NUMERIC_SEP` would
    otherwise fuse a 6x6 grid into one 36-rune sequence that never existed.

    A `|` or a `] [` ends it: see `_GROUP_BREAK`. Those are the same
    fabrication as the newline -- two things printed apart, indexed as one.

    A `-` ends it too, unless the token is exactly `-`. Being the whole
    non-digit token between two digit tokens, a lone `-` is `19-21-23`, index
    notation; a `-` with anything else around it (` -`, `,-`, `--`, ` - `) is
    the minus of `8 -2` or `0,-1`, and reading it as a separator turns a
    difference vector into runes.
    """
    return (
        _NUMERIC_SEP.fullmatch(tok) is not None
        and not (_ROW_BREAK & set(tok))
        and not _GROUP_BREAK.search(tok)
        and ("-" not in tok or tok == "-")
    )


def _numeric(text: str) -> Iterator[Run]:
    """Runs of >=4 integers all in 0..28, e.g. '[19, 21, 23, 27, 2, 14]'.

    ASCII digits only: `\\d` also matches superscripts and other scripts'
    digits, which int() then refuses. See `_numeric_sep` for what holds a run
    together: neither a newline nor a minus sign does.
    """
    run: list[int] = []
    span: list[int] = []  # [start, end) of the run in `text`

    def take() -> Iterator[Run]:
        if len(run) >= MIN_NUMERIC:
            yield Run("numeric", text[span[0] : span[1]], canon_of(run))
        run.clear()
        span.clear()

    signed = False  # the next digit token is a magnitude, not an index
    for m in _DIGIT_SPLIT.finditer(text):
        tok = m.group(0)
        if tok[0] in string.digits:  # not .isdigit(): '⁶' passes that
            if not signed and len(tok) <= 2 and int(tok) <= _tables().last_index:
                run.append(int(tok))
                span[:] = [span[0] if span else m.start(), m.end()]
                continue
            # Breaking before `-2` is not enough: its `2` must not open the
            # next run either, or '8 -2 3 18 9 -4' still indexes '2 3 18 9'.
            signed = False
        elif _numeric_sep(tok):
            signed = False
            continue
        else:
            signed = tok.endswith("-")
        yield from take()  # anything else ends the run
    yield from take()


def _translit(text: str) -> Iterator[Run]:
    """Runs of >=4 explicitly separated GP transliterations, e.g. 'F-U-TH-O-R-C'.

    Scanned token by token rather than as one regex match, so a run reads out of
    the middle of a sentence: `so F-U-TH-O-R-C then` is a hit on six tokens, not
    a miss on eight.

    A run joined by `-` or `.` is explicit notation and indexes at any length:
    F-U-L-M and I-N-T-R-O-D-U-C-T are citations, digraphs or not. A run held
    together by spaces alone is ambiguous -- prose can string single letters
    together -- so it must show real digraphs to count.
    """
    translit, multi_tokens = _tables().translit, _tables().multi_tokens
    stretch: list[re.Match[str]] = []
    seps: list[str] = []

    def take() -> Iterator[Run]:
        toks = [m.group(0).upper() for m in stretch]
        multi = sum(t in multi_tokens for t in toks)
        punctuated = any(s in "-." for s in seps)
        if len(toks) >= MIN_TRANSLIT and (
            punctuated or multi >= 2 or (len(toks) >= 6 and multi >= 1)
        ):
            raw = text[stretch[0].start() : stretch[-1].end()]
            yield Run("translit", raw, canon_of(translit[t] for t in toks))
        stretch.clear()
        seps.clear()

    prev_end = -1
    for m in _WORDS.finditer(text):
        # One separator character and nothing else keeps the run going.
        adjacent = (
            bool(stretch)
            and m.start() - prev_end == 1
            and text[prev_end] in _TRANSLIT_SEP
        )
        sep = text[prev_end] if adjacent else ""
        prev_end = m.end()
        if m.group(0).upper() not in translit:
            yield from take()
            continue
        if not adjacent:
            yield from take()
        else:
            # `adjacent` already required a non-empty stretch, so the guard
            # this used to carry (`elif stretch:`) could never be false.
            seps.append(sep)
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

    Raises ValueError if it reads as none of them, or as more than one.

    Nothing is silently dropped, in ANY branch. Keeping only the characters
    that happened to parse turns `F-U-TH-ᚠ` into a one-rune query, `F-U-TH-2`
    into a three-rune one and `hello ᚠᚡ world` into another, and then answers
    a question nobody asked. Each branch below refuses what it cannot read
    rather than reading around it.
    """
    t = _tables()
    runic = [c for c in q if corpus.is_rune(c)]
    if runic:
        foreign = sorted({c for c in runic if c not in t.rune_to_index})
        if foreign:
            raise ValueError(
                f"{''.join(foreign)} is outside the Gematria Primus 29.\n"
                "  drop it or write the sequence in indices: '0 1 2'."
            )
        stray = sorted({c for c in q if c.isascii() and c.isalnum()})
        if stray:
            raise ValueError(
                f"{q!r} mixes runes with {''.join(stray)!r}.\n"
                "  give one notation: runic codepoints, indices, "
                "or transliterations."
            )
        return canon_of(t.rune_to_index[c] for c in runic), "runic"

    toks = [x for x in _NUMERIC_SEP.split(q) if x]
    if toks and all(x.isascii() and x.isdigit() for x in toks):
        # All-digit queries must be explicitly separated indices: reading
        # '2025' as runes 20,25 or '123' as 12,3 silently answers a question
        # nobody asked.
        # `_SIGNED` first: splitting on `_NUMERIC_SEP` eats the minus of
        # '0,-2,-4,-6', leaving four clean-looking indices that the source
        # never wrote. Same rule the extractor applies (see `_numeric_sep`).
        if (
            len(toks) >= 2
            and not _SIGNED.search(q)
            and all(len(x) <= 2 and int(x) <= t.last_index for x in toks)
        ):
            return canon_of(int(x) for x in toks), "numeric"
        raise ValueError(
            f"cannot read {q!r} as rune indices.\n"
            "  separate them explicitly, one per rune in 0..28: '0 1 2' or '19-21-23'."
        )

    words = [x for x in re.split(r"[^A-Za-z]+", q.upper()) if x]
    if words and all(x in t.translit for x in words):
        # Splitting on non-letters discards digits, so 'F-U-TH-2' and
        # 'F-U-TH 3301' would come back as the same three-rune query. Refuse
        # the mixture the way the runic branch above does.
        digits = sorted({c for c in q if c.isascii() and c.isdigit()})
        if digits:
            raise ValueError(
                f"{q!r} mixes transliterations with {''.join(digits)!r}.\n"
                "  give one notation: runic codepoints, indices, "
                "or transliterations."
            )
        return canon_of(t.translit[x] for x in words), "translit"

    raise ValueError(
        f"cannot read {q!r} as runes.\n"
        "  give runic codepoints (ᚠᚢᚦ), indices (0 1 2), or "
        "transliterations (F-U-TH)."
    )
