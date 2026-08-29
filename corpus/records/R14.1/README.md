# R14.1 — opening image, Emerson and an RSA carrier

**Solver state.** On 6 January 2014, Twitter status `420087183957966849` linked `http://i.imgur.com/zN4h51m.jpg`.

**Dependencies consumed.** None from a prior route is required for the opening solve. It reuses public OutGuess and RSA-OAEP operations demonstrated in earlier rounds.

**Artifact and action.** OutGuess produced a valid signed riddle and four-part book code. “The work of a private man / who wished to transcend / He trusted himself / to produce from within” selected Ralph Waldo Emerson's *Self-Reliance*; paragraph, sentence, word and letter addressing yielded `auqgnxjtvdbll3pv.onion`.

Onion 1's title was `For Every Thing That Lives Is Holy` and it served `1033.jpg`, a Blake collage. OutGuess exposed a valid signed `Crypt::RSA::ES::OAEP` carrier with `e=65537` and a 432-bit modulus. Factoring and decrypting yielded `cu343l33nqaekrnw.onion`.

**Resulting state.** The solver arrived at onion 2 with the 2013 ISO, Gematria table, poem and prior route knowledge still historically available.

**State handed forward.** Onion 2 passes to R14.2 while the 2013 ISO, Gematria table, poem and prior route knowledge remain available.

**Evidence.** The signed carriers are [`opening book code`](artifacts/communications/2014-01-opening-book-code.asc) and [`RSA challenge`](artifacts/communications/2014-01-rsa-oaep-challenge.asc).

**Later evidence.** Onion 1's title has Gematria sum 1033, matching the filename. The verified relation covers this title and filename.

**Preservation boundary.** No private state was introduced at this transition; the route was public.
