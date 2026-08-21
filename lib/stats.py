"""Statistics over rune-index streams.

Everything takes sequences of ints in 0..28. The constants quoted in
AGENTS.md (unsolved IoC 1.000, doublet rate 0.66%) are computed by exactly
these functions; re-derive them from `corpus.load().unsolved.indices` rather
than trusting prose.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

N = 29


def counts(text: Sequence[int]) -> Counter:
    return Counter(text)


def frequencies(text: Sequence[int]) -> list[float]:
    """Per-rune relative frequency, indexed 0..28."""
    c = Counter(text)
    n = len(text) or 1
    return [c[i] / n for i in range(N)]


def ioc(text: Sequence[int]) -> float:
    """Index of coincidence, normalised so uniform random ~= 1.0.

    English through the Gematria Primus measures ~1.78; the unsolved corpus
    measures 1.000 overall and per section.
    """
    n = len(text)
    if n < 2:
        return 0.0
    c = Counter(text)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1)) * N


def periodic_ioc(text: Sequence[int], period: int) -> float:
    """Mean IoC of the `period` cosets: text[0::p], text[1::p], ...

    A repeating key of length p leaves each coset monoalphabetic, so the
    right period spikes toward plaintext IoC while wrong ones stay flat --
    ONLY for uninterrupted ciphers. Interrupters hold the keystream while
    positions advance, desynchronising the cosets: on 0.1's real ciphertext
    (key length 8, 11 interrupters in 515 runes) the true period measures
    1.180 while period 9 measures 1.281. No spike at any period does not
    exclude an interrupted periodic key.
    """
    cosets = [text[i::period] for i in range(period)]
    vals = [ioc(cs) for cs in cosets if len(cs) >= 2]
    return sum(vals) / len(vals) if vals else 0.0


def doublets(text: Sequence[int]) -> int:
    """Adjacent equal pairs. Uniform random expects n/29 ~= 3.45%."""
    return sum(1 for a, b in zip(text, text[1:], strict=False) if a == b)


def doublet_rate(text: Sequence[int]) -> float:
    return doublets(text) / (len(text) - 1) if len(text) > 1 else 0.0


def entropy(text: Sequence[int]) -> float:
    """Shannon entropy in bits per rune (log2(29) ~= 4.86 is flat)."""
    n = len(text)
    if not n:
        return 0.0
    return -sum(
        (v / n) * math.log2(v / n) for v in Counter(text).values()
    )


def chi_squared(text: Sequence[int], reference: Sequence[float]) -> float:
    """Fit of `text` against a reference distribution (see fitness module
    for reference frequencies). Lower is closer.

    Empty text scores `inf`, not 0.0 and not a ZeroDivisionError: lower is
    better here, so the degenerate candidate must sort last, the same way
    `ioc` returns 0.0 to sort a degenerate candidate last under higher-is-
    better. A sweep that hits an empty candidate should rank it away, not die.
    """
    n = len(text)
    if not n:
        return math.inf
    c = Counter(text)
    return sum(
        (c[i] - n * reference[i]) ** 2 / (n * reference[i])
        for i in range(N)
        if reference[i] > 0
    )


def ngrams(text: Sequence[int], n: int) -> Counter:
    return Counter(tuple(text[i : i + n]) for i in range(len(text) - n + 1))


def find(haystack: Sequence[int], needle: Sequence[int]) -> list[int]:
    """Every position where `needle` occurs in `haystack`.

    An empty needle raises rather than matching at all n+1 positions: that is
    the correct answer to the wrong question, and as an attack primitive a
    silent full-length hit list reads as a discovery.
    """
    if not needle:
        raise ValueError("empty needle")
    m, out = len(needle), []
    needle = tuple(needle)
    for i in range(len(haystack) - m + 1):
        if tuple(haystack[i : i + m]) == needle:
            out.append(i)
    return out


def repeats(text: Sequence[int], min_len: int = 3, min_count: int = 2) -> dict:
    """Repeated n-grams and their positions: {gram: [pos, ...]}.

    The raw material of a Kasiski examination: gaps between repeats of a
    periodic-key ciphertext cluster on multiples of the key length.
    """
    out = {}
    positions: dict[tuple, list[int]] = {}
    for i in range(len(text) - min_len + 1):
        g = tuple(text[i : i + min_len])
        positions.setdefault(g, []).append(i)
    for g, pos in positions.items():
        if len(pos) >= min_count:
            out[g] = pos
    return out


def kasiski_gaps(text: Sequence[int], min_len: int = 3) -> Counter:
    """Counter of gaps between repeated n-grams (for factoring by hand)."""
    gaps: Counter = Counter()
    for pos in repeats(text, min_len).values():
        gaps.update(b - a for a, b in zip(pos, pos[1:], strict=False))
    return gaps
