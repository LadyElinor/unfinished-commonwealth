"""Hand-counted outcomes, failure controls, and CLI for the public maintenance rehearsal."""
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.analyze_maintenance_pairs import analyze, DEADLINE, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/maintenance_pairs"
MANIFEST = (EXAMPLE / "manifest.json").read_bytes()
OUTCOMES = (EXAMPLE / "outcomes.json").read_bytes()
CHECKPOINT = "61912572098a9e07dafe143f0efe8f3fd3ac98b4fefada1f3ad1322f6593e7a9"


def recount(outcomes, manifest=MANIFEST):
    return analyze(manifest, json.dumps(outcomes).encode(), sha256(manifest).hexdigest())


class MaintenanceStudyTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = json.loads(OUTCOMES)
        self.rows = self.outcomes["runs"]

    def test_hand_counted_rehearsal(self):
        report = analyze(MANIFEST, OUTCOMES, CHECKPOINT)
        self.assertEqual(report["assigned_pairs"], 4)
        self.assertEqual(report["pair_counts"], {"governed_only": 1, "plain_only": 1, "both_correct": 1,
                                                "neither_correct": 0, "unresolved": 1})
        self.assertEqual(report["difference_bounds"], [0, .25])
        self.assertIsNone(report["point_difference"])
        self.assertIsNone(report["conditional_95_interval"])
        p, g = report["arms"]["plain"], report["arms"]["governed"]
        self.assertEqual(p["false_acceptance_bounds"], [.5, .5])
        self.assertEqual(g["false_acceptance_bounds"], [0, 0])
        self.assertEqual(p["on_time_selection"]["no_delivery"], 1)
        self.assertEqual(g["first_errors"], 2)
        self.assertEqual(g["first_errors_unresolved_at_close"], 1)
        self.assertEqual(g["repairs"], [{"task": "demo-1", "elapsed_ms": 3000}])
        self.assertEqual(g["regressions"], 1)
        self.assertEqual(g["usage"]["cost_micro_usd"], {"known_sum": 300, "known": 3, "unknown": 1})
        self.assertEqual(p["delays"][2], {"task": "demo-3", "first_submission_ms": None, "session_ms": DEADLINE})

    def test_checkpoint_and_strict_json(self):
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            analyze(MANIFEST + b' ', OUTCOMES, CHECKPOINT)
        with self.assertRaisesRegex(ValueError, "duplicate JSON name"):
            analyze(MANIFEST, OUTCOMES.replace(b'"arm": "plain"', b'"arm":"governed","arm":"plain"', 1), CHECKPOINT)
        self.outcomes["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different manifest"):
            recount(self.outcomes)

    def test_missing_and_duplicate_sessions(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError, "incomplete roster"):
            recount(self.outcomes)
        self.rows.append(self.rows[0])
        with self.assertRaisesRegex(ValueError, "duplicate run"):
            recount(self.outcomes)

    def test_assignment_and_receipt_bindings(self):
        for key, invalid in (("order", 2), ("order", True), ("task", "unknown"), ("packet_sha256", "0"*64),
                             ("workflow_sha256", self.rows[1]["workflow_sha256"]), ("agent_sha256", "1"*64),
                             ("receipt_sha256", self.rows[1]["receipt_sha256"])):
            with self.subTest(key=key, value=invalid):
                altered = copy.deepcopy(self.outcomes)
                altered["runs"][0][key] = invalid
                with self.assertRaises(ValueError):
                    recount(altered)

    def test_late_review_affects_disposition_but_keeps_on_time_output(self):
        run = self.rows[1]
        run["candidates"][0]["elapsed_ms"] = DEADLINE
        run["candidates"][1]["elapsed_ms"] = DEADLINE + 500
        run["usage"]["elapsed_ms"] = None
        report = recount(self.outcomes)
        self.assertEqual(report["difference_bounds"], [-.25, 0])
        governed = report["arms"]["governed"]
        self.assertEqual(governed["late_submissions"], 1)
        self.assertEqual(governed["accepted_grades"]["correct"], 2)
        self.assertEqual(governed["repairs"][0]["elapsed_ms"], 500)
        self.assertEqual(report["deviations"][0]["exceeded"], ["elapsed_ms"])

    def test_unknown_submission_time_uses_order_and_known_session_end(self):
        run = self.rows[1]
        run["candidates"][1]["elapsed_ms"] = None
        report = recount(self.outcomes)
        governed = report["arms"]["governed"]
        self.assertEqual(report["difference_bounds"], [0, .25])
        self.assertIsNone(governed["repairs"][0]["elapsed_ms"])
        run["usage"]["elapsed_ms"] = None
        report = recount(self.outcomes)
        self.assertEqual(report["difference_bounds"], [-.25, .25])
        governed = report["arms"]["governed"]
        self.assertEqual(governed["on_time_selection"]["timing_unresolved"], 1)
        self.assertEqual(governed["submissions_with_unresolved_timeliness"], 1)
        run["candidates"][0]["elapsed_ms"] = DEADLINE + 1
        report = recount(self.outcomes)
        self.assertEqual(report["arms"]["governed"]["late_submissions"], 2)
        self.assertEqual(report["arms"]["governed"]["submissions_with_unresolved_timeliness"], 0)

    def test_unknown_grades_and_completely_unmetered_cost(self):
        self.rows[0]["candidates"][0]["grade"] = "unknown"
        for row in self.rows:
            row["usage"]["cost_micro_usd"] = None
            if row["arm"] == "governed":
                row["disposition"] = "unresolved"
        report = recount(self.outcomes)
        self.assertEqual(report["difference_bounds"], [-.25, .25])
        self.assertEqual(report["arms"]["plain"]["false_acceptance_bounds"], [0, .5])
        self.assertIsNone(report["arms"]["governed"]["false_acceptance_bounds"])
        self.assertEqual(report["arms"]["plain"]["usage"]["cost_micro_usd"], {"known_sum": None, "known": 0, "unknown": 4})

    def test_nonstarts_stay_in_denominator_with_accrued_cost(self):
        row = self.rows[0]
        row.update(closure="not_started", candidates=[], disposition="unresolved")
        report = recount(self.outcomes)
        self.assertEqual(report["assigned_pairs"], 4)
        self.assertEqual(report["arms"]["plain"]["closures"]["not_started"], 1)
        self.assertEqual(report["arms"]["plain"]["usage"]["cost_micro_usd"]["known_sum"], 400)
        row["disposition"] = "accept"
        with self.assertRaisesRegex(ValueError, "needs a candidate"):
            recount(self.outcomes)

    def test_inconsistent_times_meters_and_grades_are_rejected(self):
        for section, key, value in (("usage", "model_requests", True), ("usage", "cost_micro_usd", -1),
                                    ("usage", "elapsed_ms", 1), ("candidate", "grade", "fair"),
                                    ("candidate", "elapsed_ms", 30), ("candidate", "sha256", self.rows[1]["candidates"][0]["sha256"])):
            with self.subTest(section=section, key=key, value=value):
                run = copy.deepcopy(self.outcomes)
                changed = run["runs"][1]
                part = changed["usage"] if section == "usage" else changed["candidates"][1]
                part[key] = value
                with self.assertRaises(ValueError):
                    recount(run)

    def test_budget_breaches_preserved_alongside_reported_reasons(self):
        row = self.rows[1]
        row["usage"].update(output_tokens=None, input_tokens=24001, reviewer_ms=600001)
        row["candidates"].append(dict(sha256="a"*64, elapsed_ms=4001, grade="incorrect"))
        row["deviations"].append("reviewer substitution")
        report = recount(self.outcomes)
        self.assertEqual(report["deviations"], [{"task": "demo-1", "arm": "governed",
                         "exceeded": ["reviewer_ms", "candidate_submissions", "combined_tokens"],
                         "reported": ["reviewer substitution"]}])
        self.assertEqual(report["arms"]["governed"]["first_errors_unresolved_at_close"], 2)

    def test_prospective_shape_and_conditional_interval(self):
        plan = json.loads(MANIFEST)
        plan["kind"] = "prospective"
        original_task = plan["tasks"][0]
        plan["tasks"] = []
        self.outcomes["runs"] = []
        for i in range(24):
            identity = str(i)
            packet = sha256(identity.encode()).hexdigest()
            first_arm = "governed" if i % 2 else "plain"
            plan["tasks"].append(dict(original_task, id=identity, lineage=identity, packet_sha256=packet, first_arm=first_arm))
            for template in self.rows[:2]:
                run = copy.deepcopy(template)
                arm = run["arm"]
                run.update(task=identity, order=1 if arm == first_arm else 2, packet_sha256=packet,
                           receipt_sha256=sha256((identity + arm).encode()).hexdigest())
                self.outcomes["runs"].append(run)
        def evaluate():
            raw = json.dumps(plan).encode()
            self.outcomes["manifest_sha256"] = sha256(raw).hexdigest()
            return recount(self.outcomes, raw)
        self.assertIsNone(evaluate()["conditional_95_interval"])
        self.outcomes["lineage_assessment"] = "independent_as_reported"
        report = evaluate()
        self.assertEqual(report["difference_bounds"], [1, 1])
        self.assertEqual(report["conditional_95_interval"], [1 - math.sqrt(2 * math.log(40) / 24), 1])
        self.outcomes["runs"][0]["deviations"] = ["reviewer saw assignment"]
        self.assertIsNone(evaluate()["conditional_95_interval"])
        private_packet = plan["tasks"][1]["packet_sha256"]
        plan["tasks"][1]["packet_sha256"] = original_task["packet_sha256"]
        with self.assertRaisesRegex(ValueError, "public rehearsal packet"):
            evaluate()
        plan["tasks"][1]["packet_sha256"] = private_packet
        plan["tasks"][1]["lineage"] = plan["tasks"][0]["lineage"]
        with self.assertRaisesRegex(ValueError, "reused assignment lineage"):
            evaluate()

    def test_prospective_roster_checks_the_published_exposure_list_before_using_it(self):
        public = json.loads(MANIFEST)
        plan = dict(public, kind="prospective", tasks=[])
        for i in range(24):
            packet = sha256(f"public roster test {i}".encode()).hexdigest()
            plan["tasks"].append(dict(id=str(i), lineage=str(i), packet_sha256=packet,
                                      first_arm="plain" if i % 2 else "governed"))
        plan["tasks"][0]["packet_sha256"] = public["tasks"][0]["packet_sha256"]
        with self.assertRaisesRegex(ValueError, "public rehearsal packet"):
            validate_manifest(plan)
        public["tasks"][0]["packet_sha256"] = "f" * 64
        with tempfile.TemporaryDirectory() as tmp:
            replacement = Path(tmp) / "manifest.json"
            replacement.write_text(json.dumps(public), encoding="utf-8")
            with patch("scripts.analyze_maintenance_pairs.PUBLIC_MANIFEST", replacement):
                with self.assertRaisesRegex(ValueError, "public rehearsal manifest checkpoint mismatch"):
                    validate_manifest(plan)

    def test_cli(self):
        args = [sys.executable, str(ROOT / "scripts/analyze_maintenance_pairs.py"),
                str(EXAMPLE / "manifest.json"), str(EXAMPLE / "outcomes.json"), "--manifest-sha256"]
        ok = subprocess.run([*args, CHECKPOINT], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(ok.stdout)["difference_bounds"], [0, .25])
        invalid = subprocess.run([*args, "000"], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("expected checkpoint", invalid.stderr)
