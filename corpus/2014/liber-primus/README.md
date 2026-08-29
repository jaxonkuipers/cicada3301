# Liber Primus

75 pages: a 17-page solved intro (`intro-00`–`intro-16`) and a 58-page body (`page-00`–`page-57`), of which only `page-56` and `page-57` are solved.

This directory is the output of the 2014 interactive route. See the cross-round [`HISTORY.md`](../../../HISTORY.md) before treating its pages as an isolated puzzle.

## Page numbers

**Body pages are numbered the way solvers number them, `page-00` to `page-57`.** That is the numbering used by the Discord channels here, the wiki and the forum, so a page number in this repository means the same thing it means everywhere else.

The book itself carries no page numbers — no folios on any page, no chapter markers in any transcription. Cicada published an order, not a numbering, so every scheme in circulation is one the community imposed.

Solver numbering cannot reach the 17 solved pages that open the book, so those use a separate `intro-00` to `intro-16` namespace under upstream's own numbers. The two never collide: a bare number always means a body page, and an intro page is always said as one.

Upstream numbers the whole book 0–74 in one run. That appears as the `book_page` column in [`pages.csv`](pages.csv) and nowhere else; `book_page = page + 17` for body pages, and `book_page` equals the intro number for intro pages.

## Files

| Path | Contents |
| --- | --- |
| [`pages.csv`](pages.csv) | one row per page: section, status, which files exist, which Discord channel discusses it, and the upstream `book_page` |
| [`sections.csv`](sections.csv) | one row per section: page range, headline, cipher, key, solution file. `first_rune` is the rune offset within `first_page` where the section truly begins — sections 0.8 and 0.11 start mid-page (offsets 9 and 91, fixed by their printed headlines), and the preceding section's text extends to that point |
| [`sentences.csv`](sentences.csv) | 262 sentences, rune text aligned to English where solved (94 of 262) |
| [`images/`](images/) | all 75 pages |
| [`transcription/`](transcription/) | rune text for the 73 pages that carry runes |
| [`solutions/`](solutions/) | decrypted English, one file per solved section |

`intro-00` and `intro-02` are front matter — a title page and a chapter divider — and carry no runes, so they have an image but no transcription.

This directory intentionally contains no candidate plaintext, hypothesis ranking, or exploratory analysis for the unsolved sections. Community proposals remain in [`../../../discord/`](../../../discord/) without being promoted into canonical corpus facts.

## Reading the transcription

The transcription preserves rune case, digits, line markers, and every non-rune mark as source data. Delimiters are upstream's:

```text
Word: -    Clause: .    Paragraph: &    Segment: $    Chapter: §    Line: /
```

`§` never actually occurs: the book has no chapter breaks in its text, and no printed page numbers on any page.

## Provenance

The Liber Primus images, transcriptions, and accepted solutions were imported from the CicadaSolvers `iddqd` archive pinned at:

```text
https://github.com/cicada-solvers/iddqd  @  0e3789ad2949c62ea7fb9e3e00ded93df3b3ce07
```

That commit is **not** in `rtkd/iddqd`, which this file previously named and whose `master` is stale; it is in `cicada-solvers/iddqd`.

Everything below is stated in upstream's book numbers, 0–74.

- **Images** are `liber-primus__images--full/NN.jpg`, byte for byte.

### Image lineage

- **75 of 75** are byte-identical to the pinned `iddqd` commit.
- **58 of 58** are byte-identical to the **original 2014 onion release** (`ky2khlqdf7qdznac.onion`), matched by image content rather than filename because the onion numbers only the 58 unsolved pages 0–57. Every match is unambiguous (distance 0.000, next-best ≥ 5.77). Those 58 are `page-00` … `page-57` — the whole unsolved corpus.
- `page-00` is additionally byte-identical to a non-GitHub lineage (the Internet Archive `liber-primus` item); the rest of that set is a downsampled re-encode.

So the unsolved pages are the files Cicada published, unmodified. Any measurement of their JPEG internals — quantization tables, ICC profile, coefficient statistics — is a measurement of the originals.

### Two intro images are malformed at source

`intro-05.jpg` and `intro-10.jpg` are not single JPEGs:

- `intro-10.jpg` is **four complete JPEGs concatenated**, and segments 2–4 are byte-for-byte the separately published `intro-11.jpg`, `intro-12.jpg` and `intro-13.jpg`. The real page-10 image is the first 754,662 bytes.
- `intro-05.jpg` is a valid JPEG (first 336,353 bytes) followed by ~336 KB of ASCII-hex and zero padding.

**These files are not repaired here, and should not be.** They are byte-identical across all five published lineages checked (`iddqd`, `krisyotam/pages`, `ibotpeaches`, `cijhho`, `scream314`), so the malformation is upstream of every archive and is part of the published record. Every decoder reads only the first image in a concatenated file, so nothing downstream is affected, and both files are solved intro pages outside the 12,956-rune unsolved corpus.

Statements about these two **files** — byte hashes, file sizes, "lacks an ICC profile" — describe a concatenation, not a page.

- **Transcriptions** come from splitting `liber-primus__transcription--master.txt` on `%`. Chunk 0 is the delimiter legend, not a page. Chunk 1 is book page 1, and chunks 2–73 are book pages 3–74; book pages 0 and 2 carry no runes and so consume no chunk. Chunks are trimmed of outer whitespace and normalized to LF.
- **`sentences.csv`** is a local index joining upstream's sentence-segmented transcription against its translation file on their shared sentence ids, collapsing upstream's double-spacing to single spaces. One local repair on top of upstream: sentence `0.8.0.14` was missing the final ᛗ of the printed word ᛚᚳᛇᛏᚷᚣᛟᛗ (page-20, printed line 6), verified against the page image; the transcription always had it. With that rune restored, sentences.csv reconstructs every section's rune stream exactly, except section 0.1's deliberate 76-rune tail gap (the unencrypted intro-05 word list, which upstream's sentence file never segmented). `lib.corpus.verify()` enforces both facts.
- **`solutions/`** is the English side of those same sentences, grouped by section.

## Page assignment evidence

The chunk-to-page assignment is not taken on faith from upstream's index. Three independent checks agree with it:

- `intro-00` and `intro-02` are front matter — one reads "Liber Primus", the other "Chapter 1 / Intus" — and neither contains a rune.
- Every segment terminator (`$`) falls at the end of a page, and every page where upstream's index ends a section carries one: `intro-01`, `intro-05`, `intro-09`, `intro-13` and `intro-16` close sections 0.0 through 0.4. A section may contain more than one segment — `intro-04` and `intro-15` also carry terminators — so `$` marks a segment boundary, not a section boundary.
- Applying section 0.0's key to `transcription/intro-01.txt` yields upstream's plaintext for section 0.0: `A WARNING / BELIEVE NOTHING FROM THIS BOOK / ...`.
