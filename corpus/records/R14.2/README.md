# R14.2 — onion 2's growing payload and three-share composition

Onion 2 began with `<!--Patience is a virtue-->` above a bare hex string that grew one byte every few minutes for roughly 23 hours to 256 bytes. It later changed to `<!--761-->`, the Gematria sum of “Patience is a virtue,” above an approximately 3.6 MB hex dump. Hex decoding and bit inversion revealed three JPEGs, the third byte-reversed.

OutGuess at preserved seeds 163, 115 and 94 recovered page `0.0 A WARNING` and three valid [signed shares](artifacts/communications/). XORing the shares produced a signed ciphertext; inverted Gematria followed by columnar transposition read `GOOD WORK / ULTIMATE TRUTH IS THE ULTIMATE ILLUSION / JOIN US AT FV7LYUCMEOZZD5J4`.

The resulting `fv7lyucmeozzd5j4.onion`, page `0.0` and the growing introduction pass to [R14.3](../R14.3/). Onion 3 later grew a separate 256-byte payload of the same one-byte-at-a-time class. Neither payload has an established consumer, and the growth schedule survives through logs rather than authenticated timing data.
