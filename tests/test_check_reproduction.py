import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContributorReproductionCheck(unittest.TestCase):
    def test_optimized_python_compares_all_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "reproduction with spaces"
            for output, published in (
                ("d1/summary.json", "study-v1-summary.json"),
                ("neighbor/results.json", "neighbor-timing-results.json"),
                ("charged/results.json", "charged-workshop-results.json"),
            ):
                path = directory / output
                path.parent.mkdir(parents=True)
                shutil.copyfile(ROOT / "examples" / published, path)

            command = [sys.executable, "-O", str(ROOT / "scripts/check_reproduction.py"), str(directory)]
            matches = subprocess.run(command, cwd=tmp, text=True, capture_output=True)
            self.assertEqual(matches.returncode, 0, matches.stdout + matches.stderr)
            self.assertEqual(matches.stdout.splitlines(),
                             ["MATCH d1/summary.json", "MATCH neighbor/results.json", "MATCH charged/results.json"])

            (directory / "d1/summary.json").unlink()
            neighbor = directory / "neighbor/results.json"
            original = neighbor.read_bytes()
            neighbor.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            mismatch = subprocess.run(command, cwd=tmp, text=True, capture_output=True)
            self.assertEqual(mismatch.returncode, 1, mismatch.stdout + mismatch.stderr)
            self.assertIn("UNREADABLE d1/summary.json", mismatch.stdout)
            self.assertIn("DIFFER neighbor/results.json", mismatch.stdout)
            self.assertIn("MATCH charged/results.json", mismatch.stdout)
