# research/

The working directory for attacks on the unsolved sections. `corpus/` holds
only canonical facts and never analysis; everything derived, exploratory, or
negative belongs here.

## Layout

| path | contents |
| --- | --- |
| [`experiments.jsonl`](experiments.jsonl) | append-only log of every attack: method, params, coverage, verdict. Written via `python3 -m tools.explog`, committed to git |
| `attacks/` | one directory per line of attack, holding scripts and findings |
| `attacks/provenance/` | image-provenance verification referenced by `corpus/liber-primus/README.md` |

## Rules

- Log every experiment, especially failures. `disproved` requires stating the
  exact coverage (which keys, which models, which sections); an unstated
  coverage claim is an `abandoned`, not a `disproved`.
- Search before running: the Discord archive (`python3 -m tools.dsearch`) for
  what the community tried, `python3 -m tools.explog search` for what this
  repo already tried.
- A "hit" is a candidate whose fitness score is far above the noise floor
  (`lib.fitness.score`) AND reads as English after `gp.unspell`. Log scores
  with the entry so a later reader can judge the margin.
- Nothing here is canonical. Promote a result into `corpus/` only when it is
  proven (rune-exact decryption), and update `lib.corpus.EXPECTED_CORPUS_SHA`
  when you do.
