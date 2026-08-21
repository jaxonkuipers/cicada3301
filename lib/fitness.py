"""Is this candidate plaintext English? Scored without a human in the loop.

The single bottleneck of automated key search is judging output. This module
scores a rune-index stream against n-gram statistics of English spelled
through the Gematria Primus -- the same spelling the book itself uses -- so
a hill-climb or a keyspace sweep can rank thousands of candidates and
surface only the ones worth reading.

Training text, ~650k runes: the Mabinogion translation (corpus/mabinogion/),
every solved English sentence of the book itself, and the public-domain
wisdom prose in reference/english/ (see its README for provenance). Measured
on held-out Cicada plaintext (0.3 and 0.14 excluded from training): English
clears random noise by ~3.3 log10/rune, and by at least ~2.9 even on 50-rune
segments (see tests/test_stats_fitness.py).

    from lib import fitness
    fitness.score(indices)       # mean quadgram log10-prob per position
    fitness.english_frequencies()  # per-rune distribution of English-via-GP

Scores are comparable only at the same n and the same training set; higher is
more English-like. Rank candidates against a same-length noise baseline and
read every outlier -- never gate on an absolute score.

This module judges FINAL English plaintext only. A correct intermediate stage
of a multi-layer cipher (say, English still under a transposition) scores far
below real English here while its unigram statistics give it away: measured,
transposed 0.3 plaintext scores -6.9 (noise -7.6, English -4.2) but keeps
ioc 1.77 and chi-squared 71 vs English frequencies (noise: 19,000+). Judge
intermediate stages with lib.stats (ioc, chi_squared, doublet_rate), not with
this score -- a flat-fitness candidate with English-like unigram stats is one
layer from solved, not dead.
"""

from __future__ import annotations

import functools
import math
from collections import Counter
from collections.abc import Sequence

from lib import corpus
from lib.paths import CORPUS, REFERENCE

N_DEFAULT = 4
_FLOOR_PENALTY = 2.0  # unseen n-grams score this many log10 units below the rarest seen


@functools.cache
def _training_indices() -> tuple[int, ...]:
    """English reference text as rune indices, spelled through the GP."""
    c = corpus.load()
    parts = [(CORPUS / "mabinogion" / "translation.txt").read_text(encoding="utf-8")]
    parts += [s.english for s in c.sentences if s.english]
    parts += [
        p.read_text(encoding="utf-8")
        for p in sorted((REFERENCE / "english").glob("*.txt"))
    ]
    return tuple(i for text in parts for i in c.gp.spell(text))


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

    Cicada mixes enciphered and plain stretches inside one section (0.1 and
    0.4, measured), so a correct key may decrypt only part of a stream. The
    stretch lifts its windows enormously while barely moving the whole-stream
    mean: rank candidates by max window as well as by the whole.
    """
    if len(text) <= size:
        return [(0, score(text, n))]
    return [(i, score(text[i : i + size], n)) for i in range(0, len(text) - size + 1, step)]


@functools.cache
def english_frequencies() -> tuple[float, ...]:
    """Per-rune frequency of English through the GP: the null model for
    chi-squared tests (lib.stats.chi_squared) and frequency attacks."""
    train = _training_indices()
    counts = Counter(train)
    n = len(train)
    return tuple(counts[i] / n for i in range(29))
