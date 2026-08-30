# Derived solver data

`english_model.json.gz` contains sufficient statistics for the English-through-Gematria-Primus fitness model: positive n-gram counts for orders 1 through 4, the original training length, and the SHA-256 digest of the rune-index training stream.

The input prose remains in Git source commit `71b0ebab3823dcff8c41674f3b1b4ffad5c91171`: the 2012 Mabinogion translation, accepted Liber Primus plaintext and three public-domain files formerly under `reference/english/`. [`build_english_model.py`](../cli/build_english_model.py) reads those local Git objects and deterministically recreates the committed gzip byte-for-byte:

```sh
python3 -m solver.cli.build_english_model --check
python3 -m solver.cli.build_english_model --output /tmp/english_model.json.gz
```

N-grams are encoded as fixed-width base-29 integers. The JSON keys and counts are sorted, insignificant whitespace is omitted, and gzip uses an empty filename and zero timestamp.

Pinned model facts:

- Training length: 650,377 runes
- Training SHA-256: `ffe950c4caf537a065819e3e5f0d56bb76015fa74023c7bf656f6ec604d0bb56`
- Distinct n-grams at orders 1–4: 29, 712, 8,649, 51,075
- Compressed asset SHA-256: `14509e5d79260f7e3a48dbd53dd95ffe9844c51ab29347e79fb0b2b2e44b2c5d`

`discord.db` indexes 109,917 messages from 13 Liber Primus community channels spanning 2019–2026. [`build_discord_db.py`](../cli/build_discord_db.py) recreates and checks it from the exports retained in source commit `71b0eba`.

The ordinary unit suite verifies both committed asset digests, the database schema, search-index parity, logical rows and a deterministic fixture build. Run both full source-snapshot reconstructions explicitly with `CICADA_REBUILD_DERIVED=1 python3 -m unittest tests.test_derived_assets`.

Both builders require a Git clone containing source commit `71b0eba`. A shallow clone can recover it with `git fetch --unshallow origin`; source archives require a full Git clone.
