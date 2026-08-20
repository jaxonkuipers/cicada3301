"""Tests for lib.stats and lib.fitness against the measured corpus facts."""

import random
import unittest

from lib import corpus, fitness, stats

c = corpus.load()


class TestStats(unittest.TestCase):
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

    def test_find_and_repeats(self):
        t = [1, 2, 3, 9, 1, 2, 3, 9, 9]
        self.assertEqual(stats.find(t, [1, 2, 3]), [0, 4])
        self.assertIn((1, 2, 3), stats.repeats(t, 3))
        self.assertEqual(stats.kasiski_gaps(t, 3)[4], 2)  # (1,2,3) and (2,3,9)


class TestFitness(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
