"""Coverage and byte-integrity tests for preserved corpus evidence."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from solver import corpus_manifest


class TestCorpusManifest(unittest.TestCase):
    @staticmethod
    def put(path: Path, data: bytes = b"evidence") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_manifest_covers_identity_and_artifacts_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            manifest = corpus / "MANIFEST.sha256"
            identity = corpus / "identity" / "key.asc"
            image = corpus / "records" / "R12.1" / "artifacts" / "final.jpg"
            route_doc = corpus / "records" / "R12.1" / "README.md"
            route_index = corpus / "route.csv"
            for path in (identity, image, route_doc, route_index):
                self.put(path)

            with mock.patch.multiple(
                corpus_manifest, ROOT=root, CORPUS=corpus, MANIFEST=manifest,
            ):
                corpus_manifest.update_manifest()
                text = manifest.read_text(encoding="utf-8")
                self.assertIn("corpus/identity/key.asc", text)
                self.assertIn("corpus/records/R12.1/artifacts/final.jpg", text)
                self.assertNotIn("README.md", text)
                self.assertNotIn("route.csv", text)
                self.assertEqual(corpus_manifest.verify_manifest(), [])

                image.write_bytes(b"changed")
                self.assertIn(
                    "sha256 mismatch: corpus/records/R12.1/artifacts/final.jpg",
                    corpus_manifest.verify_manifest(),
                )

    def test_new_immutable_file_and_removed_file_fail_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            manifest = corpus / "MANIFEST.sha256"
            first = corpus / "identity" / "key.asc"
            second = corpus / "records" / "R14.7" / "artifacts" / "page.jpg"
            self.put(first)
            with mock.patch.multiple(
                corpus_manifest, ROOT=root, CORPUS=corpus, MANIFEST=manifest,
            ):
                corpus_manifest.update_manifest()
                self.put(second)
                self.assertIn(
                    "immutable file is not manifested: "
                    "corpus/records/R14.7/artifacts/page.jpg",
                    corpus_manifest.verify_manifest(),
                )
                second.unlink()
                first.unlink()
                self.assertIn(
                    "manifest path is not immutable evidence: corpus/identity/key.asc",
                    corpus_manifest.verify_manifest(),
                )

    def test_manifest_rejects_paths_outside_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            manifest = corpus / "MANIFEST.sha256"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(f"{'0' * 64}  ../outside\n", encoding="utf-8")
            with mock.patch.multiple(
                corpus_manifest, ROOT=root, CORPUS=corpus, MANIFEST=manifest,
            ):
                errors = corpus_manifest.verify_manifest()
            self.assertIn("manifest line 1 leaves the repository", errors)

    def test_editor_guard_covers_every_immutable_root(self):
        settings = json.loads(
            (corpus_manifest.ROOT / ".claude" / "settings.json").read_text(
                encoding="utf-8"
            )
        )
        denied = set(settings["permissions"]["deny"])
        self.assertLessEqual(
            {
                "Edit(corpus/records/**/artifacts/**)",
                "Write(corpus/records/**/artifacts/**)",
                "Edit(corpus/identity/**)",
                "Write(corpus/identity/**)",
            },
            denied,
        )


if __name__ == "__main__":
    unittest.main()
