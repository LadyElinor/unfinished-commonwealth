"""Public controls and counterexamples for selection and consultation accounting."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from scripts.public_review_routing import Brief, fail_before_dispatch, run_arm

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/recount_public_review_routing.mjs"


class HostRoutingTests(unittest.TestCase):
    brief = Brief("demo-2", "candidate", ("validation", "reporting"))

    def test_ineligible_proposal(self):
        with self.assertRaisesRegex(ValueError, "ineligible"):
            run_arm("direct", self.brief, "correct", lambda brief: "keeper")

    def test_fallback_consultation_needs_third_slot(self):
        with self.assertRaisesRegex(ValueError, "exhausted"):
            run_arm("failure", self.brief, "correct", fail_before_dispatch, budget=2)

    def test_unknown_error_does_not_invoke_fallback(self):
        def unknown(brief):
            raise RuntimeError("unknown dispatch status")

        with self.assertRaisesRegex(RuntimeError, "unknown dispatch status"):
            run_arm("failure", self.brief, "correct", unknown)


@unittest.skipUnless(shutil.which("node"), "Node required for independent recount")
class RoutingRecountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.emitted = subprocess.check_output([sys.executable, ROOT / "scripts/public_review_routing.py"])

    def recount(self, raw):
        return subprocess.run(["node", CHECKER], input=raw, capture_output=True)

    def test_public_comparison(self):
        result = self.recount(self.emitted)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([(r["arm"], r["selected_by"], r["consultations"], r["slots"])
                          for r in json.loads(result.stdout)], [
            ("fixed", "fixed-selector", 1, 2), ("direct", "fixture-router", 1, 2),
            ("abstain", None, 0, 1), ("failure", "host", 1, 3),
        ])

    def test_changed_histories(self):
        for edit in ("drop-failure", "wrong-actor", "reordered-events", "free-failure",
                     "abstention-as-review", "wrong-authority", "wrong-candidate",
                     "changed-grade", "duplicate-arm", "different-brief"):
            with self.subTest(edit=edit):
                record = json.loads(self.emitted)
                fixed, direct, abstain, failure = record["runs"]
                if edit == "drop-failure":
                    failure["events"].pop(0)
                    failure["slots_used"] -= 1
                elif edit == "wrong-actor":
                    failure["events"][1]["actor"] = "fixture-router"
                elif edit == "reordered-events":
                    failure["events"].reverse()
                elif edit == "free-failure":
                    failure["events"][0]["slots"] = 0
                    failure["slots_used"] = 2
                elif edit == "abstention-as-review":
                    abstain.update(direct, arm="abstain")
                elif edit == "wrong-authority":
                    failure["selected_by"] = direct["selected_by"]
                elif edit == "wrong-candidate":
                    fixed["reviewed_candidate"] = "0" * 64
                elif edit == "changed-grade":
                    direct["illustrative_grade"] = "incorrect"
                elif edit == "duplicate-arm":
                    record["runs"][-1] = fixed
                else:
                    record["brief"]["eligible"].reverse()
                self.assertNotEqual(self.recount(json.dumps(record).encode()).returncode, 0)

    def test_ambiguous_receipt(self):
        raw = self.emitted.replace(b'"slots_used": 3', b'"slots_used": 2, "slots_used": 3')
        result = self.recount(raw)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"duplicate JSON name", result.stderr)
