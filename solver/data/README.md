# Frozen English model

`english_model.json.gz` contains sufficient statistics for the English-through-Gematria-Primus fitness model: positive n-gram counts for orders 1 through 4, the original training length, and the SHA-256 digest of the rune-index training stream.

The model was derived before removing the three public-domain prose files formerly stored in `reference/english/`. It preserves every score produced by the prior runtime-trained model without retaining or loading the raw prose. N-grams are encoded as fixed-width base-29 integers and the JSON payload is deterministically gzip-compressed.

Pinned model facts:

- Training length: 650,377 runes
- Training SHA-256: `ffe950c4caf537a065819e3e5f0d56bb76015fa74023c7bf656f6ec604d0bb56`
- Distinct n-grams at orders 1–4: 29, 712, 8,649, 51,075
- Compressed asset SHA-256: `14509e5d79260f7e3a48dbd53dd95ffe9844c51ab29347e79fb0b2b2e44b2c5d`
