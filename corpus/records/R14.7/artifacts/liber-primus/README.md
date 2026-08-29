# Liber Primus data contract

Liber Primus has 75 images: the 17-page solved introduction `intro-00`–`intro-16` and the 58-page body `page-00`–`page-57`. Only body pages 56 and 57 are solved. Body page numbers follow the community convention used by the wiki, forum and Discord archive; `book_page` in [`pages.csv`](pages.csv) records the upstream whole-book index, where body `book_page = page + 17`. The book prints no page numbers.

| Path | Contents |
| --- | --- |
| [`pages.csv`](pages.csv) | page namespace, section, status, available files, discussion channel and `book_page` |
| [`sections.csv`](sections.csv) | section ranges, headlines, ciphers, keys and solution files |
| [`sentences.csv`](sentences.csv) | 262 rune sentences, 94 aligned to accepted English |
| [`images/`](images/) | all 75 published page files |
| [`transcription/`](transcription/) | rune text for the 73 pages carrying runes |
| [`solutions/`](solutions/) | accepted English grouped by solved section |

`intro-00` and `intro-02` are a title page and chapter divider without runes. Sections 0.8 and 0.11 begin inside body pages 20 and 54; their `first_rune` values in `sections.csv` are 9 and 91. The preceding section continues to that offset. Eight body sections, 0.5–0.12, remain unsolved and contain 12,956 runes.

The transcription retains rune case, digits, line markers and non-rune marks. Its delimiters are `-` word, `.` clause, `&` paragraph, `$` segment, `§` chapter and `/` line. No `§` occurs in the book. A `$` closes a segment and can occur inside a section.

The 58 body images are byte-identical to the original onion-7 release. All 75 images are byte-identical to the pinned upstream archive. Two solved introduction files contain trailing or concatenated data; decoders read their first JPEG. [`PROVENANCE.md`](../../PROVENANCE.md) records the pinned source, image lineage, malformed-file structure, transcription derivation and page-assignment checks.
