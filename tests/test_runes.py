"""Regression tests for lib.runes extraction and query canonicalisation."""

import unittest

from lib import corpus, runes


def runs(text, notation=None):
    out = list(runes.extract(text))
    return [r for r in out if notation is None or r.notation == notation]


class TestExtraction(unittest.TestCase):
    def test_newline_does_not_join(self):
        # A pasted rune grid must not fuse into one sequence that never existed.
        grid = "ᚠᚢᚦ\nᚱᛁᚳ\nᛄᛖᛗ"
        self.assertEqual(runs(grid, "runic-joined"), [])
        self.assertEqual(len(runs(grid, "runic")), 3)

    def test_separators_still_join(self):
        (r,) = runs("ᚠᚢᚦ-ᚱᛁᚳ", "runic-joined")
        self.assertEqual(len(r.canon), 6)

    def test_non_gp_rune_breaks_run(self):
        # ᚲ is Younger Futhark, not GP: dropping it would fabricate adjacency.
        self.assertEqual(runs("ᚱᚲᚳ", "runic"), [])
        frags = runs("ᚠᚢᚦᚲᚱᛁᚳ", "runic")  # two fragments, no join across ᚲ
        self.assertEqual([r.raw for r in frags], ["ᚠᚢᚦ", "ᚱᛁᚳ"])

    def test_translit_dash_run_without_digraphs(self):
        (r,) = runs("key was F-U-L-M maybe", "translit")
        self.assertEqual(r.raw, "F-U-L-M")
        (r,) = runs("I-N-T-R-O-D-U-C-T", "translit")
        self.assertEqual(len(r.canon), 9)
        (r,) = runs("O-N-IO-N", "translit")
        self.assertEqual(len(r.canon), 4)

    def test_translit_space_run_needs_digraphs(self):
        # Space-separated single letters are how prose looks, not notation.
        self.assertEqual(runs("I saw A B C D there", "translit"), [])
        (r,) = runs("F U TH O R C", "translit")
        self.assertEqual(len(r.canon), 6)

    def test_numeric_minus_sign_is_not_a_separator(self):
        # `-` joins indices in '19-21-23', but in '8 -2' it is a sign. Eating
        # it indexed difference vectors and +/-1 matrices as rune text: 106 of
        # 1210 numeric runs in the shipped archive were fabricated this way.
        self.assertEqual(runs("8 -2  3 -2  3 18  9 -4", "numeric"), [])
        self.assertEqual(runs("0,-2,-4,-6,-10", "numeric"), [])
        self.assertEqual(runs("1  0  0 |\n|  0 -1  0 |\n|  0  0  1", "numeric"), [])
        # The magnitude must not open the next run either.
        self.assertEqual(runs("4 -6 4 9 -8 10", "numeric"), [])
        # Tight `-` between digits is still index notation.
        (r,) = runs("19-21-23-27", "numeric")
        self.assertEqual(len(r.canon), 4)

    def test_numeric_newline_does_not_join(self):
        # Same rule the runic extractor follows: the rows of a pasted grid are
        # separate sequences, not one that never existed.
        grid = "6 10 19 21 25 8\n4 15 16 17 20 4\n8 24 13 28 21 7"
        got = runs(grid, "numeric")
        self.assertEqual([len(r.canon) for r in got], [6, 6, 6])

    def test_numeric_raw_as_written(self):
        (r,) = runs("indices [19, 21, 23, 27] here", "numeric")
        self.assertEqual(r.raw, "19, 21, 23, 27")
        self.assertEqual(len(r.canon), 4)


class TestQuery(unittest.TestCase):
    def test_bare_numbers_are_rejected(self):
        for q in ("2025", "123", "3301"):
            with self.assertRaises(ValueError):
                runes.canonicalise_query(q)

    def test_separated_indices(self):
        canon, notation = runes.canonicalise_query("20 25")
        self.assertEqual(notation, "numeric")
        self.assertEqual(len(canon), 2)
        canon, _ = runes.canonicalise_query("19-21-23-27")
        self.assertEqual(len(canon), 4)

    def test_mixed_and_foreign_input_is_refused(self):
        # Silently keeping only what parses turns 'F-U-TH-ᚠ' into a one-rune
        # query and answers a question nobody asked.
        for q in ("hello ᚠᚡ world", "F-U-TH-ᚠ", "ᚠᚢᚦ 3301", "ᚱᚲᚳ"):
            with self.assertRaises(ValueError, msg=q):
                runes.canonicalise_query(q)

    def test_translit_mixed_with_digits_is_refused(self):
        # Splitting on non-letters silently discarded the digits, so both of
        # these came back as the same three-rune query.
        for q in ("F-U-TH-2", "F-U-TH 3301"):
            with self.assertRaises(ValueError, msg=q):
                runes.canonicalise_query(q)

    def test_signed_indices_are_refused(self):
        # `_NUMERIC_SEP.split` eats the minus, leaving four clean-looking
        # indices the source never wrote.
        for q in ("0,-2,-4,-6", "-1 2 3 4", "8 -2 3 18"):
            with self.assertRaises(ValueError, msg=q):
                runes.canonicalise_query(q)

    def test_clean_runic_still_reads(self):
        canon, notation = runes.canonicalise_query("ᚠᚢᚦ-ᚱᛁᚳ")
        self.assertEqual(notation, "runic")
        self.assertEqual(len(canon), 6)

    def test_translit_query(self):
        canon, notation = runes.canonicalise_query("F-U-TH")
        self.assertEqual(notation, "translit")
        self.assertEqual(len(canon), 3)


class TestGematria(unittest.TestCase):
    def test_spell_rejects_runes(self):
        gp = corpus.load().gp
        with self.assertRaises(ValueError):
            gp.spell("ᚠᚢᚦ")

    def test_to_runes_rejects_out_of_range(self):
        gp = corpus.load().gp
        with self.assertRaises(ValueError):
            gp.to_runes([100])

    def test_to_indices_skips_non_gp(self):
        gp = corpus.load().gp
        self.assertEqual(gp.to_indices("ᚠ ᚢᚲᚦ"), [0, 1, 2])

    def test_unspell(self):
        gp = corpus.load().gp
        self.assertEqual(gp.unspell(gp.spell("TUNNELING")), "TUNNELNG")
        self.assertEqual(gp.unspell([0, 1, 2], sep="-"), "F-U-TH")

    def test_spellings_track_csv(self):
        gp = corpus.load().gp
        self.assertEqual(gp.spellings["ING"], 21)
        self.assertEqual(gp.spellings["IO"], 27)
        self.assertEqual(gp.spellings["Q"], 5)  # documented extra alias


if __name__ == "__main__":
    unittest.main()
