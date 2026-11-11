"""Synthetic regression tests for research/grok_integration."""
import unittest
from fractions import Fraction
from research.grok_integration.gates import authorize
from research.grok_integration.engineering import (
    constant_acceleration, thrust_to_weight, ideal_delta_v_exhaust_units
)

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "grants": {"agent-a": {"simulate": ["fixture-1"], "publish": ["report-1"], "robot_command": ["sim-rover"]}},
            "approvals": {"approval-1": {"actor": "agent-a", "action": "publish", "resource": "report-1", "approved": True}}
        }

    def test_simulation_granted(self):
        self.assertTrue(authorize({"actor": "agent-a", "action": "simulate", "resource": "fixture-1"}, self.policy).allowed)

    def test_unknown_actor_denied(self):
        self.assertFalse(authorize({"actor": "unknown", "action": "simulate", "resource": "fixture-1"}, self.policy).allowed)

    def test_missing_policy_denied(self):
        self.assertFalse(authorize({"actor": "agent-a", "action": "simulate", "resource": "fixture-1"}, {}).allowed)

    def test_publication_requires_exact_approval(self):
        request = {"actor": "agent-a", "action": "publish", "resource": "report-1"}
        self.assertFalse(authorize(request, self.policy).allowed)
        self.assertTrue(authorize({**request, "approval": "approval-1"}, self.policy).allowed)
        self.assertFalse(authorize({**request, "resource": "report-2", "approval": "approval-1"}, self.policy).allowed)

    def test_robot_command_not_approved(self):
        self.assertFalse(authorize({"actor": "agent-a", "action": "robot_command", "resource": "sim-rover", "approval": "approval-1"}, self.policy).allowed)

    def test_malformed_grant_denied(self):
        self.assertFalse(authorize({"actor": "agent-a", "action": "simulate", "resource": "fixture-1"}, {"grants": {"agent-a": {"simulate": "*"}}}).allowed)

class EngineeringTests(unittest.TestCase):
    def test_exact_acceleration(self):
        self.assertEqual(constant_acceleration(0, 0, 6, 3), (Fraction(27), Fraction(18)))

    def test_exact_fraction(self):
        self.assertEqual(constant_acceleration(0, 1, Fraction(1, 3), 3), (Fraction(9, 2), Fraction(2)))

    def test_thrust_weight(self):
        self.assertEqual(thrust_to_weight(1962, 100, Fraction(981, 100)), Fraction(2))

    def test_mass_ratio(self):
        self.assertEqual(ideal_delta_v_exhaust_units(3000, 200, 100), (Fraction(2), Fraction(3000)))

    def test_reject_bad_inputs(self):
        with self.assertRaises(ValueError):
            thrust_to_weight(100, 0, 10)
        with self.assertRaises(ValueError):
            constant_acceleration(0, 0, 1, -1)

if __name__ == "__main__":
    unittest.main()
