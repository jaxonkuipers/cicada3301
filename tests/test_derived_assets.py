"""Reproducibility checks for the two committed derived data assets."""

from __future__ import annotations

import contextlib
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from solver.cli import build_discord_db, build_english_model
from solver.cli._git_source import SOURCE_COMMIT, GitSource
from solver.paths import DISCORD_DB


class TestSourceSnapshot(unittest.TestCase):
    def test_pinned_commit_contains_every_archived_input(self):
        source = GitSource()
        self.assertEqual(source.commit, SOURCE_COMMIT)
        self.assertEqual(
            len([path for path in source.paths("discord") if path.endswith(".txt")]),
            13,
        )
        self.assertEqual(
            [
                Path(path).name
                for path in source.paths("reference/english")
                if path.endswith(".txt")
            ],
            [
                "emerson-essays-first.txt",
                "meditations-long.txt",
                "tao-teh-king-legge.txt",
            ],
        )


class TestEnglishModelBuilder(unittest.TestCase):
    def test_builder_reproduces_committed_gzip_exactly(self):
        rebuilt = build_english_model.model_bytes()
        self.assertEqual(rebuilt, build_english_model.OUTPUT.read_bytes())
        self.assertEqual(
            hashlib.sha256(rebuilt).hexdigest(),
            build_english_model.EXPECTED_SHA256,
        )


class TestDiscordBuilder(unittest.TestCase):
    EXPORT = b"""Channel: Test / derived-data

[1/2/2021 3:04 PM] alice (pinned)
first body
{Attachments}
https://example.invalid/archive.png
"""

    def test_parser_preserves_body_extra_and_source_coordinates(self):
        messages = list(build_discord_db.parse_export("discord/test.txt", self.EXPORT))
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.channel, "test")
        self.assertEqual(message.channel_name, "Test / derived-data")
        self.assertEqual(message.ts, "2021-01-02 15:04")
        self.assertEqual(message.author, "alice")
        self.assertTrue(message.pinned)
        self.assertEqual(message.line, 3)
        self.assertEqual(message.body, ["first body"])
        self.assertEqual(
            message.extra,
            ["{Attachments}", "https://example.invalid/archive.png"],
        )

    def test_small_build_is_deterministic_and_indexes_attachment_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.db"
            second = Path(temporary) / "second.db"
            exports = [("discord/test.txt", self.EXPORT)]
            build_discord_db.build_database(first, exports=exports, expected=False)
            build_discord_db.build_database(second, exports=exports, expected=False)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with contextlib.closing(sqlite3.connect(first)) as database:
                row = database.execute(
                    "SELECT rowid FROM msg_fts WHERE msg_fts MATCH 'archive'"
                ).fetchone()
                self.assertEqual(row, (1,))
                self.assertEqual(
                    [item[1] for item in database.execute("PRAGMA table_info(msg_fts)")],
                    ["body", "extra"],
                )

                database.execute(
                    "UPDATE msg_fts SET body = 'poisoned search text' WHERE rowid = 1"
                )
                database.commit()
            with self.assertRaisesRegex(RuntimeError, "msg_fts differs from messages"):
                build_discord_db.verify_database(first, expected=False)

            with contextlib.closing(sqlite3.connect(first)) as database:
                database.execute(
                    "UPDATE msg_fts SET body = 'first body' WHERE rowid = 1"
                )
                database.execute("DROP TABLE msg_fts")
                database.execute(
                    "CREATE VIRTUAL TABLE msg_fts "
                    "USING fts5(body, extra, tokenize='porter')"
                )
                database.execute(
                    "INSERT INTO msg_fts(rowid, body, extra) "
                    "SELECT id, body, extra FROM messages"
                )
                database.commit()
            with self.assertRaisesRegex(RuntimeError, "msg_fts definition differs"):
                build_discord_db.verify_database(first, expected=False)

    def test_committed_database_matches_pinned_logical_rows(self):
        counts, digests = build_discord_db.verify_database(DISCORD_DB)
        self.assertEqual(counts, build_discord_db.EXPECTED_COUNTS)
        self.assertEqual(digests, build_discord_db.EXPECTED_LOGICAL_SHA256)

    def test_builder_reproduces_the_pinned_source_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            rebuilt = Path(temporary) / "discord.db"
            counts, digests = build_discord_db.build_database(rebuilt)
        self.assertEqual(counts, build_discord_db.EXPECTED_COUNTS)
        self.assertEqual(digests, build_discord_db.EXPECTED_LOGICAL_SHA256)


if __name__ == "__main__":
    unittest.main()
