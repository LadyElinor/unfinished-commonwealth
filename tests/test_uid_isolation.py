"""Portable gates for the opt-in Linux demonstration; no privilege in unit tests."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("uid_isolation", ROOT / "scripts/uid_isolation.py")
isolation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(isolation)


class IsolationTests(unittest.TestCase):
    def test_identity_requires_all_ids_no_groups_no_capabilities_and_no_new_privileges(self):
        identity = {"Uid": "61002 61002 61002 61002", "Gid": "61002 61002 61002 61002",
                    "Groups": "", "CapEff": "0000000000000000", "NoNewPrivs": "1"}
        self.assertTrue(isolation.valid_identity(identity, 61002))
        for key, value in (("Uid", "0 61002 0 61002"), ("Gid", "0 61002 0 61002"),
                           ("Groups", "0"), ("CapEff", "1"), ("NoNewPrivs", "0")):
            with self.subTest(key=key):
                self.assertFalse(isolation.valid_identity({**identity, key: value}, 61002))

    def test_missing_privilege_is_blocked_never_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with patch.object(isolation, "prerequisites", return_value="missing privilege"):
                self.assertEqual(isolation.main(["--run", str(output)]), 77)
            self.assertEqual(json.loads(output.read_text())["status"], "BLOCKED")

    def test_no_opt_in_or_existing_output_starts_no_process(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(isolation.subprocess, "Popen") as spawn:
            output = Path(directory) / "report.json"
            self.assertEqual(isolation.main([str(output)]), 77)
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                isolation.main(["--run", str(output)])
            self.assertEqual(output.read_bytes(), before)
            spawn.assert_not_called()

    def test_frozen_runtime_examples_and_test_data_unchanged(self):
        manifest = json.loads((ROOT / "tests/data/uid-isolation-preserved-baseline.json").read_text())
        for path, expected in manifest["sha256"].items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
