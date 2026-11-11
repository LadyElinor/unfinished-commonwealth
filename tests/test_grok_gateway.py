import unittest
from research.grok_integration.secure_gateway import Gateway, sign_approval

KEY = b"k" * 32
POLICY = {"grants": {"agent": {"publish": ["synthetic-report"]}}}
REQUEST = {"actor": "agent", "action": "publish", "resource": "synthetic-report"}

class SignedGatewayTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Gateway(KEY, set())
        self.approval = dict(REQUEST, nonce="unique-1", issued_at=100, expires_at=200, approved=True)

    def decide(self, approval=None, signature=None, request=None, policy=None, now=150):
        approval = self.approval if approval is None else approval
        signature = sign_approval(approval, KEY) if signature is None else signature
        return self.gateway.decide(REQUEST if request is None else request,
                                   POLICY if policy is None else policy,
                                   approval, signature, now=now)

    def test_signed_authorization(self):
        self.assertTrue(self.decide().allowed)

    def test_replay_rejected(self):
        self.assertTrue(self.decide().allowed)
        self.assertEqual(self.decide().reason, "replayed_approval")

    def test_expiry(self):
        self.assertFalse(self.decide(now=201).allowed)

    def test_future_issued(self):
        self.assertFalse(self.decide(now=99).allowed)

    def test_tampered_signature(self):
        self.assertFalse(self.decide(signature="0"*64).allowed)

    def test_scope_mismatch(self):
        request = dict(REQUEST, resource="another-report")
        self.assertFalse(self.decide(request=request).allowed)

    def test_missing_grant(self):
        self.assertFalse(self.decide(policy={"grants": {}}).allowed)

    def test_unsigned_decision_does_not_grant(self):
        self.assertFalse(self.decide(signature="").allowed)

    def test_denied_approval(self):
        approval = dict(self.approval, approved=False)
        self.assertFalse(self.decide(approval=approval).allowed)

    def test_invalid_key(self):
        with self.assertRaises(ValueError):
            Gateway(b"short", set())

if __name__ == "__main__":
    unittest.main()
