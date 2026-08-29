"""Behavior tests for Discord retrieval, Explog, and managed worktrees."""

import contextlib
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from lib import runes
from tools import build_discord_db as bdb
from tools import dsearch, explog, worktree

EXPORT = """\
Guild: CicadaSolvers
Channel: Liber-Primus / 54-55-jpg

[3/14/2021 9:05 AM] alice
first message

[3/14/2021 9:06 AM] bob (pinned)
runes ᚠᚢᚦᚩᚱᚳ here
second line

[3/14/2021 9:07 AM] carol
indices 19, 21, 23, 27 and a matrix
1 0 0
0 -1 0

[3/14/2021 9:08 AM] dave
{Attachments}
https://example.invalid/a.png
"""

RUNNING = [
    "--route", "R14.7", "--object", "canonical test object",
    "--operation", "one exact test operation",
    "--decision", "positive favors internal reader; negative favors lost state",
]


@contextlib.contextmanager
def archive(text=EXPORT, name="54-55.txt"):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        exports = root / "discord"
        database = root / "discord.db"
        exports.mkdir()
        (exports / name).write_text(text, encoding="utf-8")
        with (
            mock.patch.multiple(bdb, DISCORD=exports, DISCORD_DB=database, ROOT=root),
            mock.patch.multiple(
                dsearch, DISCORD=exports, DISCORD_DB=database, ROOT=root,
            ),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                bdb.main()
            yield root


def call_dsearch(argv):
    output = io.StringIO()
    error = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        code = dsearch.main(argv)
    return code, output.getvalue(), error.getvalue()


class TestDiscordIndex(unittest.TestCase):
    def test_parser_extracts_messages_and_citable_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "54-55.txt"
            path.write_text(EXPORT, encoding="utf-8")
            messages = list(bdb.parse_file(path))
        self.assertEqual([message.author for message in messages], [
            "alice", "bob", "carol", "dave",
        ])
        self.assertTrue(messages[1].pinned)
        self.assertEqual(messages[0].ts, "2021-03-14 09:05")
        lines = EXPORT.splitlines()
        for message in messages:
            self.assertIn(message.author, lines[message.line - 1])

    def test_parser_separates_attachments(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "54-55.txt"
            path.write_text(EXPORT, encoding="utf-8")
            messages = list(bdb.parse_file(path))
        self.assertEqual(messages[-1].body, [])
        self.assertIn("{Attachments}", messages[-1].extra)

    def test_header_requires_a_blank_line(self):
        text = (
            "\n[3/14/2021 9:05 AM] alice\nquoting:\n"
            "[3/14/2021 9:06 AM] bob\nstill me\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.txt"
            path.write_text(text, encoding="utf-8")
            messages = list(bdb.parse_file(path))
        self.assertEqual(len(messages), 1)
        self.assertIn("[3/14/2021 9:06 AM] bob", messages[0].body)

    def test_index_contains_messages_runes_and_provenance(self):
        with archive() as root:
            with sqlite3.connect(root / "discord.db") as database:
                self.assertEqual(
                    database.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 4,
                )
                self.assertEqual(
                    database.execute(
                        "SELECT COUNT(*) FROM runes WHERE notation='numeric'"
                    ).fetchone()[0],
                    1,
                )
                file, size, digest = database.execute(
                    "SELECT file, bytes, sha256 FROM provenance"
                ).fetchone()
            data = (root / file).read_bytes()
            self.assertEqual(size, len(data))
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())
            self.assertFalse((root / "discord.db-wal").exists())

    def test_index_build_is_atomic(self):
        with archive() as root:
            database = root / "discord.db"
            before = database.read_bytes()
            with mock.patch.object(bdb, "build", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError), \
                     contextlib.redirect_stdout(io.StringIO()):
                    bdb.main()
            self.assertEqual(database.read_bytes(), before)
            self.assertFalse((root / "discord.db.building").exists())


class TestAgentInstructions(unittest.TestCase):
    def test_archive_reviewer_must_search_and_open_both_archives(self):
        instructions = (Path(__file__).parents[1] / "AGENTS.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("fresh-context archive reviewer", instructions)
        for command in (
            'tools.explog "OBJECT OPERATION TERMS"',
            "tools.explog show ID...",
            'tools.dsearch "OBJECT OPERATION TERMS"',
            "tools.dsearch show ID...",
        ):
            self.assertIn(command, instructions)

    def test_removed_explog_views_stay_out_of_solver_instructions(self):
        instructions = (Path(__file__).parents[1] / "AGENTS.md").read_text(
            encoding="utf-8",
        )
        for command in (
            "explog context", "explog collide", "explog related",
            "explog search", "explog archive", "explog handoff",
        ):
            self.assertNotIn(command, instructions)


class TestDsearch(unittest.TestCase):
    def test_search_returns_compact_individual_messages(self):
        with archive():
            code, output, _ = call_dsearch(["first"])
        self.assertEqual(code, 0)
        self.assertIn("1  discord/54-55.txt:", output)
        self.assertIn("first message", output)
        self.assertNotIn("second line", output)

    def test_search_json_has_ids_and_total_count(self):
        repeated = EXPORT + "".join(
            f"\n[3/14/2021 9:{10 + index} AM] solver{index}\nneedle {index}\n"
            for index in range(5)
        )
        with archive(repeated):
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
        self.assertIn("> 1", output)
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
            self.assertIn("no hits", call_dsearch([
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

    def test_missing_or_stale_schema_is_diagnosed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(dsearch, "DISCORD_DB", Path(temporary) / "missing"):
                self.assertEqual(call_dsearch(["first"])[0], 2)
        with archive() as root:
            with sqlite3.connect(root / "discord.db") as database:
                database.execute("DROP TABLE msg_fts")
            code, _, error = call_dsearch(["first"])
        self.assertEqual(code, 2)
        self.assertIn("rebuild", error)

    def test_index_and_query_share_rune_minimum(self):
        self.assertEqual(bdb.MIN_CANON, runes.MIN_INDEXED)


class TestExplog(unittest.TestCase):
    @contextlib.contextmanager
    def log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "research").mkdir()
            path = root / "research" / "local.jsonl"
            with mock.patch.multiple(explog, LOG=path, ROOT=root):
                yield path

    def call(self, argv):
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = explog.main(argv)
        return code, output.getvalue(), error.getvalue()

    def add_result(self, method, **fields):
        args = [
            "add", "--section", fields.pop("section", "all"),
            "--method", method, "--verdict", fields.pop("verdict", "disproved"),
        ]
        for name, value in fields.items():
            args.extend((f"--{name.replace('_', '-')}", str(value)))
        return self.call(args)

    def test_query_returns_many_compact_ranked_records(self):
        with self.log():
            self.add_result(
                "wide-period-bound", operation="search periodic additive keys",
                coverage="periods 2 through 36 with pass stall",
            )
            self.add_result(
                "square-key", operation="period 25 square key",
                coverage="one exact phase",
            )
            code, output, _ = self.call(["period 25 square key"])
        self.assertEqual(code, 0)
        self.assertIn("#1", output)
        self.assertIn("#2", output)
        self.assertLess(output.index("#2"), output.index("#1"))
        self.assertIn("matched:", output)

    def test_query_json_is_compact_and_show_returns_full_records(self):
        with self.log():
            self.add_result(
                "payload-key", operation="apply payload as rune key",
                coverage="all 256 offsets", notes="decisive cobalt null",
            )
            _, output, _ = self.call(["payload key", "--json"])
            payload = json.loads(output)
            self.assertEqual(payload["hits"], 1)
            self.assertNotIn("notes", payload["results"][0])
            _, output, _ = self.call(["show", "1", "--json"])
            self.assertEqual(json.loads(output)[0]["notes"], "decisive cobalt null")

    def test_query_uses_object_aliases(self):
        with self.log():
            self.add_result(
                "digest-operation", object="page 56 digest",
                operation="hash one source",
            )
            _, output, _ = self.call(["deep web hash"])
        self.assertIn("digest-operation", output)

    def test_show_rejects_unknown_ids(self):
        with self.log():
            code, _, error = self.call(["show", "999"])
        self.assertEqual(code, 2)
        self.assertIn("unknown Explog ids", error)

    def test_running_lists_only_current_unresolved_locks(self):
        with self.log():
            self.call([
                "add", "--section", "all", "--method", "closed-lock",
                "--verdict", "running", *RUNNING,
            ])
            self.call([
                "add", "--section", "all", "--method", "closed-lock",
                "--verdict", "disproved", "--coverage", "one operation",
            ])
            self.call([
                "add", "--section", "all", "--method", "live-lock",
                "--verdict", "running", *RUNNING,
            ])
            _, output, _ = self.call(["running"])
        self.assertIn("live-lock", output)
        self.assertNotIn("closed-lock", output)

    def test_running_claim_requires_compact_coordination_fields(self):
        with self.log() as path:
            code, _, _ = self.call([
                "add", "--section", "all", "--method", "missing-decision",
                "--object", "object", "--operation", "operation",
                "--verdict", "running",
            ])
            self.assertEqual(code, 2)
            code, _, _ = self.call([
                "add", "--section", "all", "--method", "bloated",
                "--verdict", "running", *RUNNING, "--notes", "essay",
            ])
            self.assertEqual(code, 2)
            self.assertFalse(path.exists())

    def test_result_inherits_and_resolves_matching_claim(self):
        with self.log() as path:
            self.call([
                "add", "--section", "0.5", "--method", "operation",
                "--verdict", "running", *RUNNING,
            ])
            self.call([
                "add", "--section", "0.5", "--method", "operation",
                "--verdict", "disproved", "--coverage", "exact phase",
            ])
            result = json.loads(path.read_text().splitlines()[-1])
        self.assertEqual(result["resolves"], [1])
        self.assertEqual(result["object"], "canonical test object")

    def test_ids_increment_and_corrupt_log_blocks_append(self):
        with self.log() as path:
            for index in range(3):
                self.add_result(f"method-{index}")
            ids = [json.loads(line)["id"] for line in path.read_text().splitlines()]
            self.assertEqual(ids, [1, 2, 3])
            with path.open("a", encoding="utf-8") as file:
                file.write("not json\n")
            code, _, _ = self.add_result("method-4")
            self.assertEqual(code, 2)

    def test_concurrent_adds_receive_unique_ids(self):
        import fcntl

        if explog.fcntl is None:
            self.skipTest("fcntl unavailable")
        real_flock = fcntl.flock

        def slow(file, operation):
            real_flock(file, operation)
            if operation == fcntl.LOCK_UN:
                time.sleep(0.02)

        with self.log() as path, mock.patch.object(
            explog, "fcntl",
            mock.Mock(flock=slow, LOCK_EX=fcntl.LOCK_EX, LOCK_UN=fcntl.LOCK_UN),
        ), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            workers = [
                threading.Thread(
                    target=explog.main,
                    args=(["add", "--section", "all", "--method", f"m{i}",
                           "--verdict", "disproved"],),
                )
                for i in range(6)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            ids = [json.loads(line)["id"] for line in path.read_text().splitlines()]
        self.assertEqual(sorted(ids), [1, 2, 3, 4, 5, 6])

    def test_current_preserves_arms_and_explicit_resolutions(self):
        entries = [
            {"id": 1, "section": "all", "method": "m", "verdict": "running"},
            {"id": 2, "section": "all", "method": "m", "arm": "a",
             "verdict": "disproved"},
            {"id": 3, "section": "all", "method": "m", "arm": "b",
             "verdict": "underpowered"},
            {"id": 4, "section": "all", "method": "other",
             "resolves": [2], "verdict": "survey"},
        ]
        self.assertEqual([entry["id"] for entry in explog.current(entries)], [3, 4])

    def test_managed_wake_writes_to_its_own_shard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shards = root / "research" / "explog"
            shards.parent.mkdir()
            with mock.patch.multiple(
                explog, ROOT=root, LOG=shards, SHARD_DIR=shards,
            ), mock.patch.dict(os.environ, {"CICADA_WAKE_ID": "test-wake"}):
                code, _, _ = self.add_result("sharded")
            self.assertEqual(code, 0)
            entry = json.loads((shards / "test-wake.jsonl").read_text())
            self.assertEqual(entry["id"], "test-wake:1")


class TestWorktree(unittest.TestCase):
    @staticmethod
    def result(stdout="", returncode=0):
        return mock.Mock(stdout=stdout, stderr="", returncode=returncode)

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
        self.assertEqual(commands[0], ["git", "fetch", "origin", "main"])
        self.assertIn([
            "git", "worktree", "add", "-b", branch, str(path), "abc123",
        ], commands)

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
                return self.result(" M HISTORY.md\n")
            return self.result()

        with self.assertRaisesRegex(worktree.WorktreeError, "commit the wake"):
            worktree.publish(root=Path("/wake"), runner=runner)

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
