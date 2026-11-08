"""Exposed counterexamples and controls for equal-treatment-review-1."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commonwealth.remediation_v1.equal_treatment import review

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/equal-treatment-review.json"
MODULE = "commonwealth.remediation_v1.equal_treatment"


class EqualTreatmentTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.source = self.packet["remediation"]
        self.followup = self.packet["followup"]
        self.decision = self.packet["decision"]

    def report(self):
        return review(self.packet, as_of=7)

    def add_access_check(self, record="visit", *, result="pass", person="member-17",
                         access="open-hearing", reviewer="auditor", at=7):
        repair = self.source["repair"]
        repair["criterion"] = "claimant-used-requested-access"
        self.source["records"].append({"id": record, "at": at, "source": "visit-log",
                                       "kind": "observation", "text": "Fictional visit observation."})
        repair["checks"].append({"record": record, "reviewer_controller": reviewer,
                                 "criterion": repair["criterion"], "result": result})
        observed = {"pass": "used", "fail": "denied", "inconclusive": "unknown"}[result]
        self.followup["access_checks"].append({"record": record, "person": person,
                                              "requested_access": access, "observed": observed})

    def test_public_example_distinguishes_paper_success_from_access(self):
        before = deepcopy(self.packet)
        report = self.report()
        self.assertEqual(report["comparison"]["status"], "different-access-on-matched-facts")
        self.assertTrue(report["comparison"]["equal_recorded_penalties"])
        self.assertEqual(report["reasoning"]["contrary_precedents"], ["old-minutes"])
        self.assertFalse(report["reasoning"]["substantive_reason_cited"])
        self.assertEqual(report["merits_outside_mandate"], ["hearing-admission"])
        self.assertEqual(report["repair_status"], "supplied-record-supports-declared-criterion")
        self.assertEqual(report["personal_relief"], "access-unverified")
        self.assertTrue(report["followup_overdue"])
        self.assertEqual(self.packet, before)

    def test_mismatch_and_missing_facts_prevent_comparison(self):
        for field in ("rule_version", "conduct", "qualifications", "requested_access"):
            with self.subTest(field=field):
                peer = self.packet["comparator"]
                original = peer[field]
                for value in (None, "different"):
                    peer[field] = value
                    comparison = self.report()["comparison"]
                    self.assertEqual(comparison["status"], "comparison-inconclusive")
                    self.assertIn(field, comparison["different_facts"])
                peer[field] = original
        self.packet["comparator"]["group"] = "affiliate"
        self.assertEqual(self.report()["comparison"]["status"], "comparison-inconclusive")

    def test_neutral_and_unknown_comparisons(self):
        peer = self.packet["comparator"]
        peer["access"] = "denied"
        self.assertEqual(self.report()["comparison"]["status"], "same-access-on-matched-facts")
        peer.update(access="unknown", penalty=None)
        self.assertEqual(self.report()["comparison"]["status"], "access-unknown")
        self.assertIsNone(self.report()["comparison"]["equal_recorded_penalties"])

    def test_equal_penalties_for_two_excluded_people_do_not_establish_equal_eligibility(self):
        peer = self.packet["comparator"]
        self.packet["claimant"]["penalty"] = peer["penalty"] = 5
        peer["access"] = "denied"
        self.assertEqual(self.report()["comparison"]["status"], "same-access-on-matched-facts")
        # Compare eligibility for the same conduct to a member admitted without penalty.
        peer.update(access="admitted", penalty=0)
        self.assertEqual(self.report()["comparison"]["status"], "different-access-on-matched-facts")

    def test_custom_reason_and_silence_do_not_change_the_recorded_exclusion(self):
        before = self.report()["comparison"]
        self.packet["reasoning"]["grounds"] = ["substantive-reason", "precedent"]
        self.source["warning"].update(response=None, opportunity="expired")
        next(r for r in self.source["records"] if r["id"] == "warning")["text"] = "I felt no stigma."
        after = self.report()
        self.assertEqual(after["comparison"], before)
        self.assertEqual(after["reasoning"]["contrary_precedents"], ["old-minutes"])
        self.assertEqual(after["intent"], "not-established")

    def test_history_accounts_for_date_scope_and_absence(self):
        reasoning = self.packet["reasoning"]
        reasoning["precedents"][0]["practice"] = "different-practice"
        self.assertEqual(self.report()["reasoning"]["historical_claim_status"], "no-comparable-record-at-decision")
        reasoning["precedents"][0]["practice"] = "hearing-membership"
        reasoning["precedents"][0]["access"] = "denied"
        self.assertEqual(self.report()["reasoning"]["historical_claim_status"], "no-counterexample-in-supplied-comparables")
        next(r for r in self.source["records"] if r["id"] == "old-minutes")["at"] = 5
        result = self.report()["reasoning"]
        self.assertEqual(result["later_precedents"], ["old-minutes"])
        self.assertFalse(result["alternatives"][2]["available_at_decision"])
        self.assertEqual(result["contrary_precedents"], [])
        reasoning["historical_claim"] = None
        self.assertEqual(self.report()["reasoning"]["historical_claim_status"], "no-universal-claim")

    def test_jurisdiction_restraint_and_remand_leave_claimant_relief_open(self):
        self.assertTrue(self.report()["merits_claimed_with_dismissal"])
        self.decision["merits_issues"] = []
        for outcome in ("dismiss", "remand", "refer"):
            self.decision["disposition"] = outcome
            report = self.report()
            self.assertFalse(report["merits_claimed_with_dismissal"])
            self.assertFalse(report["merits_outside_mandate"])
            self.assertEqual(report["personal_relief"], "access-unverified")
            routes = report["reasoning"]["alternatives"]
            self.assertTrue(routes[1]["within_declared_mandate"])
            self.assertFalse(routes[2]["within_declared_mandate"])
        self.decision.update(disposition="recognize-claim", merits_issues=["hearing-admission"],
                             delegated_issues=["hearing-admission"])
        self.assertEqual(self.report()["personal_relief"], "access-unverified")

    def test_direct_use_can_be_supported_while_other_denial_remains(self):
        self.source["repair"]["checks"].clear()
        self.add_access_check()
        report = self.report()
        self.assertEqual(report["personal_relief"], "supplied-record-supports-personal-access")
        self.assertEqual(report["other_matched_denials"], [{"person": "member-58", "record": "later-register"}])
        self.assertEqual(report["systemwide_effect"], "unverified")
        self.assertFalse(report["access_observed_by_due_date"])
        self.assertFalse(report["authority_granted"])
        self.assertFalse(report["production_ready"])
        self.assertEqual(report["external_actions"], 0)

    def test_wrong_recipient_service_reviewer_time_and_untyped_pass(self):
        self.source["repair"]["checks"].clear()
        baseline = deepcopy(self.packet)
        for change in ({"person": "member-42"}, {"access": "private-hearing"},
                       {"reviewer": "hearing-office"}, {"reviewer": "intake-office"},
                       {"at": 5}, {"result": "inconclusive"}):
            with self.subTest(change=change):
                self.packet = deepcopy(baseline)
                self.source, self.followup = self.packet["remediation"], self.packet["followup"]
                self.add_access_check(**change)
                self.assertEqual(self.report()["personal_relief"], "access-unverified")
        self.packet = deepcopy(baseline)
        self.source, self.followup = self.packet["remediation"], self.packet["followup"]
        self.add_access_check()
        self.followup["access_checks"].clear()
        self.assertEqual(self.report()["personal_relief"], "access-unverified")

    def test_restored_opportunity_can_be_checked_without_claimant_participation(self):
        repair = self.source["repair"]
        repair["checks"].clear()
        self.add_access_check(at=6)
        self.followup["access_checks"][0]["observed"] = "available"
        self.assertEqual(self.report()["personal_relief"], "access-unverified")
        repair["criterion"] = repair["checks"][0]["criterion"] = "requested-access-available-to-claimant"
        self.source["warning"].update(response=None, opportunity="expired")
        report = self.report()
        self.assertEqual(report["personal_relief"], "supplied-record-supports-personal-access")
        self.assertTrue(report["access_observed_by_due_date"])
        self.assertEqual(report["first_supported_access_at"], 6)

    def test_adverse_check_survives_later_success(self):
        self.source["repair"]["checks"].clear()
        self.add_access_check("failed-visit", result="fail", at=6)
        self.add_access_check("next-visit", at=7)
        self.assertEqual(self.report()["personal_relief"], "adverse-access-observation")

    def test_owner_deadline_and_system_inventory_are_independent(self):
        self.followup.update(owner="member-17", due_at=7, other_cases=[])
        report = self.report()
        self.assertTrue(report["claimant_bears_followup"])
        self.assertFalse(report["followup_overdue"])
        self.assertEqual(report["other_observations_reviewed"], 0)
        self.assertEqual(report["systemwide_effect"], "unverified")
        self.followup.update(owner=None, due_at=None)
        self.assertIsNone(self.report()["claimant_bears_followup"])
        self.assertIsNone(self.report()["followup_overdue"])

    def test_malformed_or_cross_case_evidence_rejected(self):
        for path, value in ((("remediation", "scope"), "other-case"),
                            (("decision", "mandate_record"), None),
                            (("decision", "mandate_record"), "posted"),
                            (("claimant", "record"), "missing"),
                            (("comparator", "record"), "opinion"),
                            (("claimant", "person"), "member-42"),
                            (("claimant", "penalty"), True),
                            (("followup", "other_cases", 0, "record"), "register"),
                            (("followup", "other_cases", 0, "person"), "member-17"),
                            (("reasoning", "grounds"), ["custom"] * 33)):
            with self.subTest(path=path):
                packet = deepcopy(self.packet)
                target = packet
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    review(packet, as_of=7)

    def test_access_check_cannot_contradict_or_reuse_underlying_observation(self):
        self.add_access_check()
        self.followup["access_checks"][0]["observed"] = "denied"
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.report()
        self.followup["access_checks"][0]["observed"] = "used"
        self.followup["access_checks"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.report()

    def test_cli_reports_results_and_refuses_ambiguous_packets(self):
        def run(path):
            return subprocess.run([sys.executable, "-m", MODULE, str(path), "--as-of", "7"],
                                  cwd=ROOT, text=True, capture_output=True)
        result = run(EXAMPLE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.report())
        self.assertNotIn("private appointment", result.stdout.lower())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for content in ('{"review":{"a":1,"a":2}}', '{"penalty":NaN}', " " * (1048576 + 1)):
                path.write_text(content, encoding="utf-8")
                bad = run(path)
                self.assertEqual(bad.returncode, 2)
                self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
