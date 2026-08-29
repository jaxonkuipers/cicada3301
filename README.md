# Cicada 3301 solver

This repository reconstructs the authenticated 2012–2017 Cicada 3301 route and investigates its unresolved result.

| Path | Purpose |
| --- | --- |
| [`corpus/`](corpus/) | compact route map, one historical step per transition, primary artifacts and indexes |
| [`solver/`](solver/) | corpus access, rune and cipher operations, scoring, reusable instruments and command-line tools |
| [`research/`](research/) | active campaigns, cross-campaign conclusions and the experiment ledger |
| [`tests/`](tests/) | corpus, solver, route and coordination invariants |
| [`discord.db`](discord.db) | 2019–2026 retrospective Liber Primus community archive: 109,917 messages across 13 channels |

Start with [`AGENTS.md`](AGENTS.md). Verify the repository with:

```text
python3 -m solver.corpus
python3 -m unittest discover -s tests
ruff check solver tests
```

Enable the repository's verified-push hook once per clone:

```text
git config core.hooksPath .githooks
```
