"""Planted-answer tests for solver.search.

A search primitive can be proven in a way a cipher hypothesis cannot: plant a
key and an interrupter set, encipher, and check the search recovers exactly
what was planted. The ciphertext here comes from `cipher.vigenere_encrypt`
with `interrupter=0`, the model proven rune-exact against 0.1 and 0.4.
"""

import unittest

from solver import cipher, corpus, fitness, search

c = corpus.load()


def solved_plaintext():
    solved = {s.id for s in c.sections if s.solved}
    return [i for s in c.sentences
            if s.section in solved and s.english
            for i in c.gp.spell(s.english)]


class BeamSkips(unittest.TestCase):
    def setUp(self):
        self.pt = solved_plaintext()[:600]
        self.key = c.gp.spell("DIVINITY")
        self.ct = cipher.vigenere_encrypt(self.pt, self.key, interrupter=0)
        # The planted answer: positions where the PLAINTEXT was F. Every other
        # ciphertext F is an ordinary encryption, which is what makes the set
        # ambiguous from the ciphertext alone.
        self.planted = frozenset(i for i, p in enumerate(self.pt) if p == 0)
        self.candidates = [i for i, x in enumerate(self.ct) if x == 0]

    def test_the_search_is_not_trivial(self):
        """More ciphertext F than true interrupters, or there is nothing to find."""
        self.assertGreater(len(self.candidates), len(self.planted))
        self.assertTrue(self.planted <= set(self.candidates))

    def test_recovers_the_planted_interrupter_set(self):
        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        out = search.beam_skips(
            self.ct, self.candidates, decrypt,
            lambda t: -fitness.chi2(t), width=64, final_score=fitness.score,
        )
        self.assertEqual(out[0][1], self.planted)

    def test_recovered_set_decrypts_rune_exact(self):
        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        best = search.beam_skips(
            self.ct, self.candidates, decrypt,
            lambda t: -fitness.chi2(t), width=64, final_score=fitness.score,
        )[0][1]
        self.assertEqual(decrypt(self.ct, best), self.pt)

    def test_density_prior_preserves_recovery(self):
        """The measured 0.40 prior preserves the exact solved answer."""
        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        out = search.beam_skips(
            self.ct, self.candidates, decrypt, fitness.score,
            width=64, final_score=fitness.score, density=0.40,
        )
        self.assertEqual(out[0][1], self.planted)
        self.assertEqual(decrypt(self.ct, out[0][1]), self.pt)

    def test_density_prior_helps_a_narrow_beam(self):
        """The prior earns its place only where the prefix score cannot yet
        discriminate: a beam too narrow to carry both branches through the
        early steps."""
        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        kw = dict(width=2, final_score=fitness.score)
        without = search.beam_skips(
            self.ct, self.candidates, decrypt, fitness.score, **kw)
        with_ = search.beam_skips(
            self.ct, self.candidates, decrypt, fitness.score, density=0.40, **kw)
        planted = self.planted
        miss_without = len(without[0][1] ^ planted)
        miss_with = len(with_[0][1] ^ planted)
        self.assertLessEqual(miss_with, miss_without)

    def test_rejects_impossible_density(self):
        for d in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                search.beam_skips([1, 2], [0], lambda ct, s: ct,
                                  lambda t: 0.0, density=d)

    def test_score_n2_prunes_where_chi2_fails(self):
        """On solved 0.1, score(n=2) recovers all 11 true interrupters."""
        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        by_n2 = search.beam_skips(
            self.ct, self.candidates, decrypt,
            lambda t: fitness.score(t, n=2), width=50,
            final_score=fitness.score,
        )[0][1]
        self.assertEqual(by_n2, self.planted)

    def test_no_candidates_returns_the_empty_set(self):
        out = search.beam_skips(
            [1, 2, 3], [], lambda ct, s: list(ct), lambda t: 0.0
        )
        self.assertEqual(out, [(0.0, frozenset())])

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            search.beam_skips([1, 2], [0], lambda ct, s: ct, lambda t: 0.0, width=0)
        with self.assertRaises(ValueError):
            search.beam_skips([1, 2], [9], lambda ct, s: ct, lambda t: 0.0)


if __name__ == "__main__":
    unittest.main()


class ExactSkips(unittest.TestCase):
    """`search.solve` is `beam_skips` at infinite width. Gate it on both.

    Three claims, and they are different. The DP must recover a PLANTED set,
    like the beam. Its objective must be >= the beam's on the same input,
    because it maximises that objective exactly. And on a case small enough to
    enumerate it must equal brute force -- which is the one that would catch a
    transcription error in the recursion, since a subtly wrong DP can still
    recover an easy planted answer.
    """

    @staticmethod
    def objective(ct, cands, skips, key, density=0.40):
        """Evaluate ONE skip set under the DP's own objective.

        `solve` maximises; this scores a given set, which is what a brute-force
        comparison needs. Same formula: bigram log10 over the decryption, plus
        the binomial prior over the candidates.
        """
        import math
        pt = cipher.vigenere_decrypt(ct, key, skips=frozenset(skips))
        tab = search.tab2()
        v = sum(tab[pt[i - 1] * search.N + pt[i]] for i in range(1, len(pt)))
        k = len(skips)
        return v + k * math.log10(density) + (len(cands) - k) * math.log10(1 - density)

    def setUp(self):
        self.pt = solved_plaintext()[:600]
        self.key = c.gp.spell("DIVINITY")
        self.ct = cipher.vigenere_encrypt(self.pt, self.key, interrupter=0)
        self.planted = frozenset(i for i, p in enumerate(self.pt) if p == 0)
        self.cands = search.candidates(self.ct)
        self.rows, self.cums = search.layers_repeating(
            self.ct, self.key, search.sub)

    def test_recovers_the_planted_set_exactly(self):
        _, skips, pt = search.solve(self.ct, self.cands, self.rows, self.cums)
        self.assertEqual(skips, self.planted)
        self.assertEqual(list(pt), list(self.pt))

    def test_objective_is_at_least_the_beams(self):
        """Exact maximisation cannot lose to a width-limited search of it."""
        obj, _, _ = search.solve(self.ct, self.cands, self.rows, self.cums)

        def decrypt(ct, skips):
            return cipher.vigenere_decrypt(ct, self.key, skips=skips)

        for width in (8, 50):
            ranked = search.beam_skips(
                self.ct, self.cands, decrypt,
                lambda t: fitness.score(t, n=2), width=width)
            beam_obj = self.objective(
                self.ct, self.cands, ranked[0][1], self.key)
            self.assertGreaterEqual(
                obj + 1e-9, beam_obj,
                f"DP objective {obj} below beam w{width} {beam_obj}")

    def test_matches_exhaustive_enumeration_on_a_small_case(self):
        """Against 2^m brute force, where m is small enough to enumerate."""
        pt = solved_plaintext()[:120]
        key = c.gp.spell("PARABLE")
        ct = cipher.vigenere_encrypt(pt, key, interrupter=0)
        cands = search.candidates(ct)
        self.assertLessEqual(len(cands), 16, "case too large to enumerate")
        rows, cums = search.layers_repeating(ct, key, search.sub)
        obj, skips, _ = search.solve(ct, cands, rows, cums)

        best_obj, best_set = float("-inf"), None
        for mask in range(1 << len(cands)):
            trial = [cands[i] for i in range(len(cands)) if mask >> i & 1]
            o = self.objective(ct, cands, trial, key)
            if o > best_obj:
                best_obj, best_set = o, frozenset(trial)

        self.assertAlmostEqual(obj, best_obj, places=6)
        self.assertEqual(skips, best_set)

    def test_known_answer_on_real_ciphertext_0_1_the_hard_case(self):
        """0.13 pins the easy case; this pins the one the calibration rests on.

        `beam_skips`'s docstring says to prune with `fitness.score(t, n=2)`
        because negated `fitness.chi2` does not scale past a single
        interrupter. Solved section 0.1 has 11 interrupters among
        25 ciphertext F in 515 runes, where chi2 returns 8 true / 3 false /
        3 missed while `score(n=2)` recovers all 11 rune-exact at rank 0.
        """
        gp = c.gp
        ct = list(c.section("0.1").text().indices)[:515]
        want = [i for s in c.section("0.1").sentences()
                for i in gp.spell(s.english)][:515]
        truth = frozenset(i for i, (x, pt) in enumerate(zip(ct, want, strict=False))
                          if pt == 0 and x == 0)
        self.assertEqual(len(truth), 11, "0.1 should carry 11 true interrupters")
        key = gp.spell("DIVINITY")
        cands = [i for i, x in enumerate(ct) if x == 0]
        self.assertEqual(len(cands), 25, "0.1 should carry 25 ciphertext F")

        def dec(text, skips=frozenset()):
            return cipher.vigenere_decrypt(text, key, skips)

        out = search.beam_skips(
            ct, cands, dec, lambda s: fitness.score(s, n=2), width=50,
            final_score=lambda s: fitness.score(s, n=4))
        self.assertEqual(set(out[0][1]), set(truth))
        self.assertEqual(list(dec(ct, out[0][1])), want)

        # and the reason the docstring changed: chi2 does not get there.
        bad = search.beam_skips(
            ct, cands, dec, lambda s: -fitness.chi2(s), width=50,
            final_score=lambda s: fitness.score(s, n=4))
        self.assertNotEqual(set(bad[0][1]), set(truth),
                            "if chi2 now succeeds, the docstring's advice is stale")

    def test_refine_closes_the_case_the_exact_dp_gets_wrong(self):
        """`refine()` closes the known hard solved-section case.

        `search.py:148-157` records that the exact DP's optimum is NOT the true
        interrupter set on 0.1: it swaps 160 for 165 and returns 509 of 515
        runes, and `refine()` closes it to 515/515 by hill-climbing on 4-grams
        over flips AND swaps, since the truth differs from the DP answer by one
        of each. `solve` is the module's preferred instrument, but it was gated
        only on 0.13 -- one interrupter of five -- while the function that makes
        it correct on the hard case was ungated and its 515/515 claim rested on
        a measurement nothing re-ran.

        Both halves are asserted. If a change ever made `solve` exact here, the
        first assertion fails and the comment above it is stale -- pinning only
        `refine` would let that pass unnoticed.
        """
        gp = c.gp
        ct = list(c.section("0.1").text().indices)[:515]
        want = [i for s in c.section("0.1").sentences()
                for i in gp.spell(s.english)][:515]
        truth = frozenset(i for i, (x, pt) in enumerate(zip(ct, want, strict=False))
                          if pt == 0 and x == 0)
        cands = search.candidates(ct)
        key = gp.spell("DIVINITY")
        stream = [key[j % len(key)] for j in range(len(ct) + len(cands) + 2)]
        rows, cums = search.layers_stream(ct, stream, search.sub, len(cands) + 1)
        _, skips, pt = search.solve(ct, cands, rows, cums)

        self.assertNotEqual(set(skips), set(truth),
                            "search.py:148-157 says the DP optimum is not the "
                            "truth here; if it now is, that comment is stale")
        self.assertEqual(sum(a == b for a, b in zip(pt, want, strict=False)), 509)

        def dec(text, sk=frozenset()):
            return cipher.vigenere_decrypt(text, key, sk)

        rskips, rpt = search.refine(ct, cands, dec, skips)
        self.assertEqual(set(rskips), set(truth))
        self.assertEqual(list(rpt), want)

    def test_known_answer_on_real_ciphertext_0_13(self):
        """The strongest gate available: a set Cicada actually used.

        0.13's keystream is phi(primes) and its true interrupter set is {56} of
        five ciphertext F -- so four of the five F are ordinary encryptions and
        the answer is not forced. A planted test proves the recursion; this
        proves it on the book.
        """
        import itertools
        ct = list(c.section("0.13").text().indices)
        cands = search.candidates(ct)
        self.assertEqual(len(cands), 5, "0.13 should carry five ciphertext F")
        stream = list(itertools.islice(cipher.phi_primes(), len(ct) + 10))
        rows, cums = search.layers_stream(ct, stream, search.sub, len(cands) + 1)
        _, skips, pt = search.solve(ct, cands, rows, cums)

        self.assertEqual(set(skips), {56})
        self.assertEqual(list(pt), list(cipher.phi_prime_decrypt(ct, skips={56})))
        self.assertTrue(c.gp.unspell(list(pt)).startswith("ANENDWITHINTHEDEEPWEB"))
