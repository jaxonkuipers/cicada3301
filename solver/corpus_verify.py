"""Drift checks over the preserved corpus and its single read path.

Everything here compares `solver.corpus` against constants recorded FROM the
corpus, so an edit, a parser change or a bad merge fails loudly instead of
silently skewing results. It lives beside the data model rather than inside it:
`solver.corpus` is the read path, this module is its instrument check.

Run it as `python3 -m solver.corpus` (which delegates here) or as
`python3 -m solver.corpus_verify`; both print the same PASS/FAIL table.
"""

from __future__ import annotations

import hashlib

from solver import corpus, corpus_manifest
from solver.paths import (
    CICADA_PUBLIC_KEY,
    COMMUNICATIONS_INDEX,
    CORPUS,
    GEMATRIA_PRIMUS,
    LP,
)

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
# `python3 -c "from solver import corpus_verify; print(corpus_verify.corpus_sha256())"` after
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
# 2026-08-29: corpus evidence moved under its owning route records. The hash
# changed because it includes canonical paths; the evidence bytes are unchanged.
EXPECTED_CORPUS_SHA = "6952f734dfa69924c7abf75822ca9ac7c38d5cdd5725f6ef47bfa6a6e0159295"

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

# 2013-01-rune-table-morse carries its whole payload in tabs and spaces,
# including one leading empty line after the armor separator. Pinned because
# the first version of the reader stripped that whitespace and lost it silently.
EXPECTED_MORSE_CHARS = 559

# Sections whose sentences deliberately cover part of the rune stream.
# 0.1: the last 76 runes are the unencrypted 1033 word square (intro-05), which
# upstream's sentence segmentation omitted. Intro-05 prints the square's twelve
# number cells interleaved with its thirteen word cells.
KNOWN_SENTENCE_GAPS = {"0.1": 76}

# Sections whose one-line inverse supports rune-exact speller and headline checks.
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
    # Read the index through the loader's own reader: the drift hash must
    # not parse communications.csv differently than solver.corpus does.
    files += [CORPUS / row["path"] for row in corpus._rows(COMMUNICATIONS_INDEX)]
    for f in files:
        h.update(f.relative_to(CORPUS).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def _check_speller(c: corpus.Corpus) -> tuple[str, bool, str]:
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


def _check_headlines(c: corpus.Corpus) -> tuple[str, bool, str]:
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


def _check_section_page_spans(c: corpus.Corpus) -> tuple[str, bool, str]:
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


def _check_sentences_match_transcription(c: corpus.Corpus) -> tuple[str, bool, str]:
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

    Returns (name, passed, detail) and costs well under a second.
    """
    c = corpus.load()
    u = c.unsolved
    sha = u.sha256()
    files_sha = corpus_sha256()
    manifest_errors = corpus_manifest.verify_manifest()
    other_chars = sum(
        len(s) for p in c.pages if p.transcription for _, s in p.text().other
    )
    status = tuple(s.id for s in c.sections if not s.solved)
    leaked_headers = [
        message.id for message in c.communications
        if message.body.startswith("Hash:")
    ]
    return [
        ("corpus files sha256", files_sha == EXPECTED_CORPUS_SHA,
         files_sha[:16] + "..."),
        (
            "immutable evidence manifest",
            not manifest_errors,
            manifest_errors[0]
            if manifest_errors
            else f"{len(corpus_manifest.immutable_files())} files verified",
        ),
        # UNSOLVED_SECTIONS drives `c.unsolved`, and the status column drives
        # everything a human reads. If a section is ever solved, both must
        # move together or the 12,956-rune stream silently keeps it.
        ("UNSOLVED_SECTIONS matches status column", status == corpus.UNSOLVED_SECTIONS,
         f"{len(status)} unsolved by status"
         + ("" if status == corpus.UNSOLVED_SECTIONS else f", csv says {status}")),
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
        (
            "communication envelopes stripped",
            not leaked_headers,
            "no body begins with an armor Hash header"
            if not leaked_headers else f"leaked headers: {leaked_headers}",
        ),
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
    u = corpus.load().unsolved
    print(
        f"\n  {len(u)} unsolved runes over {len(corpus.UNSOLVED_SECTIONS)} sections, "
        f"{len(u.words())} printed words, {len(u.lines())} printed lines"
    )
    # Every check above compares the corpus against constants recorded FROM
    # the corpus. That detects drift -- an edit, a parser change, a bad merge
    # -- and nothing else. It is not evidence that the transcription is a
    # faithful reading of the scans; no check in this repo tests that, and the
    # scans hold marks the transcription has no field for (colour, drawings,
    # glyph size). PASS means "unchanged since it was pinned", not "correct".
    print(
        "\n  These checks verify internal corpus consistency. The source scans for "
        "\n  image-to-transcription validation are in "
        "corpus/records/R14.7/artifacts/liber-primus/images/."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
