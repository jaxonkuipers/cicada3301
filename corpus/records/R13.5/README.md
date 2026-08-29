# R13.5 — posters, telephones, data slices and Shamir routing

**Solver state.** `pklmx2eeh6fjt7zf.onion` eventually supplied physical coordinates. Each recovered poster combined a phone number ending in 3301 or 1033 with a two-letter/four-digit access code.

**Dependencies consumed.** R13.4 supplies the coordinate onion; R13.1 supplies the retained ISO datasets; R13.2 supplies Gematria values for the poster access codes.

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

Each local onion supplied a Shamir Secret Sharing Scheme share. Any five recovered shares reconstructed `p7amjopgric7dfdi.onion`.

**Resulting state.** Recipient reconstructions describe the shared onion as displaying a signed welcome: create a fresh anonymous webmail account and GPG key, submit the email to receive an identification number, and use that number to begin a timed test; one registration was allowed per person. The test reportedly contained 19 epistemic, logical and programming questions and set cookies named `167` and `761`.

**State handed forward.** The shared onion yields anonymous email/key registration, identification state and a timed assessment for R13.6.

**Evidence.** Exact signed public-route messages through R13.4 are indexed in [`communications.csv`](../../communications.csv). The poster calls, local shares, shared-onion welcome and question service survive through contemporary reconstruction and the locally preserved [retrospective source record](sources/retrospective-solve-record.md); their carrier bytes are absent locally.

**Later evidence.** This stage deliberately combined geographically distributed state into a common endpoint and then split solvers into individualized registration and assessment.

**Preservation boundary.** Six share-bearing locations and five exact share strings survive in the retained reconstruction; the route was described as a threshold over ten. Annapolis was reportedly found by wardialing rather than physical recovery. The exact signed welcome carrier, onion wrapper, question implementation, cookies and complete test are absent from the local corpus.
