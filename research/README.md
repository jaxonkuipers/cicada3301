# Research

| Path | Contents |
| --- | --- |
| `campaigns/<name>/STATE.md` | compact state carried across scheduled runs |
| `campaigns/<name>/FINDINGS.md` | evidence, exact coverage and conclusions |
| `campaigns/<name>/*.py` | reusable reconstruction and experiment code |
| `explog/*.jsonl` | active operation locks and closed results by wake |
| `SETTLED.md` | conclusions that constrain several campaigns |

## Retrieve prior work

```text
python3 -m solver.cli.explog "OBJECT TERM"
python3 -m solver.cli.explog "OPERATION TERM"
python3 -m solver.cli.explog show ID...
python3 -m solver.cli.explog running
python3 -m solver.cli.dsearch "OBJECT TERM"
python3 -m solver.cli.dsearch "OPERATION TERM"
python3 -m solver.cli.dsearch show ID...
```

Run several short searches, then open only the relevant ids. Explog search returns conclusions and unresolved locks; `show` opens complete events. Dsearch searches message text and attachment/embed metadata, returns compact individual messages, and opens selected surrounding conversations. Its 109,917 messages cover 13 retrospective Liber Primus channels from 2019 through 2026.

## Record a campaign

Create `research/campaigns/<name>/` and reserve sustained computation:

```text
python3 -m solver.cli.explog add --verdict running --campaign NAME --route ROUTE --object "OBJECT" --operation "OPERATION" --decision "OUTCOME INTERPRETATION"
```

Close the operation with `negative`, `positive` or `blocked`:

```text
python3 -m solver.cli.explog add --verdict VERDICT --resolves ID --coverage "EXACT CELLS TESTED" --result "OBSERVATION AND IMPLICATION" --evidence research/campaigns/NAME/FINDINGS.md
```

When a campaign is ended administratively, release its reservation with `blocked`, coverage `no cells; campaign ended by user`, and a result naming the administrative release. This release needs no evidence file. A later campaign may reserve that operation again.

Run campaign code from the repository root with `PYTHONPATH=. python3 research/campaigns/<name>/script.py`. Store generated files under the campaign's `out/` directory.

Create a managed worktree with `python3 -m solver.cli.worktree create NAME`. Publish the committed running reservation before sustained work, then publish each committed boundary checkpoint with `python3 -m solver.cli.worktree publish`.

At a boundary, rewrite `STATE.md` to its current contemporary state, causal question, live mechanisms, observations and implications, and next discriminator. Keep durable evidence and resolved mechanisms in `FINDINGS.md`.
