"""Public controls and counterexamples for selection and consultation accounting."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from scripts.public_review_routing import Brief, BudgetExhausted, fail_before_dispatch, rehearsal, run_arm

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/recount_public_review_routing.mjs"


class HostRoutingTests(unittest.TestCase):
    brief = Brief("demo-2", "candidate", ("validation", "reporting"))

    def test_unfunded_selector_is_never_called(self):
        selector = Mock(return_value="validation")
        with self.assertRaises(BudgetExhausted) as stop:
            run_arm("direct", self.brief, "correct", selector, budget=0)
        selector.assert_not_called()
        self.assertEqual(stop.exception.action, "route")
        self.assertEqual(stop.exception.receipt["events"], [])

    def test_unfunded_fallback_is_never_called(self):
        with patch("scripts.public_review_routing.first_eligible") as fallback:
            with self.assertRaises(BudgetExhausted) as stop:
                run_arm("failure", self.brief, "correct", fail_before_dispatch, budget=1)
            fallback.assert_not_called()
        self.assertEqual(stop.exception.action, "fallback")
        self.assertEqual(stop.exception.receipt["events"], [
            {"actor": "fixture-router", "action": "route", "result": "failed-before-dispatch", "slots": 1}
        ])

    def test_invalid_budgets_stop_before_selector(self):
        selector = Mock(return_value=None)
        for budget in (-1, 0.5, True, "2"):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                run_arm("direct", self.brief, "correct", selector, budget=budget)
        selector.assert_not_called()

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

    def test_original_public_receipts(self):
        # Normalize Windows console line endings for the original LF wire fixture.
        self.assertEqual(sha256(self.emitted.replace(b"\r\n", b"\n")).hexdigest(),
                         "3e412ab4cdb531768eb313e3695387c543085396721b8d4bb0b333fba8b13053")

    def test_each_public_cutoff(self):
        expected = [
            (["route"] * 4, [0, 0, 0, 0]),
            (["consult", "consult", None, "fallback"], [1, 1, 1, 1]),
            ([None, None, None, "consult"], [2, 2, 1, 2]),
            ([None] * 4, [2, 2, 1, 3]),
        ]
        for budget, (blocked, spent) in enumerate(expected):
            with self.subTest(budget=budget):
                raw = subprocess.check_output([sys.executable, ROOT / "scripts/public_review_routing.py",
                                               "--budget", str(budget)])
                result = self.recount(raw)
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = json.loads(result.stdout)
                self.assertEqual([r["blocked_action"] for r in summary], blocked)
                self.assertEqual([r["slots"] for r in summary], spent)

    def test_altered_partial_receipts(self):
        edits = [
            ({"blocked_action": None}, "blocked action"),
            ({"reviewer": None}, "reviewer"),
            ({"selected_by": "fixture-router"}, "selection authority"),
            ({"reviewed_candidate": "unearned"}, "reviewed candidate"),
            ({"illustrative_grade": "correct"}, "illustrative grade"),
            ({"slots_used": 3}, "spent slots"),
        ]
        for edit, error in edits:
            with self.subTest(edit=edit):
                report = rehearsal(budget=2)
                failure = next(run for run in report["runs"] if run["arm"] == "failure")
                failure.update(edit)
                result = self.recount(json.dumps(report).encode())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error.encode(), result.stderr)

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
