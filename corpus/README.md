# Cicada 3301 corpus and route

This directory keeps preserved puzzle artifacts beside the route reconstruction that explains when each object entered solver state.
Read this map, then open only the linked step needed for the current causal question.

Each step records solver state, dependencies consumed, artifact and action, resulting state, state handed forward, evidence, later evidence and the preservation boundary.
Evidence is **authenticated** when preserved bytes verify with Cicada's OpenPGP key, **reproduced** when independent solver reconstruction established the operation and result, **reported** when an event survives through solver records, and **partial** when a transition combines established state with a missing or reported segment. Each step states which source bytes survive locally.
Cicada's fingerprint is `6D85 4CD7 9333 22A6 01C3 286D 181F 01E5 7A35 090F`; the repeatedly named short ID is `7A35090F`.

## Route-state map

| Route | Transition | State handed forward | Status |
| --- | --- | --- | --- |
| [R12.1](steps/R12.1-final-to-mabinogion-subreddit.md) | `final.jpg` → Mabinogion subreddit | subreddit, book code, carriers and original dimensions | reproduced |
| [R12.2](steps/R12.2-subreddit-to-telephone.md) | subreddit state → telephone | exact telephone number and verified key | reproduced |
| [R12.3](steps/R12.3-telephone-to-845145127.md) | telephone arithmetic → `845145127.com` | domain, carrier and signed time gate | reproduced |
| [R12.4](steps/R12.4-domain-to-primary-enrollment.md) | timed domain → posters → enrollment | private enrollment state and numbered poster families | reproduced |
| [R12.5](steps/R12.5-individualized-rsa-and-midi.md) | individualized RSA → MIDI → signed return | partial recipient return and selection state | partial |
| [R12.6](steps/R12.6-second-chance-route.md) | poster identifiers → reported `.tk` branch | parallel enrollment endpoint; recipient result missing | reported |
| [R12.7](steps/R12.7-public-close.md) | signed close of the first public round | selection asserted; private recipient state missing | authenticated |
| [R12.8](steps/R12.8-necrome-denial.md) | signed Necrome-attribution denial | authenticated identity and conduct boundary | authenticated |
| [R13.1](steps/R13.1-opening-to-cicada-os.md) | opening image → Cicada OS | ISO, audio, data files and Twitter handle | reproduced |
| [R13.2](steps/R13.2-iso-to-gematria-primus.md) | ISO/audio/Twitter → Gematria Primus | rune system and authored `DIVINITY` wording | reproduced |
| [R13.3](steps/R13.3-gematria-to-first-onion.md) | rune-table carrier → first onion | interactive Tor text service | reproduced |
| [R13.4](steps/R13.4-interactive-onion-and-icmp.md) | onion service → ICMP pointer | coordinate-stage onion | reproduced |
| [R13.5](steps/R13.5-posters-to-shamir-routing.md) | posters/telephones → Shamir endpoint | registration and assessment state | partial |
| [R13.6](steps/R13.6-assessment-to-return-service.md) | assessment → solver-operated service | private receiver; callback state missing | partial |
| [R14.1](steps/R14.1-opening-to-rsa-carrier.md) | opening image → Emerson → RSA | onion 2 and retained earlier-round state | reproduced |
| [R14.2](steps/R14.2-growing-payload-and-xor-shares.md) | growing payload → three XOR shares | onion 3 and first introduction page | reproduced |
| [R14.3](steps/R14.3-1033-square-and-divinity.md) | 1033 square + `DIVINITY` → onion 4 | square, welcome pages and accumulated introduction | reproduced |
| [R14.4](steps/R14.4-koan-and-route-grid.md) | koan + route grid → onion 5 | instruction pages and residual grid state | reproduced |
| [R14.5](steps/R14.5-interconnectedness-and-geb.md) | Interconnectedness + GEB → onion 6 | three magic squares and onion 6 | reproduced |
| [R14.6](steps/R14.6-square-submission-and-callback.md) | square submission → private callback | complete introduction, locator and missing recipient state | partial |
| [R14.7](steps/R14.7-liber-primus-delivery.md) | shared onion → Liber Primus | complete public book; intended operation unresolved | reproduced |
| [R15.1](steps/R15.1-illegal-attribution-denial.md) | signed illegal-attribution denial | authenticated identity and conduct boundary | authenticated |
| [R16.1](steps/R16.1-liber-primus-direction.md) | signed direction to Liber Primus | words, meaning and numbers assigned authored roles | authenticated |
| [R17.1](steps/R17.1-authentication-warning.md) | signed false-path warning | OpenPGP remains the provenance boundary | authenticated |

The machine-readable graph is [`route.csv`](route.csv).
Its `predecessor` column records the primary state edge; each step's dependency field records every cross-route input.
Observed communication order, signer-asserted time and the route that introduced each message are indexed in [`communications.csv`](communications.csv).

## Current public state

The authenticated route continues through R17.1. R14.7 is its latest public puzzle-artifact delivery.
A successful R14.6 solver possessed recipient state outside the surviving public corpus.
Liber Primus is the complete unresolved public delivery. The authenticated R16.1 message explicitly names it as the way; feature and operation selection remain open.

## Preserved artifacts

| Path | Historical role |
| --- | --- |
| [`2012/`](2012/) | first recruitment puzzle, including the accepted Mabinogion source |
| [`2013/`](2013/) | second puzzle and the original Gematria Primus table |
| [`2014/`](2014/) | third puzzle and Liber Primus |
| [`2015/`](2015/), [`2016/`](2016/), [`2017/`](2017/) | later authenticated communications |
| [`identity/`](identity/) | Cicada's OpenPGP identity material |

The R14 steps follow Cicada's release order.
Cicada published the images in order; community assembly supplies the `intro-00`–`intro-16` labels.
Each step's preservation boundary records the surviving original images, audio, live services and individualized material.
Attribution follows the evidence and signature status stated in that step.
Historical domains and onion addresses identify route objects; responses from modern hosts carry modern provenance.

Retrospective Liber Primus discussion from 13 community channels spanning 2019–2026 is searchable in [`../discord.db`](../discord.db). Campaign findings hold new reconstruction and experiment results.
