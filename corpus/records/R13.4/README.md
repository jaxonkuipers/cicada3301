# R13.4 — interactive onion, retained ISO state and ICMP transport

The R13.3 Tor text service accepted commands including `help`, integer factorization, `primes`, `count`, `hello` and `hint`/`clue`. `hello` returned a hex-dumped [signed message](artifacts/communications/2013-01-telnet-hello.asc) routing to `xsxnaksict6egxkq.onion`. XORing `hint`/`clue` with R13.1's `_560.00` read `You can't see the forest when you're looking at the trees.` The service's `count` acted as a Gematria oracle, and its prime list omitted primes 73 through 1223.

Onion 2 first said “Patience is a virtue,” then served the signed instruction [“Sometimes one must knock on the sky and listen to the sound”](artifacts/communications/2013-01-knock-on-the-sky.asc). Solvers identified its backend and inspected ICMP echo replies. Interleaved sequence-1 packets carried a repeating hex stream; concatenating, hex-decoding and gunzipping `message.txt.asc` produced a valid [signed pointer](artifacts/communications/2013-01-onion-pointer.asc) to `pklmx2eeh6fjt7zf.onion`.

The third onion instructed solvers to await coordinates, passing the route and retained ISO/Gematria state to [R13.5](../R13.5/). A historical error response exposed a clearnet backend, but its intent is unknown; modern behavior at those addresses is unrelated to the historical route.
