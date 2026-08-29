# Cicada 3301 solver

This repository reconstructs the authenticated 2012–2017 Cicada 3301 route and investigates its unresolved result.

- `HISTORY.md` records the route and preservation boundaries.
- `corpus/` contains authenticated communications, Liber Primus images, transcriptions and accepted plaintext.
- `research/SETTLED.md` contains compact established state.
- `research/attacks/` receives new investigations.
- `research/explog/` receives the current append-only experiment record.
- `discord/` contains the searchable community archive used by `tools.dsearch`.

Verify the baseline with:

```text
python3 -m lib.corpus
python3 -m unittest discover -s tests
ruff check lib tools tests
```
