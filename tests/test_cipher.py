"""Known-answer tests: every solved section decrypts from its recorded key.

These prove three things at once: the cipher primitives, the measured
interrupter semantics (plaintext F passes through, keystream holds), and the
corpus alignment (section boundaries, sentences, speller). The interrupter
positions are taken from the known plaintext -- during a real attack they are
part of the unknown key; see solver/cipher's module docstring.
"""

import unittest

from solver import cipher, corpus

c = corpus.load()
gp = c.gp


def plaintext_of(sec_id):
    return [i for s in c.section(sec_id).sentences() for i in gp.spell(s.english)]


def skips_of(ct, want):
    """Ciphertext positions where the plaintext rune is the F interrupter."""
    return frozenset(
        i for i, (x, p) in enumerate(zip(ct, want, strict=False)) if p == 0 and x == 0
    )


class TestSolvedSections(unittest.TestCase):
    def test_0_0_inverted_gematria(self):
        ct = list(c.section("0.0").text().indices)
        self.assertEqual(cipher.atbash(ct), plaintext_of("0.0"))

    def test_0_2_inverted_then_shift(self):
        ct = list(c.section("0.2").text().indices)
        got = cipher.shift_decrypt(cipher.atbash(ct), 26)  # p = (28-c+3) mod 29
        self.assertEqual(got, plaintext_of("0.2"))

    def test_0_3_and_0_14_identity(self):
        for sec in ("0.3", "0.14"):
            self.assertEqual(list(c.section(sec).text().indices), plaintext_of(sec))

    def test_0_1_vigenere_divinity(self):
        ct = list(c.section("0.1").text().indices)
        want = plaintext_of("0.1")
        key = gp.spell("DIVINITY")
        # Measured on the page: runes 0-514 are enciphered, 515 to the end of
        # the section (SOME WISDOM, KNOW THIS, the word list) are printed
        # unencrypted.
        enc = 515
        got = cipher.vigenere_decrypt(ct[:enc], key, skips_of(ct[:enc], want))
        self.assertEqual(got, want[:enc])
        self.assertEqual(ct[enc : len(want)], want[enc:])  # plaintext tail

    def test_0_1_encrypt_round_trip(self):
        ct = list(c.section("0.1").text().indices)
        want = plaintext_of("0.1")
        got = cipher.vigenere_encrypt(want[:515], gp.spell("DIVINITY"))
        self.assertEqual(got, ct[:515])

    def test_0_4_vigenere_firfumferenfe(self):
        ct = list(c.section("0.4").text().indices)
        want = plaintext_of("0.4")
        key = gp.spell("FIRFUMFERENFE")
        enc = 319  # enciphered 0-318; AN INSTRUCTION onward printed unencrypted
        got = cipher.vigenere_decrypt(ct[:enc], key, skips_of(ct[:enc], want))
        self.assertEqual(got, want[:enc])
        self.assertEqual(ct[enc : len(want)], want[enc:])

    def test_0_13_phi_of_primes(self):
        ct = list(c.section("0.13").text().indices)
        want = plaintext_of("0.13")
        # One true interrupter at 56; ciphertext F at 35, 47, 51 and 74 are
        # ordinary encryptions -- ciphertext F alone does not mark a skip.
        got = cipher.phi_prime_decrypt(ct, skips={56})
        self.assertEqual(got, want)


    def test_2014_onion4_line_vigenere_without_interrupter(self):
        # The eighteen runes inside the JPEG of the signed message
        # 2014-01-let-the-text-guide-you, with digits 5 and 3 printed among
        # them in the clear. Key: the book's own
        # opening words.  Plaintext: the fourth 2014 onion,
        # avowyfgl5lkzfj3n.onion, in GP letters (U for v, C for k, S for z).
        # Both plaintext F (positions 5 and 11) are ENCIPHERED here: the
        # interrupter is a convention of the book's sections, not of every
        # Cicada Vigenere.
        ct = [2, 19, 23, 12, 0, 19, 24, 4, 1, 25, 21, 4, 21, 28, 19, 12, 0, 27]
        key = gp.spell("WELCOMEPILGRIMTOTHE")
        want = gp.spell("avowyfgl5lkzfj3n.onion")
        self.assertEqual(len(key), 18)
        self.assertEqual(gp.unspell(want), "AUOWYFGLLCSFJNONIAN")
        self.assertEqual(cipher.vigenere_decrypt(ct, key), want)
        self.assertEqual(cipher.vigenere_encrypt(want, key, interrupter=None), ct)
        self.assertNotEqual(cipher.vigenere_encrypt(want, key, interrupter=0), ct)
        self.assertEqual([i for i, x in enumerate(want) if x == 0], [5, 11])


class TestPrimitives(unittest.TestCase):
    def test_autokey_round_trips(self):
        pt = gp.spell("AN INSTRUCTION QUESTION ALL THINGS")
        key = gp.spell("FIRFUMFERENFE")
        # plaintext autokey: c = p + (key ++ p)
        stream = key + pt
        ct = [(p + stream[i]) % 29 for i, p in enumerate(pt)]
        self.assertEqual(cipher.autokey_pt_decrypt(ct, key), pt)
        # ciphertext autokey: c = p + (key ++ c)
        ct2, ks = [], list(key)
        for i, p in enumerate(pt):
            x = (p + ks[i]) % 29
            ct2.append(x)
            ks.append(x)
        self.assertEqual(cipher.autokey_ct_decrypt(ct2, key), pt)

    def test_beaufort_round_trips(self):
        pt = gp.spell("SOME WISDOM")
        key = gp.spell("DIVINITY")
        ct = [(k - p) % 29 for p, k in zip(pt, (key * 9)[: len(pt)], strict=True)]
        self.assertEqual(cipher.beaufort_decrypt(ct, key), pt)
        ct = [(p - k) % 29 for p, k in zip(pt, (key * 9)[: len(pt)], strict=True)]
        self.assertEqual(cipher.variant_beaufort_decrypt(ct, key), pt)

    def test_affine(self):
        pt = list(range(29))
        ct = [(7 * p + 11) % 29 for p in pt]
        self.assertEqual(cipher.affine_decrypt(ct, 7, 11), pt)

    def test_primitives_accept_any_iterable(self):
        # Every primitive is annotated Iterable[int]. autokey_ct_decrypt reads
        # the ciphertext twice (keystream, then text) and used to return []
        # for a generator -- a silent "no candidates" inside a sweep.
        ct = [3, 7, 11, 2, 5, 9, 14]
        key = [1, 2, 3]
        for fn in (
            cipher.vigenere_decrypt,
            cipher.beaufort_decrypt,
            cipher.variant_beaufort_decrypt,
            cipher.autokey_pt_decrypt,
            cipher.autokey_ct_decrypt,
        ):
            want = fn(list(ct), key)
            self.assertEqual(len(want), len(ct), fn.__name__)
            self.assertEqual(fn((x for x in ct), key), want, fn.__name__)
            self.assertEqual(fn(map(int, ct), key), want, fn.__name__)

        want = cipher.vigenere_encrypt(ct, key)
        self.assertEqual(cipher.vigenere_encrypt((x for x in ct), key), want)
        self.assertEqual(cipher.vigenere_encrypt(map(int, ct), key), want)

    def test_autokey_ct_skips_hold_the_keystream(self):
        # Encrypt with the measured interrupter rule (plaintext F passes
        # through, keystream holds), then decrypt with those positions skipped.
        pt = [4, 0, 9, 3, 0, 12, 7, 5]
        key = [2, 6]
        ks, ct = list(key), []
        used = 0
        for x in pt:
            if x == 0:
                ct.append(0)
                continue
            y = (x + ks[used]) % 29
            ct.append(y)
            ks.append(y)
            used += 1
        skips = {i for i, x in enumerate(pt) if x == 0}
        self.assertEqual(cipher.autokey_ct_decrypt(ct, key, skips), pt)

    def test_primes_are_cached_not_regenerated(self):
        # phi_prime_decrypt started a fresh trial-division pass every call:
        # 0.134s over the 12,956-rune stream, ~22 minutes for a 10k-candidate
        # sweep over skip-set hypotheses. 0.13's keystream is fixed.
        import itertools

        def naive():
            n = 2
            while True:
                if all(n % p for p in range(2, int(n**0.5) + 1)):
                    yield n
                n += 1

        self.assertEqual(
            list(itertools.islice(cipher.primes(), 3000)),
            list(itertools.islice(naive(), 3000)),
        )
        # Two independent iterators must not interfere through the cache.
        a, b = cipher.primes(), cipher.primes()
        self.assertEqual([next(a) for _ in range(5)], [next(b) for _ in range(5)])
        self.assertEqual(list(itertools.islice(cipher.phi_primes(), 5)),
                         [1, 2, 4, 6, 10])

    def test_prime_cache_survives_concurrent_extension(self):
        # Two threads inside the extension block both read _PRIMES[-1], both
        # scan to the same prime, and both append it: the list goes
        # non-monotonic and every later index shifts. Module-global and never
        # revalidated, so a poisoned cache outlives the threads. Forced here
        # by pausing between the read and the append; _is_prime is untouched.
        import threading
        import time

        real = cipher._is_prime
        paused = threading.Event()

        def slow(n):
            r = real(n)
            if r and len(cipher._PRIMES) == 10 and not paused.is_set():
                paused.set()
                time.sleep(0.2)
            return r

        saved = list(cipher._PRIMES)
        try:
            cipher._PRIMES.clear()
            cipher._is_prime = slow
            def churn():
                it = cipher.primes()
                for _ in range(20):
                    next(it)

            threads = [threading.Thread(target=churn) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            got = list(cipher._PRIMES)
        finally:
            cipher._is_prime = real
            cipher._PRIMES[:] = saved
        self.assertTrue(paused.is_set(), "the interleaving was never forced")
        self.assertEqual(got, sorted(set(got)), "cache went non-monotonic")
        self.assertEqual(got[:10], [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])

    def test_monoalphabetic_primitives_take_skips(self):
        # An interrupted shift had no supported path, and CLAUDE.md forbids
        # writing the arithmetic inline. Default is unchanged behaviour --
        # 0.0 and 0.2 have no interrupter, per sections.csv.
        ct = [5, 0, 9, 3]
        self.assertEqual(cipher.shift_decrypt(ct, 2, skips={1}),
                         [3, 0, 7, 1])
        self.assertEqual(cipher.atbash(ct, skips={1}), [23, 0, 19, 25])
        self.assertEqual(cipher.affine_decrypt(ct, 7, 11, skips={1}),
                         [cipher.affine_decrypt([5], 7, 11)[0], 0,
                          cipher.affine_decrypt([9], 7, 11)[0],
                          cipher.affine_decrypt([3], 7, 11)[0]])
        for fn, args in ((cipher.shift_decrypt, (2,)), (cipher.atbash, ()),
                         (cipher.affine_decrypt, (7, 11))):
            self.assertEqual(fn(ct, *args), fn(ct, *args, skips=frozenset()))

    def test_out_of_range_skips_are_refused(self):
        # Skip sets are search state; silently ignoring a stray position makes
        # an attack report coverage it did not have.
        with self.assertRaises(ValueError):
            cipher.vigenere_decrypt([1, 2, 3], [1], skips={99})
        with self.assertRaises(ValueError):
            cipher.vigenere_decrypt([1, 2, 3], [1], skips={-1})
        self.assertEqual(cipher.vigenere_decrypt([1, 2, 3], [1], skips={2}),
                         [0, 1, 3])

    def test_cipher_inputs_are_runes_and_numeric_keys_are_modular(self):
        for decrypt in (
            lambda text: cipher.shift_decrypt(text, 1),
            cipher.atbash,
            lambda text: cipher.affine_decrypt(text, 7, 11),
            lambda text: cipher.vigenere_decrypt(text, [1]),
        ):
            with self.assertRaises(ValueError, msg=decrypt):
                decrypt([1, 29, 2])
        self.assertEqual(
            cipher.vigenere_decrypt([1, 2, 3], [30]),
            cipher.vigenere_decrypt([1, 2, 3], [1]),
        )
        self.assertEqual(cipher.vigenere_decrypt([0], [29], skips={0}), [0])
        for key in ([True], [1.5]):
            with self.assertRaises(TypeError):
                cipher.vigenere_decrypt([1, 2, 3], key)

    def test_short_running_key_raises_clearly(self):
        # A key text shorter than the ciphertext used to escape as a bare
        # StopIteration, which reads as an empty iterator to the caller.
        with self.assertRaises(ValueError) as cm:
            cipher.running_key_decrypt([1, 2, 3, 4, 5], [1, 2])
        self.assertIn("exhausted", str(cm.exception))

    def test_running_key_rejects_boolean_stream_values(self):
        for value in (False, True):
            with self.assertRaises(TypeError):
                cipher.running_key_decrypt([1], [value])

    def test_skips_hold_keystream(self):
        # positions in skips pass through and do not consume the key
        ct = [5, 0, 6]
        got = cipher.vigenere_decrypt(ct, [1, 2], skips={1})
        self.assertEqual(got, [4, 0, 4])  # 5-1, pass, 6-2


if __name__ == "__main__":
    unittest.main()
