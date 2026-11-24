"""Offline change-review snapshot and restore through the production storage fence."""
import errno
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.change_review_v1 import recovery, store


@unittest.skipUnless(sys.platform == "linux" and os.geteuid() != 0, "unprivileged Linux recovery profile")
class ChangeReviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / "source.sqlite"
        self.snapshot = self.root / "snapshot.sqlite"
        self.restored = self.root / "restored.sqlite"
        register_id = store.initialize(self.source)["register_id"]
        self.proposal = {"op": "submit", "register_id": register_id, "id": "change-12",
                         "title": "Retain the sample",
                         "proposal": "Retain the bounded receipt.", "evidence": ["Sample 1."]}
        submitted = store.handle(self.source, 1001, False, self.proposal)["record"]
        self.decision = {"op": "decide", "register_id": register_id, "id": "change-12",
                         "submission_digest": submitted["submission_digest"], "decision": "approve",
                         "rationale": "The procedure retains the receipt."}

    def test_restore_preserves_decision_and_returns_exact_snapshot_bytes(self):
        approved = store.handle(self.source, 1002, True, self.decision)
        receipt = recovery.backup(self.source, self.snapshot)
        self.assertIsInstance(receipt["completed_at"], int)
        self.assertEqual((receipt["records"], receipt["decisions"]), (1, 1))
        self.assertEqual(hashlib.sha256(self.snapshot.read_bytes()).hexdigest(), receipt["sha256"])
        self.assertEqual(stat.S_IMODE(self.snapshot.stat().st_mode), 0o600)
        with self.assertRaises(ValueError):
            recovery.restore(self.snapshot, self.restored, expected_sha256="0" * 64)
        self.assertFalse(self.restored.exists())
        restored = recovery.restore(self.snapshot, self.restored, expected_sha256=receipt["sha256"])
        self.assertEqual(restored["sha256"], receipt["sha256"])
        self.assertEqual(restored["register_id"], store.verify(self.source)["register_id"])
        self.assertEqual(self.snapshot.read_bytes(), self.restored.read_bytes())
        self.assertEqual(store.handle(self.restored, 1002, True, self.decision), approved)
        result = store.handle(self.restored, 1001, False, {"op": "get", "id": "change-12"})
        self.assertEqual(result["record"], approved["record"])
        self.assertEqual(store.verify(self.restored)["decisions"], 1)

    def test_snapshot_excludes_subsequent_decision_and_refuses_replacement(self):
        original = recovery.backup(self.source, self.snapshot)
        store.handle(self.source, 1002, True, self.decision)
        with self.assertRaises(FileExistsError):
            recovery.backup(self.source, self.snapshot)
        later = recovery.backup(self.source, self.root / "later.sqlite")
        self.assertNotEqual(later["sha256"], original["sha256"])
        self.assertEqual(store.verify(self.snapshot)["decisions"], 0)
        self.assertEqual(store.verify(self.source)["decisions"], 1)

    def test_service_fence_and_private_source(self):
        from commonwealth.change_review_v1.service import exclusive_database
        for path in (self.source, self.snapshot):
            with self.subTest(path=path), exclusive_database(path), self.assertRaises(BlockingIOError):
                recovery.backup(self.source, self.snapshot)
        self.source.chmod(0o644)
        with self.assertRaises(ValueError):
            recovery.backup(self.source, self.snapshot)
        self.assertFalse(self.snapshot.exists())

    def test_raw_invalid_input_and_oversized_copy_do_not_publish(self):
        invalid = self.root / "unknown.sqlite"
        with sqlite3.connect(invalid) as db:
            db.execute("CREATE TABLE unrelated (row INTEGER)")
        invalid.chmod(0o600)
        with self.assertRaises(store.DomainError):
            recovery.restore(invalid, self.restored)
        with patch.object(store, "MAX_DATABASE_BYTES", 32), self.assertRaises(ValueError):
            recovery.backup(self.source, self.snapshot)
        self.assertFalse(self.restored.exists())
        self.assertFalse(self.snapshot.exists())
        self.assertFalse(list(self.root.glob(".change-review-copy-*")))

    def test_prepublication_sync_failure_can_retry_same_destination(self):
        with patch.object(os, "fsync", side_effect=OSError(errno.ENOSPC, "simulated full disk")):
            with self.assertRaises(OSError) as failure:
                recovery.backup(self.source, self.snapshot)
            self.assertEqual(failure.exception.errno, errno.ENOSPC)
        self.assertFalse(self.snapshot.exists())
        self.assertFalse(list(self.root.glob(".change-review-copy-*")))
        self.assertEqual(store.verify(self.source)["records"], 1)
        self.assertEqual(recovery.backup(self.source, self.snapshot)["records"], 1)

    def test_postpublication_sync_failure_is_observable_without_replacing_destination(self):
        real_sync = os.fsync

        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("simulated directory sync failure")
            real_sync(fd)

        with patch.object(os, "fsync", side_effect=fail_directory):
            with self.assertRaises(recovery.PublicationUnconfirmed):
                recovery.backup(self.source, self.snapshot)
        self.assertEqual(store.verify(self.snapshot)["records"], 1)
        with self.assertRaises(FileExistsError):
            recovery.backup(self.source, self.snapshot)
        self.assertFalse(list(self.root.glob(".change-review-copy-*")))
