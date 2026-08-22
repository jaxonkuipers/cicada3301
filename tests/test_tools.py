"""Tests for tools/: the export parser, the index, the search, the log.

lib/ was well covered and tools/ was not covered at all, which mattered most
for `build_discord_db.parse_file` -- its blank-line-before-header rule was
justified by "verified across all 109,917 messages", a claim with no
executable form. These cases pin the heuristics against synthetic exports so
the next edit is checked rather than re-argued.

Nothing here touches the real discord/ or discord.db; every test builds its
own export in a temporary directory.
"""

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from lib import runes
from tools import build_discord_db as bdb
from tools import dsearch, explog

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


@contextlib.contextmanager
def archive(text=EXPORT, name="54-55.txt"):
    """A temporary discord/ + built index, with both modules pointed at it."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        exports, db = root / "discord", root / "discord.db"
        exports.mkdir()
        (exports / name).write_text(text, encoding="utf-8")
        with (
            mock.patch.multiple(bdb, DISCORD=exports, DISCORD_DB=db, ROOT=root),
            mock.patch.multiple(dsearch, DISCORD=exports, DISCORD_DB=db, ROOT=root),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                bdb.main()
            yield root


def run(argv):
    """dsearch.main -> (exit code, stdout). stderr is discarded."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = dsearch.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def parse(text):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "9-9.txt"
        p.write_text(text, encoding="utf-8")
        return list(bdb.parse_file(p))


class TestParseFile(unittest.TestCase):
    def test_messages_authors_and_channel_name(self):
        msgs = parse(EXPORT)
        self.assertEqual([m.author for m in msgs], ["alice", "bob", "carol", "dave"])
        self.assertEqual([m.seq for m in msgs], [1, 2, 3, 4])
        self.assertEqual(msgs[0].ts, "2021-03-14 09:05")
        self.assertEqual(msgs[0].channel_name, "Liber-Primus / 54-55-jpg")
        self.assertTrue(msgs[1].pinned)
        self.assertFalse(msgs[0].pinned)
        # " (pinned)" is a marker, not part of the name.
        self.assertEqual(msgs[1].author, "bob")

    def test_body_and_extra_are_separated(self):
        msgs = parse(EXPORT)
        self.assertEqual(msgs[1].body, ["runes ᚠᚢᚦᚩᚱᚳ here", "second line"])
        self.assertEqual(msgs[3].body, [])
        self.assertIn("{Attachments}", msgs[3].extra[0])

    def test_header_must_follow_a_blank_line(self):
        # A quoted header pasted mid-paragraph is body text. Without the rule
        # it fabricates a message, and the real one is emitted twice.
        msgs = parse(
            "\n[3/14/2021 9:05 AM] alice\nquoting:\n[3/14/2021 9:06 AM] bob\nstill me\n"
        )
        self.assertEqual(len(msgs), 1)
        self.assertIn("[3/14/2021 9:06 AM] bob", msgs[0].body)

    def test_impossible_date_stays_body_text(self):
        msgs = parse("\n[3/14/2021 9:05 AM] alice\n\n[1/2/2020 9:99 PM] nope\ntail\n")
        self.assertEqual(len(msgs), 1)
        self.assertIn("[1/2/2020 9:99 PM] nope", msgs[0].body)

    def test_preamble_before_first_message_is_dropped(self):
        self.assertEqual(parse("Guild: X\nChannel: Y\nnoise\n"), [])

    def test_crlf_export(self):
        (m,) = parse("\r\n[3/14/2021 9:05 AM] alice\r\nhello\r\n")
        self.assertEqual(m.body, ["hello"])

    def test_line_numbers_are_citable(self):
        msgs = parse(EXPORT)
        lines = EXPORT.split("\n")
        for m in msgs:
            self.assertIn(m.author, lines[m.line - 1])


class TestIndex(unittest.TestCase):
    def test_build_indexes_messages_and_runes(self):
        with archive() as root:
            db = sqlite3.connect(root / "discord.db")
            db.row_factory = sqlite3.Row
            self.assertEqual(db.execute("SELECT count(*) c FROM messages").fetchone()["c"], 4)
            canons = {r["notation"]: r["canon"] for r in db.execute("SELECT * FROM runes")}
            self.assertIn("runic", canons)
            self.assertEqual(len(canons["runic"]), 6)  # ᚠᚢᚦᚩᚱᚳ
            self.assertEqual(len(canons["numeric"]), 4)  # 19, 21, 23, 27
            # The +/-1 matrix must NOT be indexed: '-1' is a sign, and its rows
            # are separate sequences. Both leaks would show up as extra runs.
            self.assertEqual(
                db.execute("SELECT count(*) c FROM runes WHERE notation='numeric'")
                .fetchone()["c"],
                1,
            )
            db.close()

    def test_provenance_records_the_source(self):
        with archive() as root:
            db = sqlite3.connect(root / "discord.db")
            (row,) = db.execute("SELECT file, bytes FROM provenance").fetchall()
            self.assertEqual(row[0], "discord/54-55.txt")
            self.assertEqual(row[1], len(EXPORT.encode()))
            db.close()

    def test_no_wal_sidecars_left_behind(self):
        # A read-only open fails if they go missing later.
        with archive() as root:
            self.assertFalse((root / "discord.db-wal").exists())
            self.assertFalse((root / "discord.db-shm").exists())


class TestSearch(unittest.TestCase):
    def test_text_search_finds_and_cites(self):
        with archive():
            code, out = run(["first", "--window", "0"])
            self.assertEqual(code, 0)
            self.assertIn("first message", out)
            self.assertIn("discord/54-55.txt:", out)

    def test_zero_hits_exits_zero(self):
        # A negative result is a result; a strict caller must record it.
        with archive():
            code, out = run(["nonexistentterm"])
            self.assertEqual(code, 0)
            self.assertIn("no hits", out)

    def test_rune_query_matches_across_notations(self):
        with archive():
            for q in ("ᚠᚢᚦᚩᚱᚳ", "0 1 2 3 4 5", "F-U-TH-O-R-C"):
                code, out = run(["--runes", q, "--window", "0", "--json"])
                self.assertEqual(code, 0, q)
                got = json.loads(out)
                self.assertEqual(got["hits"], 1, q)
                self.assertEqual(got["indices"], [0, 1, 2, 3, 4, 5], q)

    def test_json_searched_is_what_the_index_matched(self):
        # It used to carry the notation on the rune path and the query on the
        # text path, so a machine caller could not tell what had been searched.
        with archive():
            _, out = run(["--runes", "F-U-TH-O-R-C", "--json"])
            runic = json.loads(out)
            self.assertEqual(runic["searched"], "abcdef")  # canonical form
            self.assertEqual(runic["notation"], "translit")
            _, out = run(["first", "--json"])
            text = json.loads(out)
            self.assertEqual(text["searched"], "first")
            self.assertIsNone(text["notation"])
            self.assertIsNone(text["indices"])

    def test_zero_hit_json_has_the_same_shape(self):
        with archive():
            _, out = run(["nonexistentterm", "--json"])
            self.assertEqual(
                set(json.loads(out)),
                {"query", "searched", "notation", "indices", "hits", "conversations"},
            )

    def test_bad_rune_query_exits_two(self):
        with archive():
            for q in ("F-U-TH-2", "0,-2,-4,-6", "ᚠᚢ"):
                self.assertEqual(run(["--runes", q])[0], 2, q)

    def test_filters(self):
        with archive():
            self.assertIn("first message", run(["first", "--channel", "54-55"])[1])
            self.assertIn("no hits", run(["first", "--channel", "nope"])[1])
            self.assertIn("first message", run(["first", "--author", "ali"])[1])
            self.assertIn("no hits", run(["first", "--since", "2022"])[1])
            # --until covers the whole named period, not midnight on day one.
            self.assertIn("first message", run(["first", "--until", "2021"])[1])
            self.assertEqual(run(["first", "--since", "March"])[0], 2)

    def test_missing_index_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(dsearch, "DISCORD_DB", Path(tmp) / "absent.db"):
                self.assertEqual(run(["anything"])[0], 2)

    def test_degenerate_limits_are_refused(self):
        # SQLite reads LIMIT -1 as unbounded and LIMIT 0 as no rows; a negative
        # --window renders every hit as nothing while still counting it.
        with archive():
            for bad in (["--limit", "0"], ["--window", "-1"], ["--chars", "0"]):
                self.assertEqual(run(["first", *bad])[0], 2, bad)


    def test_invalid_fts_syntax_falls_back_to_quoted_terms(self):
        # The one path that deliberately answers a different question than the
        # one asked: every term becomes required, operators become literals.
        # It announces itself on stderr; nothing pinned that it still does.
        with archive():
            for query in ("auto(key", "first AND", "NEAR/"):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = dsearch.main([query])
                self.assertEqual(code, 0, query)
                self.assertIn("not valid FTS5 syntax", err.getvalue(), query)
                self.assertIn("every term required", err.getvalue(), query)

    def test_valid_fts_syntax_does_not_fall_back(self):
        with archive():
            for query in ("first", "firs*", "first OR second", "first NOT zzz"):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(err):
                    dsearch.main([query])
                self.assertNotIn("not valid FTS5", err.getvalue(), query)

    def test_query_with_nothing_searchable_exits_two(self):
        with archive():
            self.assertEqual(run(['"'])[0], 2)

    def test_main_returns_its_exit_code_without_raising(self):
        # die() and argparse both signal by raising, which made the -> int
        # annotation a half-truth and every caller catch two things.
        with archive(), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dsearch.main(["--limit", "0", "first"]), 2)
            self.assertEqual(dsearch.main(["first", "--runes", "0 1 2"]), 2)
            self.assertEqual(dsearch.main(["first"]), 0)

    def test_zero_hit_json_matches_the_populated_shape(self):
        with archive():
            empty = json.loads(run(["zzznothing", "--json"])[1])
            full = json.loads(run(["first", "--json"])[1])
            self.assertEqual(empty.keys(), full.keys())
            self.assertEqual(empty["hits"], 0)
            self.assertEqual(empty["conversations"], [])

    def test_wide_scattered_windows_do_not_blow_the_expression_depth(self):
        # The binding SQLite limit in windows() is the expression-tree depth
        # of 1000, not the parameter cap -- an OR chain hits it ~33x sooner,
        # and it surfaced as a traceback and exit 1 against a stated contract
        # of "0 = ran fine, 2 = bad query".
        many = "Guild: g\nChannel: c\n\n" + "".join(
            f"[3/14/2021 9:05 AM] u{i}\nmsg{i} needle\n\n" for i in range(3000)
        )
        with archive(text=many, name="big.txt"):
            code, out = run(["needle", "--limit", "2500", "--window", "0"])
            self.assertEqual(code, 0)
            self.assertEqual(out.count("needle"), 2500)

    def test_index_and_query_share_one_minimum_length(self):
        # Index at 3 and answer queries at 4 and every 3-rune citation is
        # silently unfindable; the two thresholds must come from one place.
        self.assertEqual(bdb.MIN_CANON, runes.MIN_INDEXED)
        with archive():
            self.assertEqual(run(["--runes", "F-U"])[0], 2)          # below it
            self.assertEqual(run(["--runes", "F-U-TH"])[0], 0)       # at it

    def test_unreadable_export_exits_two(self):
        with archive() as root:
            (root / "discord" / "54-55.txt").chmod(0o000)
            try:
                self.assertEqual(run(["first"])[0], 2)
            finally:
                (root / "discord" / "54-55.txt").chmod(0o644)

    def test_provenance_digests_what_was_indexed(self):
        # parse and hash now come from one read; they must not disagree.
        with archive() as root:
            db = sqlite3.connect(root / "discord.db")
            file, size, sha = db.execute(
                "SELECT file, bytes, sha256 FROM provenance"
            ).fetchone()
            db.close()
            data = (root / "discord" / "54-55.txt").read_bytes()
            self.assertEqual(size, len(data))
            self.assertEqual(sha, hashlib.sha256(data).hexdigest())

    def test_impossible_dates_are_refused(self):
        # ^\d{4}(-\d{2}(-\d{2})?)?$ matched '2021-99-99', and ts comparison
        # is on strings, so it quietly meant "from 2022 onward" and returned a
        # confident result set for a filter nobody asked for.
        with archive():
            for bad in ("2021-99-99", "2021-13-01", "2021-02-30", "2021-00-05"):
                self.assertEqual(run(["first", "--since", bad])[0], 2, bad)
            for good in ("2021", "2021-03", "2021-03-14"):
                self.assertEqual(run(["first", "--since", good])[0], 0, good)

    def test_query_and_runes_are_mutually_exclusive(self):
        # Running one and silently discarding the other answers a question
        # nobody asked; the rune path used to win without saying so.
        with archive():
            self.assertEqual(run(["first", "--runes", "0 1 2 3"])[0], 2)

    def test_stale_schema_is_diagnosed_not_blamed_on_the_query(self):
        # Every OperationalError used to read as invalid FTS5 syntax, so a
        # pre-ctx_fts index printed the wrong diagnosis and crashed anyway.
        with archive() as root:
            db = sqlite3.connect(root / "discord.db")
            db.execute("DROP TABLE ctx_fts")
            db.commit()
            db.close()
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(err):
                try:
                    code = dsearch.main(["first"])
                except SystemExit as e:
                    code = e.code
            self.assertEqual(code, 2)
            self.assertIn("rebuild", err.getvalue())
            self.assertNotIn("FTS5 syntax", err.getvalue())

    def test_wide_context_window_needs_no_parameter_per_seq(self):
        # The IN list grew with --limit x --window and raises "too many SQL
        # variables" on SQLite before 3.32; contiguous ranges bound it.
        with archive():
            code, out = run(["--runes", "F-U-TH-O-R-C", "--window", "500"])
            self.assertEqual(code, 0)
            self.assertIn("alice", out)

    def test_channels_honours_json_and_checks_staleness(self):
        with archive():
            code, out = run(["--channels", "--json"])
            self.assertEqual(code, 0)
            (ch,) = json.loads(out)["channels"]
            self.assertEqual(ch["channel"], "54-55")
            self.assertEqual(ch["messages"], 4)

    def test_replace_is_atomic_so_an_index_is_always_present(self):
        # replace() overwrites atomically; unlinking the index first bought
        # nothing and reopened the window the temp build exists to close.
        with archive() as root:
            db = root / "discord.db"
            seen = []
            real = Path.unlink
            def watched(self, missing_ok=False):
                seen.append(self.name)
                return real(self, missing_ok=missing_ok)
            with mock.patch.object(Path, "unlink", watched), \
                 contextlib.redirect_stdout(io.StringIO()):
                bdb.main()
            self.assertNotIn("discord.db", seen)  # never unlinked, only replaced
            self.assertTrue(db.exists())

    def test_failed_build_leaves_the_previous_index_intact(self):
        # executescript commits the schema, so unlinking first and failing
        # mid-build left a valid but empty index that answers everything with
        # nothing.
        with archive() as root:
            db = root / "discord.db"
            before = db.read_bytes()
            with mock.patch.object(bdb, "index_context", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError), \
                     contextlib.redirect_stdout(io.StringIO()):
                    bdb.main()
            self.assertEqual(db.read_bytes(), before)
            self.assertFalse((root / "discord.db.building").exists())
            self.assertEqual(run(["first"])[0], 0)


class TestExplog(unittest.TestCase):
    @contextlib.contextmanager
    def log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research").mkdir()
            with mock.patch.multiple(
                explog, LOG=root / "research" / "experiments.jsonl", ROOT=root
            ):
                yield root / "research" / "experiments.jsonl"

    def call(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = explog.main(argv)
        return code, out.getvalue()

    def test_add_list_search_round_trip(self):
        with self.log() as path:
            code, _ = self.call([
                "add", "--section", "0.5", "--method", "vigenere sweep",
                "--params", '{"key_len": "1-12"}', "--coverage", "all 29^3",
                "--verdict", "disproved", "--notes", "best fitness -3.9",
            ])
            self.assertEqual(code, 0)
            (entry,) = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(entry["id"], 1)
            self.assertEqual(entry["section"], "0.5")
            self.assertEqual(entry["params"], {"key_len": "1-12"})  # parsed as JSON
            self.assertIn("vigenere sweep", self.call(["search", "vigenere"])[1])
            self.assertIn("vigenere sweep", self.call(["list", "--section", "0.5"])[1])
            self.assertIn("no entries", self.call(["list", "--section", "0.6"])[1])
            self.assertIn("no entries", self.call(["list", "--verdict", "promising"])[1])

    def test_ids_increment(self):
        with self.log() as path:
            for _ in range(3):
                self.call(["add", "--section", "all", "--method", "m",
                           "--verdict", "running"])
            ids = [json.loads(x)["id"] for x in path.read_text().splitlines()]
            self.assertEqual(ids, [1, 2, 3])

    def test_unknown_section_is_refused(self):
        # The log is the coordination channel between agents that cannot see
        # each other: a typo'd section claims a target nobody else is watching.
        with self.log() as path:
            code, _ = self.call(["add", "--section", "0.05", "--method", "m",
                                 "--verdict", "running"])
            self.assertEqual(code, 2)
            self.assertFalse(path.exists())

    def test_non_json_params_kept_as_text(self):
        with self.log() as path:
            self.call(["add", "--section", "0.7", "--method", "m",
                       "--params", "key_len 1-12", "--verdict", "abandoned"])
            self.assertEqual(json.loads(path.read_text())["params"], "key_len 1-12")

    def test_corrupt_line_warns_and_does_not_stop_the_listing(self):
        with self.log() as path:
            path.write_text('{"id": 1, "section": "0.5"}\nnot json\n', encoding="utf-8")
            self.assertEqual(len(explog.read_log()), 1)

    def test_concurrent_adds_get_unique_ids(self):
        # `with open(...) as f, _locked(f):` unwinds _locked FIRST, so
        # releasing the lock there left the entry in the userspace buffer
        # until close -- long enough for the next process to read a log
        # without it and mint the same id. Measured: six concurrent adds all
        # got #1. The unlock->close gap is widened here to make the window
        # deterministic; _locked itself is untouched.
        import fcntl
        import threading

        if explog.fcntl is None:
            self.skipTest("no fcntl on this platform")
        real = fcntl.flock

        def slow(fd, op):
            real(fd, op)
            if op == fcntl.LOCK_UN:
                time.sleep(0.05)

        with self.log() as path:
            # One redirect around the whole block: redirect_stdout patches
            # the global sys.stdout, so per-thread redirects race each other.
            with mock.patch.object(explog, "fcntl", mock.Mock(
                flock=slow, LOCK_EX=fcntl.LOCK_EX, LOCK_UN=fcntl.LOCK_UN,
            )), contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                threads = [
                    threading.Thread(target=explog.main, args=([
                        "add", "--section", "0.5", "--method", f"m{i}",
                        "--verdict", "running",
                    ],))
                    for i in range(6)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
            ids = [json.loads(x)["id"] for x in path.read_text().splitlines() if x.strip()]
            self.assertEqual(len(ids), 6)
            self.assertEqual(sorted(ids), [1, 2, 3, 4, 5, 6])

    def test_corrupt_line_blocks_add_rather_than_minting_a_duplicate(self):
        # An unreadable line may hold the highest id, so max(ids)+1 can mint
        # one that already exists. Ids are how agents that cannot see each
        # other refer to a claim.
        with self.log() as path:
            path.write_text(
                '{"id": 1, "section": "0.5", "verdict": "running", "method": "a"}\n'
                '{"id": 2, "section": "0.5", "verdict": "running", "method": "b" OOPS\n',
                encoding="utf-8",
            )
            code, _ = self.call(
                ["add", "--section", "0.5", "--method", "x", "--verdict", "running"]
            )
            self.assertEqual(code, 2)
            self.assertEqual(len(path.read_text().splitlines()), 2)  # nothing appended

    def test_list_validates_section_like_add_does(self):
        # `list --section 0.05` printed "no entries" and exited 0, which
        # AGENTS.md step 4 tells the next agent to read as "unclaimed, take
        # it". Same typo, opposite direction, worse consequence.
        with self.log():
            self.assertEqual(self.call(["list", "--section", "0.05"])[0], 2)
            self.assertEqual(self.call(["list", "--section", "0.5"])[0], 0)
            self.assertEqual(self.call(["list", "--section", "all"])[0], 0)

    def test_empty_log_lists_cleanly(self):
        with self.log():
            code, out = self.call(["list"])
            self.assertEqual(code, 0)
            self.assertIn("no entries", out)


if __name__ == "__main__":
    unittest.main()
