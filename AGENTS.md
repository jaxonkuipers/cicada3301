# Cicada 3301 solver

Recover Cicada 3301's intended unresolved result from its preserved public route, authenticated communications and surviving artifacts. Liber Primus is the largest preserved unresolved surface within that route.

## Campaign workflow

Each automation owns one causal campaign across scheduled runs. Resume its named managed worktree and compact `research/campaigns/<name>/STATE.md`. Create a managed worktree when opening a campaign, inspect active Explog reservations, and select a preserved transition from the map in [`corpus/README.md`](corpus/README.md).

Open that transition's record and linked primary artifacts. Record the contemporary state, causal question, live mechanisms, observations and next discriminator in `STATE.md`. Give the same state and artifacts to fresh-context subagents for independent causal constructions and observable consequences. Compare their mechanisms before choosing an operation.

Give the candidate mechanisms to a separate archive-review subagent. It searches Explog for exact prior experiment coverage and, when retrospective Liber Primus discussion is relevant, searches Discord. The reviewer opens selected result or message IDs and reports dates, evidence class, assumptions and tested coverage. Command syntax and the reservation lifecycle live in [`research/README.md`](research/README.md).

Select operations through artifact causality and the historical state they could recover or change. Publish a running reservation before sustained computation. Reconstruct the relevant websites, services, requests, carriers, diagrams or instruments and test coherent alternatives and controls. Continue across scheduled runs while an in-scope discriminator can answer the campaign's causal question.

At each boundary, replace `STATE.md` with current state and put durable measurements and resolved mechanisms in `FINDINGS.md`. Close each reservation with exact coverage, result and evidence. A blocker names the unavailable evidence, affected discriminators and recovery that would reopen them.

## Historical reasoning

Use the software, protocols, cultural knowledge and network capabilities available to a capable solver at the selected transition: Tor and onion services, OutGuess, OpenPGP, image and audio tools, emulation and contemporary cipher implementations. Modern computation can replay or accelerate an artifact-selected operation.

Think with the artifacts. Reconstruct protocol exchanges, manipulate carriers, sketch dependencies and infer system roles from objects Cicada placed together. Earlier transitions supply demonstrated design language. Promote a result when evidence selects its object, representation, consumer and operation, and an unused prediction survives cheaper alternatives and controls. A selected cipher predicts plaintext beyond its fit. Prior coverage applies to the recorded operation.

Use local files and public sources. Never initiate authentication, enter credentials or attempt a login.

## Durable state

The corpus route map leads to one compact record and its owned evidence. `research/SETTLED.md` contains constraints shared by several campaigns. `discord.db` preserves retrospective community discussion. Explog stores active reservations and exact experiment conclusions.

A campaign directory contains compact `STATE.md`, concise `FINDINGS.md`, reusable scripts and gitignored `out/`. Add a conclusion to `SETTLED.md` when several campaigns need it. Update a route record when chronology or preservation evidence changes. Give every positive result to a fresh-context reviewer for prior-art, post-selection, instrument and cheaper-alternative objections.

Verify checkpoints with `python3 -m solver.corpus`, `python3 -m unittest discover -s tests` and `ruff check solver tests`. Use corpus objects through `solver.corpus`, rune arithmetic through `c.gp`, `solver.runes` and `solver.cipher`, and accepted plaintext through `solutions/`. Write Markdown prose as one physical line per semantic paragraph.
