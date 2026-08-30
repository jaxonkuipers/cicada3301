"""Searches whose space does not factor, so enumeration cannot reach it.

Reusable search primitives for parameter spaces that do not factor cleanly.

Every sweep this repo can express enumerates a small parameter that FULLY
DETERMINES the output -- an m=4 autokey primer unrolls the whole stream, a
keystream plus an offset fixes every rune. That is what makes an enumeration
exact and lets a flat result stand as a bound.

The interrupter has no such parameter, and `solver.cipher` takes `skips` as a set
the caller already knows.

Two functions here, and **prefer `solve`**. `beam_skips` came first and is a
width-limited approximation; `solve` is the same objective maximised **exactly**
by a Viterbi recursion, 136-678x faster, with no width to tune. Use `beam_skips`
only for autokey, where `solve`'s state argument does not hold. See the section
above `solve` for the derivation, the measured speedup, and the one case where
the exact n=2 maximum is not the true set. So attacks pick `skips=empty` or `skips=every
ciphertext F` -- the two extremes, neither of which Cicada uses: 0.13 prints
five ciphertext F and exactly one is a true interrupter. 0.5 has 34, all eight
unsolved sections 458.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from numbers import Integral

from solver import fitness, stats

Decrypt = Callable[[Sequence[int], frozenset], Sequence[int]]
Score = Callable[[Sequence[int]], float]


def beam_skips(
    ct: Sequence[int],
    candidates: Iterable[int],
    decrypt: Decrypt,
    score: Score,
    width: int = 200,
    final_score: Score | None = None,
    density: float | None = None,
) -> list[tuple[float, frozenset[int]]]:
    """Which of `candidates` are interrupters? Beam search, left to right.

    A decision at position i re-aligns the key for everything after it, so the
    right subset is the one whose PREFIXES decrypt well -- which is what makes
    this prunable. `decrypt(ct, skips)` must therefore be CAUSAL: output i may
    depend on input <= i only. Every stream cipher in `solver.cipher` is; a
    transposition or block cipher is not, and this is invalid on one.

    Two scores, two jobs. `score` prunes prefixes; `final_score` ranks
    survivors over the whole stream and must read word structure, since two
    subsets differing by one interrupter decrypt identically except between the
    two positions, which no unigram statistic resolves. It defaults to `score`;
    pass it.

    **Use `fitness.score(t, n=2)` as the prune score.** Measured against known
    solved-section answers, chi2 recovers the
    interrupter set exactly on 0.13 (1 of 5) and 0.4 (2 of 5), but on 0.1
    (11 of 25) it returns 8 true, 3 false, 3 missed, at widths 50 AND 200 --
    it does not scale past a single interrupter. `score(n=2)` recovers all
    three rune-exact, 0.1 included, at width 50 in under a second.

    `density` is the expected fraction of candidates that are real
    interrupters. Measured on the three solved sections, where the answer is
    known: 11/25, 2/5, 1/5 -- pooled **14/35 = 0.40**. Supplying it adds a
    binomial log-prior to each beam, per rune so it is commensurate with a
    mean-log10-per-rune `score`. It matters most in the first few steps, where
    the prefix is short and the score cannot yet discriminate, which is
    exactly where a beam otherwise collapses onto all-skip or no-skip. Pass
    None when `score` is not in per-rune log10 units (a raw chi2, say), or the
    two terms are not on the same scale. **It has not yet earned its place:**
    on all three known-answer sections it returned the identical set with and
    without, so it is neither the reason those succeed nor a measured risk.

    Returns the final beam as (score, skips), best first -- read several. Costs
    ~`2 * width * len(candidates)` prefix decryptions, so run it per section.
    """
    if width < 1:
        raise ValueError("width must be >= 1")
    if density is not None and not 0.0 < density < 1.0:
        raise ValueError(f"density must be in (0, 1), got {density}")
    ct = list(stats.as_indices(ct))
    raw_candidates = list(candidates)
    if any(isinstance(p, bool) or not isinstance(p, Integral) for p in raw_candidates):
        raise TypeError("candidate positions must be integral values")
    cand = sorted({int(p) for p in raw_candidates})
    if any(p < 0 or p >= len(ct) for p in cand):
        raise ValueError("candidate positions must be inside the ciphertext")
    rank = final_score or score
    if not cand:
        return [(rank(decrypt(ct, frozenset())), frozenset())]

    beams: list[frozenset[int]] = [frozenset()]
    for i, pos in enumerate(cand):
        # Every decision about a candidate <= pos is now made, so the decrypt
        # is settled up to the NEXT candidate. Scoring further would score
        # runes whose key alignment a later step can still move.
        end = cand[i + 1] if i + 1 < len(cand) else len(ct)
        seen: dict[frozenset[int], None] = {}
        for skips in beams:
            seen[skips] = None
            seen[skips | {pos}] = None
        m = i + 1  # candidates decided so far; identical across beams
        scored = []
        for s in seen:
            v = score(decrypt(ct[:end], s))
            if density is not None:
                k = len(s)
                v += (k * math.log10(density)
                      + (m - k) * math.log10(1.0 - density)) / end
            scored.append((v, s))
        scored.sort(key=lambda x: -x[0])
        beams = [s for _, s in scored[:width]]

    final = [(rank(decrypt(ct, s)), s) for s in beams]
    final.sort(key=lambda x: -x[0])
    return final


# ---------------------------------------------------------------------------
# The same search, solved exactly.
#
# `beam_skips` ranks prefixes on `fitness.score(n=2)` plus a binomial prior,
# both divided by the SAME prefix length at every step, so its objective is a
# sum; and `solver.cipher.apply_stream` makes the plaintext at position i depend on
# the ciphertext, on i, and on the COUNT of skips before i -- never on which
# ones. So `(skip phase, was-the-last-candidate-skipped)` is a sufficient
# statistic: repeating keys wrap phase at their key length, while aperiodic
# streams use absolute skip counts. Transitions only go phase p -> p or p+1,
# and a Viterbi recursion returns the beam's answer AT INFINITE WIDTH in O(m*M)
# per key. There is no width to tune and no pruning to defend.
#
# Measured against the beam at width 50, this recursion is 136–678 times faster
# on representative solved-section controls.
#
# NOT VALID FOR AUTOKEY. The state argument needs `apply_stream`'s contract: a
# skipped position passes the ciphertext through and consumes no keystream
# element, and the keystream element at a position is a function of its index
# alone. Vigenere, Beaufort, variant Beaufort, running key, affine and shift all
# satisfy it. Autokey does NOT -- its keystream is earlier plaintext or
# ciphertext, so WHICH positions were skipped, not how many, determines the
# stream. Autokey stays on `beam_skips`.
#
# THE EXACT ANSWER IS NOT ALWAYS THE TRUE SET, and this is measured rather than
# feared. On 0.1 the n=2 objective's true maximum is NOT the true interrupter
# set -- the DP finds -1266.876 against the truth's -1267.138, swapping position
# 160 for 165, and returns 509 of 515 runes. The beam is right there only
# because it re-ranks survivors on 4-grams. As a DETECTOR the two are the same
# instrument: the DP's w40 and w100 equal the truth's to three decimals
# (-3.995, -4.122). `refine()` closes it -- 515/515 -- by hill-climbing on
# 4-grams over flips AND swaps, since the truth differs from the DP answer by
# one of each. It costs O(m^2) decryptions, so it is for a shortlist and never
# inside a sweep.
#
# ---------------------------------------------------------------------------

N = 29
NEG = -1e30
_TAB: list[float] | None = None


def tab2() -> list[float]:
    """fitness._model(2) flattened to tab[a*29+b], the DP's per-pair cost."""
    global _TAB
    if _TAB is None:
        logs, floor = fitness._model(2)
        t = [floor] * (N * N)
        for (a, b), v in logs.items():
            t[a * N + b] = v
        _TAB = t
    return _TAB


def cum_of(row: Sequence[int]) -> list[float]:
    """cum[i] = sum of bigram logs over positions 1..i of `row`."""
    row = stats.as_indices(row)
    if len(row) == 0:
        raise ValueError("cannot build bigram sums for an empty row")
    return _cum_validated(row)


def _cum_validated(row: Sequence[int]) -> list[float]:
    t = tab2()
    n = len(row)
    cum = [0.0] * n
    run = 0.0
    prev = row[0]
    for i in range(1, n):
        x = row[i]
        run += t[prev * N + x]
        cum[i] = run
        prev = x
    return cum


def candidates(ct: Sequence[int]) -> list[int]:
    """The demonstrated interrupter space is ciphertext F (index 0)."""
    ct = stats.as_indices(ct)
    return [i for i, x in enumerate(ct) if x == 0]


@dataclass(frozen=True)
class LayerTable:
    """Plaintext rows indexed by the number of prior skipped F runes.

    ``ciphertext`` binds the derived rows to their exact source so a table
    cannot be reused accidentally with a same-length candidate stream.
    ``phase_period`` names an authored repeating-key period and permits phase
    wrap at exactly that many rows. ``None`` means the rows enumerate absolute
    skip counts, so a solve requiring more skips than represented is rejected.
    """

    rows: tuple[tuple[int, ...], ...]
    phase_period: int | None
    ciphertext: tuple[int, ...]
    cums: tuple[tuple[float, ...], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        normalized = tuple(tuple(stats.as_indices(row)) for row in self.rows)
        ciphertext = tuple(stats.as_indices(self.ciphertext))
        if not normalized:
            raise ValueError("layer table needs at least one phase row")
        if self.phase_period is not None:
            if isinstance(self.phase_period, bool) or not isinstance(
                self.phase_period, Integral
            ):
                raise TypeError("phase period must be an integral value")
            if int(self.phase_period) != len(normalized):
                raise ValueError(
                    f"phase period {self.phase_period} requires exactly that many "
                    f"rows, got {len(normalized)}"
                )
        object.__setattr__(self, "rows", normalized)
        object.__setattr__(self, "ciphertext", ciphertext)
        object.__setattr__(
            self, "cums", tuple(tuple(_cum_validated(row)) for row in normalized)
        )

    def phase(self, skips: int) -> int:
        if self.phase_period is not None:
            return skips % int(self.phase_period)
        if skips >= len(self.rows):
            raise ValueError(
                f"layer table supports at most {len(self.rows) - 1} skips, got {skips}"
            )
        return skips


def _layer_table(
    rows: Sequence[Sequence[int]],
    phase_period: int | None,
    ciphertext: Sequence[int],
) -> LayerTable:
    """Build from rows whose generators already reduce every cell modulo 29.

    The public ``LayerTable`` constructor validates arbitrary caller-supplied
    rows. Repeating that scan over every internally generated phase made the
    principal layer sweep materially slower without adding a new invariant.
    """
    normalized = tuple(tuple(row) for row in rows)
    table = object.__new__(LayerTable)
    object.__setattr__(table, "rows", normalized)
    object.__setattr__(table, "phase_period", phase_period)
    object.__setattr__(table, "ciphertext", tuple(ciphertext))
    object.__setattr__(
        table, "cums", tuple(tuple(_cum_validated(row)) for row in normalized)
    )
    return table


def _validate_layers(layers: LayerTable, text_length: int, candidate_count: int) -> None:
    if not isinstance(layers, LayerTable):
        raise TypeError(
            "solve() requires a LayerTable from layers_repeating() or "
            "layers_stream(); legacy rows/cums arguments lack phase metadata"
        )
    M = len(layers.rows)
    if len(layers.ciphertext) != text_length:
        raise ValueError(
            f"layer ciphertext has {len(layers.ciphertext)} runes, "
            f"solve ciphertext has {text_length}"
        )
    if M == 0 or len(layers.cums) != M:
        raise ValueError("layer rows and cumulative rows must have the same nonzero length")
    if layers.phase_period is None and candidate_count >= M:
        raise ValueError(
            f"insufficient phase rows: {candidate_count} candidate skips require "
            f"{candidate_count + 1} absolute-phase rows, got {M}"
        )
    for phase, (row, cum) in enumerate(zip(layers.rows, layers.cums, strict=True)):
        if len(row) != text_length or len(cum) != text_length:
            raise ValueError(
                f"phase {phase} dimensions are row={len(row)}, cumulative={len(cum)}, "
                f"ciphertext={text_length}"
            )


def _solve_candidates(ct: Sequence[int], values: Sequence[int]) -> list[int]:
    raw = list(values)
    if any(isinstance(p, bool) or not isinstance(p, Integral) for p in raw):
        raise TypeError("candidate positions must be integral values")
    cands = [int(p) for p in raw]
    if any(a >= b for a, b in zip(cands, cands[1:], strict=False)):
        raise ValueError("candidate positions must be unique and strictly increasing")
    if any(p < 0 or p >= len(ct) for p in cands):
        raise ValueError("candidate positions must be inside the ciphertext")
    non_f = [p for p in cands if ct[p] != 0]
    if non_f:
        raise ValueError(f"interrupter candidates must be ciphertext F: {non_f[:5]}")
    return cands


def solve(
    ct: Sequence[int],
    cands: Sequence[int],
    layers: LayerTable,
    density: float | None = 0.40,
) -> tuple[float, frozenset[int], list[int]]:
    """Exact max of the beam's objective. -> (objective, skips, plaintext).

    ``layers.rows[p][i]`` is the plaintext rune at position i after phase p;
    its metadata distinguishes a true repeating-key phase from absolute phase
    rows that have finite support.
    """
    ct = list(stats.as_indices(ct))
    if not ct:
        raise ValueError("ciphertext must contain at least one rune")
    cands = _solve_candidates(ct, cands)
    n = len(ct)
    m = len(cands)
    _validate_layers(layers, n, m)
    if layers.ciphertext != tuple(ct):
        raise ValueError("layer table was built for a different ciphertext")
    if density is not None and not 0.0 < density < 1.0:
        raise ValueError(f"density must be in (0, 1), got {density}")
    rows, cums = layers.rows, layers.cums
    M = len(rows)
    t = tab2()
    if density is None:
        lp_s = lp_k = 0.0
    else:
        lp_s, lp_k = math.log10(density), math.log10(1.0 - density)
    if m == 0:
        pt = list(rows[0])
        return cums[0][n - 1], frozenset(), pt

    # V0[p] / V1[p]: best objective through candidate t, ending in phase p with
    # candidate t kept / skipped.
    V0 = [NEG] * M
    V1 = [NEG] * M
    back: list[list[int]] = []

    c0 = cands[0]
    if c0 == 0:
        V0[0] = lp_k
        V1[layers.phase(1)] = lp_s
    else:
        base = cums[0][c0 - 1]
        prev = rows[0][c0 - 1]
        V0[0] = base + t[prev * N + rows[0][c0]] + lp_k
        V1[layers.phase(1)] = base + t[prev * N] + lp_s

    for idx in range(m - 1):
        a, b = cands[idx], cands[idx + 1]
        n0 = [NEG] * M
        n1 = [NEG] * M
        bk = [0] * (2 * M)
        adjacent = b == a + 1
        for p in range(M):
            row = rows[p]
            cum = cums[p]
            keep_v, skip_v = V0[p], V1[p]
            if keep_v == NEG and skip_v == NEG:
                continue
            if adjacent:
                # one bigram term, and it depends on BOTH decisions
                out_keep = keep_v
                out_skip = skip_v
                u_keep, u_skip = row[a], 0
            else:
                if keep_v != NEG:
                    out_keep = keep_v + cum[b - 1] - cum[a]
                else:
                    out_keep = NEG
                if skip_v != NEG:
                    out_skip = (skip_v + t[row[a + 1]]
                                + cum[b - 1] - cum[a + 1])
                else:
                    out_skip = NEG
                u_keep = u_skip = row[b - 1]
            for bp in (0, 1):
                v = 0 if bp else row[b]
                ck = t[u_keep * N + v] + (lp_s if bp else lp_k)
                cs = t[u_skip * N + v] + (lp_s if bp else lp_k)
                cand_keep = out_keep + ck if out_keep != NEG else NEG
                cand_skip = out_skip + cs if out_skip != NEG else NEG
                if cand_skip > cand_keep:
                    val, came = cand_skip, 1
                else:
                    val, came = cand_keep, 0
                q = layers.phase(p + bp)
                tgt = n1 if bp else n0
                if val > tgt[q]:
                    tgt[q] = val
                    bk[bp * M + q] = came
        V0, V1, = n0, n1
        back.append(bk)

    # tail after the last candidate
    a = cands[-1]
    best, bp_last, p_last = NEG, 0, 0
    for p in range(M):
        row, cum = rows[p], cums[p]
        for bp, arr in ((0, V0), (1, V1)):
            v = arr[p]
            if v == NEG:
                continue
            if a < n - 1:
                u = 0 if bp else row[a]
                v = v + t[u * N + row[a + 1]] + cum[n - 1] - cum[a + 1]
            if v > best:
                best, bp_last, p_last = v, bp, p

    # backtrack
    flags = [0] * m
    p, bp = p_last, bp_last
    for idx in range(m - 1, -1, -1):
        flags[idx] = bp
        if idx == 0:
            break
        came = back[idx - 1][bp * M + p]
        p = (p - bp) % M if layers.phase_period is not None else p - bp
        bp = came
    skips = frozenset(cands[i] for i in range(m) if flags[i])

    pt = list(ct)
    s = 0
    nxt = 0
    for i in range(n):
        if nxt < m and cands[nxt] == i:
            if flags[nxt]:
                s += 1
                nxt += 1
                continue
            nxt += 1
        pt[i] = rows[layers.phase(s)][i]
    return best, skips, pt


def layers_repeating(ct: Sequence[int], key: Sequence[int], op,
                     maxphase: int | None = None) -> LayerTable:
    """Rows for a repeating key: phase = skips mod len(key).

    Key values are numeric material and are reduced modulo 29.
    ``maxphase`` can cap construction at the largest absolute skip count a
    caller needs. A cap below the key length produces finite, non-wrapping
    support; building all key-length rows enables legitimate cyclic wrap.
    """
    ct = list(stats.as_indices(ct))
    raw_key = list(key)
    if any(isinstance(value, bool) or not isinstance(value, Integral)
           for value in raw_key):
        raise TypeError("key values must be integral")
    k = [int(value) % N for value in raw_key]
    if not k:
        raise ValueError("empty key")
    if maxphase is not None:
        if isinstance(maxphase, bool) or not isinstance(maxphase, Integral):
            raise TypeError("maxphase must be an integer")
        if maxphase < 0:
            raise ValueError("maxphase must be >= 0")
        maxphase = int(maxphase)
    n, L = len(ct), len(k)
    nph = L if maxphase is None else min(L, maxphase + 1)
    rows = []
    for p in range(nph):
        rows.append([op(ct[i], k[(i - p) % L]) % N for i in range(n)])
    return _layer_table(rows, L if nph == L else None, ct)


def layers_stream(ct: Sequence[int], stream: Sequence[int], op,
                  nphase: int) -> LayerTable:
    """Rows for an aperiodic keystream: phase = skips, 0..nphase-1.

    `stream[j]` must be defined for j in -(nphase-1) .. len(ct)-1 through the
    caller's own offsetting; this takes `stream` already sliced so that
    `stream[i]` is the element position i consumes when no skip has occurred.
    """
    ct = list(stats.as_indices(ct))
    stream = list(stream)
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in stream):
        raise TypeError("stream values must be integral")
    stream = [int(value) for value in stream]
    if isinstance(nphase, bool) or not isinstance(nphase, Integral):
        raise TypeError("nphase must be an integer")
    if nphase < 1:
        raise ValueError("nphase must be >= 1")
    nphase = int(nphase)
    n = len(ct)
    if len(stream) < n:
        raise ValueError(f"stream needs at least {n} runes, got {len(stream)}")
    rows = []
    for p in range(nphase):
        rows.append([op(ct[i], stream[i - p]) % N if i >= p
                     else op(ct[i], stream[0]) % N for i in range(n)])
    return _layer_table(rows, None, ct)


def sub(x, k):
    return x - k


def add(x, k):
    return x + k


def beaufort(x, k):
    return k - x


def refine(ct, cands, decrypt, skips, rounds: int = 3, swaps: bool = True):
    """Single-flip hill climb on 4-grams, from the DP's answer. -> (skips, pt).

    The DP maximises the n=2 objective exactly, and on 0.1 that objective's
    maximum is one flip away from the truth. 4-grams settle it; they cannot
    drive the search (the state would carry three runes) but they can polish a
    shortlist. Costs len(cands) full decryptions per round, so it is for the
    top of a sweep and never inside one.
    """
    cur = set(skips)
    best = fitness.score(decrypt(ct, frozenset(cur)))
    for _ in range(rounds):
        moved = False
        for pos in cands:
            trial = set(cur)
            trial.symmetric_difference_update({pos})
            v = fitness.score(decrypt(ct, frozenset(trial)))
            if v > best + 1e-12:
                best, cur, moved = v, trial, True
        # swaps as well as flips: on 0.1 the truth is a SWAP away from the DP
        # answer (drop 165, add 160), which no single flip reaches. Swaps cost
        # O(m^2) decryptions against flips' O(m), so a shortlist pass runs
        # swaps=False and only the single best cell pays for them.
        for out in (sorted(cur) if swaps else ()):
            for inn in cands:
                if inn in cur:
                    continue
                trial = set(cur)
                trial.discard(out)
                trial.add(inn)
                v = fitness.score(decrypt(ct, frozenset(trial)))
                if v > best + 1e-12:
                    best, cur, moved = v, trial, True
                    break
        if not moved:
            break
    return frozenset(cur), decrypt(ct, frozenset(cur))
