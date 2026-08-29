# R14.1 — opening image, Emerson and an RSA carrier

On 6 January 2014, Twitter status `420087183957966849` linked `http://i.imgur.com/zN4h51m.jpg`. OutGuess produced a valid [signed riddle and four-part book code](artifacts/communications/2014-01-opening-book-code.asc). “The work of a private man / who wished to transcend / He trusted himself / to produce from within” selected Ralph Waldo Emerson's *Self-Reliance*; paragraph, sentence, word and letter addressing yielded `auqgnxjtvdbll3pv.onion`.

Onion 1, titled `For Every Thing That Lives Is Holy`, served `1033.jpg`, a Blake collage. OutGuess exposed a signed [`Crypt::RSA::ES::OAEP` challenge](artifacts/communications/2014-01-rsa-oaep-challenge.asc) with `e=65537` and a 432-bit modulus. Factoring and decrypting it yielded `cu343l33nqaekrnw.onion`. The title's Gematria sum is 1033, matching the filename.

Onion 2 passes to [R14.2](../R14.2/). The 2013 ISO, Gematria table, Instar poem and earlier route knowledge remained historically available; this public transition introduced no private state.
