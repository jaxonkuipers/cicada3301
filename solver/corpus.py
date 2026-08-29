"""The single read path for corpus/.

Nothing outside this module may parse corpus/ directly. If the transcription,
the gematria table, or the page/section index needs interpreting differently,
change it here where everyone sees it -- not in a private copy.

    from solver import corpus
    c = corpus.load()
    c.unsolved.indices            # 12,956 ints in 0..28
    c.section("0.5").text().runes
    c.gp.spell("TUNNELING")       # [16, 1, 9, 9, 18, 20, 21]  -- 7 runes, not 8

Run `python3 -m solver.corpus` to check the corpus has not drifted.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from solver.paths import (
    CICADA_PUBLIC_KEY,
    COMMUNICATIONS_INDEX,
    CORPUS,
    GEMATRIA_PRIMUS,
    LP,
)

# Upstream's transcription marks, from corpus/2014/liber-primus/README.md.
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

# Spellings the Gematria Primus table itself does not carry. Q appears in no
# solved plaintext. QU is handled in spell() as the author handles it (K+W,
# attested CWESTIAN); this entry is the fallback for a bare Q, which the
# book never prints, and routes it through C/K's rune. Everything else --
# U/V, C/K, S/Z, NG/ING, IA/IO -- comes from the transliteration column
# of corpus/2013/gematria-primus/table.csv.
_EXTRA_SPELLINGS = {"Q": 5}


@dataclass(frozen=True)
class GematriaPrimus:
    """The 29 runes: index, prime, glyph, transliteration."""

    runes: tuple[str, ...]
    primes: tuple[int, ...]
    translits: tuple[str, ...]

    @property
    def N(self) -> int:
        """Alphabet size, from the table rather than from a literal.

        `solver.cipher` and `solver.stats` each carry their own `N = 29` because
        they never load the corpus; tests/test_corpus.py pins all three to
        this one so they cannot drift apart silently.
        """
        return len(self.runes)

    @functools.cached_property
    def _rune_to_index(self) -> dict[str, int]:
        return {r: i for i, r in enumerate(self.runes)}

    @functools.cached_property
    def spellings(self) -> dict[str, int]:
        """Every Latin spelling `spell()` accepts -> rune index.

        Built from the transliteration column of the CSV, so editing the table
        edits the speller. Every alias is live: the table says "NG/ING" and
        "IA/IO", and Cicada's own direct-transliteration sections use ING as a
        TRIGRAPH (FOLLOWING -> 7 runes) and IO for the IA rune (BEHAVIORS,
        CONSUMPTION). A speller built from the primary spellings alone runs
        every English word 3-5% long, which silently biases anything measuring
        word length.
        """
        out = {
            alias: i
            for i, tr in enumerate(self.translits)
            for alias in tr.split("/")
        }
        return out | _EXTRA_SPELLINGS

    @functools.cached_property
    def _patterns(self) -> list[tuple[str, int]]:
        pats = [(sp, r) for sp, r in self.spellings.items() if len(sp) > 1]
        pats.sort(key=lambda x: -len(x[0]))
        return pats

    def index(self, rune: str) -> int:
        return self._rune_to_index[rune]

    def to_indices(self, runes: str) -> list[int]:
        """Rune string -> indices. Non-runes are skipped.

        Skipped means skipped: a run through a dropped character comes out as
        adjacent indices. Do not feed this text where such joins would be read
        as evidence; extract clean runs first (solver.runes does).
        """
        return [self._rune_to_index[c] for c in runes if c in self._rune_to_index]

    def to_runes(self, indices: Iterable[int]) -> str:
        """Indices -> rune string. Raises on anything outside 0..28: cipher
        code must reduce mod 29 itself, deliberately, not lean on silent
        wrapping here."""
        return "".join(self.runes[self._check(i)] for i in indices)

    def _check(self, i: int) -> int:
        if not 0 <= i < self.N:
            raise ValueError(f"rune index {i} outside 0..{self.N - 1}")
        return i

    def prime(self, index: int) -> int:
        return self.primes[self._check(index)]

    def spell(self, english: str) -> list[int]:
        """English -> rune indices, with the ING trigraph and the IO alias.

        Spelled one word at a time: digraphs never form across a word boundary.
        Stripping the spaces first and matching across the join turns
        `TWO ERRORS` into ᛏᚹᛟᚱᚱᚩᚱᛋ and `NOT HAVE` into ᚾᚩᚦᚪᚢᛖ, neither of which
        is what the book prints. Exact on all 94 solved sentences.

        Case-insensitive; punctuation and digits are dropped, so a plaintext
        does not have to be cleaned first. Rune input is a mistake (you want
        `to_indices`) and raises. Digraph matching is greedy: right for every
        word Cicada printed, but IONIC spells as IO-N-I-C and PINEAPPLE crosses
        PINE|APPLE -- treat spelled lengths of arbitrary modern English as
        approximate.
        """
        if any(c in self._rune_to_index for c in english):
            raise ValueError("spell() takes English text; use to_indices() for runes")
        out: list[int] = []
        singles = self.spellings
        for word in unicodedata.normalize("NFKD", english).upper().split():
            w = "".join(c for c in word if c.isascii() and c.isalpha())
            # The author's own rule, read off 0.4's unencrypted tail:
            # QUESTION is respelled KWESTION and printed CWESTIAN, so QU
            # is K+W, not C+U. Both are 7 runes, so a length check cannot
            # see the difference and an exact lookup at n>=5 returns
            # nothing. A bare Q -- no U following -- is unattested
            # anywhere in the book and keeps the C/K fallback below.
            #
            # The attested rule is PHONETIC (/kw/), and this is an
            # orthographic approximation of it, so it over-applies to the
            # QU that is not /kw/: ANTIQUE, LIQUOR, CONQUER, MOSQUITO
            # (243 -QUE words and 95 CQU in web2). Those residual errors
            # all change the rune COUNT, so a length check catches them --
            # unlike the CUESTIAN bug this replaces, which did not. CQU is
            # handled first because C+QU would otherwise emit C twice.
            w = w.replace("CQU", "KW").replace("QU", "KW")
            i, n = 0, len(w)
            while i < n:
                for sp, r in self._patterns:
                    if w.startswith(sp, i):
                        out.append(r)
                        i += len(sp)
                        break
                else:
                    out.append(singles[w[i]])
                    i += 1
        return out

    def spell_runes(self, english: str) -> str:
        return self.to_runes(self.spell(english))

    def unspell(self, indices: Iterable[int], sep: str = "") -> str:
        """Rune indices -> readable Latin, one primary transliteration per rune.

        The inverse you read candidate plaintext with: U for U/V, C for C/K,
        NG for NG/ING, IA for IA/IO. Not round-trip exact -- EO is one rune but
        unspells as two letters -- so compare candidates in rune indices, not
        in unspelled strings.

        Range-checked like `to_runes`, and for the same reason: Python's
        negative indexing made unspell([-1]) return 'EA' and prime(-1) return
        109. This is the function candidate plaintext is READ with, so an
        off-by-one surfaced as plausible Latin instead of an exception.
        """
        prim = [tr.split("/")[0] for tr in self.translits]
        return sep.join(prim[self._check(i)] for i in indices)


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
    # Non-rune, non-mark printed content -- numerals and punctuation -- with the
    # index of the rune each run follows, or -1 for content printed before the
    # first rune. Separators inside a run (`-` between numbers, `/` at its line
    # ends) are kept in the text, so page-15's number square comes back as four
    # `/`-delimited rows, not one digit soup.
    other: tuple[tuple[int, str], ...] = ()
    # Marks printed before the first rune (page-51's `&` between the base-60
    # block and the runes). Empty for almost every page.
    leading_marks: str = ""

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
        # Only a contiguous slice can carry the printed structure across.
        #
        # `marks_after[i]` means "printed after rune i", which is a statement
        # about the pair (i, i+1). Under any step the kept runes are no longer
        # that pair, so a sliced mark stream describes adjacencies the page
        # does not have: reversing 12 runes moved a word break from after
        # rune 7 to after rune 4, and words() then split there -- silently,
        # since indices itself reverses correctly. Reversal could be
        # re-anchored by one, but a stride of 2 or 3 cannot be rescued by any
        # shift, so drop the marks for every step != 1 the way `other` is
        # already dropped. Reverse the words, not the stream, if you want the
        # printed structure of reversed text.
        contiguous = step == 1
        # A leading entry (-1) belongs only to a slice that starts at the
        # beginning.
        other = (
            tuple(
                (i - start, s)
                for i, s in self.other
                if 0 <= i - start < len(sliced)
                or (start == 0 and len(sliced) and i == -1)
            )
            if contiguous
            else ()
        )
        return RuneText(
            gp=self.gp,
            indices=sliced,
            positions=self.positions[key],
            marks_after=self.marks_after[key] if contiguous else ("",) * len(sliced),
            other=other,
            # `start == 0` alone is true of t[:0], which then carried the
            # leading content into a slice holding no runes at all -- and
            # concat([t[:0], t]) doubled it.
            leading_marks=(
                self.leading_marks if start == 0 and len(sliced) and contiguous else ""
            ),
        )

    def _split_at(self, ends_run) -> list[RuneText]:
        out, start = [], 0
        for i, m in enumerate(self.marks_after):
            if ends_run(i, m):
                out.append(self[start : i + 1])
                start = i + 1
        if start < len(self.indices):
            out.append(self[start:])
        return [t for t in out if len(t)]

    def split_on(self, mark: str) -> list[RuneText]:
        """Split into runs delimited by `mark` (WORD, CLAUSE, ...)."""
        return self._split_at(lambda i, m: mark in m)

    def words(self) -> list[RuneText]:
        """Printed words.

        A word ends at any mark except a bare `/`: the line break falls
        mid-word (0.3 prints CIRCUMFEREN/CE), so splitting on it understates
        every word that happens to cross a printed line. Printed numerals and
        punctuation (`;`, the page-10 `7`) also end the word they follow.
        """
        breaks = {i for i, _ in self.other}
        return self._split_at(
            lambda i, m: any(ch != LINE for ch in m) or i in breaks
        )

    def word_lengths(self) -> list[int]:
        return [len(w) for w in self.words()]

    def lines(self) -> list[RuneText]:
        return self.split_on(LINE)

    def sha256(self) -> str:
        """Stable fingerprint of the rune stream alone."""
        return hashlib.sha256(bytes(self.indices)).hexdigest()

    @staticmethod
    def concat(parts: Iterable[RuneText]) -> RuneText:
        # A part with no runes can still carry content: page-50 is a full page
        # of base-60 groups and not a single rune. Its `other` hangs off the
        # last rune of the preceding part; anchor -1 makes that `i + off - 1`.
        parts = [p for p in parts if len(p) or p.other or p.leading_marks]
        if not parts:
            raise ValueError("nothing to concatenate")
        off, other, leading = 0, [], ""
        marks = []
        for p in parts:
            if off == 0 and not marks:
                leading += p.leading_marks
            elif p.leading_marks:
                marks[-1] += p.leading_marks
            other.extend((max(i + off, -1) if i < 0 else i + off, s) for i, s in p.other)
            marks.extend(p.marks_after)
            off += len(p)
        return RuneText(
            gp=parts[0].gp,
            indices=tuple(i for p in parts for i in p.indices),
            positions=tuple(x for p in parts for x in p.positions),
            marks_after=tuple(marks),
            other=tuple(other),
            leading_marks=leading,
        )


# Marks that may separate the groups INSIDE a run of printed numerals or
# punctuation -- `3258-3222-.../` -- as opposed to the structural marks, which
# always end such a run.
_GROUP_SEPS = frozenset({WORD, CLAUSE, LINE})


def _parse_transcription(gp: GematriaPrimus, page: str, raw: str) -> RuneText:
    """Transcription file -> RuneText.

    Source newlines are incidental; `/` is the printed line break. Marks and
    numerals attach to the rune they follow, so nothing printed is discarded --
    including a page with no runes at all (page-50) and content printed before
    a page's first rune (page-51, the paragraph numerals on pages 36-38).

    Inside a run of non-rune content, `-` `.` `/` are that run's own group
    separators and stay in its text: the page-15 number square keeps its four
    rows. Separators trailing the run go back to the mark stream.
    """
    indices: list[int] = []
    positions: list[RunePos] = []
    marks: list[str] = []
    other: list[tuple[int, str]] = []
    line, col = 1, 1
    pending_mark, pending_other = "", ""
    leading_marks = ""

    def end_other() -> None:
        nonlocal pending_mark, pending_other
        text = pending_other.rstrip("".join(_GROUP_SEPS))
        pending_mark += pending_other[len(text):]
        if text:
            other.append((len(indices) - 1, text))
        pending_other = ""

    def flush() -> None:
        nonlocal pending_mark, leading_marks
        end_other()
        if indices:
            marks[-1] += pending_mark
        else:
            leading_marks += pending_mark
        pending_mark = ""

    for ch in raw:
        if ch in "\n\r":
            continue
        if is_rune(ch):
            flush()
            indices.append(gp.index(ch))
            positions.append(RunePos(page, line, col))
            marks.append("")
            col += 1
            continue
        if ch == LINE:
            line += 1
            col = 1
        if ch in MARKS:
            if pending_other and ch in _GROUP_SEPS:
                pending_other += ch
            else:
                end_other()
                pending_mark += ch
        elif not ch.isspace():
            pending_other += ch
    flush()

    return RuneText(
        gp=gp,
        indices=tuple(indices),
        positions=tuple(positions),
        marks_after=tuple(marks),
        other=tuple(other),
        leading_marks=leading_marks,
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

    @property
    def image_path(self) -> Path | None:
        """The scan of this page, or None. 75 images, 51 MB, read by nothing
        so far -- and the community named half its channels after what is
        drawn on them (mobius, mayfly, wing-tree, cuneiform, spiral-branches).
        Open it with the Read tool; it is a jpg."""
        return (LP / self.image) if self.image else None

    def text(self) -> RuneText:
        """This page's runes. Cached on the corpus: RuneText is immutable, and
        a sweep that calls this inside its loop should not re-read and re-parse
        the transcription every iteration."""
        cache = self._corpus._page_texts
        if self.id not in cache:
            if not self.transcription:
                cache[self.id] = RuneText(self._corpus.gp, (), (), ())
            else:
                raw = (LP / self.transcription).read_text(encoding="utf-8")
                cache[self.id] = _parse_transcription(self._corpus.gp, self.id, raw)
        return cache[self.id]


@dataclass(frozen=True)
class Section:
    id: str
    first_page: str
    # Rune offset within first_page where this section's text begins. Section
    # boundaries are not page boundaries: 0.8 begins 9 runes into page-15 and
    # 0.11 begins 91 runes into page-33, proven by where each printed headline
    # sits. Zero for every other section.
    first_rune: int
    # The last page this section OWNS -- NOT where text() ends. When the next
    # section starts mid-page, this one's text spills onto that page and ends
    # there: 0.7 owns through page-14 and spills into page-15, 0.10 owns
    # through page-32 and spills into page-33. Renamed from `last_page`, which
    # read as "where the section ends" and quietly said otherwise while nothing
    # in the repo consumed it. For the other question ask
    # `text().positions[-1].page`. Pinned by verify().
    last_owned_page: str
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
        """The section's rune stream, starting at its true first rune.

        Runes on this section's pages that precede `first_rune` belong to the
        previous section, and this section's own text extends into the next
        section's first page when that one starts mid-page. Getting this wrong
        prepends foreign runes at position 0, which desynchronises any keyed
        attack from its very first rune.
        """
        cache = self._corpus._section_texts
        if self.id in cache:
            return cache[self.id]
        own = RuneText.concat([p.text() for p in self.pages()])
        if self.first_rune:
            own = own[self.first_rune :]
        nxt = self._corpus.section_after(self.id)
        if nxt and nxt.first_rune:
            spill = self._corpus.page(nxt.first_page).text()[: nxt.first_rune]
            own = RuneText.concat([own, spill])
        cache[self.id] = own
        return own

    def channels(self) -> list[str]:
        """The archive channels discussing this section's pages.

        Every unsolved section maps to exactly one, named after the
        illustration: 0.8 -> '15-22' (mobius, 3,485 messages). The join lives
        in pages.csv and is the whole reason to claim a section rather than
        `all` -- `all` names no channel and cuts the work off from everything
        the community already established about those pages.
        """
        seen = {self._corpus.discord_channel(p.id) for p in self.pages()}
        return sorted(x for x in seen if x)

    def plaintext(self) -> str | None:
        if not self.solution_file:
            return None
        return (LP / self.solution_file).read_text(encoding="utf-8")

    def sentences(self) -> list[Sentence]:
        return [s for s in self._corpus.sentences if s.section == self.id]


@dataclass(frozen=True)
class Communication:
    """One Cicada message in public-puzzle order.

    The path layout records the round in which the bytes appeared, while
    communications.csv records release order separately from signature time.
    This matters for pre-signed objects such as 2013's onion pointer and for
    the April-signed locator delivered through a solver's service in May 2014.

    Read them through here rather than opening the files: an ad-hoc read sits
    outside corpus_sha256 and drifts silently.
    """

    id: str
    sequence: int
    round: str
    route: str
    observed_at: str
    signed_at: str
    role: str
    path: Path
    date: str        # compatibility: YYYY-MM of observation/signature
    body: str        # signed text, PGP envelope stripped
    raw: str

    @property
    def lines(self) -> list[str]:
        """Non-empty lines. Filters on the line being empty, NOT on it being
        blank: 2013-01-rune-table-morse encodes its whole payload in tabs and
        spaces, so `if ln.strip()` deletes the message."""
        return [ln for ln in self.body.splitlines() if ln]


_PGP_START = "-----BEGIN PGP SIGNED MESSAGE-----"
_PGP_SIG = "-----BEGIN PGP SIGNATURE-----"


def _read_communication(row: dict[str, str]) -> Communication:
    path = CORPUS / row["path"]
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = raw
    if _PGP_START in body:
        body = body.split(_PGP_START, 1)[1]
        # Drop the armour headers ("Hash: SHA1") up to the first blank line.
        body = body.split("\n\n", 1)[-1]
    if _PGP_SIG in body:
        body = body.split(_PGP_SIG, 1)[0]
    # strip("\n"), not strip(): whitespace is content here. The morse message
    # is nothing but tabs and spaces, and .strip() reduced it to "".
    return Communication(
        id=row["id"],
        sequence=int(row["sequence"]),
        round=row["round"],
        route=row["route"],
        observed_at=row["observed_at"],
        signed_at=row["signed_at"],
        role=row["role"],
        path=path,
        date=(row["observed_at"] or row["signed_at"])[:7],
        body=body.strip("\n"),
        raw=raw,
    )


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
        # Parsed-text caches for Page.text()/Section.text(). RuneText is a
        # frozen dataclass of tuples, so sharing one is safe.
        self._page_texts: dict[str, RuneText] = {}
        self._section_texts: dict[str, RuneText] = {}
        gp_rows = sorted(
            _rows(GEMATRIA_PRIMUS / "table.csv"), key=lambda r: int(r["index"])
        )
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
                first_rune=int(r["first_rune"]),
                last_owned_page=r["last_page"],
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
    def communications(self) -> list[Communication]:
        """Cicada messages in observed puzzle order. See Communication."""
        rows = sorted(_rows(COMMUNICATIONS_INDEX), key=lambda r: int(r["sequence"]))
        return [_read_communication(row) for row in rows]

    @functools.cached_property
    def public_key(self) -> str:
        """The armored 3301 public key, identity material rather than a message."""
        return CICADA_PUBLIC_KEY.read_text(encoding="utf-8")

    def communication(self, comm_id: str) -> Communication:
        aliases = {
            "2012-01-mabinogion-book-code": "2012-01-twenty-nine-volumes-book-code",
            "2012-01-britannica-book-code": "2012-01-twenty-nine-volumes-book-code",
            "2012-01-end-of-puzzle": "2012-02-end-of-puzzle",
            "2012-01-necrome-denial": "2012-04-necrome-denial",
            "2013-cicada-os-message": "2013-01-cicada-os-message",
            "2014-01-onion-welcome": "2014-05-onion-welcome",
        }
        if comm_id == "cicada-3301-public-key":
            return Communication(
                id=comm_id,
                sequence=0,
                round="identity",
                route="identity",
                observed_at="2012-01-05",
                signed_at="",
                role="OpenPGP identity key; not a communication",
                path=CICADA_PUBLIC_KEY,
                date="2012-01",
                body=self.public_key.strip("\n"),
                raw=self.public_key,
            )
        comm_id = aliases.get(comm_id, comm_id)
        return {c.id: c for c in self.communications}[comm_id]

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

    def section_after(self, section_id: str) -> Section | None:
        """The next section in book order, None after the last."""
        ids = [s.id for s in self.sections]
        i = ids.index(section_id) + 1
        return self.sections[i] if i < len(self.sections) else None

    def unsolved_sections(self) -> list[Section]:
        return [self.section(s) for s in UNSOLVED_SECTIONS]

    def _status_unsolved(self) -> tuple[str, ...]:
        """The unsolved sections according to sections.csv's status column."""
        return tuple(s.id for s in self.sections if not s.solved)

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

# One hash over every corpus file this module reads, so an edit anywhere --
# a transliteration cell, a solution file, one rune of one transcription --
# fails loudly instead of silently skewing results. Recompute with
# `python3 -c "from solver import corpus; print(corpus.corpus_sha256())"` after
# any deliberate corpus change, and say why in the commit.
# Recomputed 2026-08-23 when Cicada communications came under the hash. The
# The communication sources are key material and were being read by ad-hoc
# scripts outside any drift check. Nothing in corpus/ changed; the hashed set
# did.
# 2026-08-26: communications/2015-07-planned-parenthood-denial.asc was restored
# from its LF-normalised source after the repository copy lost unsigned padding.
# Signature and canonical bytes are unchanged.
# 2026-08-27: sections.csv rows 0.1, 0.4 and 0.13 carried unquoted commas in
# `notes`, so they parsed as 13/12/12 fields against an 11-field header and the
# remainder was dropped -- 0.13 lost "rune 56; ciphertext F at 35/47/51/74 are
# ordinary encryptions", the solved-section calibration material. The fields are
# quoted, and 0.1's note says "the 1033 word square", not
# "the word list with page numbers": intro-05 prints no page numbers). Notes
# column only -- the rune stream is byte-identical, 12,956 runes at
# 73473a68c3fc4296. Written LF with a targeted line edit -- a csv round-trip
# emits CRLF and restripes optional quoting, which touches unrelated rows.
# 2026-08-27: corpus source bytes were arranged by the 2012/2013/2014 puzzle
# rounds; communications.csv pinned observed order and descriptive stage separately from
# signature time. The LP rune stream is unchanged. The hash now includes paths,
# the communication index and the public key because the loader reads them.
# 2026-08-29: communications.csv replaced its descriptive stage labels with
# canonical route ids. Artifact bytes and the LP rune stream are unchanged.
EXPECTED_CORPUS_SHA = "c1e256fd548ba66c8a05f3b8b032df2898ac87addae0a173475f0b418d20065b"

# Exact counts of solved sentences with English, split by how they are checked.
# Pinning them keeps the speller check from passing vacuously when
# sentences.csv goes missing or unreadable.
EXPECTED_RUNE_EXACT, EXPECTED_LEN_EXACT = 59, 35

# How many sections each of the other two semantic checks must actually cover.
# Same reason as above: `not bad` is true of zero comparisons, so a check that
# silently stops comparing anything -- a renamed CSV column, an unreadable
# sentences.csv -- would report PASS while measuring nothing.
EXPECTED_HEADLINES_CHECKED = 12
EXPECTED_SENTENCE_SECTIONS = 15

# Total characters of non-rune printed content (RuneText.other) across all
# pages: the number squares, the base-60 block, the hash, stray numerals.
# Guards against a parser regression silently dropping any of it again.
EXPECTED_OTHER_CHARS = 1212

# Cicada messages indexed in corpus/communications.csv. The public key is
# identity material available as c.public_key / communication(key-id), but is
# deliberately not counted as a communication.
EXPECTED_COMMUNICATIONS = 37

# 2013-01-rune-table-morse carries its whole payload in tabs and spaces, so a
# body that strips whitespace reads as an empty message. Pinned because the
# first version of the reader did exactly that and lost it silently.
EXPECTED_MORSE_CHARS = 558

# Sections whose sentences deliberately do not cover the whole rune stream.
# 0.1: the last 76 runes are the unencrypted 1033 word square (intro-05), which
# upstream's sentence segmentation never included. NOT "a word list with page
# numbers" -- intro-05 prints no page numbers, only the twelve number cells of
# the square interleaved with its thirteen word cells.
KNOWN_SENTENCE_GAPS = {"0.1": 76}

# Sections whose cipher inverts in one line, so the speller and the headline
# can be checked rune for rune rather than only on length.
_INVERTIBLE = {
    "0.0": lambda i: 28 - i,
    "0.2": lambda i: (28 - i + 3) % 29,
    "0.3": lambda i: i,
    "0.14": lambda i: i,
}


def corpus_sha256() -> str:
    """Fingerprint of every corpus file the loader reads.

    Scope is exactly that: the machine indexes, public key, communications,
    LP structured text, transcriptions and accepted solutions. Page scans are
    not parsed. The English-through-GP statistics used by `solver.fitness` are
    frozen separately and identified by `fitness.training_sha256()`.
    """
    h = hashlib.sha256()
    files = [
        COMMUNICATIONS_INDEX,
        CICADA_PUBLIC_KEY,
        GEMATRIA_PRIMUS / "table.csv",
        LP / "pages.csv",
        LP / "sections.csv",
        LP / "sentences.csv",
    ]
    files += sorted((LP / "transcription").glob("*.txt"))
    files += sorted((LP / "solutions").glob("*.md"))
    files += [CORPUS / row["path"] for row in _rows(COMMUNICATIONS_INDEX)]
    for f in files:
        h.update(f.relative_to(CORPUS).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _check_speller(c: Corpus) -> tuple[str, bool, str]:
    # The speller against every solved sentence in the book. Invertible
    # sections are checked rune for rune; the rest on length, which is what a
    # speller regression actually breaks. This is where the ING trigraph, the
    # IO alias and the word-boundary rule show up.
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
    passed = (
        exact_ok == exact_n == EXPECTED_RUNE_EXACT
        and len_ok == len_n == EXPECTED_LEN_EXACT
    )
    return (
        "speller vs solved sections", passed,
        f"{exact_ok}/{exact_n} rune-exact, {len_ok}/{len_n} length-exact"
        + (f", first bad {failed[0]}" if failed else ""),
    )


def _check_headlines(c: Corpus) -> tuple[str, bool, str]:
    # Every section's text must begin with its printed headline; this is what
    # pins the first_rune offsets in sections.csv. Runic headlines compare
    # directly; english ones only where the cipher inverts in one line.
    checked, bad = 0, []
    for sec in c.sections:
        t = sec.text().indices
        if sec.headline_form == "runic":
            head = tuple(c.gp.to_indices(sec.headline.replace(" ", "")))
            start = t[: len(head)]
        elif sec.id in _INVERTIBLE:
            inv = _INVERTIBLE[sec.id]
            head = tuple(c.gp.spell(sec.headline))
            start = tuple(inv(i) for i in t[: len(head)])
        else:
            continue
        checked += 1
        if start != head:
            bad.append(sec.id)
    enough = checked == EXPECTED_HEADLINES_CHECKED
    return (
        "sections start at their headline", not bad and enough,
        f"{checked - len(bad)}/{checked} aligned"
        + (f", bad: {bad}" if bad else "")
        + ("" if enough else f" (expected {EXPECTED_HEADLINES_CHECKED} checked)"),
    )


def _check_section_page_spans(c: Corpus) -> tuple[str, bool, str]:
    # Two claims at once: last_owned_page really is the last page of pages(),
    # and the rune stream reconciles -- every rune on every page belongs to
    # exactly one section, so the mid-page spill neither loses nor duplicates
    # one. Without the second half a boundary edit could move runes between
    # sections and only the per-section counts would notice.
    bad = []
    for sec in c.sections:
        owned = sec.pages()
        if owned and owned[-1].id != sec.last_owned_page:
            bad.append(f"{sec.id}: owns {owned[-1].id}, csv says {sec.last_owned_page}")
    page_runes = sum(len(p.text()) for p in c.pages)
    section_runes = sum(len(s.text()) for s in c.sections)
    if page_runes != section_runes:
        bad.append(f"{page_runes} page runes vs {section_runes} section runes")
    return (
        "section page spans reconcile", not bad,
        f"{page_runes} runes over {len(c.pages)} pages = sum over sections"
        + (f", bad: {bad}" if bad else ""),
    )


def _check_sentences_match_transcription(c: Corpus) -> tuple[str, bool, str]:
    # sentences.csv and transcription/ are two records of the same runes;
    # nothing may diverge beyond the pinned, explained gaps.
    ok_n, bad = 0, []
    for sec in c.sections:
        rows = sec.sentences()
        if not rows:
            continue
        stream = [i for s in rows for i in c.gp.to_indices(s.runes)]
        text = list(sec.text().indices)
        gap = KNOWN_SENTENCE_GAPS.get(sec.id, 0)
        if text[: len(stream)] == stream and len(text) - len(stream) == gap:
            ok_n += 1
        else:
            k = next(
                (i for i, (a, b) in enumerate(zip(stream, text, strict=False)) if a != b),
                min(len(stream), len(text)),
            )
            bad.append(f"{sec.id}@{k}")
    enough = ok_n + len(bad) == EXPECTED_SENTENCE_SECTIONS
    return (
        "sentences match transcription", not bad and enough,
        f"{ok_n} sections exact"
        + (f", diverged: {bad}" if bad else "")
        + ("" if enough else f" (expected {EXPECTED_SENTENCE_SECTIONS} sections)"),
    )


def verify() -> list[tuple[str, bool, str]]:
    """Cheap checks that the data and the speller still behave.

    Returns (name, passed, detail). Costs well under a second -- run it at the
    start of a session, not as a ceremony.
    """
    c = load()
    u = c.unsolved
    sha = u.sha256()
    files_sha = corpus_sha256()
    other_chars = sum(
        len(s) for p in c.pages if p.transcription for _, s in p.text().other
    )
    status = c._status_unsolved()
    return [
        ("corpus files sha256", files_sha == EXPECTED_CORPUS_SHA,
         files_sha[:16] + "..."),
        # UNSOLVED_SECTIONS drives `c.unsolved`, and the status column drives
        # everything a human reads. If a section is ever solved, both must
        # move together or the 12,956-rune stream silently keeps it.
        ("UNSOLVED_SECTIONS matches status column", status == UNSOLVED_SECTIONS,
         f"{len(status)} unsolved by status"
         + ("" if status == UNSOLVED_SECTIONS else f", csv says {status}")),
        ("unsolved rune count", len(u) == EXPECTED_UNSOLVED_LEN,
         f"{len(u)} (expected {EXPECTED_UNSOLVED_LEN})"),
        ("unsolved stream sha256", sha == EXPECTED_UNSOLVED_SHA, sha[:16] + "..."),
        ("printed non-rune content", other_chars == EXPECTED_OTHER_CHARS,
         f"{other_chars} chars (expected {EXPECTED_OTHER_CHARS})"),
        ("communications readable",
         len(c.communications) == EXPECTED_COMMUNICATIONS
         and all(x.body for x in c.communications)
         and len(c.communication("2013-01-rune-table-morse").body)
         == EXPECTED_MORSE_CHARS,
         f"{len(c.communications)} messages, morse payload "
         f"{len(c.communication('2013-01-rune-table-morse').body)} chars"),
        _check_speller(c),
        _check_headlines(c),
        _check_sentences_match_transcription(c),
        _check_section_page_spans(c),
    ]


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
    # Every check above compares the corpus against constants recorded FROM
    # the corpus. That detects drift -- an edit, a parser change, a bad merge
    # -- and nothing else. It is not evidence that the transcription is a
    # faithful reading of the scans; no check in this repo tests that, and the
    # scans hold marks the transcription has no field for (colour, drawings,
    # glyph size). PASS means "unchanged since it was pinned", not "correct".
    print(
        "\n  These check the corpus against itself: PASS means nothing has "
        "drifted,\n  not that the transcription matches the scans in "
        "corpus/2014/liber-primus/images/."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
