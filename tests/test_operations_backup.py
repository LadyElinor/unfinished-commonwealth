"""Exposed operator backup/restore gates; no real deployment or power-loss test."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.engine import canonical
from commonwealth.store import Workshop
from commonwealth.participant_v1 import PROTOCOL
from commonwealth.participant_v1.store import read_credential, Refused
from commonwealth.participant_v1_1.store import Boundary
from commonwealth.operations_v1.backup import backup_database, restore_database, inspect_database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workshop = Workshop.create(self.root / 'host.sqlite')
        self.boundary = Boundary(self.workshop.path, clock=lambda: 1000)
        self.boundary.install()
        self.cap = self.boundary.issue(self.root / 'credential', ttl=60)
        self.token = read_credential(self.root / 'credential')
        task = self.boundary.task(self.token)[1]
        self.packet = canonical({'protocol': PROTOCOL, 'request_id': 'backup-request',
                                 'view_head': task['view_head'], 'proposal': task['task']['proposal_example']}).encode()
        self.receipt = self.boundary.submit(self.token, self.packet)
        self.source = self.workshop.path
        self.destination = self.root / 'copy.sqlite'

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_backup_and_inspection_do_not_mutate_source(self):
        original = self.digest(self.source)
        audit = inspect_database(self.source)
        report = backup_database(self.source, self.destination)
        self.assertEqual(self.digest(self.source), original)
        self.assertEqual(inspect_database(self.destination), audit)
        self.assertEqual((report['events'], report['receipts']), (2, 1))
        self.assertFalse(report['source_fencing_required'])
        if os.name == 'posix':
            self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)

    def test_restore_revokes_all_bearers_preserves_historical_receipt(self):
        self.boundary.issue(self.root / 'second', ttl=60)
        before = self.digest(self.source)
        original_instance = inspect_database(self.source)['instance']
        result = restore_database(self.source, self.destination, clock=lambda: 1010)
        self.assertEqual(self.digest(self.source), before)
        self.assertTrue(result['source_fencing_required'])
        self.assertEqual(result['capabilities_revoked'], 2)
        self.assertEqual(result['instance'], original_instance)
        restored = Boundary(self.destination, clock=lambda: 1010)
        for token in (self.token, read_credential(self.root / 'second')):
            with self.assertRaises(Refused) as refusal:
                restored.task(token)
            self.assertEqual(refusal.exception.code, 'UNAUTHORIZED')
        self.assertEqual(restored.operator_receipt(self.cap['capability'], 'backup-request'), self.receipt)
        self.assertTrue(restored.audit()['verified'])
        # Negative control: copying cannot fence the original host.
        self.assertEqual(self.boundary.task(self.token)[0], 200)

    def test_restore_clock_rollback_never_publishes(self):
        with self.assertRaises(ValueError):
            restore_database(self.source, self.destination, clock=lambda: 999)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.commonwealth-copy-*')), [])

    def test_invalid_clock_never_publishes(self):
        for value in (True, float('nan'), float('inf'), -1, '1000'):
            with self.assertRaises(ValueError):
                restore_database(self.source, self.destination, clock=lambda: value)
            self.assertFalse(self.destination.exists())

    def test_existing_destination_never_replaced(self):
        self.destination.write_bytes(b'existing owner data')
        for operation in (backup_database, restore_database):
            with self.assertRaises(FileExistsError):
                operation(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), b'existing owner data')

    def test_racing_publication_never_replaces_new_destination(self):
        real_link = os.link
        def raced(source, destination):
            Path(destination).write_bytes(b'concurrent owner data')
            return real_link(source, destination)
        with patch('commonwealth.operations_v1.backup.os.link', side_effect=raced):
            with self.assertRaises(FileExistsError):
                backup_database(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), b'concurrent owner data')
        self.assertEqual(list(self.root.glob('.commonwealth-copy-*')), [])

    def test_corruption_and_historical_version_never_publish(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE participant_meta SET version='participant-1.0.0'")
        with self.assertRaises(ValueError):
            backup_database(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE participant_meta SET version='participant-1.1.0'")
            db.execute("UPDATE snapshot SET body='{}'")
        with self.assertRaises(ValueError):
            backup_database(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_symlinks_refused(self):
        alias = self.root / 'alias.sqlite'
        try:
            alias.symlink_to(self.source)
        except OSError:
            self.skipTest('host prohibits symlink creation')
        with self.assertRaises(ValueError):
            backup_database(alias, self.destination)
        with self.assertRaises(ValueError):
            backup_database(self.source, alias)
        self.assertFalse(self.destination.exists())

    def test_size_bound_and_timeout_refuse_without_publication(self):
        with patch('commonwealth.operations_v1.backup.MAX_DATABASE_BYTES', 1):
            with self.assertRaises(ValueError):
                backup_database(self.source, self.destination)
        with patch('commonwealth.operations_v1.backup.time.monotonic', side_effect=[0, 100]):
            with self.assertRaises(TimeoutError):
                backup_database(self.source, self.destination, timeout=1)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.commonwealth-copy-*')), [])

    def test_sync_failure_does_not_publish(self):
        with patch('commonwealth.operations_v1.backup.os.fsync', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                restore_database(self.source, self.destination, clock=lambda: 1010)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.commonwealth-copy-*')), [])

    def test_wal_snapshot_captures_committed_state(self):
        with closing(sqlite3.connect(self.source)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            self.boundary.revoke(self.cap['capability'])
            report = backup_database(self.source, self.destination)
            self.assertEqual(report['receipts'], 1)
            self.assertEqual(inspect_database(self.destination)['capabilities'][0]['revoked'], 1)

    def test_source_missing_is_not_created(self):
        missing = self.root / 'missing.sqlite'
        with self.assertRaises(FileNotFoundError):
            backup_database(missing, self.destination)
        self.assertFalse(missing.exists())
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
