import os
import tempfile
import unittest
from research.grok_integration.durable_gateway import DurableGateway
from research.grok_integration.secure_gateway import sign_approval

KEY = b"g" * 32
REQ = {"actor": "agent", "action": "publish", "resource": "synthetic"}
POLICY = {"grants": {"agent": {"publish": ["synthetic"]}}}

class DurableGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "gateway.sqlite")
        self.gateway = DurableGateway(self.path, KEY)
        self.approval = dict(REQ, nonce="once", issued_at=10, expires_at=20, approved=True)
        self.signature = sign_approval(self.approval, KEY)

    def test_first_allowed_second_denied(self):
        self.assertTrue(self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).allowed)
        self.assertEqual(self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).reason, "replayed_approval")

    def test_replay_denied_after_restart(self):
        self.assertTrue(self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).allowed)
        restarted = DurableGateway(self.path, KEY)
        self.assertFalse(restarted.decide(REQ, POLICY, self.approval, self.signature, now=15).allowed)

    def test_denied_does_not_consume_nonce(self):
        self.assertFalse(self.gateway.decide(REQ, {"grants": {}}, self.approval, self.signature, now=15).allowed)
        self.assertTrue(self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).allowed)

    def test_invalid_signature_denied(self):
        self.assertFalse(self.gateway.decide(REQ, POLICY, self.approval, "bad", now=15).allowed)

    def test_audit_contains_decisions(self):
        import sqlite3
        self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
