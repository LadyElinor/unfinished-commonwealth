from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research.grok_integration.durable_gateway import DurableGateway
from research.grok_integration.secure_gateway import sign_approval
from research.grok_integration.simulation_delivery import SampleLedger, deliver_sample


class SampleDeliveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.key = b'synthetic only!!' * 2
        self.gateway = DurableGateway(self.root/'gate.db', self.key)
        self.ledger = SampleLedger(self.root/'ledger.db')
        self.request = dict(actor='sampler', action='simulate', resource='site-a')
        self.policy = {'grants': {'sampler': {'simulate': ['site-a']}}}
        self.grant = dict(self.request, approved=True, nonce='one', issued_at=1, expires_at=20,
                          delivery_protocol='local-sample-v1', sink_id=self.ledger.identity)

    def stage(self):
        return self.gateway.stage_simulation(self.request, self.policy, self.grant,
                                             sign_approval(self.grant, self.key), now=10)

    def count(self):
        with closing(self.ledger.connect()) as db:
            return db.execute('SELECT COUNT(*) FROM samples').fetchone()[0]

    def test_commit_then_lost_reply_recovered_after_restart_and_expiry(self):
        self.assertTrue(self.stage().allowed)
        original = self.ledger.record
        def drop_reply(*args, **kwargs):
            original(*args, **kwargs)
            raise TimeoutError('lost synthetic reply')
        with patch.object(self.ledger, 'record', side_effect=drop_reply), self.assertRaises(TimeoutError):
            deliver_sample(self.gateway, self.ledger, 'one', now=10)
        self.assertEqual(self.count(), 1)
        with closing(sqlite3.connect(self.gateway.database_path)) as db:
            self.assertIsNone(db.execute('SELECT confirmed_receipt FROM simulation_outbox').fetchone()[0])
        reopened = DurableGateway(self.gateway.database_path, self.key)
        sink = SampleLedger(self.ledger.path)
        receipt = deliver_sample(reopened, sink, 'one', now=21)
        self.assertEqual(receipt, deliver_sample(reopened, sink, 'one', now=22))
        self.assertEqual(self.count(), 1)
        self.assertFalse(self.stage().allowed)

    def test_expiry_and_destination_binding(self):
        self.assertTrue(self.stage().allowed)
        with self.assertRaisesRegex(ValueError, 'wrong sample ledger'):
            deliver_sample(self.gateway, SampleLedger(self.root/'other.db'), 'one', now=11)
        with self.assertRaisesRegex(ValueError, 'window closed'):
            deliver_sample(self.gateway, self.ledger, 'one', now=21)
        self.assertEqual(self.count(), 0)

    def test_concurrent_delivery(self):
        self.assertTrue(self.stage().allowed)
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda _: deliver_sample(self.gateway, self.ledger, 'one', now=10), range(8)))
        self.assertEqual(len(set(receipts)), 1)
        self.assertEqual(self.count(), 1)

    def test_legacy_approval_is_never_a_staged_command(self):
        del self.grant['sink_id']
        self.assertFalse(self.stage().allowed)
        self.assertTrue(self.gateway.decide(self.request, self.policy, self.grant,
                                            sign_approval(self.grant, self.key), now=10).allowed)
        with self.assertRaisesRegex(ValueError, 'no staged sample'):
            deliver_sample(self.gateway, self.ledger, 'one', now=10)

    def test_failed_staging_rolls_back_nonce(self):
        with closing(sqlite3.connect(self.gateway.database_path)) as db:
            db.execute("CREATE TRIGGER fail_stage BEFORE INSERT ON simulation_outbox "
                       "BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
        self.assertFalse(self.stage().allowed)
        with closing(sqlite3.connect(self.gateway.database_path)) as db:
            db.execute("DROP TRIGGER fail_stage")
        self.assertTrue(self.stage().allowed)

    def test_signed_arguments_outside_sample_contract_are_denied(self):
        self.grant['arguments'] = {'resource': 'site-b'}
        self.assertEqual(self.stage().reason, 'invalid_simulation_intent')
        self.assertEqual(self.count(), 0)

    def test_failed_confirmation_recovers_the_existing_effect(self):
        self.assertTrue(self.stage().allowed)
        with closing(sqlite3.connect(self.gateway.database_path)) as db:
            db.execute("CREATE TRIGGER fail_confirm BEFORE UPDATE ON simulation_outbox "
                       "BEGIN SELECT RAISE(ABORT, 'synthetic confirmation failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            deliver_sample(self.gateway, self.ledger, 'one', now=11)
        with closing(sqlite3.connect(self.gateway.database_path)) as db:
            db.execute("DROP TRIGGER fail_confirm")
        receipt = deliver_sample(self.gateway, self.ledger, 'one', now=30)
        with closing(self.ledger.connect()) as db:
            self.assertEqual(db.execute('SELECT receipt FROM samples').fetchall(), [(receipt,)])
