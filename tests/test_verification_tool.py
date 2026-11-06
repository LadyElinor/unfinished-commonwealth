"""Execute real disposable suites; do not fake unittest's reported results."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PASS = "import unittest\nclass T(unittest.TestCase):\n def test_one(self): pass\n"
SKIP = "import unittest\n@unittest.skip('unavailable control')\nclass S(unittest.TestCase):\n def test_skip(self): pass\n"
CLASS_SKIP = "import unittest\nclass S(unittest.TestCase):\n @classmethod\n def setUpClass(cls): raise unittest.SkipTest('class unavailable')\n def test_skip(self): pass\n"


class VerificationToolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for directory in ("scripts", "tests", "docs"):
            (self.root / directory).mkdir()
        for name in ("verify.py", "verification_tests.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        for name in ("README.md", "ROADMAP.md", "CONTRIBUTING.md"):
            (self.root / name).write_text("Disposable verification fixture.\n", encoding="utf-8")

    def run_case(self, code=PASS, *args):
        (self.root / "tests/test_probe.py").write_text(code, encoding="utf-8")
        receipt = self.root / "receipt.json"
        run = subprocess.run([sys.executable, str(self.root / "scripts/verify.py"),
                              "--report", str(receipt), *args], cwd=self.root.parent,
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        return run, json.loads(receipt.read_text(encoding="utf-8"))

    def test_empty_discovery_is_explicit_failure(self):
        run, r = self.run_case("")
        self.assertEqual(run.returncode, 1)
        self.assertIn("NO_TESTS_DISCOVERED", r["problems"])
        self.assertEqual(r["artifacts"]["status"], "NOT_RUN")

    def test_all_skipped_is_not_success(self):
        run, r = self.run_case(SKIP)
        self.assertEqual(run.returncode, 1)
        self.assertIn("ALL_TESTS_SKIPPED", r["problems"])
        self.assertEqual(r["tests"]["tests_not_skipped"], 0)
        self.assertEqual(r["tests"]["skipped"][0]["reason"], "unavailable control")

    def test_all_class_skipped_retains_reason_without_inventing_test_execution(self):
        run, r = self.run_case(CLASS_SKIP)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(r["tests"]["tests_run"], 0)
        self.assertIn("ALL_TESTS_SKIPPED", r["problems"])
        self.assertEqual(r["tests"]["skipped"][0]["reason"], "class unavailable")

    def test_successful_run_is_explicit_and_receipt_not_checked_as_input(self):
        run, r = self.run_case()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(r["status"], "PASSED")
        self.assertEqual(r["tests"]["tests_run"], 1)
        self.assertTrue(r["all_tests_executed"])
        self.assertFalse(r["source"]["authenticated"])
        self.assertGreater(r["elapsed_ns"], 0)

    def test_mixed_skip_retains_partial_coverage(self):
        run, r = self.run_case(PASS + SKIP)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(r["status"], "PASSED_WITH_SKIPS")
        self.assertEqual(r["tests"]["tests_not_skipped"], 1)
        self.assertFalse(r["all_tests_executed"])

    def test_class_skip_does_not_cancel_a_passing_test(self):
        run, r = self.run_case(PASS + CLASS_SKIP)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(r["tests"]["tests_run"], 1)
        self.assertEqual(r["status"], "PASSED_WITH_SKIPS")

    def test_strict_mode_refuses_mixed_skip(self):
        run, r = self.run_case(PASS + SKIP, "--require-no-skips")
        self.assertEqual(run.returncode, 1)
        self.assertIn("SKIPS_NOT_ALLOWED", r["problems"])

    def test_failure_is_retained_and_artifacts_are_not_claimed_checked(self):
        run, r = self.run_case(PASS.replace("pass", "self.fail('negative control')"))
        self.assertEqual(run.returncode, 1)
        self.assertEqual(r["status"], "FAILED")
        self.assertEqual(r["tests"]["failures"], ["test_probe.T.test_one"])
        self.assertEqual(r["artifacts"]["status"], "NOT_RUN")

    def test_missing_worker_is_unknown_not_zero_test_success(self):
        (self.root / "scripts/verification_tests.py").unlink()
        run, r = self.run_case()
        self.assertEqual(run.returncode, 1)
        self.assertIsNone(r["tests"])
        self.assertFalse(r["all_tests_executed"])

    def test_artifact_failure_is_retained(self):
        (self.root / "bad.json").write_text("{", encoding="utf-8")
        run, r = self.run_case()
        self.assertEqual(run.returncode, 1)
        self.assertEqual(r["artifacts"]["status"], "FAILED")
        self.assertTrue(r["all_tests_executed"])

    def test_broken_link_is_still_refused(self):
        (self.root / "README.md").write_text("[missing](absent.txt)", encoding="utf-8")
        run, r = self.run_case()
        self.assertEqual(run.returncode, 1)
        self.assertIn("Broken local documentation link", r["problems"][0])

    def test_existing_receipt_cannot_be_overwritten(self):
        saved = {"previous_failure": True}
        (self.root / "receipt.json").write_text(json.dumps(saved), encoding="utf-8")
        run, r = self.run_case()
        self.assertEqual(run.returncode, 2)
        self.assertEqual(r, saved)
        self.assertNotIn("Ran 1 test", run.stderr)

    def test_test_console_output_cannot_supply_counts(self):
        run, r = self.run_case(PASS.replace("pass", "print('Ran 999 tests; OK')"))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(r["tests"]["tests_run"], 1)
        self.assertIn("Ran 999", run.stderr)


if __name__ == "__main__":
    unittest.main()
