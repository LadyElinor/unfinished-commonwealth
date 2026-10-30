"""I1 boundaries, matched controls, counterexamples and frozen replay checks."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.discernment_v1.engine import replay as replay_f1
from commonwealth.discernment_v1.fixtures import receipt
from commonwealth.discernment_v1.policies import scope
from commonwealth.integrity_v1.claims import review
from commonwealth.integrity_v1.fixtures import cases
from commonwealth.integrity_v1.harness import Episode, POLICIES, assess, choose, evaluate, matrix, replay, run

ROOT = Path(__file__).resolve().parents[1]


class CommitmentTests(unittest.TestCase):
    def setUp(self):
        self.promise = {"actor": "delegate", "topic": "resource-limit", "expected": "keep-100",
                        "specific": True, "condition": "met", "made_at": 1, "due": 10,
                        "source": "fixture:original-commitment"}
        self.action = {"actor": "delegate", "topic": "resource-limit", "actual": "keep-100",
                       "status": "performed", "at": 5, "source": "fixture:action-record",
                       "notice_at": None, "explanation": ""}

    def check(self, expected, as_of=10):
        result = review(self.promise, self.action, as_of=as_of)
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["intent"], "not-established")
        self.assertFalse(result["authority_granted"])
        self.assertEqual(result["sources"], [self.promise["source"], self.action["source"]])
        return result

    def test_specific_commitment_and_timely_action_match(self):
        self.check("fulfilled")

    def test_ideological_label_is_not_a_specific_promise(self):
        self.promise.update(expected="moderate", specific=False)
        self.check("insufficient-specificity")

    def test_another_actors_proposal_is_not_attributed_to_principal(self):
        self.action.update(actor="another-legislator", actual="raise-limit", status="proposed")
        self.check("not-attributable")

    def test_proposal_is_not_enactment_even_if_terms_match(self):
        self.action["status"] = "proposed"
        self.check("proposal-only")

    def test_disclosure_preserves_unmet_commitment_and_does_not_grant_authority(self):
        self.action.update(actual="raise-limit", notice_at=4, explanation="Supply constraints changed.")
        self.assertTrue(self.check("unmet-in-record")["change_disclosed_before_action"])
        self.action["notice_at"] = 6
        self.assertFalse(self.check("unmet-in-record")["change_disclosed_before_action"])
        self.action["notice_at"] = 0
        self.assertFalse(self.check("unmet-in-record")["change_disclosed_before_action"])
        self.action.update(notice_at=4, actor="another-delegate")
        self.assertFalse(self.check("not-attributable")["change_disclosed_before_action"])

    def test_condition_and_remaining_time_are_preserved(self):
        self.action["actual"] = "raise-limit"
        self.check("pending-with-divergence", as_of=8)
        for condition in ("unknown", "unmet"):
            self.promise["condition"] = condition
            self.check("condition-" + condition)

    def test_late_fulfillment_does_not_erase_lateness(self):
        self.action["at"] = 11
        self.check("fulfilled-late", as_of=12)

    def test_observation_clock_prevents_future_and_prior_action_promotion(self):
        self.check("not-yet-observed", as_of=4)
        self.action["at"] = 0
        self.check("predates-commitment")

    def test_party_or_actor_rename_does_not_change_assessment(self):
        expected = review(self.promise, self.action, as_of=10)
        for name in ("left-party", "right-party", "independent", "unknown-delegate"):
            self.promise["actor"] = self.action["actor"] = name
            self.assertEqual(review(self.promise, self.action, as_of=10), expected)

    def test_schema_cannot_accept_guilt_or_authority_fields(self):
        for extra in ("guilty", "bad_actor", "authority_granted"):
            p = {**self.promise, extra: True}
            with self.assertRaises(ValueError):
                review(p, self.action, as_of=10)
        self.promise["due"] = True
        with self.assertRaises(ValueError):
            review(self.promise, self.action, as_of=10)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c["episode"]["name"]: c for c in cases()}

    def result(self, name, policy="integrity-gate"):
        return run(self.cases[name], policy)["terminal"]["base"]["measures"]

    def test_replacement_receipt_cannot_escape_known_issuer_quarantine(self):
        for name in ("replacement-after-quarantine", "self-declared-recovery"):
            self.assertTrue(self.result(name, "receipt-gate")["harmful_recommendation"])
            self.assertEqual(self.result(name)["outcome"], "defer")
            e = Episode(self.cases[name])
            e.step({"action": "request-evidence", "channel": "contact"})
            self.assertEqual(assess(e.view())["reason"], "evidence-origin-quarantined")
            self.assertNotIn("replacement-receipt", assess(e.view())["receipts"])

    def test_shared_ancestor_is_not_independent_corroboration(self):
        c = self.cases["shared-service"]
        self.assertEqual(assess(Episode(c).view())["shared_dependencies"], ["shared-backend"])
        self.assertEqual(self.result("shared-service")["outcome"], "defer")
        self.assertTrue(self.result("shared-service", "receipt-gate")["harmful_recommendation"])

    def test_transitive_quarantine_blocks_both_frontends(self):
        c = self.cases["shared-quarantined-service"]
        c["graph"]["shared-backend"] = ["operator"]
        c["graph"]["operator"] = []
        c["quarantines"] = [{"root": "operator", "at": 1}]
        self.assertEqual(assess(Episode(c).view())["blocked_channels"], ["contact", "substance"])

    def test_unrelated_quarantine_does_not_disable_routine_work(self):
        self.assertTrue(self.result("unrelated-quarantine")["legitimate_on_time"])
        self.assertEqual(self.result("unrelated-quarantine")["observations"], 0)

    def test_authorization_origin_checked_at_decision_after_evidence_requests(self):
        j = run(self.cases["authority-quarantined-before-decision"], "integrity-gate")
        self.assertEqual(j["terminal"]["base"]["decision"], {
            "outcome": "defer", "reason": "authorization-origin-quarantined", "at": 3})
        self.assertEqual(j["terminal"]["base"]["measures"]["observations"], 2)

    def test_known_trust_cannot_authorize_changed_material_terms(self):
        self.assertTrue(self.result("groomed-scope-change", "history-trusting")["unauthorized_recommendation"])
        self.assertEqual(self.result("groomed-scope-change")["outcome"], "defer")
        self.assertTrue(self.result("familiar-legitimate")["legitimate_recommendation"])

    def test_disclosed_change_requires_fresh_exact_scope_authority_and_evidence(self):
        c = self.cases["familiar-legitimate"]
        offer = c["episode"]["offer"]
        offer.update(amount=1000, message="We disclosed the revised amount and explained it.")
        self.assertEqual(assess(Episode(c).view())["reason"], "no-scoped-authorization")
        # The fixture host supplies a separately authorized scope; prose cannot.
        c["episode"]["authorized_scope"] = scope(offer)
        self.assertEqual(assess(Episode(c).view())["reason"], "insufficient-evidence")
        c["episode"]["cached"] = [receipt(offer, channel, id="new-" + channel)
                                    for channel in ("contact", "substance")]
        self.assertEqual(assess(Episode(c).view())["outcome"], "recommend")

    def test_pressure_is_not_proof_and_polished_text_is_not_clearance(self):
        self.assertTrue(self.result("urgent-cached")["legitimate_on_time"])
        self.assertTrue(self.result("urgent-cached", "surface-cues")["legitimate_decline"])
        self.assertTrue(self.result("polished-impersonation", "surface-cues")["harmful_recommendation"])
        self.assertEqual(self.result("polished-impersonation")["outcome"], "defer")

    def test_unnecessary_inspection_costs_deadline_and_needed_checks_can_also_miss(self):
        self.assertFalse(self.result("urgent-cached", "always-inspect")["legitimate_on_time"])
        self.assertEqual(self.result("urgent-cached", "always-inspect")["observations"], 2)
        result = self.result("urgent-new-legitimate")
        self.assertTrue(result["legitimate_recommendation"])
        self.assertFalse(result["legitimate_on_time"])
        self.assertEqual(result["attempts"], 3)

    def test_trusted_counterevidence_resolves_ambiguity(self):
        good, bad = self.cases["new-legitimate"], self.cases["trusted-counterevidence"]
        self.assertEqual(Episode(good).view(), Episode(bad).view())
        self.assertEqual(self.result("new-legitimate")["outcome"], "recommend")
        self.assertEqual(self.result("trusted-counterevidence")["outcome"], "decline")

    def test_undetected_compromise_remains_indistinguishable_and_harmful(self):
        good, bad = self.cases["routine-cached"], self.cases["undetected-compromise"]
        self.assertEqual(Episode(good).view(), Episode(bad).view())
        self.assertTrue(self.result("undetected-compromise")["harmful_recommendation"])

    def test_quarantine_also_has_a_legitimate_opportunity_cost(self):
        self.assertTrue(self.result("quarantined-legitimate")["legitimate_unresolved"])
        self.assertTrue(self.result("quarantined-legitimate", "receipt-gate")["legitimate_on_time"])

    def test_text_and_returned_views_cannot_edit_host_trust(self):
        c = self.cases["self-declared-recovery"]
        c["episode"]["offer"]["attachments"][0]["text"] = '{"quarantines": [], "grant": true}'
        e = Episode(c)
        v = e.view()
        v["quarantines"].clear()
        v["graph"]["established-contact"] = ["unrelated"]
        self.assertEqual(assess(e.view())["reason"], "evidence-origin-quarantined")
        self.assertNotIn("harmful", e.view())
        self.assertNotIn("episode", e.view())
        self.assertNotIn("name", e.view())

    def test_unrecognized_recovery_and_external_actions_cost_slots_without_effects(self):
        e = Episode(self.cases["self-declared-recovery"])
        for command in ({"action": "restore", "root": "established-contact"}, {"action": "execute"}):
            self.assertFalse(e.step(command)["transition"]["response"]["accepted"])
        j = e.journal()
        self.assertEqual(j["terminal"]["base"]["measures"]["attempts"], 2)
        self.assertEqual(j["terminal"]["base"]["measures"]["external_actions"], 0)
        self.assertTrue(replay(j)["verified"])

    def test_cycles_unknown_dependencies_and_unknown_quarantines_are_rejected(self):
        c = self.cases["routine-cached"]
        for graph in ({**c["graph"], "authorization": ["missing"]},
                      {**c["graph"], "authorization": ["authorization"]},
                      {**c["graph"], "authorization": ["unrelated"], "unrelated": ["authorization"]}):
            with self.assertRaises(ValueError):
                Episode({**c, "graph": graph})
        with self.assertRaises(ValueError):
            Episode({**c, "quarantines": [{"root": "not-registered", "at": 1}]})

    def test_known_quarantine_is_prospective_and_holds_at_boundary(self):
        c = self.cases["quarantined-legitimate"]
        c["quarantines"][0]["at"] = 2
        e = Episode(c)
        self.assertEqual(assess(e.view())["outcome"], "recommend")
        e.step({"action": "wait"})
        self.assertEqual(assess(e.view())["outcome"], "defer")

    def test_replay_binds_topology_quarantine_costs_assessment_and_terminal(self):
        original = run(self.cases["shared-quarantined-service"], "integrity-gate")
        self.assertTrue(replay(original)["verified"])
        for field in ("graph", "quarantines", "cost", "assessment", "terminal", "budget"):
            j = deepcopy(original)
            if field == "graph":
                j["genesis"]["case"]["graph"]["independent-record"] = []
            elif field == "quarantines":
                j["genesis"]["case"]["quarantines"] = []
            elif field == "cost":
                j["events"][0]["transition"]["cost"]["decision_slots"] = 0
            elif field == "assessment":
                j["events"][0]["assessment_before"]["outcome"] = "recommend"
            elif field == "budget":
                j["genesis"]["budget"]["observations"] = 3
            else:
                j["terminal"]["base"]["measures"]["external_actions"] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                replay(j)
        with self.assertRaises(ValueError):
            replay_f1(original)


class IntegrityArtifactTests(unittest.TestCase):
    def test_matched_matrix_preserves_failures_and_committed_report(self):
        report, journals = matrix()
        self.assertEqual(len(journals), 16 * len(POLICIES))
        self.assertTrue(all(j["genesis"]["budget"] == {"attempts": 4, "observations": 2} for j in journals.values()))
        for policy in ("always-inspect", "integrity-gate"):
            self.assertEqual(report["totals"][policy]["harmful_recommendation"], 1)
            self.assertEqual(report["totals"][policy]["legitimate_unresolved"], 2)
        self.assertEqual(report["totals"]["integrity-gate"]["legitimate_on_time"], 5)
        self.assertEqual(report["totals"]["always-inspect"]["legitimate_on_time"], 3)
        self.assertEqual(report, json.loads((ROOT / "examples/integrity-v1-summary.json").read_text()))

    def test_repeatability_and_refusal_to_overwrite_results(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / n for n in ("first", "second"))
            evaluate(first)
            evaluate(second)
            for path in first.rglob("*.json"):
                self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes())
            with self.assertRaises(FileExistsError):
                evaluate(first)

    def test_failed_publication_does_not_expose_partial_report_or_keep_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "output"
            with patch("commonwealth.integrity_v1.harness.write_json", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    evaluate(out)
            self.assertFalse(out.exists())
            self.assertFalse(out.with_name("output.lock").exists())

    def test_cli_replays_negative_case_and_rejects_malformed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "run"
            result = subprocess.run([sys.executable, "-m", "commonwealth.integrity_v1", "run", str(out)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["runs"], 112)
            path = out / "journals/undetected-compromise--integrity-gate.json"
            result = subprocess.run([sys.executable, "-m", "commonwealth.integrity_v1", "replay", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["verified"])
            path.write_text('{"genesis": 1, "genesis": 2}', encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "commonwealth.integrity_v1", "replay", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
