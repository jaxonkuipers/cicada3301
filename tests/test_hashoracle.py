"""Known-answer tests for solver.hashoracle and solver.pgp.

An oracle is worthless unless it FIRES. So the controls here are not "does the
candidate match page-56" -- it does not, and that is a negative result, not a
test. They are:

  * plant a digest. For every (encoding, hash) pair in the family, hash a solved
    section's real plaintext under that pair and check `identify` names it. If a
    pair were silently broken, its planted digest would come back None.
  * a real external answer. 36 of Cicada's signed communications carry an RSA
    signature over a byte string only the RFC 4880 canonicaliser produces. That
    is a known-answer test with an answer this repo did not choose.
"""

import unittest
from datetime import UTC, datetime
from unittest import mock

from solver import corpus, hashes512, pgp
from solver import hashoracle as ho

c = corpus.load()
# 0.3 is printed unenciphered (sections.csv cipher='none'), so its rune stream
# IS Cicada's plaintext -- real marks, real line breaks, no decryption step to
# be wrong about.
PLAIN = c.section("0.3").text()


class TestPage56Digest(unittest.TestCase):
    def test_digest_comes_from_the_corpus_and_is_128_hex(self):
        d = ho.page56_digest(c)
        self.assertEqual(len(d), 128)
        self.assertEqual(len(bytes.fromhex(d)), 64)

    def test_digest_is_not_the_all_zero_or_empty_hash(self):
        d = ho.page56_digest(c)
        for fn in ho.HASHES.values():
            self.assertNotEqual(fn(b"").hex(), d)


class TestOracleFires(unittest.TestCase):
    """The planted-digest control: every pair in the family must be reachable."""

    def test_every_encoding_and_hash_pair_is_identified(self):
        encs = ho.encodings(PLAIN)
        self.assertGreater(len(encs), 20)
        for ename, data in encs.items():
            for hname, fn in ho.HASHES.items():
                got = ho.identify(PLAIN, fn(data).hex())
                self.assertIsNotNone(got, f"{ename}/{hname} planted but not found")
                gote, goth = got.rsplit("/", 1)
                # Distinct names may render identical bytes; the contract is
                # that whatever is named reproduces the digest.
                self.assertEqual(encs[gote], data, f"{ename}/{hname} -> {got}")
                self.assertEqual(goth, hname)

    def test_verify_is_true_exactly_when_identify_is_not_none(self):
        d = ho.HASHES["sha512"](ho.encodings(PLAIN)["translit.upper"]).hex()
        self.assertTrue(ho.verify(PLAIN, d))
        self.assertIsNotNone(ho.identify(PLAIN, d))

    def test_coverage_matches_the_family_size(self):
        self.assertEqual(ho.coverage(PLAIN),
                         len(ho.encodings(PLAIN)) * len(ho.HASHES))

    def test_hash_catalogue_has_one_source_of_truth(self):
        self.assertIs(ho.HASHES, hashes512.ALL)
        self.assertEqual(
            dict(hashes512.ALL), dict(hashes512.STDLIB) | dict(hashes512.PUREPY)
        )
        self.assertFalse(hashes512.STDLIB.keys() & hashes512.PUREPY.keys())
        self.assertEqual((len(hashes512.STDLIB), len(hashes512.PUREPY)), (5, 6))

    def test_hash_catalogues_are_immutable_so_cached_coverage_cannot_drift(self):
        for catalogue in (hashes512.STDLIB, hashes512.PUREPY, hashes512.ALL):
            with self.assertRaises(TypeError):
                catalogue["extra"] = lambda data: bytes(64)


class TestDigestCache(unittest.TestCase):
    def test_cache_is_bounded_lru_and_cached_tables_cannot_be_mutated(self):
        self.assertGreater(len(PLAIN), 66)
        ho._digest_items.cache_clear()
        self.addCleanup(ho._digest_items.cache_clear)

        fake_hashes = {"tiny": lambda data: (data + bytes(64))[:64]}
        with mock.patch.object(ho, "HASHES", fake_hashes):
            first = PLAIN[:1]
            table = ho.digest_table(first)
            table["poison"] = "bad"
            self.assertNotIn("poison", ho.digest_table(first))
            self.assertEqual(ho._digest_items.cache_info().hits, 1)

            for start in range(1, 66):
                ho.digest_table(PLAIN[start:start + 1])
            info = ho._digest_items.cache_info()
            self.assertEqual((info.maxsize, info.currsize), (64, 64))

            misses = info.misses
            ho.digest_table(first)
            self.assertEqual(ho._digest_items.cache_info().misses, misses + 1)


class TestOracleRejects(unittest.TestCase):
    def test_a_different_section_does_not_match_a_planted_digest(self):
        d = ho.HASHES["sha512"](ho.encodings(PLAIN)["translit.upper"]).hex()
        self.assertIsNone(ho.identify(c.section("0.0").text(), d))

    def test_page56_does_not_match_any_solved_section(self):
        d = ho.page56_digest(c)
        for sid in ("0.0", "0.1", "0.2", "0.3", "0.4", "0.13", "0.14"):
            self.assertIsNone(ho.identify(c.section(sid).text(), d))


class TestEncodingsRoundTrip(unittest.TestCase):
    """A rendering that cannot be decoded back is a rendering with a bug."""

    def test_index_bytes_round_trip(self):
        e = ho.encodings(PLAIN)
        self.assertEqual(list(e["index.bytes"]), list(PLAIN.indices))
        self.assertEqual([b - 1 for b in e["index1.bytes"]], list(PLAIN.indices))

    def test_rune_encodings_round_trip(self):
        e = ho.encodings(PLAIN)
        gp = PLAIN.gp
        for tag, codec in (("utf8", "utf-8"), ("utf16le", "utf-16-le"),
                           ("utf16be", "utf-16-be"), ("utf32le", "utf-32-le"),
                           ("utf32be", "utf-32-be")):
            back = gp.to_indices(e[f"runes.{tag}"].decode(codec))
            self.assertEqual(back, list(PLAIN.indices), tag)

    def test_decimal_and_prime_renderings_round_trip(self):
        e = ho.encodings(PLAIN)
        gp = PLAIN.gp
        self.assertEqual([int(x) for x in e["index.dec.space"].split()],
                         list(PLAIN.indices))
        self.assertEqual([gp.primes.index(int(x))
                          for x in e["prime.dec.space"].split()],
                         list(PLAIN.indices))

    def test_word_and_line_segmentation_preserves_every_rune(self):
        e = ho.encodings(PLAIN)
        gp = PLAIN.gp
        for name in ("runes.utf8.words.space", "runes.utf8.lines.lf",
                     "runes.utf8.lines.crlf"):
            back = gp.to_indices(e[name].decode())
            self.assertEqual(back, list(PLAIN.indices), name)

    def test_newline_variants_are_the_base_plus_a_terminator(self):
        e = ho.encodings(PLAIN)
        self.assertEqual(e["translit.upper+lf"], e["translit.upper"] + b"\n")
        self.assertEqual(e["translit.upper+crlf"], e["translit.upper"] + b"\r\n")


class TestCicadaSigningConvention(unittest.TestCase):
    """The external known answer: Cicada's own RSA signatures."""

    key = pgp.parse_public_key(c.communication("cicada-3301-public-key").raw)
    signed = [m for m in c.communications if pgp.SIGNATURE_BEGIN in m.raw]

    def test_the_key_is_the_published_3301_fingerprint(self):
        self.assertEqual(self.key.fingerprint,
                         "6D854CD7933322A601C3286D181F01E57A35090F")
        self.assertEqual((self.key.nbits, self.key.e), (4096, 65537))

    def test_every_signed_communication_verifies(self):
        self.assertEqual(len(self.signed), 36)
        bad = [m.id for m in self.signed
               if not pgp.verify_cleartext(m.raw, self.key).ok]
        self.assertEqual(bad, [])

    def test_mutating_a_signed_body_invalidates_the_signature(self):
        message = c.communication("2012-01-key-in-front-of-you")
        mutated = message.raw.replace(
            "The key has always been right",
            "The key has never been right",
            1,
        )
        self.assertEqual(
            mutated.split(pgp.SIGNATURE_BEGIN, 1)[1],
            message.raw.split(pgp.SIGNATURE_BEGIN, 1)[1],
        )
        self.assertFalse(pgp.verify_cleartext(mutated, self.key).ok)

    def test_manifest_signature_times_come_from_the_packets(self):
        for message in self.signed:
            signature = pgp.parse_signature(message.raw)
            stamp = next(
                int.from_bytes(data, "big")
                for kind, data in pgp._subpackets(signature.hashed)
                if kind == 2
            )
            observed = datetime.fromtimestamp(stamp, UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            self.assertEqual(message.signed_at, observed, message.id)

    def test_only_the_creation_time_is_inside_the_signature(self):
        # Every signature carries exactly two subpackets on opposite sides of
        # the hash. Creation time binds; the unhashed issuer key id does not.
        for message in self.signed:
            signature = pgp.parse_signature(message.raw)
            hashed = [k for k, _ in pgp._subpackets(signature.hashed)]
            unhashed = [k for k, _ in pgp._subpackets(signature.unhashed)]
            self.assertEqual(hashed, [2], message.id)
            self.assertEqual(unhashed, [16], message.id)

    def test_canonicaliser_matches_the_signed_bytes(self):
        # rfc4880_canonical must reproduce what the signature covers, for a
        # message with no dash-escaping to complicate it.
        m = c.communication("2012-01-key-in-front-of-you")
        v = pgp.verify_cleartext(m.raw, self.key)
        self.assertTrue(v.ok)
        self.assertEqual(ho.rfc4880_canonical(m.body.strip("\n")), v.signed)

    def test_trailing_whitespace_is_stripped_not_kept(self):
        # 2013-01-rune-table-morse carries its whole payload in tabs and spaces,
        # so canonicalisation reduces it to almost nothing -- the morse payload
        # is real but sits OUTSIDE the signature.
        m = c.communication("2013-01-rune-table-morse")
        v = pgp.verify_cleartext(m.raw, self.key)
        self.assertTrue(v.ok)
        self.assertEqual(len(v.signed), 14)
        self.assertGreater(len(m.body), 500)


class TestXorShares(unittest.TestCase):
    """The three 991-byte hex blocks XOR to another signed message, exactly."""

    def test_three_hash_blocks_reconstruct_the_signed_ciphertext_file(self):
        ids = ("2014-01-liber-primus-hash-block",
               "2014-01-liber-primus-hash-block-outguess-01",
               "2014-01-liber-primus-hash-block-outguess-02")
        blobs = [bytes.fromhex("".join(c.communication(i).body.split()))
                 for i in ids]
        self.assertEqual([len(b) for b in blobs], [991, 991, 991])
        x = bytes(p ^ q ^ r for p, q, r in zip(*blobs, strict=True))
        self.assertEqual(
            x, c.communication("2014-01-signed-ciphertext").raw.encode("utf-8"))

    def test_the_interconnectedness_blob_is_an_id3_tagged_mp3(self):
        b = bytes.fromhex(
            "".join(c.communication("2014-01-interconnectedness-hex").body.split()))
        self.assertEqual(len(b), 6_651_873)
        self.assertEqual(b[:3], b"ID3")
        self.assertIn(b"Interconnectedness", b[:64])
        self.assertIn(b"3301", b[:64])

class TestHashFunctionsAreGated(unittest.TestCase):
    """Published known answers for the six functions `hashlib` does not ship.

    `hashoracle.HASHES` is 11 functions and six of them are this repo's own
    pure-Python code. An oracle that reports "no match over 704 pairs" is only
    worth something if every one of those 704 is the function it claims to be,
    so each is pinned to a vector this repo did not choose.

    The trap this guards is `keccak512` vs `sha3_512`. SHA-3 was standardised in
    August 2015 and changed Keccak's domain-separation padding from 0x01 to
    0x06; LP2 was printed in January 2014, so original Keccak is the
    period-correct function and they are different hashes of the same sponge.
    """

    KATS = (
        ("keccak512", b"",
         "0eab42de4c3ceb9235fc91acffe746b29c29a8c366b7c60e4e67c466f36a4304"
         "c00fa9caf9d87976ba469bcbe06713b435f091ef2769fb160cdab33d3670680e"),
        ("whirlpool", b"",
         "19fa61d75522a4669b44e39c1d2e1726c530232130d407f89afee0964997f7a7"
         "3e83be698b288febcf88e3e03c4f0757ea8964e59b63d93708b138cc42a66eb3"),
        ("whirlpool", b"abc",
         "4e2448a4c6f486bb16b6562c73b4020bf3043e3a731bce721ae1b303d97e6d4c"
         "7181eebdb6c57e277d0e34957114cbd6c797fc9d95d8b582d225292076d4eef5"),
        ("blake512", b"",
         "a8cfbbd73726062df0c6864dda65defe58ef0cc52a5625090fa17601e1eecd1b"
         "628e94f396ae402a00acc9eab77b4d4c2e852aaaa25a636d80af3fc7913ef5b8"),
    )

    def test_published_vectors(self):
        for name, data, want in self.KATS:
            with self.subTest(hash=name, data=data):
                self.assertEqual(ho.HASHES[name](data).hex(), want)

    def test_keccak256_is_the_ethereum_empty_hash(self):
        self.assertEqual(
            hashes512.keccak256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

    def test_the_sponge_reproduces_hashlib_sha3_and_shake(self):
        """Same sponge, SHA-3's 0x06 padding: must equal hashlib bit for bit."""
        import hashlib
        for n in (0, 1, 71, 72, 73, 135, 136, 137, 200):
            data = bytes(range(256))[:n] * 3
            self.assertEqual(hashes512._sha3_512_ours(data),
                             hashlib.sha3_512(data).digest(), n)
            self.assertEqual(hashes512._shake256_ours(data, 64),
                             hashlib.shake_256(data).digest(64), n)

    def test_keccak512_is_not_sha3_512(self):
        import hashlib
        self.assertNotEqual(ho.HASHES["keccak512"](b""),
                            hashlib.sha3_512(b"").digest())

    def test_fnv_offset_basis_is_derived_not_transcribed(self):
        self.assertEqual(hashes512._basis(32), 0x811C9DC5)
        self.assertEqual(hashes512._basis(64), 0xCBF29CE484222325)
        self.assertEqual(hashes512.fnv1a(b"foobar", 32), 0xBF9CF968)
        self.assertEqual(hashes512.fnv1a(b"foobar", 64), 0x85944171F73967E8)

    def test_every_hash_in_the_family_returns_64_bytes(self):
        for name, fn in ho.HASHES.items():
            with self.subTest(hash=name):
                self.assertEqual(len(fn(b"cicada")), 64)


if __name__ == "__main__":
    unittest.main()
