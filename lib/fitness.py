"""Is this candidate plaintext English? Scored without a human in the loop.

The single bottleneck of automated key search is judging output. This module
scores a rune-index stream against n-gram statistics of English spelled
through the Gematria Primus -- the same spelling the book itself uses -- so
a hill-climb or a keyspace sweep can rank thousands of candidates and
surface only the ones worth reading.

Training text, ~650k runes: the Mabinogion translation (corpus/mabinogion/),
every solved English sentence of the book itself, and the public-domain
wisdom prose in reference/english/ (see its README for provenance).

The margin -- English clears random noise by ~3.3 log10/rune, and by at least
~2.9 even on 50-rune segments -- was measured on a SEPARATELY BUILT held-out
model with 0.3 and 0.14 excluded. The model shipped here trains on every
solved sentence, 0.3 and 0.14 included, because at attack time those sections
are known plaintext and there is no reason to spend them. So absolute scores
on solved plaintext are flattered by memorisation: `score(0.3) = -4.22` is
partly recall, not judgement. What survives the hold-out is the RANKING, which
is all an attack uses (see tests/test_stats_fitness.py, which pins both).

    from lib import fitness
    fitness.score(indices)       # mean quadgram log10-prob per position
    fitness.english_frequencies()  # per-rune distribution of English-via-GP

Scores are comparable only at the same n and the same training set; higher is
more English-like. Rank candidates against a same-length noise baseline and
read every outlier -- never gate on an absolute score.

## Sparse by construction, and why that is fine

650k runes of training text yield 51,016 of the 29^4 possible quadgrams, so
~93% of positions in a non-English candidate take the floor and two WRONG
candidates often score identically -- a single-rune change to a noise
candidate leaves the score untouched about two thirds of the time. That is
what a ranker looks like, and it is the concrete reason for the
rank-never-threshold rule above: an absolute score below English says almost
nothing about how wrong a candidate is.

It is NOT a reason to score key searches at a lower n. A real search moves a
key position, which changes 1/k of the stream at once, not one rune.
Measured 2026-08-21, coordinate ascent from 8 random restarts on clean
Vigenere ciphertext recovers the exact key 8/8 at n=2, 3 AND 4 for key
lengths 8 and 13 once the ciphertext reaches ~200 runes, and is unreliable
at every n below ~100. Use the default and give it enough text; the n=4 case
is pinned by tests/test_stats_fitness.py.

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
import hashlib
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


def training_sha256() -> str:
    """Fingerprint of the exact training text behind every score.

    Every fitness number in research/experiments.jsonl is denominated in this
    model; change the training text and none of them stay comparable. The
    corpus-side inputs are covered by corpus.EXPECTED_CORPUS_SHA, but
    corpus/mabinogion/ and reference/english/ are not, and a length pin alone
    would miss an equal-length edit. Pinned by tests/test_stats_fitness.py.
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
    starts = list(range(0, len(text) - size + 1, step))
    # `range` stops short whenever (len - size) is not a multiple of step, and
    # the last up-to-(step-1) runes then sit in no window at all -- a blind spot
    # in exactly the tail where a short enciphered stretch is hardest to see.
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
    return tuple(counts[i] / n for i in range(29))
