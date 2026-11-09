"""Regression checks for the opinion supplement to the petition-17 review."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commonwealth.remediation_v1.opinion_review import review
from commonwealth.review_v1.__main__ import read
from commonwealth.study_v1.engine import digest


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples/equal-treatment-review.json"
OPINION = ROOT / "examples/panel-opinion-review.json"


class OpinionReviewTests(unittest.TestCase):
    def setUp(self):
        self.case, self.packet = read(CASE), read(OPINION)

    def report(self):
        return review(self.case, self.packet, as_of=7)

    def test_shared_result_with_no_shared_reason_and_no_relief(self):
        before = deepcopy(self.packet)
        report = self.report()
        self.assertEqual(report["panel"]["judgment"], "dismiss")
        self.assertEqual(report["panel"]["majority_reasons"], [])
        self.assertEqual(report["original_decision"]["personal_relief"], "access-unverified")
        self.assertEqual(report["intent"], "not-established")
        self.assertFalse(report["authority_granted"])
        self.assertEqual(report["external_actions"], 0)
        self.assertEqual(self.packet, before)

    def test_exact_footnote_joins_only(self):
        a = self.packet["passages"][1]
        a.update(part="footnote", joined_by=["arden", "lee", "ravi"])
        panel = self.report()["panel"]
        self.assertEqual(panel["majority_reasons"], ["receipt"])
        self.assertEqual(panel["passages"]["receipt"]["part"], "footnote")
        self.assertFalse(panel["passages"]["limit"]["majority_for_judgment_joined_passage"])
        a["joined_by"] = ["arden", "ravi"]  # Ravi voted for a different judgment.
        self.assertEqual(self.report()["panel"]["majority_reasons"], [])

    def test_unknown_ballot_and_abstention_do_not_reduce_denominator(self):
        for vote in ("abstain", "unknown", "uphold"):
            self.packet["panel"]["ballots"]["lee"] = vote
            panel = self.report()["panel"]
            self.assertEqual(panel["threshold"], 2)
            self.assertIsNone(panel["judgment"])

    def test_missing_vote_duplicate_join_and_syllabus_support_are_rejected(self):
        for operation in (lambda p: p["panel"]["ballots"].pop("lee"),
                          lambda p: p["panel"]["members"].append("lee"),
                          lambda p: p["passages"][1].update(joined_by=["lee","lee"]),
                          lambda p: p["passages"][1].update(joined_by=["visitor"]),
                          lambda p: p["passages"][0].update(joined_by=["lee"]),
                          lambda p: p["premises"][0].update(passage="headnote"),
                          lambda p: p["passages"][1].update(record="digest")):
            packet = deepcopy(self.packet)
            operation(packet)
            with self.assertRaises(ValueError):
                review(self.case, packet, as_of=7)

    def test_later_observation_reopens_only_its_premise(self):
        r = self.report()
        receipt = r["premises"]["identified-request"]
        self.assertEqual((receipt["at_decision"], receipt["as_of"]),
                         ("no-matching-material", "challenge-recorded"))
        self.assertEqual(receipt["later_records"]["challenges"], ["dated-application"])
        self.assertEqual(receipt["test_origin"], "passage")
        self.assertEqual(r["panel"]["ballots"]["arden"], "dismiss")

    def test_empirical_outlier_cannot_supply_rule_and_scope_is_specific(self):
        premise = self.packet["premises"][1]
        before = self.report()["premises"]["rule-for-delay"]
        self.assertEqual(before["unmatched_records"], {"queue-model":"different-kind"})
        self.assertEqual(before["test_origin"], "reviewer-proposal")
        self.packet["sources"].append({"id":"limit-3","kind":"rule","at":3,"topic":"other-delay","locator":"charter s3"})
        premise["evidence"].append({"record":"limit-3","bearing":"challenges"})
        self.assertEqual(self.report()["premises"]["rule-for-delay"]["unmatched_records"]["limit-3"], "different-topic")
        self.packet["sources"][-1]["topic"] = "delay-limit"
        self.assertEqual(self.report()["premises"]["rule-for-delay"]["at_decision"], "challenge-recorded")

    def test_contrary_known_evidence_survives_later_record(self):
        self.packet["sources"].append({"id":"counter","kind":"testimony","at":5,"topic":"member-17/request","locator":"signed account"})
        self.packet["premises"][0]["evidence"].append({"record":"counter","bearing":"supports"})
        result = self.report()["premises"]["identified-request"]
        self.assertEqual(result["at_decision"], "support-recorded")
        self.assertEqual(result["as_of"], "contested")

    def test_action_requires_one_matching_instrument(self):
        proposals = self.report()["proposals"]
        self.assertEqual(proposals["remit"]["at_decision"], "within-declared-terms")
        self.assertEqual(proposals["admit-all"]["at_decision"], "no-matching-term")
        self.assertEqual(proposals["admit-all"]["partial_terms"]["individual-order"], ["office","procedure","reach"])
        first = self.packet["mandates"][0]
        first.update(office="review-panel", reach="all-affiliates")
        self.packet["mandates"].append(dict(first, id="other", office="hearing-office", procedure="recorded-decision"))
        self.assertEqual(self.report()["proposals"]["admit-all"]["at_decision"], "no-matching-term")

    def test_conflicting_prohibition_and_later_delegation(self):
        terms = self.packet["mandates"]
        terms.append(dict(terms[1], id="prohibition", position="forbids"))
        self.assertEqual(self.report()["proposals"]["remit"]["at_decision"], "conflicting-terms")
        self.packet["sources"].append({"id":"later-term","at":7,"kind":"mandate","topic":"remand","locator":"new charter"})
        terms[1]["record"] = "later-term"
        result = self.report()["proposals"]["remit"]
        self.assertEqual(result["at_decision"], "expressly-forbidden")
        self.assertEqual(result["later_exact_terms"], ["panel-remand"])

    def test_structural_conflict_and_testimony_survive_without_finding_intent(self):
        hearing = self.report()["hearing"]
        self.assertEqual(hearing["testimony_opportunity"], "excluded")
        self.assertTrue(hearing["compensation"]["arden"]["varies_by_listed_outcome"])
        self.assertEqual(hearing["members_without_fee_information"], ["lee", "ravi"])
        self.packet["hearing"]["compensation"][0]["amounts"]["remand"] = 10
        self.assertFalse(self.report()["hearing"]["compensation"]["arden"]["varies_by_listed_outcome"])
        self.packet["hearing"].update(opportunity="unknown", record=None, compensation=[])
        self.assertEqual(len(self.report()["hearing"]["members_without_fee_information"]), 3)

    def test_source_scope_time_and_types(self):
        for operation in (lambda p: p["sources"][0].update(at=8),
                          lambda p: p["panel"].update(record="dated-application"),
                          lambda p: p["mandates"][0].update(record="panel-charter"),
                          lambda p: p["hearing"].update(record=None),
                          lambda p: p["hearing"]["compensation"][0].update(member="visitor"),
                          lambda p: p["hearing"]["compensation"][0]["amounts"].update(remand=True),
                          lambda p: p["premises"][0]["evidence"].append({"record":"absent","bearing":"supports"}),
                          lambda p: p["premises"][0]["evidence"].extend(p["premises"][0]["evidence"]),
                          lambda p: p["sources"].extend([p["sources"][0]] * 33)):
            packet = deepcopy(self.packet)
            operation(packet)
            with self.assertRaises(ValueError):
                review(self.case, packet, as_of=7)

    def test_parent_digest_pins_evidence_and_keeps_verified_relief_separate(self):
        self.case["comparison_note"] = "invalid"
        with self.assertRaises(ValueError):
            self.report()
        del self.case["comparison_note"]
        self.case["followup"]["owner"] = "new-owner"
        with self.assertRaisesRegex(ValueError, "digest"):
            self.report()
        self.packet["case_digest"] = digest(self.case)
        self.assertEqual(self.report()["original_decision"]["followup_owner"], "new-owner")

    def test_cli_reads_strict_bounded_json(self):
        cmd = [sys.executable, "-m", "commonwealth.remediation_v1.opinion_review", str(CASE)]
        ok = subprocess.run([*cmd, str(OPINION), "--as-of", "7"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout), self.report())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.json"
            for content in ('{"a":1,"a":2}', 'NaN', ' ' * 1048577):
                target.write_text(content)
                bad = subprocess.run([*cmd, str(target), "--as-of", "7"], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(bad.returncode, 2)
                self.assertNotIn("Traceback", bad.stderr)
