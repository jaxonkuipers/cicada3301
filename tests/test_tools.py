"""Behavior tests for Discord retrieval, Explog, and managed worktrees."""

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from solver import runes
from solver.cli import dsearch, worktree

DB_SCHEMA = """
CREATE TABLE messages (
    id INTEGER PRIMARY KEY, channel TEXT NOT NULL, channel_name TEXT NOT NULL,
    ts TEXT NOT NULL, author TEXT NOT NULL, pinned INTEGER NOT NULL,
    body TEXT NOT NULL, extra TEXT NOT NULL, seq INTEGER NOT NULL,
    line INTEGER NOT NULL
);
CREATE INDEX msg_channel_seq ON messages(channel, seq);
CREATE VIRTUAL TABLE msg_fts USING fts5(body, extra, tokenize='unicode61');
CREATE TABLE runes (
    id INTEGER PRIMARY KEY, msg_id INTEGER NOT NULL, notation TEXT NOT NULL,
    raw TEXT NOT NULL, canon TEXT NOT NULL, n INTEGER NOT NULL
);
CREATE VIRTUAL TABLE rune_fts USING fts5(canon, tokenize='trigram');
"""

@contextlib.contextmanager
def archive(needle_count=0):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        database = root / "discord.db"
        rows = [
            (1, "54-55", "Liber-Primus / 54-55-jpg", "2021-03-14 09:05",
             "alice", 0, "first message", "", 1, 4),
            (2, "54-55", "Liber-Primus / 54-55-jpg", "2021-03-14 09:06",
             "bob", 1, "runes ᚠᚢᚦᚩᚱᚳ here\nsecond line", "", 2, 7),
            (3, "54-55", "Liber-Primus / 54-55-jpg", "2021-03-14 09:07",
             "carol", 0, "indices 19, 21, 23, 27 and a matrix\n1 0 0\n0 -1 0",
             "", 3, 11),
            (4, "54-55", "Liber-Primus / 54-55-jpg", "2021-03-14 09:08",
             "dave", 0, "", "{Attachments}\nhttps://example.invalid/a.png", 4, 16),
        ]
        for index in range(needle_count):
            rows.append((
                5 + index, "54-55", "Liber-Primus / 54-55-jpg",
                f"2021-03-14 09:{10 + index}", f"solver{index}", 0,
                f"needle {index}", "", 5 + index, 20 + index * 3,
            ))
        with contextlib.closing(sqlite3.connect(database)) as db:
            db.executescript(DB_SCHEMA)
            db.executemany(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)", rows,
            )
            db.executemany(
                "INSERT INTO msg_fts(rowid, body, extra) VALUES (?,?,?)",
                ((row[0], row[6], row[7]) for row in rows),
            )
            canon, _ = runes.canonicalise_query("ᚠᚢᚦᚩᚱᚳ")
            db.execute(
                "INSERT INTO runes VALUES (1,2,'runic','ᚠᚢᚦᚩᚱᚳ',?,6)",
                (canon,),
            )
            db.execute("INSERT INTO rune_fts(rowid, canon) VALUES (1,?)", (canon,))
            db.commit()
        with mock.patch.object(dsearch, "DISCORD_DB", database):
            yield root


def call_dsearch(argv):
    output = io.StringIO()
    error = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        code = dsearch.main(argv)
    return code, output.getvalue(), error.getvalue()


class TestDiscordDatabase(unittest.TestCase):
    def test_committed_database_is_complete_and_healthy(self):
        database = Path(__file__).parents[1] / "discord.db"
        self.assertTrue(database.is_file())
        self.assertEqual(
            hashlib.sha256(database.read_bytes()).hexdigest(),
            "b7b9c8328a6cbfcde6640a25b199fe51044cf37a4db5cec08a2180d6f76b242f",
        )
        with contextlib.closing(sqlite3.connect(database)) as db:
            self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 109917,
            )
            self.assertEqual(db.execute("SELECT COUNT(*) FROM runes").fetchone()[0], 7755)
            self.assertEqual(
                [row[1] for row in db.execute("PRAGMA table_info(msg_fts)")],
                ["body", "extra"],
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM msg_fts").fetchone()[0], 109917,
            )


class TestDsearch(unittest.TestCase):
    def test_search_returns_compact_individual_messages(self):
        with archive():
            code, output, _ = call_dsearch(["first"])
        self.assertEqual(code, 0)
        self.assertIn("1  discord.db:messages:1", output)
        self.assertIn("first message", output)
        self.assertNotIn("second line", output)

    def test_unknown_channel_is_an_error_with_available_names(self):
        with archive():
            code, output, error = call_dsearch([
                "first", "--channel", "missing-channel",
            ])
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("unknown Discord channel 'missing-channel'", error)
        self.assertIn("54-55", error)

    def test_corrupt_database_reports_a_cli_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "discord.db"
            database.write_bytes(b"not a sqlite database")
            with mock.patch.object(dsearch, "DISCORD_DB", database):
                code, output, error = call_dsearch(["first"])
        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("cannot read discord.db", error)
        self.assertNotIn("Traceback", error)

    def test_attachment_metadata_is_searchable_and_compact(self):
        with archive():
            code, output, _ = call_dsearch(["example"])
            _, json_output, _ = call_dsearch(["example", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("discord.db:messages:4", output)
        self.assertIn("extra: {Attachments} https://example.invalid/a.png", output)
        result = json.loads(json_output)["results"][0]
        self.assertEqual(result["source"], "discord.db:messages:4")
        self.assertIn("example.invalid/a.png", result["extra"])
        self.assertEqual(result["body"], "")

    def test_search_json_has_ids_and_total_count(self):
        with archive(needle_count=5):
            _, output, _ = call_dsearch(["needle", "--limit", "2", "--json"])
        payload = json.loads(output)
        self.assertEqual(payload["hits"], 5)
        self.assertEqual(payload["shown"], 2)
        self.assertEqual(len(payload["results"]), 2)
        self.assertIsInstance(payload["results"][0]["id"], int)

    def test_show_expands_selected_ids(self):
        with archive():
            code, output, _ = call_dsearch(["show", "1", "--window", "1"])
        self.assertEqual(code, 0)
        self.assertIn("> discord.db:messages:1", output)
        self.assertIn("first message", output)
        self.assertIn("second line", output)

    def test_show_merges_overlapping_windows_and_includes_extras(self):
        with archive():
            code, output, _ = call_dsearch(["show", "3", "4", "--window", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(output.count("=== #"), 1)
        self.assertIn("https://example.invalid/a.png", output)

    def test_show_json_marks_selected_messages(self):
        with archive():
            _, output, _ = call_dsearch(["show", "2", "--json"])
        payload = json.loads(output)
        selected = [
            message for conversation in payload["conversations"]
            for message in conversation["messages"] if message["selected"]
        ]
        self.assertEqual([message["id"] for message in selected], [2])

    def test_show_rejects_unknown_ids(self):
        with archive():
            code, _, error = call_dsearch(["show", "999"])
        self.assertEqual(code, 2)
        self.assertIn("unknown message ids", error)

    def test_rune_search_canonicalizes_all_notations(self):
        with archive():
            for query in ("ᚠᚢᚦᚩᚱᚳ", "0 1 2 3 4 5", "F-U-TH-O-R-C"):
                code, output, _ = call_dsearch(["--runes", query, "--json"])
                payload = json.loads(output)
                self.assertEqual(code, 0, query)
                self.assertEqual(payload["hits"], 1, query)
                self.assertEqual(payload["indices"], [0, 1, 2, 3, 4, 5], query)

    def test_filters_validate_dates(self):
        with archive():
            self.assertIn("first message", call_dsearch([
                "first", "--channel", "54-55",
            ])[1])
            self.assertIn("no matching messages", call_dsearch([
                "first", "--since", "2022",
            ])[1])
            self.assertEqual(call_dsearch(["first", "--since", "2021-99-99"])[0], 2)

    def test_bad_queries_and_limits_return_two(self):
        with archive():
            self.assertEqual(call_dsearch(['"'])[0], 2)
            self.assertEqual(call_dsearch(["first", "--limit", "0"])[0], 2)
            self.assertEqual(call_dsearch(["show", "1", "--window", "-1"])[0], 2)
            self.assertEqual(call_dsearch(["--runes", "ᚠᚢ"])[0], 2)

    def test_invalid_fts_falls_back_visibly(self):
        with archive():
            code, output, error = call_dsearch(["first-message"])
        self.assertEqual(code, 0)
        self.assertIn("first message", output)
        self.assertIn("invalid FTS5 syntax", error)

    def test_missing_or_incompatible_database_is_diagnosed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(dsearch, "DISCORD_DB", Path(temporary) / "missing"):
                self.assertEqual(call_dsearch(["first"])[0], 2)
        with archive() as root:
            with contextlib.closing(sqlite3.connect(root / "discord.db")) as database:
                database.execute("DROP TABLE msg_fts")
                database.commit()
            code, _, error = call_dsearch(["first"])
        self.assertEqual(code, 2)
        self.assertIn("restore the committed database", error)


class TestWorktree(unittest.TestCase):
    @staticmethod
    def result(stdout="", stderr="", returncode=0):
        return mock.Mock(stdout=stdout, stderr=stderr, returncode=returncode)

    def test_create_fetches_base_and_records_managed_wake(self):
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            stdout = "abc123\n" if args[:2] == ["git", "rev-parse"] else ""
            return self.result(stdout)

        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(worktree, "ROOT", Path("/repo")):
            path, branch, base = worktree.create(
                "Cicada_1", parent=Path(temporary), stamp="20260828-120000",
                runner=runner,
            )
        self.assertEqual(path.name, "cicada-1-20260828-120000")
        self.assertEqual(branch, "wake/cicada-1-20260828-120000")
        self.assertEqual(base, "abc123")
        commands = [call[0] for call in calls]
        self.assertEqual(
            commands[0], ["git", "config", "core.hooksPath", ".githooks"],
        )
        self.assertEqual(commands[1], ["git", "fetch", "origin", "main"])
        self.assertIn([
            "git", "worktree", "add", "-b", branch, str(path), "abc123",
        ], commands)

    def test_create_reports_fetch_failure_before_creating_destination(self):
        def runner(args, **kwargs):
            if args == ["git", "fetch", "origin", "main"]:
                return self.result(stderr="origin unavailable", returncode=128)
            return self.result()

        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(worktree, "ROOT", Path("/repo")):
            parent = Path(temporary) / "wakes"
            with self.assertRaisesRegex(
                worktree.WorktreeError, "cannot fetch origin/main: origin unavailable",
            ):
                worktree.create(
                    "cicada-1", parent=parent, stamp="20260828-120000",
                    runner=runner,
                )
            self.assertFalse(parent.exists())

    def test_publish_rebases_pushes_and_confirms_reachability(self):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            if args == ["git", "branch", "--show-current"]:
                return self.result("wake/cicada-1-20260828\n")
            if args[:3] == ["git", "config", "--get"]:
                return self.result("cicada-1-20260828\n")
            if args == ["git", "status", "--porcelain"]:
                return self.result("")
            if args == ["git", "rev-parse", "HEAD"]:
                return self.result("deadbeef\n")
            return self.result()

        wake_id, commit = worktree.publish(root=Path("/wake"), runner=runner)
        self.assertEqual((wake_id, commit), ("cicada-1-20260828", "deadbeef"))
        self.assertIn(["git", "config", "core.hooksPath", ".githooks"], calls)
        self.assertIn(["git", "rebase", "origin/main"], calls)
        self.assertIn(["git", "push", "origin", "HEAD:main"], calls)
        self.assertIn([
            "git", "merge-base", "--is-ancestor", "deadbeef", "origin/main",
        ], calls)

    def test_publish_refuses_uncommitted_work(self):
        def runner(args, **kwargs):
            if args == ["git", "branch", "--show-current"]:
                return self.result("wake/cicada-1-20260828\n")
            if args[:3] == ["git", "config", "--get"]:
                return self.result("cicada-1-20260828\n")
            if args == ["git", "status", "--porcelain"]:
                return self.result(" M corpus/README.md\n")
            return self.result()

        with self.assertRaisesRegex(worktree.WorktreeError, "commit the wake"):
            worktree.publish(root=Path("/wake"), runner=runner)

    def test_publish_aborts_rebase_conflict_and_preserves_wake(self):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            if args == ["git", "branch", "--show-current"]:
                return self.result("wake/cicada-1-20260828\n")
            if args[:3] == ["git", "config", "--get"]:
                return self.result("cicada-1-20260828\n")
            if args == ["git", "status", "--porcelain"]:
                return self.result("")
            if args == ["git", "rebase", "origin/main"]:
                return self.result(stderr="CONFLICT", returncode=1)
            if args == ["git", "diff", "--name-only", "--diff-filter=U"]:
                return self.result("solver/cli/explog.py\nAGENTS.md\n")
            return self.result()

        with self.assertRaisesRegex(
            worktree.WorktreeError,
            "branch wake/cicada-1-20260828 remains resumable.*explog.py",
        ):
            worktree.publish(root=Path("/wake"), runner=runner)
        self.assertIn(["git", "rebase", "--abort"], calls)
        self.assertNotIn(["git", "push", "origin", "HEAD:main"], calls)

    def test_publish_retries_when_remote_advances(self):
        pushes = 0

        def runner(args, **kwargs):
            nonlocal pushes
            if args == ["git", "branch", "--show-current"]:
                return self.result("wake/cicada-2-20260828\n")
            if args[:3] == ["git", "config", "--get"]:
                return self.result("cicada-2-20260828\n")
            if args == ["git", "status", "--porcelain"]:
                return self.result("")
            if args == ["git", "push", "origin", "HEAD:main"]:
                pushes += 1
                return self.result(returncode=1 if pushes == 1 else 0)
            if args == ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"]:
                return self.result(returncode=1)
            if args == ["git", "rev-parse", "HEAD"]:
                return self.result("cafebabe\n")
            return self.result()

        worktree.publish(root=Path("/wake"), retries=2, runner=runner)
        self.assertEqual(pushes, 2)


if __name__ == "__main__":
    unittest.main()
