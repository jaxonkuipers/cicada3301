# Discord database provenance

`discord.db` indexes 109,917 messages from 13 Liber Primus community-channel exports spanning 2019–2026. The raw DiscordChatExporter files remain in Git source commit `71b0ebab3823dcff8c41674f3b1b4ffad5c91171`; they are absent from the current worktree because the archive cannot be reacquired.

[`build_discord_db.py`](../cli/build_discord_db.py) reads the exports directly from the local Git object database, parses them, canonicalizes rune sequences and builds full-text indexes over message bodies and attachment/embed metadata. It performs no network access and does not write raw exports to disk.

```sh
python3 -m solver.cli.build_discord_db --check
python3 -m solver.cli.build_discord_db --output /tmp/discord.db
```

The committed database has SHA-256 `b7b9c8328a6cbfcde6640a25b199fe51044cf37a4db5cec08a2180d6f76b242f`. Its physical bytes preserve a migration from the earlier body-only FTS index. A clean build has the same messages, rune rows, provenance and body-plus-extra search index, while its SQLite page arrangement can differ across build histories and SQLite releases. Logical row digests are the reproducibility contract:

| table | rows | logical SHA-256 |
| --- | ---: | --- |
| `messages` | 109,917 | `de1d59041a1b1f18e166e09c4ecdd66bb41855cbd5cf5b6f9765c26c6748f1d8` |
| `runes` | 7,755 | `63e7c36f5788e6a670421e8411d72880932e03610a2ddfd68d1612d86744af4d` |
| `provenance` | 13 | `68b6ce19fc44e04b780065f9807adfae01c0c10db46120152c5260d92095ed5c` |

Each logical digest hashes the ordered typed row values as compact UTF-8 JSON, one row per line. The builder also runs SQLite integrity checks, pins both FTS tokenizer definitions and requires each FTS rowid and indexed value to match its source table.
