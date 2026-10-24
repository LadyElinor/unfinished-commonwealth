"""Historical procedure and unchanged D1 are not rewritten by notice fixes."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from commonwealth.procedure_v1 import VERSION
from commonwealth.procedure_v1.engine import ProceduralEpisode, replay
from commonwealth.procedure_v1.legacy_p1 import VERSION as LEGACY_VERSION
from commonwealth.study_v1.engine import replay as replay_d1
from commonwealth.study_v1.fixtures import case

ROOT = Path(__file__).resolve().parents[1]


class HistoricalProcedureTests(unittest.TestCase):
    def test_all_eight_prepatch_journals_replay_without_normalization(self):
        path = ROOT / "tests/data/procedure-v100-journals.json"
        raw = path.read_bytes()
        journals = json.loads(raw)
        self.assertEqual(len(journals), 8)
        self.assertEqual(LEGACY_VERSION, "procedure-1.0.0")
        self.assertEqual(VERSION, "procedure-1.1.0")
        for name, journal in journals.items():
            original = deepcopy(journal)
            with self.subTest(trace=name):
                check = replay_d1(journal) if name == "d1-control" else replay(journal)
                self.assertTrue(check["verified"])
                self.assertEqual(check["head"], original["terminal"]["head"])
                self.assertEqual(check["events"], len(original["events"]))
                self.assertEqual(journal, original)
        self.assertEqual(path.read_bytes(), raw)

    def test_version_relabeling_cannot_reinterpret_old_or_new_history(self):
        old = json.loads((ROOT / "tests/data/procedure-v100-journals.json").read_text())["appeal-remand"]
        old["genesis"]["version"] = VERSION
        with self.assertRaises(ValueError):
            replay(old)
        e = ProceduralEpisode(case())
        e.finish()
        current = e.journal()
        for version in ("procedure-1.0.0", "procedure-unknown"):
            changed = deepcopy(current)
            changed["genesis"]["version"] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                replay(changed)

    def test_historical_terminal_tampering_still_fails(self):
        old = json.loads((ROOT / "tests/data/procedure-v100-journals.json").read_text())["terminal-appeal"]
        old["terminal"]["measures"]["outstanding"] = []
        with self.assertRaises(ValueError):
            replay(old)

    def test_d1_sources_and_recorded_results_remain_frozen(self):
        manifest = json.loads((ROOT / "tests/data/procedure-preserved-d1.json").read_text())
        for path, expected in manifest.items():
            with self.subTest(path=path):
                self.assertEqual(sha256((ROOT / path).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
