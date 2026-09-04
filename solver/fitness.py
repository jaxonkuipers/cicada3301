"""Is this candidate plaintext English? Scored without a human in the loop.

Scores a rune-index stream against frozen n-gram statistics of English spelled
through the Gematria Primus. The model was derived from ~650k runes: the
Mabinogion translation, every solved sentence of the book, and three
public-domain English references. Only sufficient statistics are shipped;
the source prose is not a runtime dependency.

    fitness.judge(indices)   # (score, chi2, ioc) -- rank sweeps on all three
    fitness.score(indices)   # mean quadgram log10-prob per position
    fitness.chi2(indices)    # unigram fit to English; lower is better

Three rules, each with a measurement behind it.

RANK, NEVER THRESHOLD. The shipped model trains on every solved sentence, so
an absolute score over known plaintext is flattered by memorisation; only the
ranking survives a hold-out. 650k runes yield 51,075 of the 29^4 quadgrams, so
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
import gzip
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple, cast

from solver import stats
from solver.stats import as_indices

N = 29  # pinned to gp.N by tests/test_corpus.py; solver.cipher and solver.stats agree

N_DEFAULT = 4
_FLOOR_PENALTY = 2.0  # unseen n-grams score this many log10 units below the rarest seen
_MODEL_PATH = Path(__file__).with_name("data") / "english_model.json.gz"


@functools.cache
def _frozen_model() -> dict[str, object]:
    """Load and minimally validate the versioned sufficient statistics."""
    with gzip.open(_MODEL_PATH, "rt", encoding="utf-8") as source:
        model = json.load(source)
    if not isinstance(model, dict):
        raise ValueError("English model root must be an object")
    if model.get("format") != 1:
        raise ValueError(f"unsupported English model format: {model.get('format')!r}")
    if model.get("alphabet_size") != N:
        raise ValueError(
            f"English model alphabet is {model.get('alphabet_size')!r}, expected {N}"
        )
    if not isinstance(model.get("counts"), dict):
        raise ValueError("English model has no n-gram counts")
    return model


def training_length() -> int:
    """Number of Gematria Primus runes represented by the frozen model."""
    return int(_frozen_model()["training_length"])


def training_sha256() -> str:
    """Fingerprint of the rune-index stream behind every score.

    Every logged fitness number is denominated in this model. The digest is
    stored with the sufficient statistics so the deleted source prose is not
    needed to identify it.
    """
    digest = _frozen_model()["training_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("English model has an invalid training digest")
    return digest


def _decode_gram(value: int, n: int) -> tuple[int, ...]:
    """Decode a fixed-width base-29 integer from the compact model."""
    gram = [0] * n
    for i in range(n - 1, -1, -1):
        value, gram[i] = divmod(value, N)
    if value:
        raise ValueError("English model contains an out-of-range n-gram")
    return tuple(gram)


@functools.cache
def _counts(n: int) -> dict[tuple[int, ...], int]:
    model = _frozen_model()
    maximum = int(model["max_order"])
    if not 1 <= n <= maximum:
        raise ValueError(f"frozen English model supports n=1..{maximum}, got {n}")
    orders = cast(dict, model["counts"])  # validated by _frozen_model
    entries = orders.get(str(n))
    if not isinstance(entries, list):
        raise ValueError(f"English model is missing order {n}")
    counts = {_decode_gram(int(code), n): int(count) for code, count in entries}
    if len(counts) != len(entries) or any(count <= 0 for count in counts.values()):
        raise ValueError(f"English model order {n} has invalid counts")
    expected = training_length() - n + 1
    if sum(counts.values()) != expected:
        raise ValueError(
            f"English model order {n} totals {sum(counts.values())}, expected {expected}"
        )
    return counts


@functools.cache
def log_table(n: int) -> tuple[dict[tuple[int, ...], float], float]:
    """The frozen model's (log10 probability per n-gram, unseen-gram floor).

    The table behind `score`, public for consumers that flatten or re-index
    it -- solver.search builds its DP cost table from order 2. Supported
    orders are 1..max_order of the shipped model; the mapping and floor are
    cached and shared, so treat them as read-only.
    """
    grams = _counts(n)
    total = sum(grams.values())
    logs = {g: math.log10(v / total) for g, v in grams.items()}
    floor = math.log10(1 / total) - _FLOOR_PENALTY
    return logs, floor


def score(text: Sequence[int], n: int = N_DEFAULT) -> float:
    """Mean log10 n-gram probability per position. Higher = more English."""
    text = as_indices(text)
    if n < 1:
        # log_table(0) counts one empty gram at probability 1.0, so every
        # candidate scores exactly 0.0 -- and real scores are negative, so a
        # miscomputed n silently promotes noise to the top of the ranking.
        raise ValueError(f"n must be >= 1, got {n}")
    if len(text) < n:
        raise ValueError(f"need at least {n} runes to score")
    logs, floor = log_table(n)
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
    chi-squared tests (solver.stats.chi_squared) and frequency attacks."""
    counts = _counts(1)
    total = training_length()
    return tuple(counts[(i,)] / total for i in range(N))


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
