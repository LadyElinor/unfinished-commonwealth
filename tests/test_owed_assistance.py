"""Public wrongful-denial case through the ordinary remediation review."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from commonwealth.remediation_v1.review import review


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/owed-assistance.json"


class OwedAssistanceTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(EXAMPLE.read_bytes())

    def report(self):
        return review(self.packet, as_of=6)

    def test_order_instruction_and_independent_full_delivery(self):
        tx = self.packet["transfers"].pop()
        unpaid = self.report()["payment"]
        self.assertEqual((unpaid["owner"], unpaid["status"], unpaid["units_without_delivery_evidence"]),
                         ("payments-office", "delivery-unverified", 100))
        self.packet["transfers"].append(tx)
        tx["status"] = "instruction-issued"
        issued = self.report()["payment"]
        self.assertEqual(issued["status"], "delivery-unverified")
        self.assertEqual(issued["checks"][0]["assessment"], "instruction-issued")
        self.packet["criterion"] = "instruction issued"
        with self.assertRaises(ValueError):
            self.report()
        del self.packet["criterion"]
        tx["status"] = "credited"
        delivered = self.report()
        self.assertEqual(delivered["payment"]["status"], "delivery-supported")
        self.assertEqual(delivered["rule_inquiry"]["other_cases_owed_correction"], ["other-8"])
        self.assertEqual(delivered["participation_review"]["required_person_work_records"], [])

    def test_wrong_target_unsupported_or_returned_payment_never_counts(self):
        for change in ({"award": "other-award"}, {"recipient": "someone-else"}, {"status": "pending"},
                       {"status": "returned"}, {"controller": "payments-office"}, {"controller": "eligibility-office"},
                       {"controller": "person-17"}):
            with self.subTest(change=change):
                p = deepcopy(self.packet)
                p["transfers"][0].update(change)
                report = review(p, as_of=6)
                self.assertEqual(report["payment"]["supported_credit_units"], 0)
                self.assertEqual(report["rule_inquiry"]["findings"]["other-8"], "correction-owed")

    def test_partial_payments_are_summed_once_and_excess_visible(self):
        tx = self.packet["transfers"][0]
        tx["units"] = 40
        self.assertEqual(self.report()["payment"]["units_without_delivery_evidence"], 60)
        second = dict(tx, record="second-credit", transfer="second-transfer", units=60)
        self.packet["transfers"].append(second)
        self.assertEqual(self.report()["payment"]["status"], "delivery-supported")
        second["units"] = 61
        self.assertEqual(self.report()["payment"]["excess_units"], 1)
        second["transfer"] = tx["transfer"]
        with self.assertRaisesRegex(ValueError, "per transfer"):
            self.report()

    def test_refusal_silence_and_emotional_expression_do_not_change_either_review(self):
        baseline = self.report()
        for choice in ("declined", "accepted", "unanswered", None):
            for words in ("I am furious. This rule hurt other people.", "I am frightened of that room.",
                          "I am grieving. Use my earlier account.", "Please examine the other cases."):
                with self.subTest(choice=choice, words=words):
                    self.packet["warning"]["account"] = words
                    self.packet["participation"] = (dict.fromkeys(("repeat-testimony", "public-reconciliation",
                        "publicity", "further-contact"), choice) if choice else {})
                    result = self.report()
                    self.assertEqual(result["packet"]["warning"]["account"], words)
                    self.assertEqual(result["payment"], baseline["payment"])
                    self.assertEqual(result["rule_inquiry"], baseline["rule_inquiry"])

    def test_acknowledgment_cannot_close_or_assign_the_rule_inquiry(self):
        self.packet["inquiry"].update(assignment=None, inventory=None, findings=[])
        report = self.report()
        inquiry = report["rule_inquiry"]
        self.assertEqual((inquiry["status"], inquiry["next_owner"]),
                         ("independent-assignment-needed", "assistance-service"))
        self.assertEqual(report["payment"]["units_without_delivery_evidence"], 0)
        self.assertIsNone(inquiry["inventory_record_used"])

    def test_review_must_follow_assignment_and_examine_the_reported_rule(self):
        for change, status in (({"assignment": {"controller": "eligibility-office"}}, "independent-assignment-needed"),
                               ({"assignment": {"controller": "person-17"}}, "independent-assignment-needed"),
                               ({"inventory": {"at": 2}}, "rule-records-review-needed"),
                               ({"inventory": {"controller": "eligibility-office"}}, "rule-records-review-needed"),
                               ({"inventory": {"rule": "unrelated-rule"}}, "rule-records-review-needed")):
            with self.subTest(change=change):
                p = deepcopy(self.packet)
                for entry, fields in change.items():
                    p["inquiry"][entry].update(fields)
                r = review(p, as_of=6)["rule_inquiry"]
                self.assertEqual(r["status"], status)
                self.assertEqual(len(r["unused_finding_records"]), 2)

    def test_findings_and_corrections_remain_open_with_the_institution(self):
        inquiry = self.packet["inquiry"]
        first, second = inquiry["findings"]
        first.update(controller="original-clerk")
        report = self.report()["rule_inquiry"]
        self.assertEqual(report["pending_files"], ["other-2"])
        self.assertEqual(report["unused_finding_records"], [first["record"]])
        self.assertEqual(report["other_cases_owed_correction"], ["other-8"])
        self.assertEqual(report["next_owner"], "review-office")
        inquiry["inventory"]["complete"] = False
        report = self.report()["rule_inquiry"]
        self.assertEqual(report["status"], "inventory-incomplete")
        self.assertEqual(report["other_cases_owed_correction"], ["other-8"])
        inquiry["inventory"]["complete"] = True
        first.update(controller="review-office", result="inconclusive")
        self.assertEqual(self.report()["rule_inquiry"]["status"], "file-findings-outstanding")
        first.update(result="no-correction-found")
        self.assertEqual(self.report()["rule_inquiry"]["status"], "other-remedies-outstanding")
        second.update(result="no-correction-found")
        self.assertEqual(self.report()["rule_inquiry"]["status"], "declared-inventory-reviewed")

    def test_empty_search_and_missing_inventory_are_distinct(self):
        inquiry = self.packet["inquiry"]
        inquiry["findings"] = []
        inquiry["inventory"]["cases"] = []
        self.assertEqual(self.report()["rule_inquiry"]["status"], "declared-inventory-reviewed")
        inquiry["inventory"]["complete"] = False
        self.assertEqual(self.report()["rule_inquiry"]["status"], "inventory-incomplete")
        inquiry["inventory"] = None
        self.assertEqual(self.report()["rule_inquiry"]["status"], "rule-records-review-needed")

    def test_omitting_a_known_adverse_file_does_not_finish_the_review(self):
        inquiry = self.packet["inquiry"]
        inquiry["inventory"]["cases"].remove("other-8")
        report = self.report()["rule_inquiry"]
        self.assertEqual(report["status"], "finding-reconciliation-needed")
        self.assertEqual(report["findings_to_reconcile"], ["file-8-review"])
        self.assertEqual(report["next_owner"], "review-office")

    def test_cost_and_required_retelling_survive_payment(self):
        result = self.report()
        costs = result["participation_review"]["recorded_burden"]
        self.assertEqual(costs["institution"]["recorded_units"], 4)
        self.assertEqual(costs["affected-person"]["entries"], 0)
        self.packet["work"].extend([
            dict(record="condition", at=3, obligation="payment", bearer="affected-person",
                 activity="Attend the ceremony to receive payment.", required=True, units=0),
            dict(record="repeat", at=4, obligation="rule-inquiry", bearer="affected-person",
                 activity="Repeat testimony to the original office.", required=True, units=2),
            dict(record="voluntary", at=5, obligation="rule-inquiry", bearer="affected-person",
                 activity="Send optional details.", required=False, units=None)])
        changed = self.report()
        self.assertEqual(changed["payment"], result["payment"])
        self.assertEqual(changed["rule_inquiry"], result["rule_inquiry"])
        participation = changed["participation_review"]
        self.assertEqual(participation["required_person_work_records"], ["condition", "repeat"])
        self.assertEqual(participation["recorded_burden"]["affected-person"],
                         {"entries": 3, "recorded_units": 2, "unknown_cost_entries": 1})

    def test_bad_evidence_packet_is_rejected_and_snapshot_detached(self):
        for obj, key, value in (("award", "units", True), ("warning", "acknowledged_at", 0),
                                ("finding", "record", "award-17"), ("finding", "at", 7),
                                ("inventory", "cases", ["case-17"]), ("inventory", "complete", 1),
                                ("work", "units", -1), ("participation", "publicity", "silence-is-consent")):
            with self.subTest(key=key, value=value):
                p = deepcopy(self.packet)
                objects = {"award": p["award"], "warning": p["warning"], "finding": p["inquiry"]["findings"][0],
                           "inventory": p["inquiry"]["inventory"], "work": p["work"][0], "participation": p["participation"]}
                objects[obj][key] = value
                with self.assertRaises(ValueError):
                    review(p, as_of=6)
        report = self.report()
        self.packet["warning"]["account"] = "replacement"
        self.assertNotEqual(report["packet"]["warning"]["account"], "replacement")

    def test_existing_cli_reviews_public_case_without_external_action(self):
        result = subprocess.run([sys.executable, "-m", "commonwealth.remediation_v1", str(EXAMPLE), "--as-of", "6"],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        r = json.loads(result.stdout)
        self.assertEqual(r["version"], "owed-assistance-1")
        self.assertNotIn("packet", r)
        self.assertNotIn(self.packet["warning"]["account"], result.stdout)
        self.assertEqual(r["payment"]["status"], "delivery-supported")
        self.assertEqual(r["rule_inquiry"]["status"], "other-remedies-outstanding")
        self.assertEqual((r["external_actions"], r["authority_granted"], r["production_ready"]), (0, False, False))
