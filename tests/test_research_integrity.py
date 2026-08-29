"""Mechanical checks for the current research record."""

import collections
import json
import unittest

from lib.paths import ROOT
from tools import explog


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


if __name__ == "__main__":
    unittest.main()
