# Cicada 3301 operational history

This ledger reconstructs the authenticated Cicada 3301 route from the state available to a capable contemporary solver. Each transition records the solver state, Cicada artifact, demonstrated action, resulting state, surviving evidence, later evidence and preservation boundary. Exact signed blocks, book codes and retained objects live in the linked corpus.

`Solver state` lists information available before the transition. `Artifact and action` records the historical carrier and reproduced solve. `Resulting state` records what the solver obtained. `Evidence` points to preserved bytes and reproducible work. `Later evidence` adds dated retrospective information. `Preservation boundary` states the surviving scope.

Evidence carries three provenance levels: **authenticated** bytes verify with Cicada's OpenPGP key; **reproduced** operations rerun from preserved bytes; **reported** events survive through contemporary solver records. Cicada's public key fingerprint is `6D85 4CD7 9333 22A6 01C3 286D 181F 01E5 7A35 090F`; the short ID repeatedly named by Cicada is `7A35090F`. Key material is under [`corpus/identity/`](corpus/identity/), and observed order versus signer-asserted signature time is indexed in [`corpus/communications.csv`](corpus/communications.csv).

Historical domains and onion addresses identify route objects. Modern responses carry modern provenance.

## Route-state map

| Route | Contemporary transition | Historical result | Preservation | State still open |
| --- | --- | --- | --- | --- |
| R12.1–R12.4 | `final.jpg` → subreddit → telephone → `845145127.com` → physical posters → enrollment onion | reproduced public route | strong carriers and signed instructions; some web and telephone bytes lost | physical-carrier custody and server state |
| R12.5 | individualized RSA → MIDI → signed solver return | RSA and MIDI operations reproduced; subsequent assessment reported | one RSA instance and MIDI survive; recipient correspondence is partial | private assessment state and selection outcome |
| R12.6 | whitespace identifiers → reported second-chance onion | reported route | signed identifier carrier survives; server exchange is partial | exact eligibility and recipient result |
| R13.1–R13.4 | opening image → Cicada OS → audio/Twitter → Gematria Primus → interactive onion/ICMP | reproduced public operations | primary carriers and signed instructions are substantial; live services are gone | retained machine and service state |
| R13.5 | posters/telephones → data slices → Shamir routing | partly reproduced and contemporaneously reported | public artifacts are partial | complete distributed payload and recipient state |
| R13.6 | assessment → solver-operated Tor return service | authenticated recipient operation | signed instruction survives | Cicada callback and resulting private state |
| R14.1–R14.5 | opening image → RSA/onion chain → growing payloads → shares, squares, grids and book code | public route substantially reproduced | carriers and contemporary records preserve the operations; live onion state is gone | transient server behavior where bytes were never captured |
| R14.6 | magic-square submission → recipient-operated callback service | authenticated operation and reported success path | form, square artifacts and callback instruction survive | successful submission response and callback state |
| R14.7 | shared onion delivery → Liber Primus | common delivery reproduced | complete public image set and signed locator survive | intended consumer, operation and resulting state |
| R15.1 | signed denial | authenticated communication | exact signed bytes | — |
| R16.1 | signed direction to Liber Primus | authenticated communication | exact signed bytes | operational meaning of words, meaning and numbers |
| R17.1 | signed provenance warning | authenticated communication | exact signed bytes | — |

## 2012 — public trail to individualized selection

### R12.1 — `final.jpg` to the Mabinogion subreddit

**Solver state.** A 509×503 JPEG named `final.jpg`, preserved as `1CcV1.jpg`, displayed the invitation beginning “Hello. We are looking for highly intelligent individuals” and said a message was hidden in the image. One archived trace places a carrier copy on 4chan `/b/` thread `372100808` at `2012-01-04 16:28:15`; this is the earliest preserved posting instance.

**Artifact and action.** The JPEG's appended text ended with `TIBERIVS CLAVDIVS CAESAR says "lxxt>33m2mqkyv2gsq3q=w]O2ntk"`. A Caesar shift of four produced `http://i.imgur.com/m9sYK.jpg`; that duck decoy said “Looks like you can't guess how to get the message out,” selecting OutGuess. `outguess -r 1CcV1.jpg` returned a 76-entry book code and `http://www.reddit.com/r/a2e7j6ic78h0j/`. The decoy itself had no useful OutGuess payload.

**Resulting state.** The solver held the subreddit, its ciphertext text, the 76 coordinates and two images: `KXLOP.jpg` (“Welcome”) and `8D7hN.jpg` (“Problems?”).

**Evidence.** The accepted source text is under [`corpus/2012/mabinogion/`](corpus/2012/mabinogion/); the signed route messages are under [`corpus/2012/communications/`](corpus/2012/communications/).

**Later evidence.** The 509 and 503 dimensions were deliberately reused at R12.3. The moderator names `CageThrottleUs` and `ImagoOnNib` are anagrams of Charlotte Guest and Mabinogion, respectively.

**Preservation boundary.** Preservation begins with the known `/b/` instance. The first upload, additional board threads and complete contemporary custody chain remain unavailable.

### R12.2 — subreddit state to the telephone number

**Solver state.** The solver held the subreddit, the OutGuess book code, ciphertext posts, the full subreddit name `a2e7j6ic78h0j7eiejd0120`, its header symbols and the two images.

**Artifact and action.** OutGuess on `KXLOP.jpg` produced Cicada's signed key announcement: future messages would use key `7A35090F`. OutGuess on `8D7hN.jpg` produced the signed instruction “The key has always been right in front of your eyes.” The hexadecimal full subreddit name and header encode the repeating shifts `10,2,14,7,19,6,18,12,7,8,17,0,19,7,14,18,14,19,13,0,1,2,0`; applying them to the subreddit text recovered Charlotte Guest's *Mabinogion*. Addressing that text with the original 76-entry book code, with full stops omitted, read `CALL US AT US TELEPHONE NUMBER TWO ONE FOUR THREE NINE OH NINE SIX OH EIGHT`.

**Resulting state.** The exact telephone number was `(214) 390-9608`, or `+1 214-390-9608`.

**Evidence.** The accepted source text lives under [`corpus/2012/mabinogion/`](corpus/2012/mabinogion/); the two signed instructions are [`key announcement`](corpus/2012/communications/2012-01-key-announcement.asc) and [`key in front of you`](corpus/2012/communications/2012-01-key-in-front-of-you.asc).

**Later evidence.** Later routes repeat three roles demonstrated here: visible objects select tools, names select sources and solved readouts direct external actions.

**Preservation boundary.** The live subreddit layout no longer provides its exact 2012 browsing context; the accepted plaintext and operations are preserved independently.

### R12.3 — telephone instruction to `845145127.com`

**Solver state.** The solver could call `(214) 390-9608` and still possessed the original 509×503 JPEG.

**Artifact and action.** The recording said: “There are three prime numbers associated with the original final.jpg image. 3301 is one of them. You will have to find the other two. Multiply all three of these numbers together and add a .com to find the next step.” Both image dimensions are prime, so `509 × 503 × 3301 = 845145127`.

**Resulting state.** The exact destination was `http://845145127.com/`. It served `cicada.jpg`; OutGuess on that image returned a signed “Patience is a virtue” message instructing solvers to return at `17:00 UTC, Monday 9 January 2012`.

**Evidence.** The signed time gate is [`2012-01-patience-check-back.asc`](corpus/2012/communications/2012-01-patience-check-back.asc). The literal phone instruction and carrier dimensions fix the arithmetic domain derivation.

**Later evidence.** Cicada explicitly named the `.com` construction and the original carrier supplied the two missing operands. This establishes the historical reason to derive and visit `845145127.com`.

**Preservation boundary.** The telephone service is gone and no authoritative original recording file is in the canonical corpus; surviving recordings and transcriptions agree on the operational instruction.

### R12.4 — timed domain, physical carriers and primary enrollment

**Solver state.** At the appointed time the solver held `845145127.com`, `cicada.jpg`, the verified signing key and the previous book-source precedent.

**Artifact and action.** The domain published “Find our symbol at the location nearest you” and fourteen coordinates. Reapplying OutGuess to `cicada.jpg` exposed a signed subset of twelve coordinates, authenticating the physical-posting instruction. The public list was: `52.216802,21.018334`; `48.85057059876962,2.406892329454422`; `48.85030144151387,2.407538741827011`; `47.664196,-122.313301`; `47.637520,-122.346277`; `47.622993,-122.312576`; `37.577070,126.813122`; `37.5196666666667,126.995`; `36.0665472222222,-94.1726416666667`; `33.966808,-117.650488`; `29.909098706850486,-89.99312818050384`; `25.684702,-80.441289`; `21.584069,-158.104211`; `-33.90281,151.18421`.

**Artifact and action.** Recovered posters in Warsaw, Paris, Miami, Arkansas and Sydney carried QR codes to numbered JPEGs on `845145127.com`. OutGuess produced two signed 22-position book codes. “A poem of fading death, named for a king / Meant to be read only once and vanish” selected William Gibson's *Agrippa* and resolved exactly to `sq6wmgv2zcsrix6t.onion`. “In twenty-nine volumes, knowledge was once contained” is commonly associated with the Britannica `CICADA` article; the preserved source resolves 18 of 22 positions and leaves its exact edition open.

**Resulting state.** `sq6wmgv2zcsrix6t.onion/cgi-bin/get_email` displayed a signed enrollment form. It instructed the solver to create a never-used public webmail address while using Tor, submit it, wait for a number, then revisit the same onion at `/<number>`; the example number was `3894894230934209`.

**Evidence.** The exact signed coordinate, book-code and enrollment messages are [`coordinates`](corpus/2012/communications/2012-01-coordinates.asc), [`Agrippa route`](corpus/2012/communications/2012-01-book-code-poem.asc), [`twenty-nine volumes route`](corpus/2012/communications/2012-01-twenty-nine-volumes-book-code.asc) and [`enrollment`](corpus/2012/communications/2012-01-anonymous-email-enrollment.asc).

**Later evidence.** Ten numbered carrier identifiers survive in the later signed whitespace release: `162667212858`, `316744223127`, `414974253863`, `427566844663`, `598852142735`, `889296759263` for the twenty-nine-volumes family and `644169769482`, `876873892385`, `935691396441`, `963846244281` for the *Agrippa* family. Those identifiers later participate in the reported second-chance route at R12.6.

**Preservation boundary.** Not all fourteen physical carriers were recovered or photographed. The Britannica source and four missing characters are unresolved. Original server bytes, enrollment database state and proof that every submission was accepted are absent.

### R12.5 — individualized RSA, MIDI and signed solver return

**Solver state.** An enrolled solver possessed a fresh email address, a received number and a private same-URL path on the enrollment onion.

**Artifact and action.** A surviving authenticated page said it would display once and supplied a unique low-bit RSA modulus and unique `Crypt::RSA` 1.99 OAEP ciphertext to each solver. The preserved instance used `e=65537`, a 372-bit modulus and four 47-byte ciphertext blocks. Factoring the modulus and reproducing the legacy OAEP convention yields the exact 20-digit plaintext `33521494043430258676`; the solver returned that value to the same URL. A correct response reportedly produced “Correct. We'll email you.” Sharing individualized material triggered the authenticated removal message in [`2012-01-sharing-disqualification.asc`](corpus/2012/communications/2012-01-sharing-disqualification.asc).

**Resulting state.** The next preserved stage is a signed and encrypted MIDI carrier. Its first track's notes and delta times supplied the alphabet that decoded the instruction: create a GPG key for the solver's email; upload it to the MIT keyservers; encrypt a supplied word list to Cicada's public key; sign it with the solver's key; send the ASCII-armored ciphertext to the Gmail address from which the numbers arrived. The second track used the Blake chorus printed in the accompanying message as its known answer.

**Evidence.** The surviving carrier measurements and decoded instructions are recorded in this transition; authenticated messages surrounding the stage are under [`corpus/2012/communications/`](corpus/2012/communications/).

**Later evidence.** Cicada used recipient-specific ciphertext, one-display callback state, a solver-generated public key, solver signatures, encrypted email and explicit anti-collaboration enforcement in 2012. These roles define the demonstrated 2012 system design.

**Preservation boundary.** The exact post-MIDI return packet, recipient mailbox, server implementation and private reply after the signed word-list submission do not survive. A leaked February recruitment letter describes Cicada's stated beliefs and organization, but its public paste is unauthenticated and cannot supply route state. The public round closed with the signed `Valēte!` message on 6 February.

### R12.6 — reported second-chance route

**Solver state.** The individualized RSA instruction itself said: `There is a second chance to get your own RSA message and key. Follow the "Numbers dot TK" hint to find it.` Separately, `845145127.com` became a whitespace-only page whose tabs and spaces decoded to a valid signed list of the ten numbered JPEG identifiers from R12.4.

**Artifact and action.** A close-time solver account grouped the ten identifiers by their two signed book-code families, selected each group's maximum and added them: `889296759263 + 963846244281 = 1853143003544`. It reports visiting `1853143003544.tk`, reading DNS TXT `Go to my largest part`, factoring `1853143003544 = 2 × 2 × 2 × 7 × 33091839349`, and visiting `33091839349.tk`. That site served `NHYLD.jpg`, an image of Waterhouse's *The Lady of Shalott*; OutGuess exposed Cicada's valid signed “Miss round 1? Care for a second chance?” message, the exact image URL `http://i.imgur.com/hkdgl.png`, and 22 coordinates. Blake's *Marriage of Heaven and Hell*, plate 4, resolved the coordinates to `cginiziglyaobyph.onion`.

**Resulting state.** The reported onion mirrored anonymous email enrollment and was intended to issue another individualized RSA message and key.

**Evidence.** The whitespace number list is [`2012-01-location-numbers.asc`](corpus/2012/communications/2012-01-location-numbers.asc); the authenticated Blake carrier is [`2012-01-second-chance.asc`](corpus/2012/communications/2012-01-second-chance.asc).

**Later evidence.** The signed selector and signed Blake endpoint bracket a `.tk` middle preserved through contemporary testimony. The Blake carrier supplies the second-chance book code; the individualized RSA carrier belongs to R12.5.

**Preservation boundary.** Cicada's signatures cover the numbered list and Blake carrier. Contemporary testimony supplies the grouping rule, `.tk` domains, DNS TXT record, `NHYLD.jpg`, onion wrapper and enrollment account. The primary numbered domain is `845145127.com`.

## 2013 — operating system, rune system, distributed routing and solver services

### R13.1 — opening image to Cicada OS

**Solver state.** On 4–5 January 2013, `232.jpg`, preserved as `gqvvmk.jpg`, appeared in multiple 4chan `/b/` and `/x/` threads with “Hello again” and said the first clue was hidden in the image.

**Artifact and action.** OutGuess returned a signed riddle and three-part book code. “A book whose study is forbidden / Once dictated to a beast; / To be read once and then destroyed” selected Aleister Crowley's *Liber AL vel Legis*. Addressing chapter, verse and character produced `https://www.dropbox.com/s/r7sgeb5dtmzj14s/3301`.

**Resulting state.** The Dropbox object was a roughly 130 MB bootable ISO with `BOOT`, `DATA` and `AUDIO` directories. The canonical directory audit records `BOOT/3301.IMG`, `AUDIO/761.MP3` and the data files `560.13`, `560.17` and `_560.00`.

**Evidence.** The signed book code is [`2013-01-opening-book-code.asc`](corpus/2013/communications/2013-01-opening-book-code.asc); the surviving signed Cicada OS message is [`2013-01-cicada-os-message.asc`](corpus/2013/communications/2013-01-cicada-os-message.asc).

**Later evidence.** Booting printed primes through 3301, pausing at 1033 and 3301, then displayed `@1231507051321 / The key is all around you. / Good luck. / 3301`.

**Preservation boundary.** Multiple opening threads are reported, but a complete first-upload custody chain is not preserved.

### R13.2 — ISO, audio and Twitter to Gematria Primus

**Solver state.** The solver held the complete ISO, `761.MP3`, the handle `@1231507051321`, and the instruction that the key was “all around you.” The MP3's ID3 title was `The Instar Emergence`, artist `3301`; appended bytes contained `Parable 1,595,277,641` and the poem “Like the instar, tunneling to the surface / We must shed our own circumferences; / Find the divinity within and emerge.”

**Artifact and action.** The Twitter account emitted offset-labelled 65-byte hex blocks. Reassembling them by offset produced a byte stream; XOR with the exact `761.MP3` bytes yielded the Gematria Primus rune-table JPEG.

**Resulting state.** The solver held a 29-row rune alphabet, transliterations, values and prime ordering: [`corpus/2013/gematria-primus/`](corpus/2013/gematria-primus/).

**Evidence.** The reconstructed scan and machine-readable table are under [`corpus/2013/gematria-primus/`](corpus/2013/gematria-primus/). The scan prints `U`; the machine table's U/V alias is a transcription convention.

**Later evidence.** The poem's three line sums are 1259, 1031 and 1229, and their product is the printed parable number. `DIVINITY` later becomes the historically selected key at R14.3.

**Preservation boundary.** The original Twitter service state and every timing observation are not canonical inputs; the reconstructed byte stream and scan are preserved.

### R13.3 — Gematria scan to the first onion

**Solver state.** The solver held the recovered rune-table JPEG and knew OutGuess from prior authenticated routes.

**Artifact and action.** OutGuess returned a valid signed message whose apparent body was whitespace. Tabs and spaces decoded as binary to `Come to emiwp4muu2ktwknf.onion / We shall await you there. / Good luck. / 3301`.

**Resulting state.** `emiwp4muu2ktwknf.onion` displayed “Web browsers are useless here” and exposed an interactive text service over Tor.

**Evidence.** The signed carrier is [`2013-01-rune-table-morse.asc`](corpus/2013/communications/2013-01-rune-table-morse.asc).

**Later evidence.** OpenPGP clear-sign canonicalization strips trailing whitespace, so the signature authenticates the surrounding clear-signed object but does not cryptographically bind the 558-character whitespace payload. The route is nevertheless preserved by contemporary reconstruction.

**Preservation boundary.** Original HTTP headers and service binaries are not preserved.

### R13.4 — interactive onion, retained ISO state and ICMP transport

**Solver state.** A contemporary solver had the ISO files, Gematria table and Tor text service. Commands included `help`, integer factorization, `primes`, `count`, `hello` and `hint`/`clue`.

**Artifact and action.** `hello` returned a hex-dumped signed message routing to `xsxnaksict6egxkq.onion`. `hint`/`clue`, XORed with ISO file `_560.00`, read `You can't see the forest when you're looking at the trees.` The service's `count` acted as a Gematria oracle; its prime list deliberately omitted primes 73 through 1223. Onion 2 first said “Patience is a virtue,” then the signed message “You already have everything you need to continue. Sometimes one must knock on the sky and listen to the sound.”

**Artifact and action.** Solvers identified the onion backend and inspected ICMP echo replies. Interleaved packets with sequence number 1 carried a repeating hex stream; concatenating it, decoding hex and gunzipping `message.txt.asc` produced a valid signed pointer to `pklmx2eeh6fjt7zf.onion`.

**Resulting state.** The third onion instructed solvers to stand by for coordinates.

**Evidence.** The authenticated route messages are [`telnet hello`](corpus/2013/communications/2013-01-telnet-hello.asc), [`knock on the sky`](corpus/2013/communications/2013-01-knock-on-the-sky.asc) and [`onion pointer`](corpus/2013/communications/2013-01-onion-pointer.asc).

**Later evidence.** This route combined Tor, a text protocol, ICMP payload capture and retained ISO state.

**Preservation boundary.** The historical account derived a clearnet backend from an error response; intent of that leak is unknown. Modern hosts or addresses are not route evidence.

### R13.5 — posters, telephones, data slices and Shamir routing

**Solver state.** `pklmx2eeh6fjt7zf.onion` eventually supplied physical coordinates. Each recovered poster combined a phone number ending in 3301 or 1033 with a two-letter/four-digit access code.

**Artifact and action.** Calling a poster number and entering the Gematria value of its access code returned `Dataset`, `Offset` and hex `Data`. XORing the data with the named ISO file beginning at that offset yielded a location-specific onion. The preserved routes are:

| Location | Telephone | Access code | Data source and offset | Resulting onion |
| --- | --- | --- | --- | --- |
| Dallas, Texas | `+1 205-396-3301` | `JD: 3789` | `560.17`, reported offset 16433/33461 | `y2wyuvrqraowagc5.onion` |
| Okinawa, Japan | `+1 626-586-1033` | `YF: 1032` | `560.13`, offset 378610 | `wzwmcwmsk5cb7gjn.onion` |
| Moscow, Russia | `+1 928-237-3301` | `CR: 1311` | `560.13`, offset 1111111 | `qw7mhchzvuq6f2mf.onion` |
| Little Rock, Arkansas | `+1 719-428-3301` | `LM: 7167` | `560.13`, offset 13831 | `4l6uipnstbggwjyv.onion` |
| Annapolis, Maryland | `+1 253-655-1033` | `PX: 4347` | `560.17`, offset 77977 | `erwfcsdvx6pm2rsk.onion` |
| Portland, Oregon | `+1 424-999-1033` | `GH: 1723` | `560.13`, offset 12821 | `gbyh7znm6c7ezsmr.onion` |
| Columbus, Georgia | `+1 469-251-1033` | `NR: 2911` | `560.17`, offset 617 | no local onion/share preserved |

**Artifact and action.** Each local onion supplied a Shamir Secret Sharing Scheme share. Any five recovered shares reconstructed `p7amjopgric7dfdi.onion`.

**Resulting state.** The shared onion displayed a signed welcome: create a fresh anonymous webmail account and GPG key, submit the email to receive an identification number, and use that number to begin a timed test; one registration was allowed per person. The test reportedly contained 19 epistemic, logical and programming questions and set cookies named `167` and `761`.

**Evidence.** The signed public route messages that bracket this stage are under [`corpus/2013/communications/`](corpus/2013/communications/); local share and question-service bytes are only partially preserved.

**Later evidence.** This stage deliberately combined geographically distributed state into a common endpoint and then split solvers into individualized registration and assessment.

**Preservation boundary.** Only six shares are preserved; the route was described as a threshold over ten. Annapolis was reportedly found by wardialing rather than physical recovery. The signature binds the welcome text but not the onion wrapper, question implementation, cookies or every reported test item.

### R13.6 — assessment to solver-operated return service

**Solver state.** A successful individual had a fresh email/key, identification state and answers accepted by the timed test.

**Artifact and action.** Cicada's signed instruction required each solver to write a TCP server alone, expose it as a Tor hidden service and send the onion address and port by GPG-encrypted email. The line protocol required `WELCOME`, `RAND`, `QUINE`, `BASE29`, `CODE`, `KOAN`, Diffie–Hellman, `NEXT` and `GOODBYE`. Crucially, `NEXT` made the solver's server acknowledge and record arbitrary text sent by Cicada's client.

**Resulting state.** The solver, not Cicada, operated the next-stage receiver. An unsigned reported server log contains `NEXT` around a signed-looking recruitment letter, but no authenticated callback packet survives.

**Evidence.** The authenticated instruction's line protocol and state semantics are recorded in this transition. The reported callback body lacks an authenticated surviving packet.

**Later evidence.** Recipient-operated hidden services recur in 2014 with an HTTP upload callback, but the protocols and retained state differ.

**Preservation boundary.** No authenticated 2013 callback body, recipient binding, complete service log or downstream private route survives. The public route vanished and the Twitter account later became `@1231507051321_`; that fact does not recover the missing `NEXT` payload.

## 2014 — composed onion chain to the unresolved delivery

The order below is Cicada's release order. The repository's `intro-00`–`intro-16` names are community assembly labels, because Cicada published an order rather than page numbers.

### R14.1 — opening image, Emerson and an RSA carrier

**Solver state.** On 6 January 2014, Twitter status `420087183957966849` linked `http://i.imgur.com/zN4h51m.jpg`.

**Artifact and action.** OutGuess produced a valid signed riddle and four-part book code. “The work of a private man / who wished to transcend / He trusted himself / to produce from within” selected Ralph Waldo Emerson's *Self-Reliance*; paragraph, sentence, word and letter addressing yielded `auqgnxjtvdbll3pv.onion`.

**Artifact and action.** Onion 1's title was `For Every Thing That Lives Is Holy` and it served `1033.jpg`, a Blake collage. OutGuess exposed a valid signed `Crypt::RSA::ES::OAEP` carrier with `e=65537` and a 432-bit modulus. Factoring and decrypting yielded `cu343l33nqaekrnw.onion`.

**Resulting state.** The solver arrived at onion 2 with the 2013 ISO, Gematria table, poem and prior route knowledge still historically available.

**Evidence.** The signed carriers are [`opening book code`](corpus/2014/communications/2014-01-opening-book-code.asc) and [`RSA challenge`](corpus/2014/communications/2014-01-rsa-oaep-challenge.asc).

**Later evidence.** Onion 1's title has Gematria sum 1033, matching the filename. The verified relation covers this title and filename.

**Preservation boundary.** No private state was introduced at this transition; the route was public.

### R14.2 — onion 2's growing payload and three-share composition

**Solver state.** Onion 2 began with `<!--Patience is a virtue-->` above a bare hex string that grew one byte every few minutes for roughly 23 hours to 256 bytes.

**Artifact and action.** The page later changed to `<!--761-->`—the Gematria sum of “Patience is a virtue”—above an approximately 3.6 MB hex dump. Hex decoding and bit inversion revealed three JPEGs, the third byte-reversed. OutGuess on the images, at preserved seeds 163, 115 and 94, recovered page `0.0 A WARNING` and three valid signed shares. XORing the shares produced a signed ciphertext; inverted Gematria followed by columnar transposition read `GOOD WORK / ULTIMATE TRUTH IS THE ULTIMATE ILLUSION / JOIN US AT FV7LYUCMEOZZD5J4`.

**Resulting state.** The resulting address was `fv7lyucmeozzd5j4.onion`.

**Evidence.** The three signed shares and reconstructed signed ciphertext are indexed as communication records 21–24 in [`corpus/communications.csv`](corpus/communications.csv).

**Later evidence.** This stage composed representation changes, multiple carriers and authenticated shares before yielding a locator. Onion 3 later grew a distinct bare 256-byte payload in the same one-byte-at-a-time object class; neither payload has an established operational role.

**Preservation boundary.** The growth timing survives through logs rather than an authenticated schedule. It does not establish that timing encodes another payload.

### R14.3 — onion 3, the 1033 square and the 2013 key

**Solver state.** Onion 3 grew a distinct 256-byte hex payload under `<!--1033-->`. A leaked Apache status surface later carried two opposed JPEGs with data between them.

**Artifact and action.** Comparing the forward and reversed JPEGs recovered a 5×5 magic square with constant 1033. Later images supplied `0.1 WELCOME`, including “SOME WISDOM” and the 1033 word square. OutGuess produced the signed instruction `Let the text guide you` and an 18-rune ciphertext. The word `DIVINITY`, already available in the 2013 Instar poem, decrypted that line; `WELCOMEPILGRIMTOTHE`, text on the page just received, then decoded its runic locator.

**Resulting state.** The address was `avowyfgl5lkzfj3n.onion`.

**Evidence.** The signed selector is [`2014-01-let-the-text-guide-you.asc`](corpus/2014/communications/2014-01-let-the-text-guide-you.asc); exact chronology and known answers are in the 2014 release findings.

**Later evidence.** This is the clearest demonstrated cross-year dependency: the intended key for a 2014 object came from authored 2013 material and was already held when the consumer arrived. The later Liber Primus page that prints `DIVINITY` had not yet been served.

**Preservation boundary.** Intent of the Apache status exposure is not authenticated. The repeated 256-byte payload has no established consumer.

### R14.4 — onion 4's koan, instruction and route grid

**Solver state.** Onion 4 initially displayed another 256-byte hex string under `<!--3301-->`, then later served a signed gzip carrier containing four images now assembled as introduction pages 06, 07, 09 and 08.

**Artifact and action.** The readable pages formed `0.2 A KOAN` and an instruction to do four unreasonable things. OutGuess on intro-08 yielded an unsigned grid. The fixed column order `1736254` transposed it exactly to `TO BELIEVE TRUTH IS TO DESTROY POSSIBILITY`, the 16-character locator `q4utgdi2n4m4uim5`, and residual `9133`.

**Resulting state.** The solver reached `q4utgdi2n4m4uim5.onion`.

**Evidence.** The source object is [`2014-01-fallen-behind-outguess-08.asc`](corpus/2014/communications/2014-01-fallen-behind-outguess-08.asc); the grid, column order and readout are stated above.

**Later evidence.** The old walkthrough sometimes concatenates residual `9133` onto the onion; version-2 onion hostnames are 16 characters, and the preserved route hostname is `q4utgdi2n4m4uim5`.

**Preservation boundary.** The 3301-labelled 256-byte string lacks an established operation. The unsigned grid's carrier provenance, not a PGP signature, supports its route role.

### R14.5 — Interconnectedness and the GEB book code

**Solver state.** Onion 5 served a valid signed hexadecimal carrier which decoded to an MP3 titled `Interconnectedness`, artist `3301`, duration about 277.133 seconds. A later state served Goya's *Portrait of Andrés del Peral* with a superimposed Rasputin and numerical square material.

**Artifact and action.** OutGuess on the portrait yielded bzip-compressed signed content; splitting its hex produced images of Gödel's incompleteness theorem and Escher's *Eye*, plus Bach's Trio Sonata in G Major. Those three objects selected Hofstadter's *Gödel, Escher, Bach*. Applying the accompanying chapter/line/word/letter book code yielded `ut3qtzbrvs7dtvzp.onion`.

**Resulting state.** The solver reached onion 6. Independently, OpenPuff 4.00 on `Interconnectedness.mp3`, maximum MP3 capacity and password `33011033` yielded three magic squares of orders 5, 7 and 5 with constants 3301, 1033 and 1033.

**Evidence.** The signed source stages are [`Interconnectedness hex`](corpus/2014/communications/2014-01-interconnectedness-hex.asc) and [`onion-5 Liber Primus carrier`](corpus/2014/communications/2014-01-onion5-liber-primus.asc).

**Later evidence.** Onion 6 explicitly consumed the three squares. Community reconstruction established the OpenPuff extraction and discovered the password during solving.

**Preservation boundary.** The independent intent of the portrait's extra numbers and residual onion-4 `9133` is not established.

### R14.6 — magic-square submission and recipient-operated callback

**Solver state.** Onion 6 first served four sequential JPEGs including readable `0.3 THE LOSS OF DIVINITY`. OutGuess on each returned the same valid signed instruction: create one Tor hidden service capable of CGI uploads, then post the three magic squares and its URL; work alone. Four copies framed a 3×3 box `10 12 10 / 12 14 12 / 10 12 10` with outer digits 3, 3, 0 and 1.

**Artifact and action.** Six days later the signed form required the three squares and a Tor service URL, specified upload path `/cgi-bin/upload`, file input name `file`, and required a newly generated GPG public key at `/key.asc`. Submitting returned `107.jpg`, `167.jpg` and `229.jpg`, byte-identical to introduction pages 14, 15 and 16; together they form `0.4 A KOAN`, another instruction and the 3301 square.

**Resulting state.** A successful solver now operated a private HTTP endpoint and possessed its keypair, exact submitted values, whatever root page they chose to serve, and the complete introduction. On 2 May, reported access logs show Cicada's client GET `/key.asc`, GET `/`, then POST `message.txt.asc` to `/cgi-bin/upload`, using Cicada-labelled user agents. The posted file was a valid signed message created 2 April: “Your enlightenment awaits you” at `ky2khlqdf7qdznac.onion`.

**Evidence.** The four signed hidden-service instructions, signed form and signed locator are communication records 29–34 in [`corpus/communications.csv`](corpus/communications.csv).

**Later evidence.** The visible form reportedly accepted any squares meeting its order/sum constraints, and the final locator was common across preserved recipients. That does not establish what Cicada learned or returned through the private callback, or whether eligibility had already been decided.

**Preservation boundary.** The submitted square bytes, solver private key, exact `/key.asc`, served root body, raw request/response bodies, server-side validation, per-recipient state and any private reply are not preserved. Chronology alone cannot fill these missing-state questions.

### R14.7 — shared onion-7 delivery and Liber Primus

**Solver state.** A successful solver possessed every earlier public 2014 object, the full introduction, their private callback state and the valid signed onion-7 locator.

**Artifact and action.** `ky2khlqdf7qdznac.onion` served one HTML page with title `133`, a `<div id="331">`, and images `0.jpg` through `57.jpg` in order. These 58 body images joined the 17 earlier introduction images to form Liber Primus. The body includes runic prose, illustrations, magic squares, printed marks, the page-49–51 256-byte interruption, page 56's verified 512-bit value and readable ending pages 56–57.

**Resulting state.** The public route ends in the largest preserved unresolved Cicada surface: 12,956 unsolved runes plus unresolved non-rune objects and their dependency graph. Page 56 says a deep-web page has a hash matching its signed value; page 57 says `AN END / WITHIN THE DEEP WEB, THERE EXISTS A PAGE THAT HASHES TO` the preceding runes.

**Evidence.** Canonical images, transliterations, solved plaintext and measurements live under [`corpus/2014/liber-primus/`](corpus/2014/liber-primus/); the signed locator is [`2014-05-onion-welcome.asc`](corpus/2014/communications/2014-05-onion-welcome.asc).

**Later evidence.** Every preserved observer received the same public body. The signed locator was created 2 April and delivered 2 May. The 2016 authenticated message explicitly says Liber Primus is the way and that its words, meaning and numbers are operative.

**Preservation boundary.** No authenticated instruction explains how a recipient was meant to consume the full body. It remains unresolved whether onion 7 is complete common state, awaits an internal reader, composes with lost R14.6 state, or mixes those roles. Printed community sections are not established cryptographic units, and prior successful ciphers do not select later siblings.

## 2015–2017 — authenticated continuation

### R15.1 — denial of illegal attribution

**Solver state.** News reports connected “3301” and Cicada symbolism to a group claiming attacks against Planned Parenthood.

**Artifact and action.** On 28 July 2015 Cicada signed a denial: “We do not engage in illegal activities,” were not associated with that group and did not condone use of their name, number or symbolism.

**Resulting state.** The message established an authenticated identity and conduct boundary; it did not advance an artifact route.

**Evidence.** Exact bytes: [`2015-07-planned-parenthood-denial.asc`](corpus/2015/communications/2015-07-planned-parenthood-denial.asc).

**Later evidence.** This continues the same position as the authenticated April 2012 Necrome denial.

**Preservation boundary.** Publication venue provenance is less important than the valid signature for authorship of the bytes; the message names no puzzle operation.

### R16.1 — explicit direction to Liber Primus

**Solver state.** Liber Primus remained unresolved and unsigned purported continuations circulated.

**Artifact and action.** The message signed at `2016-01-01 00:01:07Z` states: `The path lies empty; epiphany seeks the devoted. Liber Primus is the way. Its words are the map, their meaning is the road, and their numbers are the direction. Seek and you will be found.` It ends `Beware false paths. Verify OpenPGP 7A35090F.`

**Resulting state.** Words, meanings and numbers in Liber Primus became direct authored evidence, while signature verification remained the boundary for purported Cicada instructions.

**Evidence.** Exact bytes: [`2016-01-liber-primus.asc`](corpus/2016/communications/2016-01-liber-primus.asc).

**Later evidence.** The message assigns map, road and direction roles to Liber Primus's words, meaning and numbers. Their representation and operation remain open.

**Preservation boundary.** “Words,” “meaning” and “numbers” remain underdetermined; compatibility with that sentence is not confirmation of a candidate.

### R17.1 — final authenticated warning

**Solver state.** False paths and unsigned claimed solutions continued after the 2016 direction.

**Artifact and action.** On 4 April 2017 Cicada signed with SHA-512: `Beware false paths. Always verify PGP signature from 7A35090F. 3301`.

**Resulting state.** This is the latest authenticated public Cicada communication preserved in the corpus.

**Evidence.** Exact bytes: [`2017-04-final-warning.asc`](corpus/2017/communications/2017-04-final-warning.asc).

**Later evidence.** The warning governs provenance, not which unsolved object to attack.

**Preservation boundary.** No later signed result, correction, continuation or solution is known in the canonical corpus.

## Current public state

The public artifact route ends at R14.7; authenticated commentary continues through R17.1. A successful R14.6 solver possessed state outside the surviving public corpus. Liber Primus is the largest unresolved surface and Cicada explicitly names it as the way. The unresolved result belongs to the state transition following the complete 2014 route.

Use this route and its primary artifacts to reconstruct the contemporary solver's state and form a causal question. After identifying candidate mechanisms, give them to the archive reviewer for current Explog and Discord retrieval.
