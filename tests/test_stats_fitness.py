"""Tests for solver.stats and solver.fitness against measured corpus facts."""

import hashlib
import random
import unittest
from collections import Counter
from enum import IntEnum

from solver import cipher, corpus, fitness, stats

c = corpus.load()


class TestStats(unittest.TestCase):
    def test_shared_index_validation_checks_every_rune(self):
        class Rune(IntEnum):
            F = 0
            U = 1

        accepted = [Rune.F, Rune.U, 28]
        self.assertEqual(list(stats.as_indices(accepted)), [0, 1, 28])
        for bad, error in (
            ([0, 1, 29, 2], ValueError),
            ([0, -1, 2], ValueError),
            ([0, True, 2], TypeError),
            ([0, 1.0, 2], TypeError),
        ):
            with self.assertRaises(error, msg=bad):
                stats.as_indices(bad)

    def test_shared_index_validation_preserves_one_shot_iterables(self):
        self.assertEqual(
            stats.counts(iter([0, 1, 1, 2])), Counter({1: 2, 0: 1, 2: 1})
        )

    def test_invalid_runes_cannot_reach_statistics_or_fitness_tables(self):
        for fn in (
            stats.ioc,
            stats.frequencies,
            lambda text: stats.ngrams(text, 2),
            fitness.score,
            fitness.judge,
        ):
            with self.assertRaises(ValueError, msg=fn):
                fn([0, 1, 2, 29, 3, 4])
        with self.assertRaises(ValueError):
            stats.find([0, 1, 2], [1, 29])

    def test_unsolved_ioc_is_flat(self):
        # The published constraint: unigram IoC 1.000 over the unsolved stream.
        self.assertAlmostEqual(stats.ioc(c.unsolved.indices), 1.000, places=2)

    def test_unsolved_doublets_suppressed(self):
        u = c.unsolved.indices
        self.assertEqual(stats.doublets(u), 86)
        self.assertLess(stats.doublet_rate(u), 0.01)  # vs 1/29 ~= 3.45% random

    def test_english_via_gp_ioc(self):
        eng = c.gp.spell(" ".join(s.english for s in c.sentences if s.english))
        self.assertGreater(stats.ioc(eng), 1.6)  # structured, unlike ciphertext

    def test_periodic_ioc_finds_a_planted_period(self):
        rng = random.Random(3301)
        eng = c.gp.spell(" ".join(s.english for s in c.sentences if s.english))
        key = [rng.randrange(29) for _ in range(7)]
        ct = [(p + key[i % 7]) % 29 for i, p in enumerate(eng)]
        right = stats.periodic_ioc(ct, 7)
        wrong = max(stats.periodic_ioc(ct, k) for k in (2, 3, 4, 5, 6, 8, 9, 10, 11))
        self.assertGreater(right, 1.6)
        self.assertGreater(right, wrong + 0.3)

    def test_degenerate_input_ranks_last(self):
        # A sweep hitting an empty candidate must rank it away, not crash and
        # not sort it first. chi_squared is lower-is-better, hence inf.
        freqs = fitness.english_frequencies()
        self.assertEqual(stats.chi_squared([], freqs), float("inf"))
        self.assertEqual(stats.ioc([]), 0.0)
        self.assertEqual(stats.doublet_rate([]), 0.0)

    def test_empty_needle_is_refused(self):
        # Matching at all n+1 positions is the right answer to the wrong
        # question; as an attack primitive it reads as a discovery.
        with self.assertRaises(ValueError):
            stats.find(list(range(10)), [])

    def test_find_and_repeats(self):
        t = [1, 2, 3, 9, 1, 2, 3, 9, 9]
        self.assertEqual(stats.find(t, [1, 2, 3]), [0, 4])
        self.assertIn((1, 2, 3), stats.repeats(t, 3))
        self.assertEqual(stats.kasiski_gaps(t, 3)[4], 2)  # (1,2,3) and (2,3,9)


class TestFitness(unittest.TestCase):
    def test_training_set_pinned(self):
        # Any change to the frozen counts rescales fitness scores and breaks
        # comparability with logged experiments. The model retains the length
        # and digest of the rune-index stream it replaced, while an asset hash
        # catches any mutation of the sufficient statistics themselves.
        # The earlier CQU -> KW spelling emitted one extra rune at each of
        # the 39 CQU occurrences (C+QU used to emit C twice, under the old
        # Q -> C rule as well).
        self.assertEqual(fitness.training_length(), 650_377)
        # By content too: a length pin misses an equal-length edit that would
        # silently rescale every logged score.
        # spell() applies the author's
        # QU -> KW (attested CWESTIAN, 0.4's plain tail) and CQU -> KW.
        # 563 QU occurrences in the training text change their second rune;
        # 39 CQU occurrences also lose one. Measured effect on scores against
        # the previous model: -5.1e-05 on 0.3's plaintext and -9.8e-04 on the
        # unsolved stream, with chi2 and ioc unchanged.
        self.assertEqual(
            fitness.training_sha256(),
            "ffe950c4caf537a065819e3e5f0d56bb76015fa74023c7bf656f6ec604d0bb56",
        )
        self.assertEqual(
            hashlib.sha256(fitness._MODEL_PATH.read_bytes()).hexdigest(),
            "14509e5d79260f7e3a48dbd53dd95ffe9844c51ab29347e79fb0b2b2e44b2c5d",
        )

    def test_frozen_model_carries_sufficient_statistics(self):
        # The deleted prose is replaced by positive counts for every order the
        # scorer documents and uses. Cardinalities pin that this is the full
        # former model rather than a reduced approximation.
        expected_cardinalities = {1: 29, 2: 712, 3: 8_649, 4: 51_075}
        for n, cardinality in expected_cardinalities.items():
            counts = fitness._counts(n)
            self.assertEqual(len(counts), cardinality)
            self.assertEqual(sum(counts.values()), fitness.training_length() - n + 1)

    def test_unsupported_model_order_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "supports n=1..4"):
            fitness.score(list(range(20)), n=5)

    def test_degenerate_n_and_period_are_refused(self):
        # _model(0) counts one empty gram at p=1.0, so every candidate scored
        # exactly 0.0 -- and real scores are negative, so noise sorted first.
        for n in (0, -1):
            with self.assertRaises(ValueError, msg=n):
                fitness.score([1, 2, 3, 4], n)
        for period in (0, -3):
            with self.assertRaises(ValueError, msg=period):
                stats.periodic_ioc(list(range(50)), period)
        with self.assertRaises(ValueError):
            stats.chi_squared([1, 2], [0.5, 0.5])  # short reference

    def test_impossible_runes_are_not_discarded(self):
        # Skipping the zero-probability term threw away the most damning
        # evidence: a candidate matching the reference exactly except for 5
        # runes it calls impossible scored 0.50, all of it from the 5
        # occurrences missing elsewhere.
        ref = [1 / 28] * 28 + [0.0]
        self.assertEqual(stats.chi_squared(list(range(28)) * 10, ref), 0.0)
        with self.assertRaises(ValueError) as cm:
            stats.chi_squared(list(range(28)) * 10 + [28] * 5, ref)
        self.assertIn("28", str(cm.exception))

    def test_holed_reference_names_the_runes(self):
        # Only an unsmoothed reference can reach this, and returning inf made
        # it silent: a whole baseline column came out inf with nothing said.
        # An unsmoothed solved-plaintext reference is exactly how it happened.
        counts = Counter(
            i for s in c.sentences if s.english and c.section(s.section).solved
            for i in c.gp.spell(s.english)
        )
        n = sum(counts.values())
        ref = [counts[i] / n for i in range(29)]
        holes = [i for i in range(29) if ref[i] == 0]
        self.assertTrue(holes, "solved plaintext should not cover all 29 runes")
        with self.assertRaises(ValueError) as cm:
            stats.chi_squared(list(c.section("0.5").text().indices), ref)
        self.assertIn("smooth", str(cm.exception))
        # The documented reference has no holes, so it scores fine.
        freqs = fitness.english_frequencies()
        self.assertGreater(min(freqs), 0)
        self.assertGreater(
            stats.chi_squared(list(c.section("0.5").text().indices), freqs), 1000
        )

    def test_runetext_and_list_agree_and_cost_the_same(self):
        # AGENTS.md shows fitness.score(t) with t a RuneText; slicing one
        # rebuilt a RuneText per window, 24x slower for an identical answer.
        rt = c.unsolved
        idx = list(rt.indices)
        self.assertEqual(fitness.score(rt), fitness.score(idx))
        self.assertEqual(fitness.windowed(rt), fitness.windowed(idx))
        for fn in (stats.ioc, stats.doublet_rate, stats.entropy, stats.counts):
            self.assertEqual(fn(rt), fn(idx), fn.__name__)

    def test_alphabet_size_is_shared(self):
        self.assertEqual(fitness.N, stats.N)
        self.assertEqual(len(fitness.english_frequencies()), stats.N)

    def test_windowed_refuses_degenerate_geometry(self):
        # step=0 used to escape as "range() arg 3 must not be zero".
        for kwargs in ({"step": 0}, {"step": -5}, {"size": 2}):
            with self.assertRaises(ValueError, msg=kwargs):
                fitness.windowed(list(range(500)), **kwargs)

    def test_windowed_covers_the_tail(self):
        # Every rune must fall inside some window; range() stopping short left
        # the last up-to-(step-1) runes scored by nothing.
        for length in (1000, 1010, 1024, 137):
            w = fitness.windowed([i % 29 for i in range(length)], size=100, step=25)
            covered = {j for i, _ in w for j in range(i, i + 100)}
            self.assertEqual(covered, set(range(length)), length)

    def test_english_scores_far_above_noise(self):
        rng = random.Random(1033)
        english = c.gp.spell(
            "THE LOSS OF DIVINITY THE CIRCUMFERENCE PRACTICES THREE BEHAVIORS "
            "WHICH CAUSE THE LOSS OF DIVINITY"
        )
        noise = [rng.randrange(29) for _ in range(len(english))]
        gap = fitness.score(english) - fitness.score(noise)
        self.assertGreater(gap, 2.0)  # log10 units per rune: a wide margin

    def test_solved_plaintext_beats_ciphertext(self):
        # 0.5's ciphertext must look like noise; 0.3's plaintext like English.
        self.assertGreater(
            fitness.score(list(c.section("0.3").text().indices)),
            fitness.score(list(c.section("0.5").text().indices)) + 1.5,
        )

    def test_judge_ranks_known_solution_first(self):
        # The judge behind every attack: whatever the cipher hypothesis, the
        # last step is fitness.score ranking candidates. This pins that a key
        # sweep would surface 0.1's known key even with interrupters ignored
        # (11 of them in 515 runes desync the tail; the head still lifts the
        # score clear of every random key). If this fails, every negative
        # sweep result since the regression is meaningless -- fix the scorer
        # before trusting any new "disproved".
        # (0.1's plaintext is in the training text, which flatters absolute
        # scores; the ranking margin holds with it excluded too, measured
        # 2026-08-21 on a held-out model: right key beat the best of 3000
        # random keys by ~8 sd of the random-key spread.)
        ct = list(c.section("0.1").text().indices)[:515]
        right = fitness.score(cipher.vigenere_decrypt(ct, c.gp.spell("DIVINITY")))
        rng = random.Random(7)
        best_random = max(
            fitness.score(
                cipher.vigenere_decrypt(ct, [rng.randrange(29) for _ in range(8)])
            )
            for _ in range(500)
        )
        self.assertGreater(right, best_random + 0.1)

    def test_windowed_finds_a_partial_stretch(self):
        # Cicada mixes enciphered and plain stretches (0.1, 0.4): a correct
        # key decrypting only 100 of 1000 runes must still surface. Whole-
        # stream ranking sees it weakly; the windowed max sees it decisively.
        rng = random.Random(42)
        eng = c.gp.spell(
            "THE HIDDEN PATTERN EMERGES WHEN THE SEEKER STOPS FORCING THE "
            "ANSWER AND BEGINS TO LISTEN TO THE STRUCTURE OF THE PROBLEM"
        )[:100]
        noise = [rng.randrange(29) for _ in range(1000)]
        mixed = noise[:400] + eng + noise[500:]
        best = max(s for _, s in fitness.windowed(mixed))
        noise_best = max(s for _, s in fitness.windowed(noise))
        self.assertGreater(best, noise_best + 1.5)

    def test_default_n_drives_a_key_search(self):
        # The scorer is sparse at n=4 (~93% of noise positions take the floor),
        # which makes it a ranker rather than a distance -- but NOT unusable
        # for key search, because a search moves a key position and with it
        # 1/k of the stream. Pins that coordinate ascent at the DEFAULT n
        # still recovers an exact key, so nobody "fixes" the sparsity by
        # dropping n in inner loops. 200 runes is where it becomes reliable;
        # below ~100 it is unreliable at every n.
        eng = c.gp.spell(" ".join(s.english for s in c.sentences if s.english))[:200]
        rng = random.Random(3301)
        for klen in (8, 13):
            key = [rng.randrange(29) for _ in range(klen)]
            ct = [(p + key[i % klen]) % 29 for i, p in enumerate(eng)]
            guess = [rng.randrange(29) for _ in range(klen)]
            best = fitness.score(cipher.vigenere_decrypt(ct, guess))
            for _ in range(15):
                moved = False
                for i in range(klen):
                    for v in range(29):
                        trial = list(guess)
                        trial[i] = v
                        sc = fitness.score(cipher.vigenere_decrypt(ct, trial))
                        if sc > best:
                            best, guess, moved = sc, trial, True
                if not moved:
                    break
            self.assertEqual(guess, key, f"key length {klen}")

    def test_english_frequencies_sum_to_one(self):
        freqs = fitness.english_frequencies()
        self.assertAlmostEqual(sum(freqs), 1.0, places=9)
        self.assertEqual(len(freqs), 29)
        # chi-squared: unsolved ciphertext is far from English frequencies
        u = list(c.unsolved.indices)
        eng = c.gp.spell(" ".join(s.english for s in c.sentences if s.english))
        self.assertGreater(
            stats.chi_squared(u, freqs), stats.chi_squared(eng, freqs) * 3
        )


class LatinTextIsRejected(unittest.TestCase):
    """The floor bug: Latin text scored as a confident constant.

    A tuple of characters matches no trained n-gram, so every position took
    the floor and every input returned exactly the same number. A sweep ranked
    on it reports a confident nothing.
    """

    def test_score_rejects_latin(self):
        for bad in ("THECIRCUMFERENCEIS", "WELCOMEPILGRIMTOTHE", "QQQQQQQQQQQQQQQQQQ"):
            with self.assertRaises(TypeError):
                fitness.score(bad)

    def test_the_three_that_tied_now_separate_when_spelled(self):
        gp = corpus.load().gp
        eng = [fitness.score(gp.spell(w))
               for w in ("THECIRCUMFERENCEIS", "WELCOMEPILGRIMTOTHE")]
        junk = fitness.score(gp.spell("QQQQQQQQQQQQQQQQQQ"))
        self.assertTrue(all(e > junk + 3.0 for e in eng), (eng, junk))

    def test_stats_reject_latin_too(self):
        for fn in (stats.ioc, stats.doublet_rate, stats.entropy):
            with self.assertRaises(TypeError):
                fn("HELLOWORLD")

    def test_runetext_and_lists_still_pass(self):
        c = corpus.load()
        self.assertIsInstance(fitness.score(c.section("0.5").text()), float)
        self.assertIsInstance(fitness.score(list(c.unsolved.indices[:200])), float)


if __name__ == "__main__":
    unittest.main()
