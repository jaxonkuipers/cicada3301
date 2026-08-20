"""The single read path for corpus/.

Nothing outside this module may parse corpus/ directly. If the transcription,
the gematria table, or the page/section index needs interpreting differently,
change it here where everyone sees it -- not in a private copy.

    from lib import corpus
    c = corpus.load()
    c.unsolved.indices            # 12,956 ints in 0..28
    c.section("0.5").text().runes
    c.gp.spell("TUNNELING")       # [16, 1, 9, 9, 18, 20, 21]  -- 7 runes, not 8

Run `python3 -m lib.corpus` to check the corpus has not drifted.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from lib.paths import CORPUS, LP

# Upstream's transcription marks, from corpus/liber-primus/README.md.
WORD, CLAUSE, PARAGRAPH, SEGMENT, CHAPTER, LINE = "-", ".", "&", "$", "§", "/"
MARKS = frozenset({WORD, CLAUSE, PARAGRAPH, SEGMENT, CHAPTER, LINE})

# The Runic Unicode block. Wider than the 29 Gematria Primus runes, which is
# what you want when recognising rune text written by hand somewhere else.
RUNIC_FIRST, RUNIC_LAST = "ᚠ", "᛿"

# Sections 0.5 through 0.12 -- everything Cicada has never let be read.
UNSOLVED_SECTIONS = ("0.5", "0.6", "0.7", "0.8", "0.9", "0.10", "0.11", "0.12")


def is_rune(ch: str) -> bool:
    return RUNIC_FIRST <= ch <= RUNIC_LAST


# --------------------------------------------------------------------------
# Gematria Primus
# --------------------------------------------------------------------------

# Latin spellings that collapse to one rune, longest first within each rune.
# Both aliases in the transliteration column are live: the table says "NG/ING"
# and "IA/IO", and Cicada's own direct-transliteration sections use ING as a
# TRIGRAPH (FOLLOWING -> 7 runes) and IO for the IA rune (BEHAVIORS, CONSUMPTION).
# A speller built from the primary spellings alone runs every English word 3-5%
# long, which silently biases anything measuring word length.
_MULTI = {
    2: ["TH"],
    12: ["EO"],
    21: ["ING", "NG"],
    22: ["OE"],
    25: ["AE"],
    27: ["IA", "IO"],
    28: ["EA"],
}
_SINGLE = {
    "F": 0, "U": 1, "V": 1, "O": 3, "R": 4, "C": 5, "K": 5, "Q": 5,
    "G": 6, "W": 7, "H": 8, "N": 9, "I": 10, "J": 11, "P": 13,
    "X": 14, "S": 15, "Z": 15, "T": 16, "B": 17, "E": 18, "M": 19,
    "L": 20, "D": 23, "A": 24, "Y": 26,
}


@dataclass(frozen=True)
class GematriaPrimus:
    """The 29 runes: index, prime, glyph, transliteration."""

    runes: tuple[str, ...]
    primes: tuple[int, ...]
    translits: tuple[str, ...]

    N = 29

    @functools.cached_property
    def _rune_to_index(self) -> dict[str, int]:
        return {r: i for i, r in enumerate(self.runes)}

    @functools.cached_property
    def _patterns(self) -> list[tuple[str, int]]:
        pats = [(sp, r) for r, sps in _MULTI.items() for sp in sps]
        pats.sort(key=lambda x: -len(x[0]))
        return pats

    @functools.cached_property
    def spellings(self) -> dict[str, int]:
        """Every Latin spelling `spell()` accepts -> rune index.

        Flat view of the same table, for callers that need to recognise a
        transliteration someone else wrote rather than produce one.
        """
        return _SINGLE | {sp: r for r, sps in _MULTI.items() for sp in sps}

    def index(self, rune: str) -> int:
        return self._rune_to_index[rune]

    def to_indices(self, runes: str) -> list[int]:
        """Rune string -> indices. Non-runes are skipped."""
        return [self._rune_to_index[c] for c in runes if is_rune(c)]

    def to_runes(self, indices: Iterable[int]) -> str:
        return "".join(self.runes[i % self.N] for i in indices)

    def prime(self, index: int) -> int:
        return self.primes[index]

    def spell(self, english: str) -> list[int]:
        """English -> rune indices, with the ING trigraph and the IO alias.

        Spelled one word at a time: digraphs never form across a word boundary.
        Stripping the spaces first and matching across the join turns
        `TWO ERRORS` into ᛏᚹᛟᚱᚱᚩᚱᛋ and `NOT HAVE` into ᚾᚩᚦᚪᚢᛖ, neither of which
        is what the book prints. Exact on all 94 solved sentences.

        Case-insensitive; punctuation is dropped, so a plaintext does not have
        to be cleaned first.
        """
        out: list[int] = []
        for word in unicodedata.normalize("NFKD", english).upper().split():
            w = "".join(c for c in word if c.isascii() and c.isalpha())
            i, n = 0, len(w)
            while i < n:
                for sp, r in self._patterns:
                    if w.startswith(sp, i):
                        out.append(r)
                        i += len(sp)
                        break
                else:
                    out.append(_SINGLE[w[i]])
                    i += 1
        return out

    def spell_runes(self, english: str) -> str:
        return self.to_runes(self.spell(english))


# --------------------------------------------------------------------------
# Rune text
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunePos:
    """Where a rune sits on the printed page."""

    page: str
    line: int
    col: int


@dataclass(frozen=True)
class RuneText:
    """A rune stream plus the printed structure around it.

    `indices` is the only thing a cipher acts on. Everything else -- the marks,
    the page/line/column of each rune -- is printed structure kept alongside it
    so an attack can use it without re-parsing the transcription.
    """

    gp: GematriaPrimus
    indices: tuple[int, ...]
    positions: tuple[RunePos, ...]
    # Marks printed immediately after rune i, in order. Usually '' or one mark.
    marks_after: tuple[str, ...]
    # Non-rune, non-mark printed content: numerals and punctuation, with the
    # index of the rune they follow. The intro number squares live here.
    other: tuple[tuple[int, str], ...] = ()

    def __len__(self) -> int:
        return len(self.indices)

    @property
    def runes(self) -> str:
        return self.gp.to_runes(self.indices)

    def __getitem__(self, key: int | slice) -> int | RuneText:
        """An int gives the rune index; a slice gives a RuneText."""
        if isinstance(key, int):
            return self.indices[key]
        sliced = self.indices[key]
        start, _, step = key.indices(len(self.indices))
        # Only a contiguous slice can carry `other` across: with a step there is
        # no longer a rune for each numeral to hang off.
        other = (
            tuple((i - start, s) for i, s in self.other if 0 <= i - start < len(sliced))
            if step == 1
            else ()
        )
        return RuneText(
            gp=self.gp,
            indices=sliced,
            positions=self.positions[key],
            marks_after=self.marks_after[key],
            other=other,
        )

    def _split(self, ends_run) -> list[RuneText]:
        out, start = [], 0
        for i, m in enumerate(self.marks_after):
            if ends_run(m):
                out.append(self[start : i + 1])
                start = i + 1
        if start < len(self.indices):
            out.append(self[start:])
        return [t for t in out if len(t)]

    def split_on(self, mark: str) -> list[RuneText]:
        """Split into runs delimited by `mark` (WORD, CLAUSE, ...)."""
        return self._split(lambda m: mark in m)

    def words(self) -> list[RuneText]:
        """Printed words. Any mark ends a word, not just the word separator."""
        return self._split(bool)

    def word_lengths(self) -> list[int]:
        return [len(w) for w in self.words()]

    def lines(self) -> list[RuneText]:
        return self.split_on(LINE)

    def sha256(self) -> str:
        """Stable fingerprint of the rune stream alone."""
        return hashlib.sha256(bytes(self.indices)).hexdigest()

    @staticmethod
    def concat(parts: Iterable[RuneText]) -> RuneText:
        parts = [p for p in parts if len(p)]
        if not parts:
            raise ValueError("nothing to concatenate")
        off, other = 0, []
        for p in parts:
            other.extend((i + off, s) for i, s in p.other)
            off += len(p)
        return RuneText(
            gp=parts[0].gp,
            indices=tuple(i for p in parts for i in p.indices),
            positions=tuple(x for p in parts for x in p.positions),
            marks_after=tuple(m for p in parts for m in p.marks_after),
            other=tuple(other),
        )


def _parse_transcription(gp: GematriaPrimus, page: str, raw: str) -> RuneText:
    """Transcription file -> RuneText.

    Source newlines are incidental; `/` is the printed line break. Marks and
    numerals attach to the rune they follow, so nothing printed is discarded.
    """
    indices: list[int] = []
    positions: list[RunePos] = []
    marks: list[str] = []
    other: list[tuple[int, str]] = []
    line, col = 1, 1
    pending_mark, pending_other = "", ""

    def flush() -> None:
        nonlocal pending_mark, pending_other
        if indices:
            marks[-1] += pending_mark
            if pending_other:
                other.append((len(indices) - 1, pending_other))
        pending_mark, pending_other = "", ""

    for ch in raw:
        if ch in "\n\r":
            continue
        if is_rune(ch):
            flush()
            indices.append(gp.index(ch))
            positions.append(RunePos(page, line, col))
            marks.append("")
            col += 1
        elif ch in MARKS:
            pending_mark += ch
            if ch == LINE:
                line += 1
                col = 1
        elif not ch.isspace():
            pending_other += ch
    flush()

    return RuneText(
        gp=gp,
        indices=tuple(indices),
        positions=tuple(positions),
        marks_after=tuple(marks),
        other=tuple(other),
    )


# --------------------------------------------------------------------------
# Pages, sections, sentences
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Page:
    id: str
    book_page: int
    section: str
    status: str
    image: str
    transcription: str
    discord_channel: str
    notes: str
    _corpus: Corpus = field(repr=False, compare=False)

    def text(self) -> RuneText:
        if not self.transcription:
            return RuneText(self._corpus.gp, (), (), ())
        raw = (LP / self.transcription).read_text(encoding="utf-8")
        return _parse_transcription(self._corpus.gp, self.id, raw)


@dataclass(frozen=True)
class Section:
    id: str
    first_page: str
    last_page: str
    headline: str
    headline_form: str
    status: str
    cipher: str
    key: str
    solution_file: str
    notes: str
    _corpus: Corpus = field(repr=False, compare=False)

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def pages(self) -> list[Page]:
        return [p for p in self._corpus.pages if p.section == self.id]

    def text(self) -> RuneText:
        return RuneText.concat([p.text() for p in self.pages()])

    def plaintext(self) -> str | None:
        if not self.solution_file:
            return None
        return (LP / self.solution_file).read_text(encoding="utf-8")

    def sentences(self) -> list[Sentence]:
        return [s for s in self._corpus.sentences if s.section == self.id]


@dataclass(frozen=True)
class Sentence:
    id: str
    section: str
    runes: str
    english: str


def _rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Corpus:
    def __init__(self) -> None:
        gp_rows = sorted(_rows(CORPUS / "gematria-primus.csv"), key=lambda r: int(r["index"]))
        self.gp = GematriaPrimus(
            runes=tuple(r["rune"] for r in gp_rows),
            primes=tuple(int(r["prime"]) for r in gp_rows),
            translits=tuple(r["transliteration"] for r in gp_rows),
        )
        self.pages = [
            Page(
                id=r["page"],
                book_page=int(r["book_page"]),
                section=r["section"],
                status=r["status"],
                image=r["image"],
                transcription=r["transcription"],
                discord_channel=r["discord_channel"],
                notes=r["notes"],
                _corpus=self,
            )
            for r in _rows(LP / "pages.csv")
        ]
        self.sections = [
            Section(
                id=r["section"],
                first_page=r["first_page"],
                last_page=r["last_page"],
                headline=r["headline"],
                headline_form=r["headline_form"],
                status=r["status"],
                cipher=r["cipher"],
                key=r["key"],
                solution_file=r["solution_file"],
                notes=r["notes"],
                _corpus=self,
            )
            for r in _rows(LP / "sections.csv")
        ]
        self.sentences = [
            Sentence(r["sentence_id"], r["section"], r["runes"], r["english"])
            for r in _rows(LP / "sentences.csv")
        ]

    @functools.cached_property
    def _pages_by_id(self) -> dict[str, Page]:
        return {p.id: p for p in self.pages}

    @functools.cached_property
    def _sections_by_id(self) -> dict[str, Section]:
        return {s.id: s for s in self.sections}

    def page(self, page_id: str) -> Page:
        return self._pages_by_id[page_id]

    def section(self, section_id: str) -> Section:
        return self._sections_by_id[section_id]

    def unsolved_sections(self) -> list[Section]:
        return [self.section(s) for s in UNSOLVED_SECTIONS]

    @functools.cached_property
    def unsolved(self) -> RuneText:
        """Sections 0.5-0.12 in book order -- the 12,956 runes nobody has read."""
        return RuneText.concat([s.text() for s in self.unsolved_sections()])

    def discord_channel(self, page_id: str) -> str:
        return self.page(page_id).discord_channel


@functools.cache
def load() -> Corpus:
    return Corpus()


# --------------------------------------------------------------------------
# Drift check
# --------------------------------------------------------------------------

# The unsolved corpus as measured on 2026-08-19. If either of these moves, the
# transcription or this parser changed, and every result derived from it is
# suspect until you know which.
EXPECTED_UNSOLVED_LEN = 12956
EXPECTED_UNSOLVED_SHA = (
    "73473a68c3fc4296f16009716d7fee18c9c102173e6e70d090c9494cc5bd9252"
)

# Sections whose cipher inverts in one line, so the speller can be checked rune
# for rune rather than only on length.
_INVERTIBLE = {
    "0.0": lambda i: 28 - i,
    "0.2": lambda i: (28 - i + 3) % 29,
    "0.3": lambda i: i,
    "0.14": lambda i: i,
}


def verify() -> list[tuple[str, bool, str]]:
    """Cheap checks that the data and the speller still behave.

    Returns (name, passed, detail). Costs well under a second -- run it at the
    start of a session, not as a ceremony.
    """
    c = load()
    u = c.unsolved
    out = [
        ("unsolved rune count", len(u) == EXPECTED_UNSOLVED_LEN,
         f"{len(u)} (expected {EXPECTED_UNSOLVED_LEN})"),
    ]
    sha = u.sha256()
    out.append(("unsolved stream sha256", sha == EXPECTED_UNSOLVED_SHA, sha[:16] + "..."))

    # The speller against every solved sentence in the book. Invertible sections
    # are checked rune for rune; the rest on length, which is what a speller
    # regression actually breaks. This is where the ING trigraph, the IO alias
    # and the word-boundary rule show up.
    exact_ok = exact_n = len_ok = len_n = 0
    failed: list[str] = []
    for sec in c.sections:
        if not sec.solved:
            continue
        inv = _INVERTIBLE.get(sec.id)
        for s in sec.sentences():
            if not s.english:
                continue
            spelled = c.gp.spell(s.english)
            printed = c.gp.to_indices(s.runes)
            if inv:
                exact_n += 1
                ok = [inv(i) for i in printed] == spelled
                exact_ok += ok
            else:
                len_n += 1
                ok = len(printed) == len(spelled)
                len_ok += ok
            if not ok:
                failed.append(s.id)
    out.append(
        ("speller vs solved sections", exact_ok == exact_n and len_ok == len_n,
         f"{exact_ok}/{exact_n} rune-exact, {len_ok}/{len_n} length-exact"
         + (f", first bad {failed[0]}" if failed else ""))
    )
    return out


def main() -> int:
    rows = verify()
    width = max(len(n) for n, _, _ in rows)
    ok = all(passed for _, passed, _ in rows)
    for name, passed, detail in rows:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:<{width}}  {detail}")
    u = load().unsolved
    print(
        f"\n  {len(u)} unsolved runes over {len(UNSOLVED_SECTIONS)} sections, "
        f"{len(u.words())} printed words, {len(u.lines())} printed lines"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
