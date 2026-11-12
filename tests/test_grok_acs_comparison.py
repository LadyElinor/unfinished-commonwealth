"""Offline custody checks for the observed comparison; native replay has its own CI job."""
from copy import deepcopy
import json
import unittest

from research.acs_comparison.__main__ import HERE, KEY, compare, fixture, inputs, sha
from research.grok_integration.secure_gateway import sign_approval


class ComparisonEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((HERE / "observed-source-build.json").read_bytes())
        self.expected = json.loads((HERE / "expected.json").read_bytes())

    def test_all_six_cases_and_matching_inputs(self):
        names = {"replay", "unauthorized_publication", "cross_agent_delegation",
                 "missing_evidence", "embedded_tool_request", "interrupted_execution"}
        self.assertEqual(set(self.expected), names)
        self.assertEqual(set(self.report["cases"]), names)
        for case in names:
            compare(case, self.report["cases"][case], self.expected[case])
        for field, name in [("rego_sha256", "policy/comparison.rego"), ("oracle_sha256", "expected.json"),
                            ("manifest_sha256", "manifest.yaml"), ("cortac_projection_sha256", "cortac-input.json")]:
            self.assertEqual(self.report[field], sha((HERE / name).read_bytes()))
        self.assertEqual(fixture()["receipt"]["id"], "r4")

    def test_replay_and_recovery_receipts(self):
        replay = self.report["cases"]["replay"]
        for field in ("snapshot_sha256", "approval_sha256", "confirmation"):
            self.assertEqual(len({r[field] for r in replay}), 1)
        for row in replay:
            self.assertEqual(row["sink_receipts"], [row["confirmation"]])
        crash = self.report["delivery_recovery"]
        first, later = crash["after_exit"], crash["after_reopen"]
        self.assertIsNone(first["confirmation"])
        self.assertEqual(first["outbox"], "pending")
        self.assertEqual(later["outbox"], "confirmed")
        self.assertEqual(first["sink_receipts"], [later["confirmation"]])
        self.assertEqual(first["sink_receipts"], later["sink_receipts"])

    def test_lost_disagreement_is_rejected(self):
        rows = deepcopy(self.report["cases"]["missing_evidence"])
        rows[0]["shadow_allowed"] = False
        with self.assertRaises(ValueError):
            compare("missing_evidence", rows, self.expected["missing_evidence"])

    def test_translated_inputs_keep_distinct_authorities(self):
        for case in self.expected:
            request, grants, approval, signature, snapshot = inputs(case, "fixture-sink")
            self.assertEqual(signature, sign_approval(approval, KEY))
            self.assertEqual(snapshot["tool_call"]["name"], request["action"])
            self.assertEqual(snapshot["envelope"]["agent"]["id"], request["actor"])
            self.assertEqual(set(grants["grants"]), {"executor"})
            self.assertNotIn("signature", str(snapshot))
            self.assertNotIn("used_nonces", str(snapshot))
            self.assertEqual(snapshot["tool_call"]["args"]["receipt"]["scope"], "SYNTHETIC_SCRATCH_ONLY")
