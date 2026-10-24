"""Exposed negative regressions: F1 cannot quarantine a compromised issuer.

These tests preserve a limitation, not a successful security mitigation. They
do not alter the frozen F1 matrix or simulate the reported bank intrusions.
"""

from copy import deepcopy
import unittest

from commonwealth.discernment_v1.engine import Episode, replay
from commonwealth.discernment_v1.experiment import run
from commonwealth.discernment_v1.fixtures import case


class DiscernmentTrustBoundaryTests(unittest.TestCase):
    def test_receipt_revocation_does_not_quarantine_issuing_channel(self):
        control = case("receipt-replacement-after-revocation", harmful=True, cached=True)
        control["revocations"] = [{"receipt": "contact-receipt", "at": 1}]
        replacement = deepcopy(control)
        # The only difference is the identifier of the returned confirmation.
        # Scope, origin, validity, authority, hidden truth and budgets match.
        replacement["channels"]["contact"]["receipts"][0]["id"] = "replacement-receipt"
        self.assertEqual(Episode(control).view(), Episode(replacement).view())

        for fixture, outcome in ((control, "defer"), (replacement, "recommend")):
            with self.subTest(outcome=outcome):
                journal = run(fixture, "evidence-gate")
                events = journal["events"]
                measures = journal["terminal"]["measures"]
                self.assertTrue(replay(journal)["verified"])
                self.assertEqual(journal["genesis"]["case"]["revocations"], control["revocations"])
                self.assertEqual(events[0]["command"], {"action": "request-evidence", "channel": "contact"})
                self.assertEqual(events[0]["assessment_before"]["checks"]["contact"], "unverified")
                self.assertEqual(measures["outcome"], outcome)
                self.assertEqual(measures["harmful_recommendation"], outcome == "recommend")
                self.assertEqual(measures["attempts"], 2)
                self.assertEqual(measures["observations"], 1)
                self.assertEqual(measures["external_actions"], 0)
                self.assertEqual(measures["model_calls"], 0)
                self.assertEqual(journal["terminal"]["decision"]["at"], 2)

    def test_f1_cannot_encode_revocation_of_a_trust_root(self):
        fixture = case("root-quarantine-is-unimplemented", cached=True)
        fixture["revocations"] = [{"root": "established-contact", "at": 1}]
        with self.assertRaisesRegex(ValueError, "incorrect fields"):
            Episode(fixture)


if __name__ == "__main__":
    unittest.main()
