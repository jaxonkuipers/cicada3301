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

The images, transcriptions and accepted solutions derive from `cicada-solvers/iddqd` at commit `0e3789ad2949c62ea7fb9e3e00ded93df3b3ce07`. All 75 image files match that commit byte-for-byte; the 58 body images also match the original onion-7 release with content distance 0.000 and next-best distance at least 5.77. `sentences.csv` restores the image-verified final ᛗ in sentence `0.8.0.14`; its only section-stream gap is section 0.1's 76-rune unencrypted word-list tail. `solver.corpus.verify()` checks both facts.

Two solved introduction files are compound. In `intro-05.jpg`, the page is the first 336,353-byte JPEG; the remainder is ASCII hex and zero padding. In `intro-10.jpg`, the page is the first 754,662-byte JPEG; the remaining three JPEGs repeat `intro-11`, `intro-12` and `intro-13`. Decoders read the first JPEG in each file.
