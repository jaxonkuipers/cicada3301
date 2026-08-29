# Cicada 3301 solver

Recover Cicada 3301's intended unresolved result from the preserved public route, authenticated communications and surviving artifacts. Liber Primus is the largest preserved unresolved surface in that route.

## Start or resume a campaign

1. A scheduled automation owns one causal campaign across runs. Resume its named worktree and synchronize it with `origin/main` while preserving campaign state. For a new campaign, create a current worktree with `python3 -m solver.cli.worktree create NAME` and continue from the printed path.
2. Inspect `python3 -m solver.cli.explog running` and the route map in `corpus/README.md`. Choose a provenance-supported preserved transition and a causal question outside the exact operations already reserved.
3. Open that transition under `corpus/records/` and its linked primary artifacts. Write the contemporary solver state, causal question, live mechanisms, observations and next discriminator in `research/campaigns/<name>/STATE.md`.
4. Give fresh-context subagents the selected state and artifacts. Ask each for an independent causal construction and its observable consequences. The campaign owner compares and synthesizes their mechanisms.
5. Give those mechanisms to a separate fresh-context archive reviewer. The reviewer runs several short Explog queries, opens relevant result ids, and reports exact prior coverage and tested assumptions. For retrospective Liber Primus community evidence, the reviewer also queries the 2019–2026 Discord archive, opens selected message ids, and reports the dates and source type:

```text
python3 -m solver.cli.explog "OBJECT TERM"
python3 -m solver.cli.explog "OPERATION TERM"
python3 -m solver.cli.explog show ID...
python3 -m solver.cli.dsearch "OBJECT TERM"
python3 -m solver.cli.dsearch "OPERATION TERM"
python3 -m solver.cli.dsearch show ID...
```

6. Select a mechanism by artifact causality and the state its outcomes recover or change. Reserve it with an exact object, operation and decision:

```text
python3 -m solver.cli.explog add --verdict running --campaign NAME --route ROUTE --object "OBJECT" --operation "OPERATION" --decision "OUTCOME INTERPRETATION"
git add research/explog research/campaigns/NAME/STATE.md
git commit -m "Reserve NAME operation"
python3 -m solver.cli.worktree publish
```

7. Reconstruct and test the mechanism through coherent observations and pivots. Build the websites, services, requests, carriers, diagrams or instruments that make it concrete. Continue while an in-scope operation can answer the causal question. At each scheduled boundary, rewrite `STATE.md` to the current five fields, put durable evidence in `FINDINGS.md`, commit the checkpoint and publish it.

Close the reservation with its exact tested coverage, result and evidence:

```text
python3 -m solver.cli.explog add --verdict negative --resolves ID --coverage "EXACT CELLS TESTED" --result "OBSERVATION AND IMPLICATION" --evidence research/campaigns/NAME/FINDINGS.md
```

Use `positive` for a surviving result and `blocked` for an exact evidential blocker. A blocker identifies the unavailable evidence, the discriminators that require it and the recovery that would reopen the question.

## Work from the historical state

Use the software, protocols, cultural knowledge and network capabilities available to a capable solver at the selected transition: Tor and onion services, OutGuess, OpenPGP, image and audio tools, emulation and contemporary cipher implementations. Modern computation can replay or accelerate an artifact-selected operation.

Think with the artifacts. Reconstruct protocol exchanges, operate faithful local replicas, sketch dependencies, manipulate carriers and invent mechanisms from objects Cicada placed together. Earlier transitions supply demonstrated design language and system roles.

Promote a result when artifact evidence selects its object, representation, consumer and operation. Run the cheapest alternatives and controls, then require an unused prediction. A selected cipher predicts plaintext beyond its fit. Prior coverage applies to the exact operation recorded.

Use local files and publicly accessible sources. Never initiate authentication, enter credentials or attempt a login.

## Keep durable state compact

`corpus/README.md` is the route map; each `corpus/records/` directory supplies one transition or signed statement and the evidence it owns. `research/SETTLED.md` holds constraints used by several campaigns. `discord.db` preserves a 2019–2026 retrospective Liber Primus community archive. Explog stores active locks and exact experiment results.

A campaign directory contains `STATE.md`, concise `FINDINGS.md`, reusable scripts and gitignored `out/`. At every boundary, replace `STATE.md` with the current contemporary state and artifacts, causal question, live mechanisms, observations and implications, and next discriminator. Put resolved mechanisms and supporting evidence in `FINDINGS.md`. Add a conclusion to `research/SETTLED.md` when several campaigns need it. Update a corpus record when chronology or preservation evidence changes.

Give a positive result to a fresh-context reviewer with its claim, evidence and archive tools. Incorporate its prior-art, post-selection, instrument and cheaper-alternative objections before promoting the result.

## Verify

```text
python3 -m solver.corpus
python3 -m unittest discover -s tests
ruff check solver tests
```

Use corpus objects through `solver.corpus`, rune arithmetic through `c.gp`, `solver.runes` and `solver.cipher`, and solved text through `solutions/`. Write Markdown prose as one physical line per semantic paragraph.
