"""Is this candidate plaintext English? Scored without a human in the loop.

Scores a rune-index stream against n-gram statistics of English spelled
through the Gematria Primus. Training text, ~650k runes: the Mabinogion
translation, every solved sentence of the book, reference/english/.

    fitness.judge(indices)   # (score, chi2, ioc) -- rank sweeps on all three
    fitness.score(indices)   # mean quadgram log10-prob per position
    fitness.chi2(indices)    # unigram fit to English; lower is better

Three rules, each with a measurement behind it.

RANK, NEVER THRESHOLD. The shipped model trains on every solved sentence, so
an absolute score over known plaintext is flattered by memorisation; only the
ranking survives a hold-out. 650k runes yield 51,016 of the 29^4 quadgrams, so
~93% of positions in a wrong candidate take the floor and two wrong candidates
often score identically.

MATCH n TO THE MOVE SIZE OF THE SEARCH. A Vigenere key position changes 1/k of
the stream and coordinate ascent recovers the key at n=2, 3 and 4 alike. A move
that changes ONE symbol -- per-column substitution, one interrupter flip --
leaves the n=4 score untouched two thirds of the time, so that landscape is
flat and a climber cannot start: use n=2, or chi2. N_DEFAULT is a default, not
a recommendation.

SCORE JUDGES FINAL ENGLISH ONLY, and IOC IS THE ONLY SIBLING THAT CATCHES
EVERY FIRST STAGE. Transposed solved plaintext scores -6.78 against the unsolved
corpus's -7.62, inside the band a sweep calls flat, while keeping chi2 76 and
ioc 1.80 against its 275,803 and 1.00. But that is the transposition case, where
unigrams survive. A SUBSTITUTED first stage of 0.3 scores -7.52 and reads chi2
39,698 -- both INSIDE LP2's own bands (-7.53..-7.67 and 13,671..78,985) -- while
its ioc stays 1.775 against LP2's 0.988..1.004. Rank on score, carry chi2 and
ioc through the same sweep, and rank on IOC when the target is an intermediate
stage rather than final English.

tests/test_stats_fitness.py pins the ranking and the training hash.
"""

from __future__ import annotations

import functools
import hashlib
import math
from collections import Counter
from collections.abc import Sequence
from typing import NamedTuple

from lib import corpus, stats
from lib.paths import MABINOGION, REFERENCE
from lib.stats import as_indices

N = 29  # pinned to gp.N by tests/test_corpus.py; lib.cipher and lib.stats agree

N_DEFAULT = 4
_FLOOR_PENALTY = 2.0  # unseen n-grams score this many log10 units below the rarest seen


@functools.cache
def _training_indices() -> tuple[int, ...]:
    """English reference text as rune indices, spelled through the GP."""
    c = corpus.load()
    parts = [(MABINOGION / "translation.txt").read_text(encoding="utf-8")]
    parts += [s.english for s in c.sentences if s.english]
    parts += [
        p.read_text(encoding="utf-8")
        for p in sorted((REFERENCE / "english").glob("*.txt"))
    ]
    return tuple(i for text in parts for i in c.gp.spell(text))


def training_sha256() -> str:
    """Fingerprint of the training text behind every score.

    Every logged fitness number is denominated in this model. The 2012
    Mabinogion and reference/english sit outside EXPECTED_CORPUS_SHA, so
    nothing else would catch an edit to them.
    """
    h = hashlib.sha256()
    h.update(bytes(_training_indices()))
    return h.hexdigest()


@functools.cache
def _model(n: int) -> tuple[dict[tuple, float], float]:
    """(log10-probability per n-gram, floor for unseen ones)."""
    train = _training_indices()
    grams = Counter(tuple(train[i : i + n]) for i in range(len(train) - n + 1))
    total = sum(grams.values())
    logs = {g: math.log10(v / total) for g, v in grams.items()}
    floor = math.log10(1 / total) - _FLOOR_PENALTY
    return logs, floor


def score(text: Sequence[int], n: int = N_DEFAULT) -> float:
    """Mean log10 n-gram probability per position. Higher = more English."""
    text = as_indices(text)
    if n < 1:
        # _model(0) counts one empty gram at probability 1.0, so every
        # candidate scores exactly 0.0 -- and real scores are negative, so a
        # miscomputed n silently promotes noise to the top of the ranking.
        raise ValueError(f"n must be >= 1, got {n}")
    if len(text) < n:
        raise ValueError(f"need at least {n} runes to score")
    logs, floor = _model(n)
    total = sum(
        logs.get(tuple(text[i : i + n]), floor) for i in range(len(text) - n + 1)
    )
    return total / (len(text) - n + 1)


def windowed(
    text: Sequence[int], size: int = 100, step: int = 25, n: int = N_DEFAULT
) -> list[tuple[int, float]]:
    """Score overlapping windows: [(start, score), ...].

    Cicada mixes enciphered and plain stretches inside one section (0.1, 0.4),
    so a correct key may decrypt only part of a stream -- which lifts its
    windows while barely moving the mean. Rank by max window and by the whole.
    """
    text = as_indices(text)
    if step < 1 or size < n:
        raise ValueError(f"need step >= 1 and size >= {n}, got step={step} size={size}")
    if len(text) <= size:
        return [(0, score(text, n))]
    starts = list(range(0, len(text) - size + 1, step))
    # `range` stops short unless (len - size) divides step, leaving the last
    # up-to-(step-1) runes in no window -- a blind spot in the tail.
    if starts[-1] != len(text) - size:
        starts.append(len(text) - size)
    return [(i, score(text[i : i + size], n)) for i in starts]


@functools.cache
def english_frequencies() -> tuple[float, ...]:
    """Per-rune frequency of English through the GP: the null model for
    chi-squared tests (lib.stats.chi_squared) and frequency attacks."""
    train = _training_indices()
    counts = Counter(train)
    n = len(train)
    return tuple(counts[i] / n for i in range(N))


def chi2(text: Sequence[int]) -> float:
    """Unigram fit to English-through-the-GP. Lower is more English-like.

    The obvious reference to build by hand -- the 2901 solved runes -- has
    holes at EO/OE/AE that `stats.chi_squared` rejects. Use this instead.
    """
    return stats.chi_squared(text, english_frequencies())


class Judgement(NamedTuple):
    score: float  # FINAL English only
    chi2: float  # unigram fit; survives any transposition
    ioc: float  # 1.0 uniform, ~1.78 English; survives any transposition


def judge(text: Sequence[int], n: int = N_DEFAULT) -> Judgement:
    """All three statistics at once. A candidate flat on `score` with
    English-like `chi2` and `ioc` is one layer from solved, not dead."""
    text = as_indices(text)
    return Judgement(score(text, n), chi2(text), stats.ioc(text))
