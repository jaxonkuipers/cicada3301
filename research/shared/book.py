"""The book's own plaintext, without this repo's metadata.

`corpus.Section.plaintext()` returns the solution FILE, markdown header and
all, so a consumer that extracts words from it picks up repo vocabulary --
SECTION, TRANSCRIPTION, POLYALPHABETIC, GEMATRIA, CSV, MOD, PHI. Measured over
the seven solved sections: `plaintext()` yields 291 distinct words and 3,924
runes against the book's own 261 and 2,901, so **1,023 runes (26%) are not
Cicada's text** and 30 words are this repo's.

`sentences.csv` carries the rune/English alignment Cicada actually printed, so
it is the clean source. Use these helpers for anything that mines the book's
vocabulary, builds a running key from it, or enumerates its phrases.

Nothing here reparses the corpus: it is a thin, correct view over
`lib.corpus`.
"""

from __future__ import annotations

import re

from lib import corpus

__all__ = ["plaintext", "words", "spelled", "sections"]


def sections(c) -> list:
    """The solved sections that carry an English alignment, in book order."""
    return [s for s in c.sections if s.solved and s.sentences()]


def plaintext(section) -> str:
    """The section's printed English, one space between sentences."""
    return " ".join(s.english for s in section.sentences() if s.english)


def words(section) -> list[str]:
    """Upper-case word tokens of the section's printed English, in order."""
    return re.findall(r"[A-Za-z]+", plaintext(section).upper())


def spelled(section, gp) -> list[int]:
    """The section's printed English as rune indices, words run together."""
    out: list[int] = []
    for w in words(section):
        out += gp.spell(w)
    return out


def _selftest() -> None:
    c = corpus.load()
    raw, clean = set(), set()
    nraw = nclean = 0
    for s in c.sections:
        if not (s.solved and s.solution_file):
            continue
        for w in re.findall(r"[A-Za-z]+", s.plaintext().upper()):
            raw.add(w)
            nraw += len(c.gp.spell(w))
        for w in words(s):
            clean.add(w)
            nclean += len(c.gp.spell(w))
    print(f"  Section.plaintext(): {len(raw)} distinct words, {nraw} runes")
    print(f"  book.plaintext():    {len(clean)} distinct words, {nclean} runes")
    print(f"  repo metadata mined by the former: {len(raw - clean)} words, "
          f"{nraw - nclean} runes")
    print(f"  contaminants: {sorted(raw - clean)}")
    assert not (clean - raw), "the clean view must be a subset"
    assert nclean == 2901, nclean


if __name__ == "__main__":
    _selftest()
