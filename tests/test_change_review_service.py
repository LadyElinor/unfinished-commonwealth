from contextlib import contextmanager
from pathlib import Path
import errno
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from commonwealth.change_review_v1 import service, store


@unittest.skipUnless(sys.platform == "linux", "Linux Unix credentials required")
class ChangeReviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.db = self.root / "db.sqlite"
        self.path = self.root / "service.sock"
        self.uid = os.geteuid()
        store.initialize(self.db)

    def require_packets(self):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET):
                pass
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.EACCES, errno.EPROTONOSUPPORT):
                self.skipTest("kernel or execution environment denies Unix sequenced packets")
            raise

    @contextmanager
    def client_loop(self, reviewers=False):
        # The integration job runs the production entry point as three distinct
        # UIDs. Here exercise the request loop with the calling kernel identity.
        submit, review = (set(), {self.uid}) if reviewers else ({self.uid}, set())
        self.require_packets()
        stopped = threading.Event()
        with service._listener(self.path) as endpoint:
            server = threading.Thread(target=service._run,
                                      args=(endpoint, self.db, submit, review, stopped.is_set))
            server.start()
            try:
                yield
            finally:
                stopped.set()
                server.join(timeout=5)
                self.assertFalse(server.is_alive())

    def test_real_packets_readiness_and_submit(self):
        payload = {"op": "submit", "id": "public-data", "title": "Document the new source",
                   "proposal": "Add the decision date.", "evidence": ["Minutes, section 3"]}
        with self.client_loop():
            health = service.request(self.path, {"op": "ready"})["result"]
            self.assertTrue(health["ready"])
            self.assertEqual(health["register_id"], store.ready(self.db)["register_id"])
            payload["register_id"] = health["register_id"]
            submitted = service.request(self.path, payload)
            self.assertTrue(submitted["ok"], submitted)
            self.assertEqual(submitted, service.request(self.path, payload))
            self.assertEqual(submitted["result"]["record"]["owner_uid"], self.uid)
            self.assertEqual(service.request(self.path, {"op": "decide"})["error"], "permission_denied")
        with self.client_loop(reviewers=True):
            self.assertTrue(service.request(self.path, {"op": "ready"})["result"]["ready"])
            self.assertEqual(service.request(self.path, payload)["error"], "permission_denied")
            self.assertEqual(service.request(self.path, {"op": "get", "id": "public-data"})["result"]
                             ["record"]["title"], payload["title"])

    def test_idle_peer_does_not_block_another_request(self):
        with self.client_loop(), socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as idle:
            idle.connect(str(self.path))
            self.assertTrue(service.request(self.path, {"op": "ready"})["ok"])
            self.assertTrue(service.request(self.path, {"op": "ready"})["ok"])

    def test_readiness_checks_live_database(self):
        with self.client_loop():
            self.db.rename(self.root / "offline.sqlite")
            self.assertFalse(service.request(self.path, {"op": "ready"})["ok"])
            self.assertFalse(self.db.exists())

    def test_single_service_and_recovery_fence(self):
        other = self.root / "not-initialized.sqlite"
        with service.exclusive_database(other):
            with self.assertRaises(BlockingIOError):
                with service.exclusive_database(other):
                    self.fail("second holder admitted")
        with service.exclusive_database(other):
            self.assertFalse(other.exists())
        self.assertEqual((self.root / ".not-initialized.sqlite.service-lock").stat().st_mode & 0o777, 0o600)

    def test_stale_socket_replaced_but_live_socket_preserved(self):
        self.require_packets()
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as stale:
            stale.bind(str(self.path))
            stale.listen(2)
            with self.assertRaises(ValueError):
                with service._listener(self.path):
                    self.fail("active socket replaced")
            self.assertTrue(self.path.is_socket())
        with service._listener(self.path):
            self.assertEqual(self.path.lstat().st_mode & 0o777, 0o660)
            with self.assertRaises(BlockingIOError):
                with service._listener(self.path):
                    self.fail("another database claimed the live endpoint")
        self.assertFalse(self.path.exists())

    def test_occupied_path_or_replacement_is_preserved(self):
        self.path.write_text("existing")
        with self.assertRaises(ValueError):
            with service._listener(self.path):
                self.fail("non-socket overwritten")
        self.assertEqual(self.path.read_text(), "existing")
        self.path.unlink()
        self.require_packets()
        with service._listener(self.path):
            self.path.unlink()
            self.path.write_text("replacement")
        self.assertEqual(self.path.read_text(), "replacement")

    def test_admitted_request_scopes_and_live_check(self):
        self.assertTrue(service._dispatch(self.db, 111, {111}, {222}, {"op": "ready"})["ok"])
        self.assertTrue(service._dispatch(self.db, 222, {111}, {222}, {"op": "ready"})["ok"])
        for uid, payload in ((333, {"op": "ready"}), (111, {"op": "decide"}), (222, {"op": "submit"})):
            with self.subTest(uid=uid, payload=payload):
                self.assertEqual(service._dispatch(self.db, uid, {111}, {222}, payload)["error"],
                                 "permission_denied")

    def test_reserved_database_names(self):
        for name in ("copy-journal", "db-wal", "db-shm", ".other.service-lock", ".x.socket-lock"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                with service.exclusive_database(self.root / name):
                    self.fail("reserved filename admitted")

    def test_disjoint_roles_and_parent_permissions(self):
        with self.assertRaises(ValueError):
            service._roles([self.uid + 1], [self.uid + 1])
        with self.assertRaises(ValueError):
            service._roles([self.uid], [self.uid + 1])
        self.root.chmod(0o750)
        with self.assertRaises(ValueError):
            with service.exclusive_database(self.db):
                self.fail("shared data directory admitted")
        self.root.chmod(0o770)
        with self.assertRaises(ValueError):
            service._directory(self.path, shared=True)

    def test_foreground_start_deny_same_uid_and_sigterm(self):
        if self.uid == 0:
            with self.assertRaises(ValueError):
                service.serve(self.db, self.path, {1}, {2})
            return
        self.require_packets()
        cmd = [sys.executable, "-m", "commonwealth.change_review_v1", "serve",
               "--database", str(self.db), "--socket", str(self.path),
               "--submitter-uid", str(self.uid + 1), "--reviewer-uid", str(self.uid + 2)]
        for _ in range(2):
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                until = time.monotonic() + 8
                while not self.path.is_socket() and process.poll() is None and time.monotonic() < until:
                    time.sleep(.02)
                self.assertTrue(self.path.is_socket(), "service did not start")
                while True:
                    try:
                        health = service.request(self.path, {"op": "ready"})
                        break
                    except ConnectionRefusedError:
                        if time.monotonic() >= until:
                            raise
                        time.sleep(.02)
                self.assertEqual(health["error"], "permission_denied")
                process.terminate()
                self.assertEqual(process.wait(timeout=5), 0)
                self.assertFalse(self.path.exists())
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)
