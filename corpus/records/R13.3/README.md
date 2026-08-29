# R13.3 — Gematria scan to the first onion

Applying OutGuess to R13.2's Gematria Primus JPEG returned a valid [signed message](artifacts/communications/2013-01-rune-table-morse.asc) whose visible body was whitespace. Decoding its tabs and spaces as binary read `Come to emiwp4muu2ktwknf.onion / We shall await you there. / Good luck. / 3301`.

`emiwp4muu2ktwknf.onion` displayed “Web browsers are useless here” and exposed an interactive text service over Tor, which passes to [R13.4](../R13.4/). OpenPGP clear-sign canonicalization strips trailing whitespace, so the signature authenticates the surrounding object while the 558-character whitespace payload rests on contemporary reconstruction. The original HTTP headers and service binaries are unavailable.
