# R13.4 — interactive onion, retained ISO state and ICMP transport

**Solver state.** A contemporary solver had the ISO files, Gematria table and Tor text service. Commands included `help`, integer factorization, `primes`, `count`, `hello` and `hint`/`clue`.

**Dependencies consumed.** R13.3 supplies the interactive onion service; R13.1 supplies retained ISO file `_560.00`; R13.2 supplies the Gematria table.

**Artifact and action.** `hello` returned a hex-dumped signed message routing to `xsxnaksict6egxkq.onion`. `hint`/`clue`, XORed with ISO file `_560.00`, read `You can't see the forest when you're looking at the trees.` The service's `count` acted as a Gematria oracle; its prime list deliberately omitted primes 73 through 1223. Onion 2 first said “Patience is a virtue,” then the signed message “You already have everything you need to continue. Sometimes one must knock on the sky and listen to the sound.”

Solvers identified the onion backend and inspected ICMP echo replies. Interleaved packets with sequence number 1 carried a repeating hex stream; concatenating it, decoding hex and gunzipping `message.txt.asc` produced a valid signed pointer to `pklmx2eeh6fjt7zf.onion`.

**Resulting state.** The third onion instructed solvers to stand by for coordinates.

**State handed forward.** The coordinate-stage onion and retained ISO/Gematria state pass to R13.5.

**Evidence.** The authenticated route messages are [`telnet hello`](artifacts/communications/2013-01-telnet-hello.asc), [`knock on the sky`](artifacts/communications/2013-01-knock-on-the-sky.asc) and [`onion pointer`](artifacts/communications/2013-01-onion-pointer.asc).

**Later evidence.** This route combined Tor, a text protocol, ICMP payload capture and retained ISO state.

**Preservation boundary.** The historical account derived a clearnet backend from an error response; intent of that leak is unknown. Modern hosts or addresses are not route evidence.
