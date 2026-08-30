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
from numbers import Integral

N = 29


def as_indices(text) -> Sequence[int]:
    """Whatever was passed -> a plain sequence of rune indices.

    Everything here is annotated `Sequence[int]`, but the type callers hold is
    `RuneText`, and AGENTS.md shows it being passed directly. That works --
    slicing a RuneText yields a RuneText -- but every `text[i:i+n]` inside a
    loop then rebuilds one and re-maps its `other`, measured 24x slower on the
    unsolved stream for an identical answer. Normalise once at the edge.

    Latin text is REJECTED rather than scored. `fitness.score("QQQQ...")` used
    to return the model floor -- a confident, constant number -- because a
    tuple of characters matches no trained n-gram, so every position floored
    and every input scored identically. Measured: THECIRCUMFERENCEIS,
    WELCOMEPILGRIMTOTHE and QQQQQQQQQQQQQQQQQQ all returned exactly
    -7.813189, and spelled through `gp.spell` they score -4.05, -4.54 and
    -7.81. Use `c.gp.spell(...)` at the edge.

    The first element establishes an integral rune stream, accepting Python
    and NumPy integer scalars. Built-in ``min``/``max`` then enforce the range
    over the whole stream without a Python type-check loop in every scorer.
    A scorer is a decision boundary, so an out-of-range candidate must fail
    before it can index a model table or receive an apparently meaningful score.
    """
    text = getattr(text, "indices", text)
    if not hasattr(text, "__len__") or not hasattr(text, "__getitem__"):
        # Preserve one-shot iterables rather than returning them exhausted.
        # NumPy arrays already provide both operations and stay zero-copy.
        text = tuple(text)
    if not len(text):
        return text
    first = text[0]
    if isinstance(first, bool) or not isinstance(first, Integral):
        raise TypeError(
            f"expected rune indices (integral values in 0..{N - 1}), got "
            f"{type(first).__name__} -- spell Latin with c.gp.spell() first"
        )
    try:
        lo, hi = min(text), max(text)
    except TypeError as exc:
        raise TypeError(
            f"expected comparable rune indices in 0..{N - 1}"
        ) from exc
    if lo < 0 or hi >= N:
        bad = lo if lo < 0 else hi
        raise ValueError(f"rune index {bad} outside 0..{N - 1}")
    return text


def counts(text: Sequence[int]) -> Counter:
    return Counter(as_indices(text))


def frequencies(text: Sequence[int]) -> list[float]:
    """Per-rune relative frequency, indexed 0..28."""
    text = as_indices(text)
    c = Counter(text)
    n = len(text) or 1
    return [c[i] / n for i in range(N)]


def ioc(text: Sequence[int]) -> float:
    """Index of coincidence, normalised so uniform random ~= 1.0.

    English through the Gematria Primus measures ~1.78; the unsolved corpus
    measures 1.000 overall and per section.
    """
    text = as_indices(text)
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
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    text = as_indices(text)
    cosets = [text[i::period] for i in range(period)]
    vals = [ioc(cs) for cs in cosets if len(cs) >= 2]
    return sum(vals) / len(vals) if vals else 0.0


def doublets(text: Sequence[int]) -> int:
    """Adjacent equal pairs. Uniform random expects n/29 ~= 3.45%."""
    text = as_indices(text)
    return sum(1 for a, b in zip(text, text[1:], strict=False) if a == b)


def doublet_rate(text: Sequence[int]) -> float:
    text = as_indices(text)
    return doublets(text) / (len(text) - 1) if len(text) > 1 else 0.0


def entropy(text: Sequence[int]) -> float:
    """Shannon entropy in bits per rune (log2(29) ~= 4.86 is flat)."""
    text = as_indices(text)
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
    if len(reference) < N:
        raise ValueError(f"reference needs {N} frequencies, got {len(reference)}")
    text = as_indices(text)
    n = len(text)
    if not n:
        return math.inf
    c = Counter(text)
    # A rune the reference calls impossible is the most damning evidence there
    # is, and skipping the term discarded it: a candidate matching the
    # reference exactly except for 5 such runes scored 0.50 instead of 0.00,
    # all of it from the 5 occurrences MISSING elsewhere.
    #
    # This raises rather than returning inf. With a reference that assigns
    # every rune some probability -- fitness.english_frequencies() has a floor
    # of 7.8e-05 -- the branch is unreachable, so the only way here is a
    # reference with a hole in it, which is a fault in the model and not a
    # property of the candidate. Returning inf made that silent: a baseline
    # table built against unsmoothed solved-plaintext frequencies came out inf
    # in every ciphertext row, a whole column voided with nothing said.
    impossible = sorted(i for i in range(N) if reference[i] <= 0 and c[i])
    if impossible:
        raise ValueError(
            f"reference gives zero probability to rune(s) {impossible}, which "
            f"the text uses; chi-squared is undefined there.\n"
            "  use fitness.english_frequencies(), or smooth your reference."
        )
    return sum(
        (c[i] - n * reference[i]) ** 2 / (n * reference[i])
        for i in range(N)
        if reference[i] > 0
    )


def ngrams(text: Sequence[int], n: int) -> Counter:
    text = as_indices(text)
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    return Counter(tuple(text[i : i + n]) for i in range(len(text) - n + 1))


def find(haystack: Sequence[int], needle: Sequence[int]) -> list[int]:
    """Every position where `needle` occurs in `haystack`.

    An empty needle raises rather than matching at all n+1 positions: that is
    the correct answer to the wrong question, and as an attack primitive a
    silent full-length hit list reads as a discovery.
    """
    haystack = as_indices(haystack)
    needle = as_indices(needle)
    if len(needle) == 0:
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
    text = as_indices(text)
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
