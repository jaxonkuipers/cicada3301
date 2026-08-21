# Liber Primus

Unsolved: 12,956 runes, sections 0.5–0.12, 56 of 58 body pages.

## Start here

1. `python3 -m lib.corpus` — every line must read PASS and exit 0, including 12,956 runes and sha256 `73473a68c3fc4296…`. On any FAIL, stop: the corpus or the parser changed and every derived result is void.
2. `python3 -m tools.build_discord_db` — required on a fresh clone.
3. Read `corpus/liber-primus/sections.csv`. Seven sections solved, eight unsolved; cipher, key, true rune boundaries (`first_rune`), and measured interrupter behaviour per section.
4. Search before claiming novelty: the archive (`tools.dsearch`) for what the community tried, the experiment log (`tools.explog`) for what this repo tried. Record every attempt; `disproved` requires stating exactly what was searched. The frontier is `explog list --verdict promising` (and `abandoned`): start there, and end every session by logging your own leads with the numbers. Other agents may be working right now and cannot see you: log a `running` entry BEFORE starting an attack, then list again — if an earlier `running` entry covers the same target, pick different work.
5. the text is presumed decipherable; a failed attack indicts the method and its coverage, never the puzzle; "no solution exists" is not a recordable conclusion

## Commands

Run from the repo root. Use `-m`; `python3 tools/dsearch.py` fails with `ModuleNotFoundError: No module named 'lib'`.

```
python3 -m lib.corpus                 # drift check
python3 -m unittest discover -s tests # regression + known-answer tests
ruff check lib tools tests            # lint
python3 -m tools.build_discord_db     # build/rebuild discord.db (~3s)
python3 -m tools.dsearch QUERY        # search discussion (--json for machines)
python3 -m tools.dsearch --runes SEQ  # search rune text, any notation
python3 -m tools.dsearch --channels   # list channels
python3 -m tools.explog add|list|search  # the experiment log
```

`dsearch` exits 0 on zero hits (a negative result is a result) and 2 on a bad query.

## Never

- Never parse `corpus/` yourself. Use `lib.corpus`.
- Never hardcode the rune alphabet or the transliteration table. Use `c.gp`.
- Never write another rune-notation converter. Use `lib.runes`.
- Never grep for runes. The same sequence appears as codepoints, as transliterations, and as indices, split by `-` `.` `/`. Grep finds one form and misses the rest.
- Never treat `discord/` as evidence. It is unverified discussion.
- Never write cipher arithmetic inline. `lib.cipher` is proven against every solved section; a private loop with a subtle interrupter bug produces plausible garbage.
- Never eyeball candidate plaintexts in bulk. Rank with `fitness.score`, read only the outliers.
- Never write analysis into `corpus/`. Derived work, scripts, and results go in `research/`; log runs with `tools.explog`.
- Never edit the `EXPECTED_*` constants in `lib/corpus.py` to make a FAIL pass. They change only as part of a deliberate corpus change, recomputed and explained in that commit.
- Never commit bulk output. One directory per direction under `research/attacks/<slug>/` (the slug matching the explog method); commit scripts and a findings note, keep candidate dumps and sweep logs in its `out/`, which is gitignored.

## Read data from data, not from this file

| question | source |
| --- | --- |
| cipher, key, boundaries, interrupters per section | `corpus/liber-primus/sections.csv` |
| page status, section, channel | `corpus/liber-primus/pages.csv` |
| page images, sourced from onion | `corpus/liber-primus/images/` |
| rune↔English, 94 solved | `corpus/liber-primus/sentences.csv` |
| rune table | `corpus/gematria-primus.csv` via `c.gp` |
| solved plaintext | `corpus/liber-primus/solutions/` |
| what the community tried | `python3 -m tools.dsearch` |
| what this repo tried | `research/experiments.jsonl` via `tools.explog` |

## API

```python
from lib import cipher, corpus, fitness, stats
c = corpus.load()
c.unsolved.indices          # 12,956 ints in 0..28 — property, not a call
c.section("0.5").text()     # RuneText: .runes .indices .words() .lines() .other
c.gp.spell("TUNNELING")     # [16, 1, 9, 9, 18, 20, 21] — 7 runes, not 8
c.gp.unspell(indices)       # rune indices -> readable Latin

cipher.vigenere_decrypt(ct, key, skips=frozenset())   # skips = interrupted positions
cipher.autokey_pt_decrypt(ct, key) / autokey_ct_decrypt / beaufort_decrypt
cipher.phi_prime_decrypt(ct, skips={56})              # 0.13, exact

stats.ioc(t); stats.periodic_ioc(t, k); stats.doublet_rate(t)
stats.repeats(t); stats.kasiski_gaps(t); stats.find(haystack, needle)
fitness.score(t)            # quadgram log-prob; rank with it, never threshold.
                            # Held-out Cicada English clears same-length noise
                            # by ~3 log10/rune, even on 50-rune segments --
                            # read every outlier.
fitness.windowed(t)         # per-window scores: a key decrypting only a
                            # stretch (0.1/0.4 pattern) shows here, not in the
                            # whole-stream mean.
                            # fitness judges FINAL English only. Judge multi-
                            # stage intermediates with stats.ioc/chi_squared:
                            # English under a transposition keeps ioc ~1.77
                            # while scoring near noise on quadgrams.
```

`spell()` handles the `ING` trigraph, `IO` = the `IA` rune, and per-word spelling so digraphs never cross a space; it is greedy, so treat spelled lengths of arbitrary modern English (IONIC, PINEAPPLE) as approximate. `words()` does not split at a bare `/` — that is a printed line break falling mid-word.

## The interrupter

Proven by rune-exact decryption of 0.1, 0.4 and 0.13 (`tests/test_cipher.py`):

- Plaintext F passes through unencrypted and the keystream does NOT advance.
- A ciphertext F elsewhere is an ordinary encryption, so ciphertext F alone is ambiguous: interrupter positions are part of the key an attack must search.
- Cicada mixes enciphered and plain stretches inside one section: 0.1 is enciphered only for runes 0–514, 0.4 only for 0–318. Consider the same for unsolved sections before declaring a method dead.

## Think like the author

Every solved key came from the book's own vocabulary and machinery, not from a dictionary: DIVINITY (0.1) is the book's central theme, FIRFUMFERENFE (0.4) is CIRCUMFERENCE — a solved-plaintext word — with every C corrupted to F, the interrupter rune itself, and 0.13's keystream is phi(primes), the totient of the same primes the Gematria Primus assigns each rune. Cicada wrote "the key is in front of you" (`corpus/communications/2012-01-key-in-front-of-you.asc`). Generate hypotheses from inside the material: solved plaintext vocabulary, headlines, the communications, gematria structure (primes, indices, 3301/1033), the printed anomalies below. Prefer schemes one conceptual step past the solved escalation — substitution, then keyed polyalphabetic with interrupter, then mathematical keystream — over arbitrary sweeps the community exhausted years ago.

## Printed anomalies

All held in `RuneText.other` with their group structure intact. Re-derive with `c.page(ID).text().other`:

- `intro-16` — 5×5 magic square, constant 3301, rows and columns and both diagonals. Solved page but the square itself is unexplained.
- `page-15` — 4×4 number square: rows 12670 / 12713 / 12350 / 8250, all columns differ. It sits in section **0.7's** tail (the 9 runes before 0.8's headline). Unsolved.
- `page-49`–`page-51` — 256 groups in base 60 over `0-9 A-Z a-x`, decoding to 256 bytes spanning 0..255, 161 distinct, not a permutation. `page-50` carries no runes at all. Unsolved.
- `page-56` — 128 hex characters, a SHA-512 digest, the "deep web hash". Solved page, but the deep web hash itself is unsolved.
- Numerals in otherwise pure rune text: `7` mid-line on page-10 (unexplained), and `1` `2` `3` `4` `5` at paragraph starts across pages 36–38 — an ordered list numbering, echoed by intro-11's leading `2`.
