from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest.mock import patch
import sqlite3
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
        self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)

    def test_two_gateways_share_one_nonce(self):
        start = Barrier(2)
        def decide():
            gateway = DurableGateway(self.path, KEY)
            start.wait(timeout=5)
            return gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).reason
        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [pool.submit(decide) for _ in range(2)]
            self.assertCountEqual([future.result() for future in attempts],
                                  ["signed_authorization", "replayed_approval"])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT allowed FROM decisions ORDER BY id").fetchall(), [(1,), (0,)])

    def test_log_failure_rolls_back_consumption(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_log BEFORE INSERT ON decisions "
                       "BEGIN SELECT RAISE(ABORT, 'synthetic log failure'); END")
        result = self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15)
        self.assertEqual(result.reason, "persistence_or_validation_error")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
            db.execute("DROP TRIGGER fail_log")
        self.assertTrue(self.gateway.decide(REQ, POLICY, self.approval, self.signature, now=15).allowed)

    def test_default_clock_sampled_inside_write_transaction(self):
        statements = []
        connect = self.gateway._connect
        def traced_connection():
            db = connect()
            db.set_trace_callback(statements.append)
            return db
        def clock():
            return 21 if "BEGIN IMMEDIATE" in statements else 15
        with patch.object(self.gateway, "_connect", traced_connection), patch(
                "research.grok_integration.durable_gateway.time.time", side_effect=clock):
            result = self.gateway.decide(REQ, POLICY, self.approval, self.signature)
        self.assertEqual(result.reason, "expired_or_future_approval")

if __name__ == "__main__":
    unittest.main()
