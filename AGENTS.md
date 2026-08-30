# Cicada 3301 solver

Recover Cicada 3301's intended unresolved result from its preserved public route, authenticated communications and surviving artifacts. Liber Primus is the largest preserved unresolved surface within that route.

## Campaign workflow

Each automation owns one causal campaign across scheduled runs. Resume the managed worktree that the campaign's committed `research/campaigns/<name>/STATE.md` names on its `Managed wake:` line. A wake that no committed `STATE.md` names is not a campaign; when the conversation names no campaign, open a new one rather than adopting a stray wake. Create a managed worktree when opening a campaign, inspect active Explog reservations, and select a preserved transition from the map in [`corpus/README.md`](corpus/README.md).

Open that transition's record and linked primary artifacts. Record the contemporary state, causal question, live mechanisms, observations and next discriminator in `STATE.md`. Give the same state and artifacts to fresh-context subagents, each assigned a distinct consumer class: book-wide geometry, section-local operation, external address or output, semantic word–number mechanism, historical protocol or service state, and an unconstrained construction. Each names the artifact prediction that would falsify its mechanism. Compare their mechanisms before choosing an operation, and concentrate several agents on one branch only after that comparison.

Give the candidate mechanisms to a separate archive-review subagent. It searches Explog and Discord for each mechanism's object, consumer and operation, opens the surrounding conversation of every selected result or message rather than the hit alone, and reports dates, evidence class, assumptions and coverage. It classifies each neighbouring proposal as tested, proposed but untested, or underspecified, so a claim of no prior coverage is judged against the neighbourhood of prior reasoning rather than against duplicates of the eventual computation. Command syntax and the reservation lifecycle live in [`research/README.md`](research/README.md).

Select operations through artifact causality and the historical state they could recover or change. Publish a running reservation before sustained computation. Reconstruct the relevant websites, services, requests, carriers, diagrams or instruments and test coherent alternatives and controls. Continue across scheduled runs while an in-scope discriminator can answer the campaign's causal question.

At each boundary, replace `STATE.md` with current state and put durable measurements and resolved mechanisms in `FINDINGS.md`. Close each reservation with exact coverage and result; evidence-backed results cite their evidence. A blocker names the unavailable evidence, affected discriminators and recovery that would reopen them.

## Historical reasoning

Use the software, protocols, cultural knowledge and network capabilities available to a capable solver at the selected transition: Tor and onion services, OutGuess, OpenPGP, image and audio tools, emulation and contemporary cipher implementations. Modern computation can replay or accelerate an artifact-selected operation.

Think with the artifacts. Reconstruct protocol exchanges, manipulate carriers, sketch dependencies and infer system roles from objects Cicada placed together. Earlier transitions supply demonstrated design language. Promote a result when evidence selects its object, representation, consumer and operation, and an unused prediction survives cheaper alternatives and controls; only a promoted result closes as `positive`. Recovered prior art, reconstructions and scoped negatives close as `negative` with their recovered inputs in `FINDINGS.md` or the route record. A selected cipher predicts plaintext beyond its fit. Prior coverage applies to the recorded operation.

Use local files and public sources. Never initiate authentication, enter credentials or attempt a login.

## Durable state

The corpus route map leads to one compact record and its owned evidence. `discord.db` preserves retrospective community discussion. Explog stores active reservations and exact experiment conclusions.

A campaign directory contains compact `STATE.md`, concise `FINDINGS.md`, reusable scripts and gitignored `out/`. Put historical conclusions in their route record, mechanical invariants in code and tests, and experiment conclusions in campaign findings and Explog. Give every positive result to a fresh-context reviewer for prior-art, post-selection, instrument and cheaper-alternative objections and for whether it meets the promotion rule; the reviewer judges the verdict label as well as the arithmetic.

Verify checkpoints with `python3 -m solver.corpus`, `python3 -m unittest discover -s tests` and `ruff check solver tests`. Use corpus objects through `solver.corpus`, rune arithmetic through `c.gp`, `solver.runes` and `solver.cipher`, and accepted plaintext through `solutions/`. Write Markdown prose as one physical line per semantic paragraph.
