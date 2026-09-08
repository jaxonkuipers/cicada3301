# Research

| Path | Contents |
| --- | --- |
| `campaigns/<name>/STATE.md` | compact state carried across scheduled runs |
| `campaigns/<name>/FINDINGS.md` | evidence, exact coverage and conclusions |
| `campaigns/<name>/*.py` | reusable reconstruction and experiment code |
| `explog/*.jsonl` | active operation locks and closed results by wake |

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

Run several short searches, then open only the relevant ids. Explog search matches any query term and ranks records holding more of them higher, so a partial vocabulary degrades to ranked results rather than silence; it returns conclusions and unresolved locks, and `show` opens complete events. Dsearch searches message text and attachment/embed metadata, returns compact individual messages, and opens selected surrounding conversations. Its 109,917 messages cover 13 retrospective Liber Primus channels from 2019 through 2026.

## Record a campaign

Create `research/campaigns/<name>/` and reserve sustained computation:

```text
python3 -m solver.cli.explog add --verdict running --campaign NAME --route ROUTE --object "OBJECT" --operation "OPERATION" --decision "OUTCOME INTERPRETATION"
```

Close the operation with `negative`, `positive` or `blocked`:

```text
python3 -m solver.cli.explog add --verdict VERDICT --resolves ID --coverage "EXACT CELLS TESTED" --result "OBSERVATION AND IMPLICATION" --evidence research/campaigns/NAME/FINDINGS.md
```

Name `--object` with a canonical id where one exists — a route id, `lp:SECTION` or `lp:PAGE`, a communications.csv id, or a repository file path — so one artifact groups under one key; any other prose is accepted verbatim. A running `add` prints the closed results nearest the new claim's object and operation: open them with `show` before computing, and cite the ones the reservation is judged against.

`positive` records a promoted result: evidence selects the object, representation, consumer and operation, and an unused prediction survived cheaper alternatives and controls. Recovered prior art, reconstructions and scoped negatives close as `negative`, with the recovered inputs in `FINDINGS.md` or the route record. `blocked` names the unavailable evidence, the affected discriminators and the recovery that would reopen them.

When a campaign is ended administratively, release its reservation with `blocked`, coverage `no cells; campaign ended by user`, and a result naming the administrative release. This release needs no evidence file. A later campaign may reserve that operation again.

Run campaign code from the repository root with `PYTHONPATH=. python3 research/campaigns/<name>/script.py`. Store generated files under the campaign's `out/` directory.

## Consolidate the ledger

Roughly every 50 closures, open a `ledger-consolidation` campaign whose object is the ledger itself. Flag closed results that are textually different but causally the same operation, write per-route coverage summaries into the route records, and regenerate `research/explog/DIGEST.md` — a compact route → object → cluster view of every closed result, derived from the record rather than declared by writers, so wrong groupings cost a rerun instead of a migration. The consolidator writes only the digest and route-record summaries; ledger shards stay append-only and untouched.

Create a managed worktree with `python3 -m solver.cli.worktree create NAME`, using the campaign name. It prints the wake id `NAME-STAMP`; `STATE.md` carries the line `Managed wake: NAME-STAMP` directly under its title, and `python3 -m solver.cli.worktree publish` refuses a checkpoint whose changed `STATE.md` names another wake or none. `python3 -m solver.cli.worktree list` shows the managed wakes on this machine and the committed campaigns bound to each. Publish the committed running reservation before sustained work, then publish each committed boundary checkpoint.

At a boundary, rewrite `STATE.md` to its current contemporary state, causal question, live mechanisms, observations and implications, and next discriminator. Keep durable evidence and resolved mechanisms in `FINDINGS.md`.
