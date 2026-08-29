# Cicada 3301 solver

Goal: recover Cicada 3301's intended unresolved result from the full authenticated route. Liber Primus is the largest preserved unsolved artifact within that route.

## Continue the campaign

1. This automation owns one causal campaign across scheduled runs. The automation conversation, together with any `STATE.md` it names, identifies that campaign; research scripts and findings are shared artifacts. Resume the worktree named in the conversation, then inspect `python3 -m tools.explog running` for concurrent locks. When no campaign worktree is named, create one with `python3 -m tools.worktree create NAME` from the primary checkout and continue from the printed path before interpreting repository-local work.
2. When opening a campaign, read the route-state map at the start of `HISTORY.md`, choose an authenticated transition and then read that transition and its linked primary artifacts. Establish the contemporary solver state, the causal question, several artifact-grounded mechanisms for the intended next state and the observable differences they predict.
3. Parallel automations widen the search by owning distinct transitions or causal questions. Within a campaign, use fresh-context subagents for distinct artifact relationships or constructions, giving them the selected contemporary state and primary artifacts. The main agent retains causal ownership and synthesizes their mechanisms.
4. Give the candidate mechanisms to a separate fresh-context archive reviewer. The reviewer reduces each mechanism to canonical object, operation and parameter cells, consults relevant cross-campaign constraints in `research/SETTLED.md`, searches the current experiment record with `python3 -m tools.explog "OBJECT OPERATION TERMS"` and opens relevant records with `python3 -m tools.explog show ID...`; it searches community messages with `python3 -m tools.dsearch "OBJECT OPERATION TERMS"` and opens relevant conversations with `python3 -m tools.dsearch show ID...`. It returns exact matches, broader experiments whose coverage contains those cells, result ids, tested assumptions and community evidence for each candidate. The main agent opens the returned covering records before reserving an operation.
5. Choose among the surviving mechanisms by artifact causality and by the state their ordinary outcomes recover or change. Archive coverage removes exact duplication and bounds the meaning of prior results. Before writing a custom instrument or starting sustained computation, add and commit a compact `running` claim naming the canonical object, exact operation and the decision its outcomes inform. Publish committed checkpoints with `python3 -m tools.worktree publish`.
6. Investigate through reasoning, reconstruction, emulation and coherent tests. Build the websites, services, requests, carriers, diagrams or small tools that make the mechanism concrete. Carry the causal question through related observations and pivots across scheduled runs. At each scheduled boundary, preserve the contemporary state, live mechanisms, observations and next discriminator; the next run resumes there. Close the campaign when it recovers intended state, answers its causal question for another campaign to consume or reaches an exact evidential blocker.

Build `discord.db` when the archive reviewer reports a missing or stale index.

## Work from the historical state

Use the software, protocols, cultural knowledge and network capabilities available to a capable 2012–2014 solver: Tor and onion services, OutGuess, OpenPGP, image and audio tools, emulation and contemporary cipher implementations. Modern computation may replay or accelerate an operation selected from that state.

Think with the artifacts. Reconstruct protocol exchanges, operate faithful local replicas, sketch dependencies, manipulate carriers and invent mechanisms from objects Cicada placed together. Earlier solves supply design language and demonstrated system roles.

A useful progression is:

```text
contemporary state -> causal mechanisms -> observable differences
-> construction or operation -> intended next state
```

Promote a result when artifact evidence selects its object, representation, consumer and operation. Run the cheapest alternatives and controls, then require an unused prediction. A selected cipher predicts plaintext beyond its fit. Coverage bounds apply to the exact recorded operation.

An evidential blocker names the unavailable evidence, shows which remaining discriminators require it and records what recovery would reopen the question.

## Coordinate and preserve memory

The automation conversation is the campaign's primary working memory. When durable recovery or coordination needs a repository checkpoint, keep a compact `STATE.md` in the active `research/attacks/<campaign>/` directory containing only the contemporary state and artifacts, causal question and live mechanisms, observations and implications, and next discriminator. Supporting detail and execution output belong in findings and gitignored `out/`.

`HISTORY.md` holds the complete route ledger. `research/SETTLED.md` holds constraints that affect several investigations. Explog stores current experiment results and exact operation locks; Dsearch retrieves community messages and selected surrounding conversations. Research retrieval uses these records and committed findings. Running claims may span scheduled runs under their owning automation, while other agents select unreserved operations.

Give a positive result to a fresh-context reviewer with its claim, evidence and archive tools. The reviewer returns prior art, post-selection, instrument and cheaper-alternative objections, the strongest supported interpretation and the best next test. The campaign owner incorporates the review.

Keep ordinary closures in Explog and attack findings. Add a conclusion to `research/SETTLED.md` when it constrains several future investigations. Update `HISTORY.md` when authenticated chronology or the preservation boundary changes.

Use local and publicly accessible sources. Keep authentication and credential entry outside the research workflow.

## Verification

```text
python3 -m lib.corpus
python3 -m unittest discover -s tests
ruff check lib tools tests
```

Use corpus objects through `lib.corpus`, rune arithmetic through `c.gp` / `lib.runes` / `lib.cipher`, and solved text through `solutions/`. Write Markdown prose as one physical line per semantic paragraph.
