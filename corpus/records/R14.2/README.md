# R14.2 — onion 2's growing payload and three-share composition

**Solver state.** Onion 2 began with `<!--Patience is a virtue-->` above a bare hex string that grew one byte every few minutes for roughly 23 hours to 256 bytes.

**Dependencies consumed.** R14.1 supplies onion 2; R12.1 establishes OutGuess as an authored carrier operation; R13.2 supplies Gematria Primus.

**Artifact and action.** The page later changed to `<!--761-->`—the Gematria sum of “Patience is a virtue”—above an approximately 3.6 MB hex dump. Hex decoding and bit inversion revealed three JPEGs, the third byte-reversed. OutGuess on the images, at preserved seeds 163, 115 and 94, recovered page `0.0 A WARNING` and three valid signed shares. XORing the shares produced a signed ciphertext; inverted Gematria followed by columnar transposition read `GOOD WORK / ULTIMATE TRUTH IS THE ULTIMATE ILLUSION / JOIN US AT FV7LYUCMEOZZD5J4`.

**Resulting state.** The resulting address was `fv7lyucmeozzd5j4.onion`.

**State handed forward.** Onion 3, page `0.0 A WARNING` and the accumulated introduction state pass to R14.3; both 256-byte growing payloads remain unassigned.

**Evidence.** The three signed shares and reconstructed signed ciphertext are indexed as communication records 21–24 in [`corpus/communications.csv`](../../communications.csv).

**Later evidence.** This stage composed representation changes, multiple carriers and authenticated shares before yielding a locator. Onion 3 later grew a distinct bare 256-byte payload in the same one-byte-at-a-time object class; neither payload has an established operational role.

**Preservation boundary.** The growth timing survives through logs rather than an authenticated schedule. It does not establish that timing encodes another payload.
