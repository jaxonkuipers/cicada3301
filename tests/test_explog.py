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

from solver.cli import explog


class TestExplog(unittest.TestCase):
    @contextlib.contextmanager
    def log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "research").mkdir()
            path = root / "research" / "local.jsonl"
            with mock.patch.multiple(explog, LOG=path, ROOT=root):
                yield path

    @staticmethod
    def running(object_="test object", operation="exact operation"):
        return [
            "add", "--verdict", "running", "--campaign", "test-campaign",
            "--route", "R14.7", "--object", object_, "--operation", operation,
            "--decision", "positive favors a reader; negative favors lost state",
        ]

    @staticmethod
    def call(argv):
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = explog.main(argv)
        return code, output.getvalue(), error.getvalue()

    def close(self, entry_id=1, verdict="negative", **fields):
        args = [
            "add", "--verdict", verdict, "--resolves", str(entry_id),
            "--coverage", fields.pop("coverage", "all 256 offsets and two controls"),
            "--result", fields.pop("result", "zero hits; the selected relation fails"),
        ]
        for name, value in fields.items():
            args.extend((f"--{name.replace('_', '-')}", str(value)))
        return self.call(args)

    def test_verdicts_are_the_whole_lifecycle(self):
        self.assertEqual(explog.VERDICTS, ("running", "negative", "positive", "blocked"))

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
            self.assertEqual(path.read_text(), "")

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
            ])
            self.assertEqual(code, 2)
            self.assertIn("unknown Explog ids", error)

    def test_result_inherits_claim_and_releases_lock(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            self.assertEqual(self.close(evidence="research/campaigns/test/FINDINGS.md")[0], 0)
            entries = [json.loads(line) for line in path.read_text().splitlines()]
            result = entries[-1]
            self.assertEqual(result["resolves"], 1)
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

    def test_duplicate_active_operation_is_rejected(self):
        with self.log():
            self.assertEqual(self.call(self.running("Page 56", "Hash Exact Body"))[0], 0)
            code, _, error = self.call(self.running("page-56", "hash exact body"))
        self.assertEqual(code, 2)
        self.assertIn("already reserved", error)

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
            self.assertIn("#2 [negative]", output)
            self.assertIn("cobalt control passes", output)
            self.assertIn("1 of 1", error)
            _, output, _ = self.call(["cobalt", "--json"])
            payload = json.loads(output)
            self.assertEqual(payload["hits"], 1)
            self.assertEqual(payload["results"][0]["id"], 2)
            self.assertIn("result", payload["results"][0])
            _, output, _ = self.call(["show", "2", "--json"])
            self.assertEqual(json.loads(output)[0]["coverage"], "all 256 offsets and two controls")

    def test_search_collapses_a_closed_claim_but_show_retains_it(self):
        with self.log():
            self.assertEqual(self.call(self.running("rare object", "rare operation"))[0], 0)
            self.assertEqual(self.close(result="the rare operation failed")[0], 0)
            _, output, _ = self.call(["rare", "--json"])
            payload = json.loads(output)
            self.assertEqual(payload["hits"], 1)
            self.assertEqual(payload["results"][0]["id"], 2)
            _, output, _ = self.call(["show", "1", "2", "--json"])
            self.assertEqual([entry["id"] for entry in json.loads(output)], [1, 2])

    def test_show_and_query_validate_inputs(self):
        with self.log():
            code, _, error = self.call(["show", "999"])
            self.assertEqual(code, 2)
            self.assertIn("unknown Explog ids", error)
            self.assertEqual(self.call(["--limit", "0", "anything"])[0], 2)
            self.assertEqual(self.call(["---"])[0], 2)

    def test_corrupt_log_blocks_append(self):
        with self.log() as path:
            self.assertEqual(self.call(self.running())[0], 0)
            with path.open("a", encoding="utf-8") as output:
                output.write("not json\n")
            code, _, error = self.call(self.running("other", "other operation"))
        self.assertEqual(code, 2)
        self.assertIn("refusing to append", error)

    def test_concurrent_claims_receive_unique_ids(self):
        if explog.fcntl is None:
            self.skipTest("fcntl unavailable")
        with self.log() as path, contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            workers = [
                threading.Thread(
                    target=explog.main,
                    args=(self.running(f"object {index}", f"operation {index}"),),
                )
                for index in range(8)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            entries = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(sorted(entry["id"] for entry in entries), list(range(1, 9)))

    def test_managed_wake_uses_own_shard_and_records_its_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shards = root / "research" / "explog"
            shards.parent.mkdir()
            with mock.patch.multiple(
                explog, ROOT=root, LOG=shards, SHARD_DIR=shards,
            ), mock.patch.dict(os.environ, {"CICADA_WAKE_ID": "test-wake"}):
                code, _, _ = self.call(self.running())
            self.assertEqual(code, 0)
            entry = json.loads((shards / "test-wake.jsonl").read_text())
            self.assertEqual(entry["id"], "test-wake:1")
            self.assertEqual(entry["log_path"], "research/explog/test-wake.jsonl")


if __name__ == "__main__":
    unittest.main()
