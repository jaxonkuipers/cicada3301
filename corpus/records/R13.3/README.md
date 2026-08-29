# R13.3 — Gematria scan to the first onion

**Solver state.** The solver held the recovered rune-table JPEG and knew OutGuess from prior authenticated routes.

**Dependencies consumed.** R13.2 supplies the recovered Gematria Primus JPEG; R12.1 establishes OutGuess as an authored carrier operation.

**Artifact and action.** OutGuess returned a valid signed message whose apparent body was whitespace. Tabs and spaces decoded as binary to `Come to emiwp4muu2ktwknf.onion / We shall await you there. / Good luck. / 3301`.

**Resulting state.** `emiwp4muu2ktwknf.onion` displayed “Web browsers are useless here” and exposed an interactive text service over Tor.

**State handed forward.** The first interactive onion service passes to R13.4.

**Evidence.** The signed carrier is [`2013-01-rune-table-morse.asc`](artifacts/communications/2013-01-rune-table-morse.asc).

**Later evidence.** OpenPGP clear-sign canonicalization strips trailing whitespace, so the signature authenticates the surrounding clear-signed object but does not cryptographically bind the 558-character whitespace payload. The route is nevertheless preserved by contemporary reconstruction.

**Preservation boundary.** Original HTTP headers and service binaries are not preserved.
