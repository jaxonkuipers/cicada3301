# Cicada 3301 corpus and route

This directory is organized by route record. Each `records/Rxx.x/README.md` explains one transition or signed statement, and its `artifacts/` directory owns the preserved objects introduced there. Later records link back to those canonical objects.
Read this map, then open the one record needed for the current causal question.

Transition records state the solver's input state, consumed dependencies, action, resulting state, handoff, evidence and preservation boundary. Statement records preserve the context, signed statement, operational effect, evidence and preservation boundary.
Evidence is **authenticated** when preserved bytes verify with Cicada's OpenPGP key, **reproduced** when independent solver reconstruction established the operation and result, **reported** when an event survives through solver records, and **partial** when a transition combines established state with a missing or reported segment. Each record states which source bytes survive locally.
Cicada's fingerprint is `6D85 4CD7 9333 22A6 01C3 286D 181F 01E5 7A35 090F`; the repeatedly named short ID is `7A35090F`.

## Route-state map

| Route | Record | Result | Status |
| --- | --- | --- | --- |
| [R12.1](records/R12.1/) | `final.jpg` → Mabinogion subreddit | subreddit, book code, carriers and original dimensions | reproduced |
| [R12.2](records/R12.2/) | subreddit state → telephone | exact telephone number and verified key | reproduced |
| [R12.3](records/R12.3/) | telephone arithmetic → `845145127.com` | domain, carrier and signed time gate | reproduced |
| [R12.4](records/R12.4/) | timed domain → posters → enrollment | private enrollment state and numbered poster families | reproduced |
| [R12.5](records/R12.5/) | individualized RSA → MIDI → signed return | partial recipient return and selection state | partial |
| [R12.6](records/R12.6/) | poster identifiers → reported `.tk` branch | parallel enrollment endpoint; recipient result missing | reported |
| [R12.7](records/R12.7/) | signed close of the first public round | selection asserted; private recipient state missing | authenticated |
| [R12.8](records/R12.8/) | signed Necrome-attribution denial | authenticated identity and conduct boundary | authenticated |
| [R13.1](records/R13.1/) | opening image → Cicada OS | ISO, audio, data files and Twitter handle | reproduced |
| [R13.2](records/R13.2/) | ISO/audio/Twitter → Gematria Primus | rune system and authored `DIVINITY` wording | reproduced |
| [R13.3](records/R13.3/) | rune-table carrier → first onion | interactive Tor text service | reproduced |
| [R13.4](records/R13.4/) | onion service → ICMP pointer | coordinate-stage onion | reproduced |
| [R13.5](records/R13.5/) | posters/telephones → Shamir endpoint | registration and assessment state | partial |
| [R13.6](records/R13.6/) | assessment → solver-operated service | private receiver; callback state missing | partial |
| [R14.1](records/R14.1/) | opening image → Emerson → RSA | onion 2 and retained earlier-round state | reproduced |
| [R14.2](records/R14.2/) | growing payload → three XOR shares | onion 3 and first introduction page | reproduced |
| [R14.3](records/R14.3/) | 1033 square + `DIVINITY` → onion 4 | square, welcome pages and accumulated introduction | reproduced |
| [R14.4](records/R14.4/) | koan + route grid → onion 5 | instruction pages and residual grid state | reproduced |
| [R14.5](records/R14.5/) | Interconnectedness + GEB → onion 6 | three magic squares and onion 6 | reproduced |
| [R14.6](records/R14.6/) | square submission → private callback | complete introduction, locator and missing recipient state | partial |
| [R14.7](records/R14.7/) | shared onion → Liber Primus | complete public book; intended operation unresolved | reproduced |
| [R15.1](records/R15.1/) | signed illegal-attribution denial | authenticated identity and conduct boundary | authenticated |
| [R16.1](records/R16.1/) | signed direction to Liber Primus | words, meaning and numbers assigned authored roles | authenticated |
| [R17.1](records/R17.1/) | signed false-path warning | OpenPGP remains the provenance boundary | authenticated |

The machine-readable graph is [`route.csv`](route.csv).
Its `kind` column distinguishes transitions from signed statements. Its `predecessor` column records the primary route edge. Each transition record's dependency field records every cross-route input.
Observed communication order, signer-asserted time and the route that introduced each message are indexed in [`communications.csv`](communications.csv).

## Current public state

The authenticated route continues through R17.1. R14.7 is its latest public puzzle-artifact delivery.
A successful R14.6 solver possessed recipient state outside the surviving public corpus.
Liber Primus is the complete unresolved public delivery. The authenticated R16.1 message explicitly names it as the way; feature and operation selection remain open.

## Layout

| Path | Historical role |
| --- | --- |
| [`records/`](records/) | route records and the artifacts and source records they own |
| [`identity/`](identity/) | Cicada's OpenPGP identity material |
| [`route.csv`](route.csv) | machine-readable route graph, record kind and evidence status |
| [`communications.csv`](communications.csv) | observed and signer-asserted chronology of preserved messages |

Immutable files under `records/*/artifacts/`, `records/*/sources/` and `identity/` are pinned by [`MANIFEST.sha256`](MANIFEST.sha256). Verify them with `python3 -m solver.corpus_manifest verify`. A deliberate evidence-byte change is recorded with `python3 -m solver.corpus_manifest update` and reviewed with its provenance change.

The R14 records follow Cicada's release order.
Cicada published the images in order; community assembly supplies the `intro-00`–`intro-16` labels.
Each record's preservation boundary records the surviving original images, audio, live services and individualized material.
Attribution follows the evidence and signature status stated in that record.
Historical domains and onion addresses identify route objects; responses from modern hosts carry modern provenance.

Retrospective Liber Primus discussion from 13 community channels spanning 2019–2026 is searchable in [`../discord.db`](../discord.db). Campaign findings hold new reconstruction and experiment results.
