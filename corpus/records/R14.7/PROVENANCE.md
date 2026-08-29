# R14.7 Liber Primus provenance

The images, transcriptions and accepted solutions came from `cicada-solvers/iddqd` at commit `0e3789ad2949c62ea7fb9e3e00ded93df3b3ce07`; this commit is absent from the stale `rtkd/iddqd` repository previously named here. The image source is `liber-primus__images--full/NN.jpg`. All 75 local images are byte-identical to that commit. Content matching also establishes that all 58 body images are byte-identical to the original 2014 `ky2khlqdf7qdznac.onion` release; each match has distance 0.000 and next-best distance at least 5.77. `page-00` independently matches the Internet Archive `liber-primus` item, whose remaining files are downsampled re-encodes.

## Published file structure

`intro-10.jpg` concatenates four complete JPEGs. Its first 754,662 bytes are page 10; the remaining segments are byte-identical to `intro-11.jpg`, `intro-12.jpg` and `intro-13.jpg`. `intro-05.jpg` contains a valid 336,353-byte JPEG followed by roughly 336 KB of ASCII hex and zero padding. Both files are byte-identical across the five checked lineages: `iddqd`, `krisyotam/pages`, `ibotpeaches`, `cijhho` and `scream314`. The corpus retains the published bytes. Image decoders use the first JPEG, and both files belong to the solved introduction outside the 12,956-rune unresolved body. File hashes, sizes and metadata measurements for these two paths therefore describe their complete compound files.

## Text derivation

Transcriptions derive from `liber-primus__transcription--master.txt`, split on `%`. Chunk 0 is the delimiter legend; chunk 1 is book page 1; chunks 2–73 are book pages 3–74. Book pages 0 and 2 carry no runes. Page chunks are trimmed and normalized to LF.

`sentences.csv` joins upstream's sentence-segmented transcription to its translation by sentence ID and normalizes double spaces. One image-verified repair restores the final ᛗ in sentence `0.8.0.14`, in the printed word ᛚᚳᛇᛏᚷᚣᛟᛗ on body page 20, line 6. The master transcription already contained that rune. The sentence index reconstructs every section rune stream except section 0.1's 76-rune tail: the unencrypted `intro-05` word list was never segmented upstream. `solver.corpus.verify()` checks both conditions. Files under `solutions/` contain the English side of the same joined sentences, grouped by section.

## Page assignment

Three checks independently support the chunk-to-page assignment. `intro-00` reads “Liber Primus” and `intro-02` reads “Chapter 1 / Intus”; neither contains runes. Segment terminators fall at page ends, including the section-closing pages `intro-01`, `intro-05`, `intro-09`, `intro-13` and `intro-16`. Applying section 0.0's key to `transcription/intro-01.txt` yields the accepted warning plaintext beginning `A WARNING / BELIEVE NOTHING FROM THIS BOOK`.
