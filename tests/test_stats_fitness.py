"""Tests for lib.stats and lib.fitness against the measured corpus facts."""

import random
import unittest

from lib import cipher, corpus, fitness, stats

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
    def test_training_set_pinned(self):
        # Any change to the training text (corpus/mabinogion, sentences.csv,
        # reference/english/) rescales every fitness score and breaks
        # comparability with logged experiment scores. Deliberate changes
        # update this pin and say so in the commit.
        self.assertEqual(len(fitness._training_indices()), 650_416)

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
