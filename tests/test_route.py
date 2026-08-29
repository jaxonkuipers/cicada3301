"""Integrity checks for the historical route and its communication index."""

import csv
import re
import unittest
from pathlib import Path

from solver.paths import CORPUS

ROUTE_ID = re.compile(r"^R\d{2}\.\d+$")
STEP_FIELDS = (
    "**Solver state.**",
    "**Dependencies consumed.**",
    "**Artifact and action.**",
    "**Resulting state.**",
    "**State handed forward.**",
    "**Evidence.**",
    "**Later evidence.**",
    "**Preservation boundary.**",
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


class RouteIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route_rows = rows(CORPUS / "route.csv")
        cls.route_ids = {row["route"] for row in cls.route_rows}

    def test_route_ids_paths_and_predecessors_are_canonical(self):
        ids = [row["route"] for row in self.route_rows]
        paths = [row["path"] for row in self.route_rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(ROUTE_ID.fullmatch(route) for route in ids))
        for row in self.route_rows:
            self.assertIn(row["status"], {"authenticated", "reproduced", "reported", "partial"})
            if row["predecessor"]:
                self.assertIn(row["predecessor"], self.route_ids)
                self.assertNotEqual(row["predecessor"], row["route"])
            self.assertTrue((CORPUS / row["path"]).is_file())

    def test_predecessors_form_a_topological_dag(self):
        seen: set[str] = set()
        for row in self.route_rows:
            predecessor = row["predecessor"]
            if predecessor:
                self.assertIn(predecessor, seen, (row["route"], predecessor))
            seen.add(row["route"])

    def test_every_step_has_the_state_handoff_fields(self):
        indexed = {CORPUS / row["path"] for row in self.route_rows}
        present = set((CORPUS / "steps").glob("R*.md"))
        self.assertEqual(present, indexed)
        route_map = (CORPUS / "README.md").read_text(encoding="utf-8")
        for row in self.route_rows:
            path = CORPUS / row["path"]
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith(f"# {row['route']}"), path)
            for field in STEP_FIELDS:
                self.assertIn(field, text, f"{path}: {field}")
            self.assertIn(f"[{row['route']}]({row['path']})", route_map)

    def test_communications_use_route_ids_and_existing_artifacts(self):
        communications = rows(CORPUS / "communications.csv")
        self.assertTrue(communications)
        self.assertNotIn("stage", communications[0])
        communication_ids = [row["id"] for row in communications]
        self.assertEqual(len(communication_ids), len(set(communication_ids)))
        self.assertEqual(
            [int(row["sequence"]) for row in communications],
            list(range(1, len(communications) + 1)),
        )
        for row in communications:
            self.assertIn(row["route"], self.route_ids)
            self.assertTrue((CORPUS / row["path"]).is_file(), row["path"])

    def test_route_markdown_links_resolve(self):
        documents = [CORPUS / "README.md", *(CORPUS / "steps").glob("*.md")]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
                target = target.split("#", 1)[0]
                if target and "://" not in target:
                    self.assertTrue((document.parent / target).resolve().exists(), (
                        document, target,
                    ))

if __name__ == "__main__":
    unittest.main()
