"""Mechanical checks for the current research record."""

import collections
import json
import unittest

from solver.cli import explog
from solver.paths import ROOT


class ExperimentLogIntegrity(unittest.TestCase):
    def test_all_records_parse_and_handles_are_unique(self):
        bad = []
        entries = explog.read_log(bad)
        self.assertFalse(bad)
        handles = [str(entry.get("id")) for entry in entries]
        self.assertTrue(all(explog.HANDLE.fullmatch(handle) for handle in handles))
        duplicates = [
            handle for handle, count in collections.Counter(handles).items()
            if count > 1
        ]
        self.assertFalse(duplicates)

    def test_shard_entries_name_their_source_file(self):
        for path in explog.log_paths():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self.assertEqual(entry.get("log_path"), str(path.relative_to(ROOT)))

    def test_records_follow_the_small_lifecycle(self):
        entries = explog.read_log()
        self.assertFalse(explog.ledger_errors(entries))
        for entry in entries:
            self.assertIn(entry.get("verdict"), explog.VERDICTS)
            if entry.get("verdict") == "running":
                self.assertTrue(entry.get("object"))
                self.assertTrue(entry.get("operation"))
                self.assertTrue(entry.get("decision"))
            else:
                self.assertTrue(entry.get("coverage"))
                self.assertTrue(entry.get("result"))
                self.assertIsNotNone(entry.get("resolves"))


class ExplogLifecycleIntegrity(unittest.TestCase):
    @staticmethod
    def claim(entry_id=1):
        return {
            "id": entry_id,
            "verdict": "running",
            "campaign": "campaign",
            "route": "R14.7",
            "object": "object",
            "operation": "operation",
            "decision": "decision",
        }

    @classmethod
    def result(cls, entry_id=2, target=1, **changes):
        entry = {
            **cls.claim(target),
            "id": entry_id,
            "verdict": "negative",
            "resolves": target,
            "coverage": "all selected cells",
            "result": "no relation",
        }
        entry.update(changes)
        return entry

    def test_forward_reference_is_rejected(self):
        errors = explog.ledger_errors([self.result(), self.claim()])
        self.assertTrue(any("forward or unknown" in error for error in errors))

    def test_a_claim_can_be_closed_only_once(self):
        errors = explog.ledger_errors([
            self.claim(), self.result(), self.result(entry_id=3),
        ])
        self.assertTrue(any("already closed" in error for error in errors))

    def test_a_result_must_target_a_running_record(self):
        errors = explog.ledger_errors([
            self.claim(), self.result(), self.result(entry_id=3, target=2),
        ])
        self.assertTrue(any("non-running" in error for error in errors))

    def test_result_identity_matches_the_claim(self):
        self.assertFalse(explog.ledger_errors([self.claim(), self.result()]))
        for field in explog.INHERITED_FIELDS:
            errors = explog.ledger_errors([
                self.claim(), self.result(**{field: "different"}),
            ])
            self.assertTrue(any(field in error for error in errors), field)

    def test_active_object_operation_pair_is_unique(self):
        duplicate = {
            **self.claim(2),
            "object": "OBJECT",
            "operation": "operation",
        }
        errors = explog.ledger_errors([self.claim(), duplicate])
        self.assertTrue(any("duplicates active operation" in error for error in errors))

        closed_then_reopened = [
            self.claim(), self.result(), {**duplicate, "id": 3},
        ]
        self.assertFalse(explog.ledger_errors(closed_then_reopened))


if __name__ == "__main__":
    unittest.main()
