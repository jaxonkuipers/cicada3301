# Research workspace

Root `HISTORY.md` reconstructs the authenticated route. `SETTLED.md` contains the compact established state needed across investigations. This directory begins with no experiment history.

## Layout

| Path | Contents |
| --- | --- |
| `SETTLED.md` | durable facts and cross-campaign conclusions |
| `attacks/` | one committed investigation per directory |
| `explog/` | append-only JSONL shards written by solver wakes |
| `surveys/` | cited community or public-source evidence |
| `shared/` | reusable research instruments |

## Retrieve current work

The archive reviewer checks the experiment record and community discussion after candidate mechanisms have been formed:

```text
python3 -m tools.explog "OBJECT OPERATION TERMS"
python3 -m tools.explog show ID...
python3 -m tools.explog running
python3 -m tools.dsearch "OBJECT OPERATION TERMS"
python3 -m tools.dsearch show ID...
```

Explog queries return compact matching records. `show` opens selected records and `running` lists current locks. Dsearch returns matching messages; its `show` command opens surrounding conversations.

## Record work

Use `research/attacks/<slug>/` for an investigation, matching the Explog method. Preserve executable code and concise findings; keep generated output under the investigation's gitignored `out/` directory. Add a running claim before sustained computation and resolve it with exact coverage and a result.

Managed wakes create isolated worktrees with `python3 -m tools.worktree create NAME` and publish committed checkpoints with `python3 -m tools.worktree publish`.

Run research code from the repository root:

```text
PYTHONPATH=. python3 research/attacks/<slug>/thing.py
```

Use `lib.corpus` for corpus objects and `research/shared/book.py` for the 2,901-rune solved control stream. Use `fitness.english_frequencies()` as the chi-squared reference and evaluate candidate plaintext with `fitness.judge` plus direct reading.
