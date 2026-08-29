"""Provide the book's plaintext without solution-file metadata.

`corpus.Section.plaintext()` returns the markdown solution file, so a consumer
that mines words from it takes this repo's own vocabulary -- SECTION,
TRANSCRIPTION, POLYALPHABETIC, GEMATRIA, CSV -- as Cicada's text: 30 words and
1,023 runes, 26% of what the accessor returns. `research/shared/book.py` is the
clean view over `sentences.csv`. These tests pin the invariant so the defect
cannot come back silently.
"""

import re
import sys
import unittest
from pathlib import Path

from lib import corpus

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "shared"))
import book  # noqa: E402

c = corpus.load()

# The metadata the solution files carry and the book does not.
CONTAMINANTS = {
    "ALIGNMENT", "CSV", "DIRECT", "ENGLISH", "GEMATRIA", "INTRO", "INVERTED",
    "KEY", "LEVEL", "MOD", "PAGES", "PHI", "POLYALPHABETIC", "PRIMUS", "RUNE",
    "RUNES", "SECTION", "SENTENCE", "SENTENCES", "SHIFT", "SUBSTITUTION",
    "SUCCESSIVE", "TRANSCRIPTION", "TRANSLITERATION",
}


def _raw_words(section):
    return set(re.findall(r"[A-Za-z]+", (section.plaintext() or "").upper()))


class Book(unittest.TestCase):
    def test_clean_plaintext_is_2901_runes(self):
        """The book's own English spells to 2,901 runes."""
        n = sum(len(book.spelled(s, c.gp)) for s in book.sections(c))
        self.assertEqual(n, 2901, "the clean plaintext changed")

    def test_clean_view_carries_no_repo_metadata(self):
        got = {w for s in book.sections(c) for w in book.words(s)}
        leaked = got & CONTAMINANTS
        self.assertFalse(leaked, f"repo metadata reached book.words(): {sorted(leaked)}")

    def test_clean_view_is_a_subset_of_the_raw_file(self):
        """Nothing is invented: every clean word appears in the solution file."""
        for s in book.sections(c):
            self.assertLessEqual(set(book.words(s)), _raw_words(s), s.id)

    def test_the_defect_is_still_real(self):
        """If plaintext() is ever fixed upstream, this test says so."""
        raw = {w for s in c.sections if s.solved and s.solution_file
               for w in _raw_words(s)}
        clean = {w for s in book.sections(c) for w in book.words(s)}
        self.assertTrue(
            raw & CONTAMINANTS,
            "Section.plaintext() no longer leaks repo metadata; retire "
            "book.py's rationale and this test",
        )
        self.assertGreater(len(raw - clean), 20)


if __name__ == "__main__":
    unittest.main()
