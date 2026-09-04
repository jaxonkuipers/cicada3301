"""Behavior tests for the small experiment ledger contract."""

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from solver import explog as ledger_mod
from solver.cli import explog

WAKE = "test-wake"


def hid(sequence):
    """The handle id the test wake's shard assigns to entry `sequence`."""
    return f"{WAKE}:{sequence}"


class TestExplog(unittest.TestCase):
    @contextlib.contextmanager
    def log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "research").mkdir()
            (root / "corpus").mkdir()
            (root / "corpus" / "route.csv").write_text(
                "route,round\nR12.1,2012\nR14.7,2014\n", encoding="utf-8",
            )
            evidence = root / "research" / "campaigns" / "test" / "FINDINGS.md"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("findings\n", encoding="utf-8")
            self.ledger = ledger_mod.Ledger(root=root)
            with mock.patch.dict(os.environ, {"CICADA_WAKE_ID": WAKE}):
                yield self.ledger.shard(WAKE)

    @staticmethod
    def running(object_="test object", operation="exact operation"):
        return [
            "add", "--verdict", "running", "--campaign", "test-campaign",
            "--route", "R14.7", "--object", object_, "--operation", operation,
            "--decision", "positive favors a reader; negative favors lost state",
        ]

    def call(self, argv):
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = explog.main(argv, ledger=self.ledger)
        return code, output.getvalue(), error.getvalue()

    def close(self, entry_id=None, verdict="negative", **fields):
        evidence = fields.pop(
            "evidence", "research/campaigns/test/FINDINGS.md",
        )
        args = [
            "add", "--verdict", verdict,
            "--resolves", str(hid(1) if entry_id is None else entry_id),
            "--coverage", fields.pop("coverage", "all 256 offsets and two controls"),
            "--result", fields.pop("result", "zero hits; the selected relation fails"),
        ]
        if evidence is not None:
            args.extend(("--evidence", str(evidence)))
        for name, value in fields.items():
            args.extend((f"--{name.replace('_', '-')}", str(value)))
        return self.call(args)

    def test_verdicts_are_the_whole_lifecycle(self):
        self.assertEqual(
            ledger_mod.VERDICTS, ("running", "negative", "positive", "blocked"),
        )

    def test_running_claim_has_one_compact_shape(self):
        with self.log() as path:
            code, _, error = self.call([
                "add", "--verdict", "running", "--object", "object",
                "--operation", "operation",
            ])
            self.assertEqual(code, 2)
            self.assertIn("--decision", error)
            code, _, error = self.call(self.running() + ["--coverage", "premature"])
            self.assertEqual(code, 2)
            self.assertIn("result fields", error)
            self.assertFalse(path.exists())

    def test_running_claim_requires_a_canonical_route(self):
        with self.log() as path:
            args = self.running()
            route = args.index("--route")
            del args[route:route + 2]
            code, _, error = self.call(args)
            self.assertEqual(code, 2)
            self.assertIn("needs --route", error)

            args = self.running()
            args[args.index("--route") + 1] = "R14.8"
            code, _, error = self.call(args)
            self.assertEqual(code, 2)
            self.assertIn("unknown route R14.8", error)
            self.assertFalse(path.exists())

    def test_result_requires_live_claim_exact_coverage_and_result(self):
        with self.log():
            self.assertEqual(self.call(self.running())[0], 0)
            code, _, error = self.call([
                "add", "--verdict", "negative", "--resolves", "1",
                "--result", "failed",
            ])
            self.assertEqual(code, 2)
            self.assertIn("exact --coverage", error)
            code, _, error = self.call([
                "add", "--verdict", "negative", "--resolves", "1",
                "--coverage", "all cells",
            ])
            self.assertEqual(code, 2)
            self.assertIn("--result", error)
            code, _, error = self.call([
                "add", "--verdict", "negative", "--resolves", "999",
                "--coverage", "all cells", "--result", "failed",
                "--evidence", "research/campaigns/test/FINDINGS.md",
            ])
            self.assertEqual(code, 2)
            self.assertIn("unknown Explog ids", error)
            code, _, error = self.close(evidence=None)
            self.assertEqual(code, 2)
            self.assertIn("at least one --evidence", error)

    def test_result_inherits_claim_and_releases_lock(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            self.assertEqual(self.close(evidence="research/campaigns/test/FINDINGS.md")[0], 0)
            entries = [json.loads(line) for line in path.read_text().splitlines()]
            result = entries[-1]
            self.assertEqual(result["resolves"], hid(1))
            self.assertEqual(result["object"], "test object")
            self.assertEqual(result["operation"], "exact operation")
            self.assertEqual(result["campaign"], "test-campaign")
            self.assertEqual(result["route"], "R14.7")
            self.assertEqual(
                result["decision"],
                "positive favors a reader; negative favors lost state",
            )
            self.assertEqual(result["evidence"], ["research/campaigns/test/FINDINGS.md"])
            _, output, _ = self.call(["running"])
            self.assertEqual(output, "no entries\n")

    def test_administrative_blocked_release_needs_no_evidence(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            code, _, error = self.close(
                verdict="blocked",
                coverage="no cells; campaign ended by user",
                result="administrative release",
                evidence=None,
            )
            self.assertEqual(code, 0, error)
            result = json.loads(path.read_text().splitlines()[-1])
            self.assertNotIn("evidence", result)
            self.assertFalse(ledger_mod.current(self.ledger.read()))

    def test_result_evidence_must_be_a_file_inside_the_repository(self):
        with self.log() as path:
            root = self.ledger.root
            self.assertEqual(self.call(self.running())[0], 0)
            code, _, error = self.close(evidence="research/missing.md")
            self.assertEqual(code, 2)
            self.assertIn("not an existing regular file", error)
            code, _, error = self.close(evidence="research/campaigns/test")
            self.assertEqual(code, 2)
            self.assertIn("not an existing regular file", error)
            code, _, error = self.close(evidence="../outside.txt")
            self.assertEqual(code, 2)
            self.assertIn("leaves the repository", error)

            absolute = root / "research" / "campaigns" / "test" / "FINDINGS.md"
            self.assertEqual(self.close(evidence=str(absolute))[0], 0)
            result = json.loads(path.read_text().splitlines()[-1])
            self.assertEqual(
                result["evidence"], ["research/campaigns/test/FINDINGS.md"],
            )

    def test_duplicate_active_operation_is_rejected(self):
        with self.log():
            self.assertEqual(self.call(self.running("Page 56", "Hash Exact Body"))[0], 0)
            code, _, error = self.call(self.running("page-56", "hash exact body"))
        self.assertEqual(code, 2)
        self.assertIn("already reserved", error)

    def test_merged_duplicate_locks_do_not_block_other_writes_or_resolution(self):
        with self.log():
            claims = [
                {
                    "id": entry_id,
                    "created_at": f"2026-08-29T00:00:0{entry_id}+00:00",
                    "verdict": "running",
                    "campaign": f"campaign-{entry_id}",
                    "route": "R14.7",
                    "object": "same object",
                    "operation": "same operation",
                    "decision": "decision",
                }
                for entry_id in (1, 2)
            ]
            self.ledger.shard_dir.mkdir(parents=True)
            self.ledger.shard("peer").write_text(
                "".join(json.dumps(entry) + "\n" for entry in claims),
                encoding="utf-8",
            )
            self.assertTrue(ledger_mod.active_duplicate_errors(self.ledger.read()))
            code, _, warning = self.call(self.running("other", "other operation"))
            self.assertEqual(code, 0)
            self.assertIn("warning: running claim 2 duplicates", warning)
            self.assertEqual(self.close(entry_id=1)[0], 0)
            self.assertEqual(self.close(entry_id=2)[0], 0)
            self.assertFalse(ledger_mod.lifecycle_errors(self.ledger.read()))
            self.assertEqual(
                [entry["id"] for entry in ledger_mod.current(self.ledger.read())],
                [hid(1)],
            )

    def test_result_has_one_target_and_cannot_override_claim_identity(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            code, _, error = self.call([
                "add", "--verdict", "negative", "--resolves", "1",
                "--resolves", "1", "--coverage", "all cells",
                "--result", "failed",
            ])
            self.assertEqual(code, 2)
            self.assertIn("exactly one --resolves", error)
            for option, value in (
                ("--campaign", "replacement"),
                ("--route", "R12.1"),
                ("--object", "replacement object"),
                ("--operation", "replacement operation"),
                ("--decision", "replacement decision"),
            ):
                code, _, error = self.call([
                    "add", "--verdict", "negative", "--resolves", "1",
                    "--coverage", "all cells", "--result", "failed",
                    option, value,
                ])
                self.assertEqual(code, 2, option)
                self.assertIn("inherits claim identity", error, option)
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_search_is_direct_compact_and_opens_ids(self):
        with self.log():
            self.assertEqual(self.call(self.running("byte block", "apply cyclic key"))[0], 0)
            self.assertEqual(self.close(result="cobalt control passes; target has zero hits")[0], 0)
            code, output, error = self.call(["cobalt zero"])
            self.assertEqual(code, 0)
            self.assertIn(f"#{hid(2)} [negative]", output)
            self.assertIn("cobalt control passes", output)
            self.assertIn("1 of 1", error)
            _, output, _ = self.call(["cobalt", "--json"])
            payload = json.loads(output)
            self.assertEqual(payload["hits"], 1)
            self.assertEqual(payload["results"][0]["id"], hid(2))
            self.assertIn("result", payload["results"][0])
            _, output, _ = self.call(["show", hid(2), "--json"])
            self.assertEqual(
                json.loads(output)[0]["coverage"], "all 256 offsets and two controls",
            )

    def test_search_collapses_a_closed_claim_but_show_retains_it(self):
        with self.log():
            self.assertEqual(self.call(self.running("rare object", "rare operation"))[0], 0)
            self.assertEqual(self.close(result="the rare operation failed")[0], 0)
            _, output, _ = self.call(["rare", "--json"])
            payload = json.loads(output)
            self.assertEqual(payload["hits"], 1)
            self.assertEqual(payload["results"][0]["id"], hid(2))
            _, output, _ = self.call(["show", hid(1), hid(2), "--json"])
            self.assertEqual(
                [entry["id"] for entry in json.loads(output)], [hid(1), hid(2)],
            )

    def test_show_and_query_validate_inputs(self):
        with self.log():
            code, _, error = self.call(["show", "999"])
            self.assertEqual(code, 2)
            self.assertIn("unknown Explog ids", error)
            self.assertEqual(self.call(["--limit", "0", "anything"])[0], 2)
            self.assertEqual(self.call(["---"])[0], 2)

    def test_likely_command_typo_errors_but_multiword_query_works(self):
        with self.log():
            code, _, error = self.call(["runing"])
            self.assertEqual(code, 2)
            self.assertIn("did you mean 'running'", error)
            self.assertEqual(self.call(self.running())[0], 0)
            self.assertEqual(self.close(result="cobalt zero")[0], 0)
            code, output, _ = self.call(["cobalt", "zero"])
            self.assertEqual(code, 0)
            self.assertIn(f"#{hid(2)} [negative]", output)

    def test_corrupt_log_blocks_append(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            with path.open("a", encoding="utf-8") as output:
                output.write("not json\n")
            code, _, error = self.call(self.running("other", "other operation"))
        self.assertEqual(code, 2)
        self.assertIn("refusing to append", error)

    def test_non_object_and_invalid_utf8_rows_have_file_diagnostics(self):
        with self.log() as path:
            path.parent.mkdir(parents=True)
            path.write_text("[]\n", encoding="utf-8")
            code, output, error = self.call(["running"])
            self.assertEqual(code, 0)
            self.assertEqual(output, "no entries\n")
            self.assertIn("research/explog/test-wake.jsonl:1", error)
            self.assertIn("expected object", error)
            self.assertIn("showing readable records", error)

            path.write_bytes(b"\xff\n")
            code, output, error = self.call(["running"])
            self.assertEqual(code, 0)
            self.assertEqual(output, "no entries\n")
            self.assertIn("research/explog/test-wake.jsonl", error)
            self.assertIn("not valid UTF-8", error)
            self.assertIn("showing readable records", error)

    def test_reference_drift_warns_without_disabling_reads_or_unrelated_adds(self):
        with self.log():
            self.assertEqual(self.call(self.running())[0], 0)
            self.assertEqual(self.close()[0], 0)
            root = self.ledger.root
            (root / "research" / "campaigns" / "test" / "FINDINGS.md").unlink()
            (root / "corpus" / "route.csv").write_text(
                "route,round\nR12.1,2012\n", encoding="utf-8",
            )

            code, output, warning = self.call(["show", hid(2)])
            self.assertEqual(code, 0)
            self.assertIn("zero hits", output)
            self.assertIn("stale route", warning)
            self.assertIn("stale evidence", warning)

            args = self.running("other object", "other operation")
            args[args.index("--route") + 1] = "R12.1"
            code, _, warning = self.call(args)
            self.assertEqual(code, 0)
            self.assertIn("stale route", warning)
            self.assertIn("stale evidence", warning)

    def test_structural_drift_warns_on_reads_and_blocks_append(self):
        with self.log() as path:
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({
                    "id": 1,
                    "created_at": "2026-08-29T00:00:00+00:00",
                    "verdict": "maybe",
                    "route": "R14.7",
                }) + "\n",
                encoding="utf-8",
            )
            code, output, warning = self.call(["running"])
            self.assertEqual(code, 0)
            self.assertEqual(output, "no entries\n")
            self.assertIn("invalid Explog ledger", warning)

            code, _, error = self.call(self.running("other", "other operation"))
            self.assertEqual(code, 2)
            self.assertIn("refusing to append", error)

    def test_concurrent_claims_receive_unique_ids(self):
        if ledger_mod.fcntl is None:
            self.skipTest("fcntl unavailable")
        with self.log() as path, contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            workers = [
                threading.Thread(
                    target=explog.main,
                    args=(self.running(f"object {index}", f"operation {index}"),),
                    kwargs={"ledger": self.ledger},
                )
                for index in range(8)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            entries = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(
            sorted(entry["id"] for entry in entries),
            [hid(sequence) for sequence in range(1, 9)],
        )

    def test_wake_shard_records_handle_ids_and_its_own_path(self):
        with self.log() as path:
            code, _, _ = self.call(self.running())
            self.assertEqual(code, 0)
            entry = json.loads(path.read_text())
            self.assertEqual(entry["id"], hid(1))
            self.assertEqual(entry["log_path"], "research/explog/test-wake.jsonl")

    def test_invalid_wake_id_errors_and_unmanaged_fallback_warns(self):
        with self.log():
            with mock.patch.dict(
                os.environ, {"CICADA_WAKE_ID": "bad_wake"}, clear=True,
            ):
                code, _, error = self.call(self.running())
            self.assertEqual(code, 2)
            self.assertIn("invalid CICADA_WAKE_ID", error)
            self.assertFalse(self.ledger.shard_dir.exists())

        runner = mock.Mock(return_value=mock.Mock(stdout="main\n"))
        error = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), \
             contextlib.redirect_stderr(error):
            self.assertEqual(ledger_mod.current_wake_id(runner), "local")
        self.assertIn("fallback Explog wake id", error.getvalue())


if __name__ == "__main__":
    unittest.main()
