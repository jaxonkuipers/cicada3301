# R13.2 — ISO, audio and Twitter to Gematria Primus

**Solver state.** The solver held the complete ISO, `761.MP3`, the handle `@1231507051321`, and the instruction that the key was “all around you.” The MP3's ID3 title was `The Instar Emergence`, artist `3301`; appended bytes contained `Parable 1,595,277,641` and the poem “Like the instar, tunneling to the surface / We must shed our own circumferences; / Find the divinity within and emerge.”

**Dependencies consumed.** R13.1 supplies the bootable ISO, exact `761.MP3` bytes, Twitter handle and instruction that the key was all around the solver.

**Artifact and action.** The Twitter account emitted offset-labelled 65-byte hex blocks. Reassembling them by offset produced a byte stream; XOR with the exact `761.MP3` bytes yielded the Gematria Primus rune-table JPEG.

**Resulting state.** The solver held a 29-row rune alphabet, transliterations, values and prime ordering: [`artifacts/gematria-primus/`](artifacts/gematria-primus/).

**State handed forward.** The Gematria Primus table passes to R13.3 and later routes; the authored `DIVINITY` wording remains available for R14.3.

**Evidence.** The reconstructed scan and machine-readable table are under [`artifacts/gematria-primus/`](artifacts/gematria-primus/). The scan prints `U`; the machine table's U/V alias is a transcription convention.

**Later evidence.** The poem's three line sums are 1259, 1031 and 1229, and their product is the printed parable number. `DIVINITY` later becomes the historically selected key at R14.3.

**Preservation boundary.** The original Twitter service state and every timing observation are not canonical inputs; the reconstructed byte stream and scan are preserved.
