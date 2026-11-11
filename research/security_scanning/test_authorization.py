"""Offline regression checks for the three synthetic failure classes."""
import unittest
from research.security_scanning.authorization import Gate, Principal

class SyntheticAuthorizationTests(unittest.TestCase):
    def test_public_data_exposure_denied(self):
        self.assertFalse(Gate().check(None, "alpha", "read_private"))

    def test_cross_team_denied_even_if_authenticated(self):
        self.assertFalse(Gate().check(Principal("user", frozenset({"beta"})), "alpha", "read_private"))

    def test_robot_requires_exact_approval_and_revocation(self):
        gate = Gate({"permit": ("operator", "alpha", "move_simulated")})
        principal = Principal("operator", frozenset({"alpha"}))
        self.assertFalse(gate.check(principal, "alpha", "move_simulated", robotic=True))
        self.assertFalse(gate.check(principal, "alpha", "other", "permit", robotic=True))
        self.assertTrue(gate.check(principal, "alpha", "move_simulated", "permit", robotic=True))
        gate.revoke("permit")
        self.assertFalse(gate.check(principal, "alpha", "move_simulated", "permit", robotic=True))
        self.assertEqual(len(gate.audit), 5)

if __name__ == "__main__":
    unittest.main()
