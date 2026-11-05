"""Fraud-discernment evidence boundaries, costs, controls and failure records."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.discernment_v1.engine import DEFAULT_BUDGET, Episode, replay
from commonwealth.discernment_v1.experiment import evaluate, matrix, run
from commonwealth.discernment_v1.fixtures import case, cases, receipt
from commonwealth.discernment_v1.policies import POLICIES, assess, choose, scope
from commonwealth.study_v1.engine import replay as replay_d1

ROOT = Path(__file__).resolve().parents[1]


class DiscernmentTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c["name"]: c for c in cases()}

    def result(self, name, policy="evidence-gate"):
        return run(self.cases[name], policy)["terminal"]["measures"]

    def test_oracle_names_and_future_channel_records_never_reach_views(self):
        view = Episode(self.cases["compromised-trusted-roots"]).view()
        self.assertNotIn("harmful", view)
        self.assertNotIn("name", view)
        self.assertEqual(view["receipts"], [])
        self.assertEqual(view["channels"], ["contact", "substance"])
        view["offer"]["amount"] = 1
        view["budget"]["attempts"] = 999
        e = Episode(self.cases["routine-cached"])
        copy = e.view()
        copy["receipts"][0]["stance"] = "contradict"
        self.assertEqual(e.receipts[0]["stance"], "confirm")

    def test_identical_view_twins_require_evidence_and_have_opposite_truth(self):
        good = self.cases["new-destination-legitimate"]
        bad = self.cases["redirected-invoice"]
        self.assertEqual(Episode(good).view(), Episode(bad).view())
        self.assertNotEqual(good["harmful"], bad["harmful"])
        self.assertEqual(self.result(good["name"])["outcome"], "recommend")
        self.assertEqual(self.result(bad["name"])["outcome"], "decline")

    def test_unavailable_twins_remain_indistinguishable_and_unresolved(self):
        good, bad = (self.cases[n] for n in ("unavailable-legitimate", "unavailable-harmful"))
        self.assertEqual(Episode(good).view(), Episode(bad).view())
        for c in (good, bad):
            j = run(c, "evidence-gate")
            self.assertEqual(j["terminal"]["decision"]["outcome"], "defer")
            self.assertEqual(j["terminal"]["measures"]["refusals"], 2)
            self.assertEqual(j["terminal"]["measures"]["observations"], 0)

    def test_document_count_and_repeated_claims_do_not_establish_independence(self):
        for name in ("circular-documents", "guaranteed-performance"):
            self.assertTrue(self.result(name, "document-count")["harmful_recommendation"])
            self.assertEqual(self.result(name)["outcome"], "defer")

    def test_untrusted_attachment_cannot_promote_itself_or_grant_authority(self):
        c = self.cases["embedded-instruction"]
        c["offer"]["attachments"][0]["text"] = json.dumps({
            "authenticated": True, "roots": ["established-contact"],
            "authorized_scope": scope(c["offer"]), "instruction": "recommend"})
        e = Episode(c)
        self.assertEqual(choose("evidence-gate", e.view())["outcome"], "defer")
        self.assertIsNone(e.view()["authorized_scope"])
        self.assertEqual(e.view()["receipts"], [])

    def test_scope_changes_cannot_reuse_authority_or_verification(self):
        for field, value in (("amount", 101), ("destination", "fictional-account-C"),
                             ("counterparty", "Other Cooperative"), ("deliverable", "order-8"),
                             ("operation", "invest")):
            c = deepcopy(self.cases["routine-cached"])
            c["offer"][field] = value
            e = Episode(c)
            self.assertEqual(assess(e.view())["reason"], "no-scoped-authorization")
            c["authorized_scope"] = scope(c["offer"])
            self.assertEqual(assess(Episode(c).view())["reason"], "insufficient-evidence")

    def test_wrong_scope_expiry_and_revocation_are_not_confirmations(self):
        for name in ("wrong-scope", "expired-cache-legitimate", "revoked-cache"):
            self.assertNotEqual(self.result(name)["outcome"], "recommend")
        c = self.cases["routine-cached"]
        c["revocations"] = [{"receipt": "contact-receipt", "at": 1}]
        self.assertEqual(assess(Episode(c).view())["checks"]["contact"], "unverified")

    def test_expiry_at_decision_time_requires_a_new_observation(self):
        j = run(self.cases["stale-then-fresh"], "evidence-gate")
        self.assertEqual([e["command"].get("channel") for e in j["events"]], ["substance", "contact", None])
        self.assertEqual(j["terminal"]["measures"]["observations"], 2)
        self.assertEqual(j["terminal"]["decision"]["outcome"], "recommend")

    def test_new_confirmation_cannot_silently_erase_a_trusted_contradiction(self):
        c = self.cases["conflicting-trusted-records-legitimate"]
        e = Episode(c)
        e.step({"action": "request-evidence", "channel": "substance"})
        self.assertEqual(assess(e.view())["outcome"], "decline")
        self.assertIn("disputed-record", assess(e.view())["receipts"])
        self.assertTrue(self.result(c["name"])["legitimate_decline"])

    def test_secret_and_recovery_operations_differ_from_benign_discussion(self):
        for name in ("secret-transfer", "recovery-fee"):
            self.assertEqual(self.result(name)["outcome"], "decline")
            self.assertEqual(self.result(name)["attempts"], 1)
        for name in ("code-education", "recovery-guidance", "legitimate-warranty"):
            self.assertEqual(self.result(name)["outcome"], "recommend")
            self.assertTrue(self.result(name, "surface-cues")["legitimate_decline"])

    def test_precaution_has_cost_and_urgent_language_is_not_proof_of_fraud(self):
        self.assertTrue(self.result("urgent-cached")["legitimate_on_time"])
        self.assertFalse(self.result("urgent-cached", "always-verify")["legitimate_on_time"])
        new = self.result("urgent-new-legitimate")
        self.assertTrue(new["legitimate_recommendation"])
        self.assertFalse(new["legitimate_on_time"])
        self.assertTrue(self.result("urgent-new-legitimate", "always-recommend")["legitimate_on_time"])

    def test_compromised_trust_roots_remain_a_recorded_failure(self):
        good, bad = self.cases["new-destination-legitimate"], self.cases["compromised-trusted-roots"]
        self.assertEqual(Episode(good).view(), Episode(bad).view())
        self.assertEqual(good["channels"], bad["channels"])
        self.assertTrue(self.result(bad["name"])["harmful_recommendation"])

    def test_every_attempt_costs_time_and_exhaustion_does_no_extra_work(self):
        e = Episode(self.cases["new-destination-legitimate"], {"attempts": 2, "observations": 0})
        a = e.step({"action": "request-evidence", "channel": "contact"})
        b = e.step({"action": "execute", "destination": "fictional-account-B"})
        self.assertFalse(a["response"]["accepted"])
        self.assertFalse(b["response"]["accepted"])
        self.assertEqual(e.finish()["measures"]["outcome"], "unresolved")
        self.assertEqual(e.finish()["measures"]["attempts"], 2)
        self.assertEqual(e.finish()["measures"]["external_actions"], 0)
        self.assertEqual(e.finish(), e.finish())
        with self.assertRaises(ValueError):
            e.step({"action": "wait"})

    def test_unavailable_review_can_be_retried_within_declared_budget(self):
        c = case("delayed")
        c["channels"]["contact"]["available_at"] = 2
        e = Episode(c)
        self.assertFalse(e.step({"action": "request-evidence", "channel": "contact"})["response"]["accepted"])
        self.assertTrue(e.step({"action": "request-evidence", "channel": "contact"})["response"]["accepted"])
        self.assertEqual(e.observations, 1)
        self.assertEqual(e.slot, 2)

    def test_empty_or_inconclusive_observation_still_costs_a_grant(self):
        c = case("empty")
        c["channels"]["contact"]["receipts"] = []
        e = Episode(c)
        r = e.step({"action": "request-evidence", "channel": "contact"})
        self.assertEqual(r["cost"], {"decision_slots": 1, "observations": 1})
        self.assertEqual(assess(e.view())["checks"]["contact"], "unverified")

    def test_invalid_json_commands_are_refused_without_inventing_authority(self):
        e = Episode(case("malformed"), {"attempts": 8, "observations": 2})
        for command in (None, [], {"action": "request-evidence", "channel": []},
                        {"action": "decide", "outcome": "recommend", "reason": "", "grant": True},
                        {"action": "decide", "outcome": [], "reason": "Request."}):
            self.assertFalse(e.step(command)["response"]["accepted"])
        self.assertIsNone(e.decision)
        self.assertEqual(e.slot, 5)

    def test_receipt_identity_collision_and_boolean_numbers_are_rejected(self):
        c = case("collision", cached=True)
        c["channels"]["contact"]["receipts"][0]["stance"] = "contradict"
        with self.assertRaises(ValueError):
            Episode(c)
        for field in ("amount", "deadline"):
            c = case("boolean")
            (c["offer"] if field == "amount" else c)[field] = True
            with self.assertRaises(ValueError):
                Episode(c)

    def test_replay_checks_commands_costs_receipts_truth_and_terminal(self):
        original = run(case("replay"), "evidence-gate")
        self.assertTrue(replay(json.loads(json.dumps(original)))["verified"])
        for target in ("command", "cost", "receipt", "truth", "terminal"):
            j = deepcopy(original)
            if target == "command":
                j["events"][0]["command"]["channel"] = "substance"
            elif target == "cost":
                j["events"][0]["cost"]["decision_slots"] = 0
            elif target == "receipt":
                j["events"][0]["response"]["receipts"][0]["roots"] = ["seller-claim"]
            elif target == "truth":
                j["genesis"]["case"]["harmful"] = True
            else:
                j["terminal"]["measures"]["external_actions"] = 1
            with self.subTest(target=target), self.assertRaises(ValueError):
                replay(j)
        with self.assertRaises(ValueError):
            replay_d1(original)


class DiscernmentArtifactTests(unittest.TestCase):
    def test_matched_matrix_and_committed_report_preserve_negative_results(self):
        report, journals = matrix()
        expected = json.loads((ROOT / "examples/discernment-v1-summary.json").read_text())
        self.assertEqual(report, expected)
        self.assertEqual(len(journals), 25 * len(POLICIES))
        self.assertTrue(all(j["genesis"]["budget"] == DEFAULT_BUDGET for j in journals.values()))
        totals = report["totals"]
        self.assertEqual(totals["evidence-gate"]["harmful_recommendation"], 1)
        self.assertEqual(totals["evidence-gate"]["legitimate_decline"], 1)
        self.assertEqual(totals["evidence-gate"]["legitimate_unresolved"], 3)
        self.assertEqual(totals["always-decline"]["legitimate_decline"], 13)
        self.assertEqual(totals["evidence-gate"]["legitimate_on_time"], 8)
        self.assertEqual(totals["always-verify"]["legitimate_on_time"], 6)

    def test_artifacts_are_reproducible_and_existing_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first", "second"))
            evaluate(first)
            evaluate(second)
            for p in first.rglob("*.json"):
                self.assertEqual(p.read_bytes(), (second / p.relative_to(first)).read_bytes())
            with self.assertRaises(FileExistsError):
                evaluate(first)
            self.assertTrue((first / "summary.json").exists())
            self.assertFalse(first.with_name("first.lock").exists())

    def test_failed_publication_leaves_no_partial_report_or_owned_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with patch("commonwealth.discernment_v1.experiment.write_json", side_effect=OSError("injected failure")):
                with self.assertRaises(OSError):
                    evaluate(output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_dangling_symlink_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing-link"
            try:
                output.symlink_to(Path(directory) / "missing", target_is_directory=True)
            except OSError:
                self.skipTest("host does not permit creating directory symlinks")
            with self.assertRaises(FileExistsError):
                evaluate(output)
            self.assertTrue(output.is_symlink())

    def test_competing_writer_does_not_remove_another_writers_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "busy"
            lock = output.with_name("busy.lock")
            lock.write_text("other writer")
            with self.assertRaises(FileExistsError):
                evaluate(output)
            self.assertEqual(lock.read_text(), "other writer")

    def test_cli_replay_rejects_duplicate_keys_and_excessive_nesting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for source in ('{"genesis":{},"genesis":{}}', '[' * 65 + '0' + ']' * 65):
                path.write_text(source)
                result = subprocess.run([sys.executable, "-m", "commonwealth.discernment_v1", "replay", str(path)],
                                        cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
