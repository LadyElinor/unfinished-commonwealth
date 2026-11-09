"""Regression cases for decisions that depend on a particular comparator, role or time."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commonwealth.decision_premises import review
from commonwealth.study_v1.engine import digest


EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "decision_premises"


class PremiseReviewTests(unittest.TestCase):
    def setUp(self):
        self.decision = json.loads((EXAMPLES / "decision.json").read_text())
        self.supplement = json.loads((EXAMPLES / "supplement.json").read_text())

    def question(self, name):
        report = review(self.decision, self.supplement)
        return next(q for q in report["questions"] if q["id"] == name)

    def entry(self, name):
        return next(r for r in self.supplement["records"] if r["id"] == name)

    def test_reappraisal_preserves_decision_and_downstream_limits(self):
        decision, supplement = deepcopy(self.decision), deepcopy(self.supplement)
        first, later = review(decision), review(decision, supplement)
        self.assertEqual(first["decision_digest"], later["decision_digest"])
        self.assertEqual([q["original"] for q in first["questions"]],
                         [q["original"] for q in later["questions"]])
        self.assertEqual((decision, supplement), (self.decision, self.supplement))
        self.assertEqual(later["intent"], "not-established")
        self.assertIs(later["authority_granted"], False)
        self.assertEqual(later["external_actions"], 0)
        self.assertNotIn(self.decision["records"][0]["account"], json.dumps(later))

    def test_changed_premise_or_old_evidence_breaks_parent_binding(self):
        for part, key in (("rules", "rival"), ("records", "account")):
            altered = deepcopy(self.decision)
            altered[part][0][key] += " revised"
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, "different decision"):
                review(altered, self.supplement)

    def test_rate_uses_a_matched_change_and_reports_exact_difference(self):
        q = self.question("effect")
        self.assertEqual(q["original"], "unresolved")
        self.assertEqual(q["historical_followup"], "reconsider-finding")
        self.assertEqual(q["records"][1]["basis"], "relative-change=-3/20")
        self.assertEqual(q["records"][1]["timing"], "later-disclosed-original-event")
        # Double the comparator cohort and numerator. Its rate stays identical.
        self.entry("paired-returns")["data"]["comparison_after"] = [130, 200]
        self.assertEqual(self.question("effect"), q)
        self.entry("paired-returns")["data"]["comparison_after"] = [40, 100]
        self.assertEqual(self.question("effect")["historical_followup"], "no-change-trigger-shown")

    def test_incomparable_rate_or_missing_denominator_cannot_validate_effect(self):
        row = self.entry("paired-returns")["data"]
        for key, value in (("comparison", "another-place"), ("before", 1), ("comparison_before", None)):
            with self.subTest(key=key):
                saved = row[key]
                row[key] = value
                self.assertEqual(self.question("effect")["historical_review"], "unresolved")
                row[key] = saved
        row["treated_before"] = [4, 0]
        with self.assertRaises(ValueError):
            self.question("effect")

    def test_parallel_outcomes_and_later_observations_do_not_establish_agreement(self):
        q = self.question("agreement")
        self.assertEqual(q["original"], "unresolved")
        self.assertEqual(q["historical_followup"], "open-inquiry")
        self.entry("meeting-record")["event_at"] = 7
        q = self.question("agreement")
        self.assertEqual(q["historical_review"], "unresolved")
        self.assertEqual(q["subsequent_followup"], "review-subsequent-event")

    def test_returned_notice_and_opposed_readings_survive_reappraisal(self):
        self.assertEqual(self.question("notice")["historical_followup"], "renew-notice")
        q = self.question("disputed-reading")
        self.assertEqual(q["historical_review"], "conflicting-records")
        self.assertEqual(q["records"][1]["timing"], "available-then-omitted")
        self.supplement["records"].append(dict(self.entry("second-reader"), id="third-reader"))
        self.assertEqual(self.question("disputed-reading")["historical_review"], "conflicting-records")

    def test_votes_on_result_or_summary_cannot_establish_agreement_on_reasons(self):
        q = self.question("earlier-ruling")
        self.assertEqual(q["original"], "unresolved")
        self.assertEqual(q["historical_followup"], "reconsider-finding")
        data = self.entry("paragraph-vote")["data"]
        data["joined"] += ["cedar", "dove", "elm"]
        for role in ("syllabus", "judgment-only", "separate-writing"):
            with self.subTest(role=role):
                data["part"] = role
                self.assertEqual(self.question("earlier-ruling")["historical_review"], "unresolved")
        data["part"] = "reasons"
        self.assertEqual(self.question("earlier-ruling")["historical_followup"], "no-change-trigger-shown")
        data["joined"][0] = "unrelated-officer"
        self.assertEqual(self.question("earlier-ruling")["historical_review"], "unresolved")

    def test_distinct_controller_substance_and_reversal_power_are_each_necessary(self):
        row = next(r for r in self.decision["records"] if r["id"] == "chair-review")
        for controller, examined, reverse, triggered in (
            ("licence-guild", True, True, True), ("exchange-desk", True, True, True),
            ("separate-office", False, True, True), ("separate-office", True, False, True),
            ("separate-office", True, True, False)):
            with self.subTest(controller=controller, examined=examined, reverse=reverse):
                row["data"] = dict(reviewer_controller=controller, examined_merits=examined, can_reverse=reverse)
                self.supplement["decision_digest"] = digest(self.decision)
                self.assertEqual(self.question("supervision")["historical_review"] == "change-condition-reported", triggered)

    def test_missing_supervision_information_is_inconclusive(self):
        row = next(r for r in self.decision["records"] if r["id"] == "chair-review")
        row["data"] = {"reviewer_controller": None, "examined_merits": True, "can_reverse": None}
        self.supplement["decision_digest"] = digest(self.decision)
        self.assertEqual(self.question("supervision")["historical_review"], "unresolved")

    def test_grant_requires_right_act_issuer_actor_scope_and_original_time(self):
        row = self.entry("later-instrument")
        self.assertEqual(self.question("mandate")["historical_review"], "unresolved")
        row["event_at"] = 3
        self.assertEqual(self.question("mandate")["historical_followup"], "refer-for-mandate-review")
        for key in ("action", "actor", "issuer"):
            before = row["data"][key]
            row["data"][key] = "other"
            self.assertEqual(self.question("mandate")["historical_review"], "unresolved")
            row["data"][key] = before
        row["scope"] = "another-exchange"
        self.assertEqual(self.question("mandate")["historical_review"], "unresolved")
        row["scope"] = "exchange-east"
        row["data"]["ends"] = 5
        self.assertEqual(self.question("mandate")["historical_review"], "unresolved")
        self.supplement["records"].append(dict(row, id="other-mandate", data=dict(row["data"], ends=9)))
        self.assertEqual(self.question("mandate")["historical_followup"], "refer-for-mandate-review")

    def test_group_and_paperwork_cannot_resolve_a_persons_relief(self):
        q = self.question("personal-relief")
        self.assertEqual(q["historical_review"], "unresolved")
        self.assertEqual(q["subsequent_followup"], "verify-individual-relief")
        row = self.entry("door-check")
        for key, value in (("scope", "all-members"), ("stage", "merits"), ("criterion", "hearing-ordered")):
            with self.subTest(key=key):
                before = row[key]
                row[key] = value
                self.assertEqual(self.question("personal-relief")["subsequent_events"], "unresolved")
                row[key] = before

    def test_licence_burden_needs_a_matched_attributable_impact(self):
        q = self.question("licence-charge")
        self.assertEqual(q["original"], "unresolved")
        self.assertEqual(q["records"][1]["basis"], "excess-over-declared-impact=20")
        self.assertEqual(q["historical_followup"], "reconsider-finding")
        data = self.entry("work-study")["data"]
        data["attributable"] = 30
        self.assertEqual(self.question("licence-charge")["historical_followup"], "no-change-trigger-shown")
        data["unit"] = "tokens"
        self.assertEqual(self.question("licence-charge")["historical_review"], "unresolved")

    def test_poor_outcomes_leave_original_purpose_open_until_relevant_evidence_arrives(self):
        self.assertEqual(self.question("purpose")["historical_review"], "unresolved")
        later = self.entry("missed-forecast")
        earlier = dict(later, id="advance-commitment", kind="observation", data={"value": True},
                       event_at=2, available_at=8, source="dated-minutes",
                       account="A signed commitment to the selected provider preceded the public plan.")
        self.supplement["records"].append(earlier)
        self.assertEqual(self.question("purpose")["historical_followup"], "reconsider-finding")
        self.assertEqual(review(self.decision, self.supplement)["intent"], "not-established")

    def test_successive_supplements_keep_disagreement_and_validate_previous_checkpoint(self):
        repair = dict(self.entry("door-check"), id="restored", available_at=10, event_at=10,
                      data={"value": True}, account="The original hearing is now accessible.")
        second = dict(self.supplement, as_of=10, records=[repair], previous_digest=digest(self.supplement))
        report = review(self.decision, self.supplement, second)
        self.assertEqual(report["supplement_digests"], [digest(self.supplement), digest(second)])
        q = next(q for q in report["questions"] if q["id"] == "personal-relief")
        self.assertEqual(q["subsequent_events"], "different-results-over-time")
        self.assertEqual(q["subsequent_followup"], "verify-individual-relief")
        with self.assertRaisesRegex(ValueError, "predecessor mismatch"):
            review(self.decision, second)
        tampered = deepcopy(self.supplement)
        tampered["records"].pop()
        with self.assertRaisesRegex(ValueError, "predecessor mismatch"):
            review(self.decision, tampered, second)
        second["as_of"] = 8
        with self.assertRaises(ValueError):
            review(self.decision, self.supplement, second)
        second["as_of"] = 10
        self.entry("door-check")["available_at"] = 10
        second["previous_digest"] = digest(self.supplement)
        with self.assertRaises(ValueError):
            review(self.decision, self.supplement, second)

    def test_benefit_or_observed_urgency_cannot_substitute_for_a_mandate(self):
        rule = next(r for r in self.decision["rules"] if r["id"] == "mandate")
        rule.update(method="observation", parameters={})
        with self.assertRaisesRegex(ValueError, "requires a mandate"):
            review(self.decision)

    def test_reject_ambiguous_id_chronology_and_attempt_to_turn_inquiry_into_judgment(self):
        self.supplement["records"].append(self.entry("door-check"))
        with self.assertRaisesRegex(ValueError, "duplicate record"):
            review(self.decision, self.supplement)
        self.supplement["records"].pop()
        self.entry("door-check")["available_at"] = 99
        with self.assertRaises(ValueError):
            review(self.decision, self.supplement)
        self.decision["rules"][1]["on_change"] = "reconsider-finding"
        with self.assertRaisesRegex(ValueError, "outside decision stage"):
            review(self.decision)

    def test_cli_validates_raw_inputs_and_emits_only_sourced_findings(self):
        cli = [sys.executable, "-m", "commonwealth.decision_premises", str(EXAMPLES / "decision.json")]
        ok = subprocess.run(cli + [str(EXAMPLES / "supplement.json")], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(ok.stdout), review(self.decision, self.supplement))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for raw in ('{"schema": 1, "schema": 2}', 'null', ' ' * (1024**2 + 1)):
                path.write_text(raw)
                bad = subprocess.run(cli + [str(path)], capture_output=True, text=True)
                self.assertEqual(bad.returncode, 2)
                self.assertFalse(bad.stdout)


if __name__ == "__main__":
    unittest.main()
