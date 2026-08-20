"""Regression tests for lib.corpus parsing.

Every case here is pinned against the printed pages themselves; if one fails,
the parser or the transcription changed and derived results are suspect.
Run: python3 -m unittest discover -s tests
"""

import unittest

from lib import corpus

c = corpus.load()


class TestDrift(unittest.TestCase):
    def test_unsolved_stream(self):
        u = c.unsolved
        self.assertEqual(len(u), corpus.EXPECTED_UNSOLVED_LEN)
        self.assertEqual(u.sha256(), corpus.EXPECTED_UNSOLVED_SHA)

    def test_verify_all_pass(self):
        for name, passed, detail in corpus.verify():
            self.assertTrue(passed, f"{name}: {detail}")


class TestOther(unittest.TestCase):
    """Non-rune printed content must survive parsing with its structure."""

    def test_page15_number_square(self):
        (anchor, text), = c.page("page-15").text().other
        self.assertEqual(anchor, 8)  # follows the 9-rune tail of section 0.7
        rows = [[int(n) for n in row.split("-")] for row in text.split("/")]
        self.assertEqual([len(r) for r in rows], [4, 4, 4, 4])
        self.assertEqual([sum(r) for r in rows], [12670, 12713, 12350, 8250])

    def test_page49_block(self):
        (anchor, text), = c.page("page-49").text().other
        self.assertEqual(anchor, 65)
        rows = [row.split("-") for row in text.split("/")]
        self.assertEqual([len(r) for r in rows], [8] * 10)

    def test_page50_runeless_page(self):
        t = c.page("page-50").text()
        self.assertEqual(len(t), 0)
        (anchor, text), = t.other
        self.assertEqual(anchor, -1)
        rows = [row.split("-") for row in text.split("/")]
        self.assertEqual([len(r) for r in rows], [8] * 13)

    def test_page51_block_before_runes(self):
        t = c.page("page-51").text()
        (anchor, text) = t.other[0]
        self.assertEqual(anchor, -1)
        rows = [row.split("-") for row in text.split("/")]
        self.assertEqual([len(r) for r in rows], [8] * 9)
        self.assertIn("&", t.leading_marks)  # paragraph break before the runes

    def test_base60_block_decodes_to_256_bytes(self):
        groups = []
        for pid in ("page-49", "page-50", "page-51"):
            for _, text in c.page(pid).text().other:
                groups += text.replace("/", "-").split("-")
        self.assertEqual(len(groups), 256)
        alphabet = "0123456789" + "".join(
            chr(x) for x in range(ord("A"), ord("Z") + 1)
        ) + "".join(chr(x) for x in range(ord("a"), ord("x") + 1))
        vals = [alphabet.index(g[0]) * 60 + alphabet.index(g[1]) for g in groups]
        self.assertTrue(all(0 <= v <= 255 for v in vals))
        self.assertEqual(len(set(vals)), 161)

    def test_page56_hash_and_semicolon(self):
        t = c.page("page-56").text()
        self.assertEqual(t.other[0], (18, ";"))
        hexblock = t.other[1][1].replace("/", "")
        self.assertEqual(len(hexblock), 128)
        int(hexblock, 16)  # must be valid hex

    def test_paragraph_numerals(self):
        self.assertEqual(c.page("page-36").text().other, ((98, "1"),))
        self.assertEqual(
            c.page("page-37").text().other, ((-1, "2"), (90, "3"), (188, "4"))
        )
        self.assertEqual(c.page("page-38").text().other, ((56, "5"),))
        self.assertEqual(c.page("intro-11").text().other[0], (-1, "2"))
        self.assertEqual(c.page("page-10").text().other, ((168, "7"),))

    def test_concat_carries_runeless_page(self):
        t = corpus.RuneText.concat(
            [c.page(p).text() for p in ("page-49", "page-50", "page-51")]
        )
        anchors = [a for a, _ in t.other]
        # page-50's block follows page-49's last rune; page-51's does too
        # (page-50 contributes no runes), in printed order.
        self.assertEqual(anchors, [65, 65, 65])
        n49 = len(c.page("page-49").text())
        self.assertEqual(n49, 66)
        # page-51's leading '&' lands on the last rune before it
        self.assertIn("&", t.marks_after[65])

    def test_slicing_other(self):
        t = c.page("page-15").text()
        self.assertEqual(len(t[:9].other), 1)  # tail keeps its square
        self.assertEqual(t[9:].other, ())  # headline onward has none
        self.assertEqual(len(t[:9]), 9)


class TestWords(unittest.TestCase):
    def test_line_break_does_not_split_words(self):
        t = c.section("0.3").text()  # identity cipher: plaintext alignment
        prim = [tr.split("/")[0] for tr in c.gp.translits]
        words = ["".join(prim[i] for i in w.indices) for w in t.words()]
        self.assertIn("CIRCUMFERENCE", words)  # printed CIRCUMFEREN/CE
        self.assertEqual(len(words), 181)

    def test_unsolved_word_count(self):
        self.assertEqual(len(c.unsolved.words()), 2899)

    def test_split_on_word_mark(self):
        t = c.page("intro-11").text()
        self.assertTrue(len(t.split_on(corpus.WORD)) > 10)


if __name__ == "__main__":
    unittest.main()
