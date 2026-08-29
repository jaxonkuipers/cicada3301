"""Typed apostrophes must agree between the two transcription records.

`corpus/2014/liber-primus/transcription/*.txt` and `sentences.csv` both carry the
typed apostrophes of the book, while the drift check compares rune-index
streams that strip `'`. This pins agreement in both directions, by section
offset, for every section that has sentence rows.
"""
from __future__ import annotations

import csv
import unittest

from solver import corpus


def apostrophes_in_sentences(c):
    """{section: {offset of the rune the apostrophe follows}} from sentences.csv."""
    out = {}
    per_section = {}
    with open(corpus.LP / "sentences.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            per_section.setdefault(row["section"], []).append(row["runes"])
    for sid, rows in per_section.items():
        text = "".join(rows)
        n = -1
        offs = set()
        for ch in text:
            if ch == "'":
                offs.add(n)
            elif c.gp.to_indices(ch):
                n += 1
        out[sid] = offs
    return out


class Apostrophes(unittest.TestCase):
    def test_sentences_and_transcription_agree(self):
        c = corpus.load()
        want = apostrophes_in_sentences(c)
        for sid, offs in want.items():
            t = c.section(sid).text()
            have = {i for i, s in t.other if "'" in s}
            self.assertEqual(
                have, offs,
                f"section {sid}: apostrophes in transcription/ at {sorted(have)} "
                f"but in sentences.csv at {sorted(offs)}",
            )


if __name__ == "__main__":
    unittest.main()
