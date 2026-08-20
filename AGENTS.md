# Liber Primus

Unsolved: 12,956 runes, sections 0.5–0.12, 56 of 58 body pages.

## Start here

1. `python3 -m lib.corpus` — must print 12,956 runes, sha256 `73473a68c3fc4296…`, 94/94 sentences. On any mismatch, stop: the transcription or the parser changed and every derived result is void.
2. `python3 -m tools.build_discord_db` — required on a fresh clone.
3. Read `corpus/liber-primus/sections.csv`. Seven sections solved, eight unsolved, one cipher and key per section.
4. Search the archive before claiming novelty. Record whether a method was disproved or merely abandoned.

## Commands

Run from the repo root. Use `-m`; `python3 tools/dsearch.py` fails with `ModuleNotFoundError: No module named 'lib'`.

```
python3 -m lib.corpus                 # drift check
python3 -m tools.build_discord_db     # build/rebuild discord.db (~3s)
python3 -m tools.dsearch QUERY        # search discussion
python3 -m tools.dsearch --runes SEQ  # search rune text, any notation
python3 -m tools.dsearch --channels   # list channels
```

## Never

- Never parse `corpus/` yourself. Use `lib.corpus`.
- Never hardcode the rune alphabet or the transliteration table. Use `c.gp`.
- Never write another rune-notation converter. Use `lib.runes`.
- Never grep for runes. The same sequence appears as codepoints, as transliterations, and as indices, split by `-` `.` `/`. Grep finds one form and misses the rest.
- Never treat `discord/` as evidence. It is unverified discussion.

## Read data from data, not from this file

| question | source |
| --- | --- |
| cipher and key per section | `corpus/liber-primus/sections.csv` |
| page status, section, channel | `corpus/liber-primus/pages.csv` |
| rune↔English, 94 solved | `corpus/liber-primus/sentences.csv` |
| rune table | `corpus/gematria-primus.csv` via `c.gp` |
| solved plaintext | `corpus/liber-primus/solutions/` |
| what was already tried | `python3 -m tools.dsearch` |

## API

```python
from lib import corpus
c = corpus.load()
c.unsolved.indices        # 12,956 ints in 0..28 — property, not a call
c.section("0.5").text()   # RuneText: .runes .indices .words() .lines() .other
c.gp.spell("TUNNELING")   # [16, 1, 9, 9, 18, 20, 21] — 7 runes, not 8
```

`spell()` already handles the `ING` trigraph, `IO` = the `IA` rune, and per-word spelling so digraphs never cross a space.

## Facts not recorded anywhere else

Cipher structure, from the `notes` column of `sections.csv`:

- Rune `F` (index 0) is left unencrypted in sections 0.1, 0.4 and 0.13. Model the interrupter before attacking any unsolved section.
- 0.13 subtracts φ(i-th prime), and 3301 is prime.

Printed anomalies, all held in `RuneText.other`. Re-derive any of them with `c.page(ID).text().other`:

- `intro-16` — 5×5 magic square, constant 3301, rows and columns and both diagonals. Solved page but the square itself is unexplained.
- `page-15` — 4×4 number square: rows 12670 / 12713 / 12350 / 8250, all columns differ. Unsolved.
- `page-49`–`page-51` — 256 groups in base 60 over `0-9 A-Z a-x`, decoding to 256 bytes spanning 0..255, 161 distinct, not a permutation. `page-50` carries no runes at all. Unsolved.
- `page-56` — 128 hex characters, a SHA-512 digest, the "deep web hash". Solved page, but the deep web hash itself is unsolved.
- Stray numerals in otherwise pure rune text: `7` on page-10, `1` on page-36, `34` on page-37, `5` on page-38. Unexplained.
