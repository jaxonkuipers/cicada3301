"""Known-answer tests: every solved section decrypts from its recorded key.

These prove three things at once: the cipher primitives, the measured
interrupter semantics (plaintext F passes through, keystream holds), and the
corpus alignment (section boundaries, sentences, speller). The interrupter
positions are taken from the known plaintext -- during a real attack they are
part of the unknown key; see lib/cipher's module docstring.
"""

import unittest

from lib import cipher, corpus

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

    def test_short_running_key_raises_clearly(self):
        # A key text shorter than the ciphertext used to escape as a bare
        # StopIteration, which reads as an empty iterator to the caller.
        with self.assertRaises(ValueError) as cm:
            cipher.running_key_decrypt([1, 2, 3, 4, 5], [1, 2])
        self.assertIn("exhausted", str(cm.exception))

    def test_skips_hold_keystream(self):
        # positions in skips pass through and do not consume the key
        ct = [5, 0, 6]
        got = cipher.vigenere_decrypt(ct, [1, 2], skips={1})
        self.assertEqual(got, [4, 0, 4])  # 5-1, pass, 6-2


if __name__ == "__main__":
    unittest.main()
