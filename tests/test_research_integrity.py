"""Mechanical checks for committed Explog data and its lifecycle contract."""

import csv
import json
import subprocess
import unittest

from solver.cli import explog
from solver.paths import ROOT


class CommittedExplogIntegrity(unittest.TestCase):
    """Validate HEAD without observing another wake's uncommitted shards."""

    def test_committed_shards_parse_and_follow_the_lifecycle(self):
        listed = subprocess.run(
            [
                "git", "ls-tree", "-r", "--name-only", "HEAD",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        committed_paths = frozenset(listed.stdout.splitlines())
        paths = sorted(
            path for path in committed_paths
            if path.startswith("research/explog/") and path.endswith(".jsonl")
        )
        entries = []
        for path in paths:
            source = subprocess.run(
                ["git", "show", f"HEAD:{path}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout
            try:
                text = source.decode("utf-8")
            except UnicodeDecodeError as exc:
                self.fail(f"{path} is not valid UTF-8 at byte {exc.start}")
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.fail(f"{path}:{line_number} is not valid JSON: {exc}")
                self.assertIsInstance(entry, dict, f"{path}:{line_number}")
                self.assertEqual(entry.get("log_path"), path, f"{path}:{line_number}")
                entries.append(entry)
        route_source = subprocess.run(
            ["git", "show", "HEAD:corpus/route.csv"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        routes = frozenset(
            row["route"] for row in csv.DictReader(route_source)
        )
        self.assertFalse(explog.lifecycle_errors(entries))
        self.assertFalse(explog.reference_warnings(
            entries, known_routes=routes, known_evidence=committed_paths,
        ))


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
            "evidence": ["research/SETTLED.md"],
        }
        entry.update(changes)
        return entry

    def test_resolution_is_id_based_not_created_or_merged_order(self):
        self.assertFalse(explog.ledger_errors([self.result(), self.claim()]))
        other_claim = {
            **self.claim(3), "object": "OBJECT", "operation": "OPERATION",
        }
        other_result = self.result(entry_id=4, target=3, object="OBJECT",
                                   operation="OPERATION")
        entries = [other_result, self.result(), other_claim, self.claim()]
        self.assertFalse(explog.ledger_errors(entries))
        self.assertFalse(explog.current(entries))

    def test_unknown_resolution_is_rejected(self):
        errors = explog.ledger_errors([self.result(target=999), self.claim()])
        self.assertTrue(any("unknown reference" in error for error in errors))

    def test_duplicate_ids_are_rejected(self):
        errors = explog.ledger_errors([self.claim(), self.claim()])
        self.assertTrue(any("duplicate Explog id" in error for error in errors))

    def test_record_shape_is_part_of_the_lifecycle_contract(self):
        for change, phrase in (
            ({"id": "bad id"}, "invalid Explog id"),
            ({"verdict": "maybe"}, "invalid verdict"),
            ({"object": ""}, "lacks object"),
        ):
            errors = explog.ledger_errors([{**self.claim(), **change}])
            self.assertTrue(any(phrase in error for error in errors), errors)
        errors = explog.ledger_errors([
            self.claim(), self.result(evidence=[]),
        ])
        self.assertTrue(any("lacks evidence" in error for error in errors), errors)
        errors = explog.ledger_errors([
            {**self.claim(), "resolves": "other:1"},
        ])
        self.assertTrue(any("contains result fields" in error for error in errors), errors)
        errors = explog.reference_warnings(
            [{**self.claim(), "route": "R99.9"}],
            known_routes=frozenset({"R14.7"}),
        )
        self.assertTrue(any("unknown route" in error for error in errors), errors)
        errors = explog.reference_warnings(
            [self.claim(), self.result(evidence=["research/missing.md"])],
            known_routes=frozenset({"R14.7"}),
            known_evidence=frozenset(),
        )
        self.assertTrue(any("absent from the snapshot" in error for error in errors), errors)

    def test_snapshot_validation_uses_snapshot_routes_and_files(self):
        entries = [self.claim(), self.result()]
        self.assertFalse(explog.reference_warnings(
            entries,
            known_routes=frozenset({"R14.7"}),
            known_evidence=frozenset({"research/SETTLED.md"}),
        ))
        errors = explog.reference_warnings(
            entries,
            known_routes=frozenset({"R12.1"}),
            known_evidence=frozenset(),
        )
        self.assertTrue(any("unknown route" in error for error in errors), errors)
        self.assertTrue(any("absent from the snapshot" in error for error in errors), errors)

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
        errors = explog.active_duplicate_errors([self.claim(), duplicate])
        self.assertTrue(any("duplicates active operation" in error for error in errors))
        self.assertFalse(explog.ledger_errors([self.claim(), duplicate]))

        closed_then_reopened = [
            self.claim(), self.result(), {**duplicate, "id": 3},
        ]
        self.assertFalse(explog.ledger_errors(closed_then_reopened))


if __name__ == "__main__":
    unittest.main()
