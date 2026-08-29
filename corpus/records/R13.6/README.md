# R13.6 — assessment to solver-operated return service

**Solver state.** A successful individual had a fresh email/key, identification state and answers accepted by the timed test.

**Dependencies consumed.** R13.5 supplies accepted assessment state, a fresh email and key, and the solver identification path.

**Artifact and action.** Recipient-preserved reconstructions describe a Cicada-signed instruction requiring each solver to write a TCP server alone, expose it as a Tor hidden service and send the onion address and port by GPG-encrypted email. The line protocol required `WELCOME`, `RAND`, `QUINE`, `BASE29`, `CODE`, `KOAN`, Diffie–Hellman, `NEXT` and `GOODBYE`. Crucially, `NEXT` made the solver's server acknowledge and record arbitrary text sent by Cicada's client.

**Resulting state.** The solver, not Cicada, operated the next-stage receiver. An unsigned reported server log contains `NEXT` around a signed-looking recruitment letter, but no authenticated callback packet survives.

**State handed forward.** A solver-operated hidden-service receiver and its unavailable callback state form the surviving boundary of the 2013 private route.

**Evidence.** The instruction's line protocol and reported signature status survive through recipient reconstruction; its exact signed bytes are absent locally. A [December 2013 mirror pinned to its original Gist revision](https://gist.github.com/navinpai/7837596/98b383923095465ba02432ffc6be06c4a877b2b9) preserves the command grammar as a contemporary secondary source; its [provenance record](sources/tcp-server-mirror.md) records the immutable source URLs and hashes. The callback body survives through an unauthenticated reported server log.

**Later evidence.** Recipient-operated hidden services recur in 2014 with an HTTP upload callback, but the protocols and retained state differ.

**Preservation boundary.** The exact signed instruction, authenticated 2013 callback body, recipient binding, complete service log and downstream private route are absent from the local corpus. The public route vanished and the Twitter account later became `@1231507051321_`; that fact does not recover the missing `NEXT` payload.
