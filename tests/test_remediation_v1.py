"""Exposed fictional regression cases, not evidence of real governance benefit."""

from copy import deepcopy
import unittest
import tempfile
from pathlib import Path

from commonwealth.remediation_v1.__main__ import load_packet

from commonwealth.remediation_v1.review import review


def packet():
    return {
        "scope": "failed-sensor-batch", "decision_controller": "original-office",
        "records": [
            {"id": "warning", "at": 1, "source": "test-log", "kind": "warning", "text": "Required test failed."},
            {"id": "dissent", "at": 2, "source": "affected-service", "kind": "dissent", "text": "Do not freeze unrelated batches."},
            {"id": "clear", "at": 2, "source": "separate-test", "kind": "exonerating", "text": "Other batches passed."},
        ],
        "finding": {"status": "substantiated-defect", "basis": ["warning"]},
        "warning": {"record": "warning", "received_at": 2, "response": None, "opportunity": "open"},
        "options": [
            {"id": "targeted-inspection", "scope": "failed-sensor-batch", "authority_ref": "host-grant-1", "duration": 1, "prevented_loss": 8, "restriction_loss": 1},
            {"id": "freeze-everything", "scope": "all-batches", "authority_ref": "host-grant-1", "duration": 3, "prevented_loss": 8, "restriction_loss": 12},
        ],
        "repair": None,
    }


def repaired():
    result = packet()
    result["records"].append({"id": "check", "at": 5, "source": "independent-test-log", "kind": "observation", "text": "One repaired batch passed required test."})
    result["repair"] = {"id": "repair-1", "scope": result["scope"], "implementer_controller": "repair-office", "ordered_at": 3,
                        "implemented_at": 4, "criterion": "required-test-on-batch",
                        "checks": [{"record": "check", "reviewer_controller": "independent-office", "criterion": "required-test-on-batch", "result": "pass"}]}
    return result


class RemediationTests(unittest.TestCase):
    def test_targeted_inspection_does_not_wait_for_intent(self):
        result = review(packet(), as_of=6)
        self.assertEqual(result["protection"], "consider-bounded-protection")
        self.assertEqual(result["selected_option"], "targeted-inspection")
        self.assertEqual(result["intent"], "not-established")
        self.assertFalse(result["authority_granted"])
        self.assertFalse(result["production_ready"])
        self.assertEqual(result["external_actions"], 0)

    def test_pair_innocent_service_overbroad_freeze(self):
        case = packet()
        case["finding"] = {"status": "contradicted", "basis": ["clear"]}
        case["options"] = [case["options"][1]]
        result = review(case, as_of=6)
        self.assertEqual(result["protection"], "reconsider-adverse-reliance")
        self.assertIsNone(result["selected_option"])
        self.assertEqual(result["packet"]["records"], case["records"])
        self.assertEqual(result["intent"], "not-established")

    def test_preserve_original_warning_dissent_and_exoneration(self):
        case = packet()
        result = review(case, as_of=6)
        self.assertEqual(result["packet"], case)
        result["packet"]["records"][0]["text"] = "changed"
        self.assertEqual(case["records"][0]["text"], "Required test failed.")

    def test_digest_changes_when_exonerating_record_changes(self):
        case = packet()
        old = review(case, as_of=6)["packet_digest"]
        case["records"][2]["text"] = "Correction: more batches passed."
        self.assertNotEqual(review(case, as_of=6)["packet_digest"], old)

    def test_unknown_delivery_requires_routing_not_ignored_accusation(self):
        case = packet()
        case["warning"]["received_at"] = None
        self.assertEqual(review(case, as_of=6)["warning_followup"], "verify-warning-delivery")

    def test_receipt_without_response_needs_documented_response(self):
        self.assertEqual(review(packet(), as_of=6)["warning_followup"], "documented-response-needed")

    def test_response_is_not_proof_of_effectiveness(self):
        case = packet()
        case["records"].append({"id": "response", "at": 3, "source": "office", "kind": "response", "text": "We fixed it."})
        case["warning"].update(response="response", opportunity="responded")
        result = review(case, as_of=6)
        self.assertEqual(result["warning_followup"], "response-recorded-not-validated")
        self.assertEqual(result["repair_status"], "no-repair-record")

    def test_order_alone_is_not_implemented(self):
        case = repaired()
        case["repair"]["implemented_at"] = None
        self.assertEqual(review(case, as_of=6)["repair_status"], "ordered-not-implemented")

    def test_implementation_alone_is_not_effectiveness(self):
        case = repaired()
        case["repair"]["checks"] = []
        self.assertEqual(review(case, as_of=6)["repair_status"], "effectiveness-unverified")

    def test_independent_observation_is_bounded(self):
        self.assertEqual(review(repaired(), as_of=6)["repair_status"], "supplied-record-supports-declared-criterion")

    def test_self_verification_cannot_close_repair(self):
        for controller in ("original-office", "repair-office"):
            case = repaired()
            case["repair"]["checks"][0]["reviewer_controller"] = controller
            self.assertEqual(review(case, as_of=6)["repair_status"], "effectiveness-unverified")

    def test_preimplementation_or_wrong_criterion_cannot_close(self):
        for key, value in (("criterion", "unrelated-test"), ("at", 3)):
            case = repaired()
            if key == "at":
                case["records"][-1][key] = value
            else:
                case["repair"]["checks"][0][key] = value
            self.assertEqual(review(case, as_of=6)["repair_status"], "effectiveness-unverified")

    def test_later_success_does_not_erase_failed_check(self):
        case = repaired()
        case["repair"]["checks"][0]["result"] = "fail"
        case["records"].append({"id": "later", "at": 6, "source": "test-two", "kind": "observation", "text": "Later sample passed."})
        check = deepcopy(case["repair"]["checks"][0])
        check.update(record="later", result="pass")
        case["repair"]["checks"].append(check)
        result = review(case, as_of=6)
        self.assertEqual(result["repair_status"], "failed-independent-check")
        self.assertEqual(len(result["checks"]), 2)

    def test_nonqualifying_failure_still_requires_review(self):
        for controller, criterion in (("original-office", "required-test-on-batch"),
                                      ("independent-office", "other-criterion")):
            case = repaired()
            case["records"].append({"id": "failed", "at": 6, "source": "another-log", "kind": "observation", "text": "A concern remains."})
            case["repair"]["checks"].append({"record": "failed", "reviewer_controller": controller,
                                               "criterion": criterion, "result": "fail"})
            self.assertEqual(review(case, as_of=6)["repair_status"], "adverse-observation-needs-review")

    def test_same_time_check_cannot_prove_post_repair_outcome(self):
        case = repaired()
        case["records"][-1]["at"] = case["repair"]["implemented_at"]
        result = review(case, as_of=6)
        self.assertEqual(result["repair_status"], "effectiveness-unverified")
        self.assertEqual(result["assurance"], "unverified-host-supplied-records")

    def test_inconclusive_check_blocks_effectiveness(self):
        case = repaired()
        case["repair"]["checks"][0]["result"] = "inconclusive"
        self.assertEqual(review(case, as_of=6)["repair_status"], "effectiveness-unverified")

    def test_unresolved_finding_does_not_recommend_restriction(self):
        case = packet()
        case["finding"]["status"] = "unresolved"
        result = review(case, as_of=6)
        self.assertEqual(result["protection"], "review-needed-no-supported-restriction")
        self.assertEqual(result["warning_followup"], "documented-response-needed")

    def test_no_authority_or_no_net_protection(self):
        for change in ({"authority_ref": None}, {"restriction_loss": 8}, {"scope": "other"}):
            case = packet()
            case["options"][0].update(change)
            self.assertIsNone(review(case, as_of=6)["selected_option"])

    def test_invalid_records_are_rejected(self):
        for change in (lambda c: c["records"].append(deepcopy(c["records"][0])),
                       lambda c: c["finding"].update(basis=["missing"]),
                       lambda c: c["finding"].update(basis=[]),
                       lambda c: c["finding"].update(basis=[["bad"]]),
                       lambda c: c["finding"].update(basis=[{"bad": "id"}]),
                       lambda c: c["records"][0].update(at=7),
                       lambda c: c["warning"].update(received_at=0),
                       lambda c: c["warning"].update(opportunity="responded"),
                       lambda c: c["options"][0].update(duration=True),
                       lambda c: c.update(intent="fraud")):
            case = packet()
            change(case)
            with self.assertRaises(ValueError):
                review(case, as_of=6)

    def test_loader_rejects_duplicate_json_keys_at_any_depth(self):
        for raw in ('{"finding": 1, "finding": 2}', '{"finding": {"status": "unresolved", "status": "contradicted"}}'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "packet.json"
                path.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                    load_packet(path)

    def test_loader_limits_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "exceeds"):
                load_packet(path)

    def test_no_output_alias_to_input(self):
        case = repaired()
        result = review(case, as_of=6)
        case["repair"]["checks"][0]["result"] = "fail"
        self.assertEqual(result["checks"][0]["result"], "pass")


if __name__ == "__main__":
    unittest.main()
