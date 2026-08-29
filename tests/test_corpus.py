"""Regression tests for lib.corpus parsing.

Every case here is pinned against the printed pages themselves; if one fails,
the parser or the transcription changed and derived results are suspect.
Run: python3 -m unittest discover -s tests
"""

import unittest

from lib import cipher, corpus, fitness, stats

c = corpus.load()


class TestDrift(unittest.TestCase):
    def test_unsolved_stream(self):
        u = c.unsolved
        self.assertEqual(len(u), corpus.EXPECTED_UNSOLVED_LEN)
        self.assertEqual(u.sha256(), corpus.EXPECTED_UNSOLVED_SHA)

    def test_verify_all_pass(self):
        for name, passed, detail in corpus.verify():
            self.assertTrue(passed, f"{name}: {detail}")


class TestAlphabetSize(unittest.TestCase):
    def test_one_alphabet_size_everywhere(self):
        # gp.N is derived from the table; lib.cipher and lib.stats each carry
        # their own literal because they never load the corpus. Nothing else
        # would notice if they drifted apart.
        self.assertEqual(c.gp.N, len(c.gp.runes))
        self.assertEqual(c.gp.N, cipher.N)
        self.assertEqual(c.gp.N, stats.N)
        self.assertEqual(c.gp.N, fitness.N)


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

    def test_strided_slices_drop_the_printed_structure(self):
        # marks_after[i] means "printed after rune i" -- a claim about the pair
        # (i, i+1). Under any step the kept runes are not that pair, so a
        # sliced mark stream asserts adjacencies the page does not have.
        # Reversing used to move a word break by one and split words there.
        t = c.section("0.5").text()[:12]
        self.assertTrue(any(t.marks_after))  # the forward slice does have marks
        rev = t[::-1]
        self.assertEqual(rev.indices, t.indices[::-1])  # runes still reverse
        self.assertEqual(rev.marks_after, ("",) * len(rev))
        self.assertEqual(len(rev.words()), 1)  # no fabricated break
        self.assertEqual(rev.other, ())
        self.assertEqual(rev.leading_marks, "")
        every_other = t[::2]
        self.assertEqual(every_other.marks_after, ("",) * len(every_other))
        # A contiguous slice is untouched.
        self.assertEqual(t[:8].marks_after, t.marks_after[:8])

    def test_empty_prefix_slice_carries_nothing(self):
        # Both guards tested `start == 0`, which is true of t[:0], so an empty
        # slice kept 215 chars of `other` and the leading marks -- and
        # concat([t[:0], t]) then doubled them.
        t = c.page("page-51").text()
        self.assertTrue(t.leading_marks and t.other)
        empty = t[:0]
        self.assertEqual(len(empty), 0)
        self.assertEqual(empty.other, ())
        self.assertEqual(empty.leading_marks, "")
        joined = corpus.RuneText.concat([empty, t[0:]])
        self.assertEqual(joined.other, t.other)
        self.assertEqual(joined.leading_marks, t.leading_marks)
        # A genuinely runeless page is built by the parser, not by slicing,
        # and must still carry its block.
        p50 = c.page("page-50").text()
        self.assertEqual(len(p50), 0)
        self.assertEqual(len(p50.other), 1)

    def test_slicing_other(self):
        t = c.page("page-15").text()
        self.assertEqual(len(t[:9].other), 1)  # tail keeps its square
        self.assertEqual(t[9:].other, ())  # headline onward has none
        self.assertEqual(len(t[:9]), 9)


class TestArchiveJoin(unittest.TestCase):
    """The reason to claim a section rather than `all`."""

    def test_every_unsolved_section_names_exactly_one_channel(self):
        for sec in c.unsolved_sections():
            self.assertEqual(len(sec.channels()), 1, sec.id)
        self.assertEqual(c.section("0.8").channels(), ["15-22"])
        self.assertEqual(c.section("0.12").channels(), ["40-55"])

    def test_every_page_scan_resolves(self):
        withimg = [p for p in c.pages if p.image]
        self.assertEqual(len(withimg), 75)
        for page in withimg:
            self.assertTrue(page.image_path.exists(), page.id)
            self.assertEqual(page.image_path.suffix, ".jpg")


class TestCommunications(unittest.TestCase):
    """Key material, not background reading -- and read through lib.corpus so
    it stays inside the drift hash."""

    def test_envelope_is_stripped(self):
        k = c.communication("2012-01-key-in-front-of-you")
        self.assertNotIn("PGP", k.body)
        self.assertTrue(k.body.startswith("The key has always been right"))
        self.assertEqual(k.date, "2012-01")

    def test_book_code_coordinates_survive(self):
        b = c.communication("2012-01-twenty-nine-volumes-book-code")
        self.assertIn("twenty-nine volumes", b.lines[0])
        coords = [ln for ln in b.lines if ln.count(":") == 1 and ln[0].isdigit()]
        self.assertGreaterEqual(len(coords), 15)
        for ln in coords:
            a, b_ = ln.split(":")
            int(a), int(b_)  # line:word, both integers

        # The old filename asserted the riddle's Mabinogion back-reference was
        # the source. Keep it as an API alias for recorded experiments; the
        # canonical name stays neutral because Britannica remains an 18/22 fit.
        old = c.communication("2012-01-mabinogion-book-code")
        self.assertEqual(old.id, "2012-01-twenty-nine-volumes-book-code")
        self.assertEqual(old.raw, b.raw)

    def test_whitespace_payload_survives(self):
        # The morse message is nothing but tabs and spaces. A body built with
        # .strip() reduced it to "" and the loss was silent.
        m = c.communication("2013-01-rune-table-morse")
        self.assertEqual(len(m.body), corpus.EXPECTED_MORSE_CHARS)
        self.assertEqual(set(m.body), {"\t", "\n", " "})
        self.assertEqual(len(m.lines), 4)

    def test_files_without_an_envelope_still_read(self):
        for cid in ("2014-01-fallen-behind-outguess-08", "cicada-3301-public-key"):
            self.assertTrue(c.communication(cid).body)

    def test_covered_by_the_drift_hash(self):
        self.assertEqual(len(c.communications), corpus.EXPECTED_COMMUNICATIONS)
        self.assertEqual(corpus.corpus_sha256(), corpus.EXPECTED_CORPUS_SHA)

    def test_manifest_controls_public_puzzle_order(self):
        self.assertEqual(
            [m.sequence for m in c.communications],
            list(range(1, corpus.EXPECTED_COMMUNICATIONS + 1)),
        )
        self.assertEqual(c.communications[0].stage, "reddit-and-mabinogion")
        self.assertEqual(c.communications[12].stage, "opening")
        self.assertEqual(c.communications[18].stage, "opening")
        self.assertEqual(c.communications[33].stage, "callback-and-onion-7")

    def test_signature_time_is_not_release_order(self):
        pointer = c.communication("2013-01-onion-pointer")
        hint = c.communication("2013-01-knock-on-the-sky")
        self.assertLess(pointer.signed_at, hint.signed_at)
        self.assertGreater(pointer.sequence, hint.sequence)
        callback = c.communication("2014-05-onion-welcome")
        self.assertEqual(callback.signed_at[:7], "2014-04")
        self.assertEqual(callback.observed_at[:7], "2014-05")

    def test_pre_migration_ids_remain_aliases(self):
        aliases = {
            "2012-01-end-of-puzzle": "2012-02-end-of-puzzle",
            "2012-01-necrome-denial": "2012-04-necrome-denial",
            "2013-cicada-os-message": "2013-01-cicada-os-message",
            "2014-01-onion-welcome": "2014-05-onion-welcome",
        }
        for old, canonical in aliases.items():
            self.assertEqual(c.communication(old).id, canonical)

    def test_round_paths_and_identity_are_separate(self):
        for message in c.communications:
            self.assertTrue(message.path.is_file())
            self.assertEqual(message.id, message.path.stem)
            self.assertEqual(message.path.relative_to(corpus.CORPUS).parts[0],
                             message.round if message.round != "post-2014"
                             else message.observed_at[:4])
        self.assertNotIn("cicada-3301-public-key",
                         {message.id for message in c.communications})
        self.assertIn("BEGIN PGP PUBLIC KEY BLOCK", c.public_key)


class TestSectionBoundaries(unittest.TestCase):
    """Sections start at their headline, not at a page edge."""

    def test_mid_page_starts(self):
        for sec, n in (("0.8", 9), ("0.11", 91)):
            s = c.section(sec)
            self.assertEqual(s.first_rune, n)
            t = s.text()
            head = c.gp.to_indices(s.headline.replace(" ", ""))
            self.assertEqual(list(t.indices[: len(head)]), head)

    def test_last_owned_page_is_not_where_the_text_ends(self):
        # The field says which page the section owns; text() follows the spill
        # one page further. The old name read as "where the section ends" and
        # quietly said otherwise, and nothing consumed it, so nothing noticed.
        for sec_id, owned, ends in (("0.7", "page-14", "page-15"),
                                    ("0.10", "page-32", "page-33")):
            sec = c.section(sec_id)
            self.assertEqual(sec.last_owned_page, owned, sec_id)
            self.assertEqual(sec.pages()[-1].id, owned, sec_id)
            self.assertEqual(sec.text().positions[-1].page, ends, sec_id)

    def test_pages_and_sections_hold_the_same_runes(self):
        # The spill must neither lose nor duplicate a rune.
        self.assertEqual(sum(len(p.text()) for p in c.pages),
                         sum(len(s.text()) for s in c.sections))

    def test_preceding_section_gets_the_spill(self):
        # 0.7 runs 9 runes into page-15 and owns the number square there.
        t = c.section("0.7").text()
        self.assertEqual(len(t), 1738)
        self.assertEqual(t.positions[-1].page, "page-15")
        self.assertTrue(any("3258" in s for _, s in t.other))
        # 0.10 runs 91 runes into page-33.
        t10 = c.section("0.10").text()
        self.assertEqual(len(t10), 1524)
        self.assertEqual(t10.positions[-1].page, "page-33")
        # 0.8 and 0.11 no longer carry the foreign prefix.
        self.assertEqual(len(c.section("0.8").text()), 1894)
        self.assertEqual(len(c.section("0.11").text()), 1589)

    def test_unsolved_stream_unmoved(self):
        # Boundary shifts are internal to 0.5-0.12: the concatenated stream
        # must not move.
        self.assertEqual(c.unsolved.sha256(), corpus.EXPECTED_UNSOLVED_SHA)

    def test_sentences_reconstruct_sections(self):
        for sec in c.sections:
            rows = sec.sentences()
            if not rows:
                continue
            stream = [i for s in rows for i in c.gp.to_indices(s.runes)]
            text = list(sec.text().indices)
            gap = corpus.KNOWN_SENTENCE_GAPS.get(sec.id, 0)
            self.assertEqual(text[: len(stream)], stream, sec.id)
            self.assertEqual(len(text) - len(stream), gap, sec.id)


class TestWords(unittest.TestCase):
    def test_line_break_does_not_split_words(self):
        t = c.section("0.3").text()  # identity cipher: plaintext alignment
        prim = [tr.split("/")[0] for tr in c.gp.translits]
        words = ["".join(prim[i] for i in w.indices) for w in t.words()]
        self.assertIn("CIRCUMFERENCE", words)  # printed CIRCUMFEREN/CE
        self.assertEqual(len(words), 181)

    def test_unsolved_word_count(self):
        # 2,900 since the page-35 apostrophe (PE'T) was restored on 2026-08-25:
        # words() splits at typed marks, as it does for the four other apostrophes.
        self.assertEqual(len(c.unsolved.words()), 2900)

    def test_split_on_word_mark(self):
        t = c.page("intro-11").text()
        self.assertTrue(len(t.split_on(corpus.WORD)) > 10)


class TestAuthorSpelling(unittest.TestCase):
    """The book's own orthography, where it differs from standard English."""

    def test_qu_spells_as_the_author_spells_it(self):
        # The only Q sound Cicada prints is QUESTION, respelled KWESTION and
        # printed CWESTIAN in 0.4's unencrypted tail. Routing Q through C/K
        # instead gives CUESTIAN -- same 7 runes, differing at rune 1, so a
        # length check cannot see it and an exact lookup at n>=5 returns
        # nothing.
        self.assertEqual(c.gp.spell("QUESTION"), c.gp.spell("KWESTION"))
        self.assertEqual(c.gp.unspell(c.gp.spell("QUESTION")), "CWESTIAN")
        tail = c.gp.unspell(c.section("0.4").text().indices[319:])
        self.assertIn(c.gp.unspell(c.gp.spell("QUESTION")), tail)

    def test_bare_q_keeps_the_c_fallback(self):
        # No word in the book has a Q without a following U, so this is
        # convention, not attestation -- pinned so it stays deliberate.
        self.assertEqual(c.gp.unspell(c.gp.spell("IRAQ")), "IRAC")

    def test_widsom_and_beleive_are_the_author_not_the_speller(self):
        # 0.3 is a direct transliteration, so its printed runes are read, not
        # decrypted: the same section spells BELEIUE once and BELIEUE once.
        # Two one-off transpositions, not a rule -- so nothing to encode.
        got = {
            c.gp.unspell(c.gp.to_indices(s.runes))
            for s in c.section("0.3").sentences()
            if "BELE" in (s.english or "").upper() or "BELI" in (s.english or "").upper()
        }
        self.assertTrue(any("BELEIUE" in g for g in got))
        self.assertTrue(any("BELIEUE" in g for g in got))

class CorpusCsvShape(unittest.TestCase):
    """Every corpus CSV row must have exactly the header's field count.

    sections.csv rows 0.1, 0.4 and 0.13 once carried unquoted commas in `notes`
    and parsed as 13/12/12 fields against an 11-field header; the remainder was
    silently dropped, and `lib.corpus` returned 0.13's notes ending mid-clause
    at "(one interrupter" -- losing the interrupter position and the four
    ordinary ciphertext F used by the solved-section calibration.

    A DictReader hides this: it buckets extras under the None key. Compare the
    field count instead.
    """

    def test_every_row_matches_its_header(self):
        import csv

        bad = []
        for path in sorted((corpus.CORPUS).rglob("*.csv")):
            with path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
            if not rows:
                continue
            width = len(rows[0])
            for n, row in enumerate(rows[1:], start=2):
                if row and len(row) != width:
                    bad.append(f"  {path.name}:{n} has {len(row)} fields, "
                               f"header has {width}")
        self.assertFalse(bad, "\n".join(
            ["CSV rows must match their header; quote fields containing commas."]
            + bad))

class SentencesCoverage(unittest.TestCase):
    """`c.sentences` does not cover all solved runes, and the shortfall is exact.

    `c.sentences` omits 0.1's word square. Spelling every sentence's English
    gives 2,901 runes against 2,977 in
    the solved-section streams, and the whole 76-rune gap sits in 0.1 (596 vs
    672). Every other solved section matches exactly.

    Without this, an agent deriving "all solved text" from `c.sentences` loses
    76 runes silently, while the text still ends somewhere plausible.

    * `solutions/` is NOT the safe alternative. 0.1's solution file also spells
      to 596 runes against 672 of ciphertext -- the word square is absent there
      too. No English source in the repo covers it; it lives only in the rune
      stream.
    * The COVERAGE invariant is not new here. `lib/corpus.py`'s
      KNOWN_SENTENCE_GAPS and `verify()` already compare sentence runes to the
      stream RUNE FOR RUNE across 15 sections and assert the same 76. What this
      test adds, and the reason to keep it, is different and narrower: it spells
      the English, so it pins that `gp.spell` reproduces the printed rune count
      per section -- which the rune-based gate cannot see, because it reads the
      transcribed rune column and never spells anything.
    """

    EXPECT = {"0.0": 0, "0.1": 76, "0.2": 0, "0.3": 0,
              "0.4": 0, "0.13": 0, "0.14": 0}

    def test_gap_is_exactly_the_word_square_in_0_1(self):
        c = corpus.load()
        gp = c.gp
        gaps, tot_sent, tot_stream = {}, 0, 0
        for s in c.sections:
            if not (s.solved and s.solution_file):
                continue
            sent = sum(len(gp.spell(x.english)) for x in s.sentences()
                       if x.english)
            stream = len(list(s.text().indices))
            gaps[s.id] = stream - sent
            tot_sent += sent
            tot_stream += stream
        self.assertEqual(gaps, self.EXPECT,
                         "sentence-vs-stream shortfall moved from 0.1's word square")
        self.assertEqual((tot_sent, tot_stream), (2901, 2977))


class SectionPartition(unittest.TestCase):
    """Every page rune lies in exactly one section, at fixed per-section counts.

    `EXPECTED_UNSOLVED_SHA` pins the concatenated unsolved stream, so a boundary
    move across the solved/unsolved line is caught. A shift *within* the
    unsolved block is not: the concatenation is unchanged and so is its hash,
    while every per-section statistic silently re-attributes runes.

    `escape_joint.py` hard-codes the eight body lengths as a literal
    `LENGTHS = [729, 1145, 1738, 1894, 1021, 1524, 1589, 3316]`, so a boundary
    shift would leave it simulating the wrong geometry with inputs that still
    hash correctly. Three `sections.csv` rows once carried unquoted commas in
    `notes` and parsed at the wrong width, so the partition is pinned here.
    """

    COUNTS = {
        "0.0": 184, "0.1": 672, "0.2": 778, "0.3": 755, "0.4": 408,
        "0.5": 729, "0.6": 1145, "0.7": 1738, "0.8": 1894, "0.9": 1021,
        "0.10": 1524, "0.11": 1589, "0.12": 3316, "0.13": 85, "0.14": 95,
    }

    def test_per_section_rune_counts(self):
        self.assertEqual({s.id: len(s.text().indices) for s in c.sections},
                         self.COUNTS)

    def test_partition_is_exact(self):
        page_runes = sum(len(p.text().indices) for p in c.pages)
        section_runes = sum(len(s.text().indices) for s in c.sections)
        self.assertEqual(page_runes, section_runes)
        self.assertEqual(page_runes, sum(self.COUNTS.values()))

    def test_only_runeless_front_matter_sits_outside_a_section(self):
        assigned = {p.id for s in c.sections for p in s.pages()}
        outside = [p for p in c.pages if p.id not in assigned]
        self.assertEqual(sorted(p.id for p in outside),
                         ["intro-00", "intro-02"])
        for p in outside:
            self.assertEqual(len(p.text().indices), 0, p.id)


if __name__ == "__main__":
    unittest.main()
