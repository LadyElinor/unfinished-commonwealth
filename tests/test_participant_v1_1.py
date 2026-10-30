"""Exposed B1.1 clock-floor regressions; historical B1 remains reproducible."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import subprocess
import sys
import json
import unittest
from unittest.mock import patch

from commonwealth.engine import canonical
from commonwealth.store import Workshop
from commonwealth.participant_v1 import PROTOCOL
from commonwealth.participant_v1.store import Boundary as B1, Refused, read_credential
from commonwealth.participant_v1.transport import Server, request
from commonwealth.participant_v1_1 import VERSION
from commonwealth.participant_v1_1.store import Boundary


class ClockFloorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workshop = Workshop.create(self.root / "workshop.sqlite")
        self.now = 1000
        self.boundary = Boundary(self.workshop.path, clock=lambda: self.now)
        self.boundary.install()
        self.cap = self.boundary.issue(self.root / "token", ttl=60)
        self.token = read_credential(self.root / "token")

    def refused(self, code, fn):
        with self.assertRaises(Refused) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def floor(self):
        with closing(self.workshop.connect()) as db:
            return db.execute("SELECT last_wall FROM participant_meta").fetchone()[0]

    def restart(self):
        self.boundary = Boundary(self.workshop.path, clock=lambda: self.now)

    def packet(self):
        _, task = self.boundary.task(self.token)
        return canonical({"protocol": PROTOCOL, "request_id": "clock-request",
                          "view_head": task["view_head"],
                          "proposal": task["task"]["proposal_example"]}).encode()

    def test_historical_expiry_counterexample_remains_reproducible(self):
        other = Workshop.create(self.root / "historical.sqlite")
        old = B1(other.path, clock=lambda: self.now)
        old.install()
        old.issue(self.root / "historical-token", ttl=60)
        token = read_credential(self.root / "historical-token")
        self.now = 1061
        self.refused("UNAUTHORIZED", lambda: old.task(token))
        self.now = 1050
        self.assertEqual(B1(other.path, clock=lambda: self.now).task(token)[0], 200)

    def test_expired_refusal_survives_restart_and_rollback(self):
        self.now = 1061
        self.refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))
        self.assertEqual(self.floor(), 1061)
        self.now = 1050
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))
        self.now = 1061
        self.refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))

    def test_expiry_is_exact_at_boundary(self):
        self.now = 1059
        self.assertEqual(self.boundary.task(self.token)[0], 200)
        self.now = 1060
        self.refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))
        self.now = 1059
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))

    def test_unauthorized_observation_persists_without_attempt(self):
        self.now = 1040
        self.refused("UNAUTHORIZED", lambda: self.boundary.task("wrong-token"))
        self.now = 1030
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 0)
        self.assertEqual(len(self.workshop.events()), 1)

    def test_missing_receipt_observation_persists(self):
        self.now = 1040
        self.refused("RECEIPT_NOT_FOUND", lambda: self.boundary.receipt(self.token, "absent"))
        self.now = 1030
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))

    def test_failed_issuance_keeps_floor_but_not_new_capability(self):
        self.now = 1040
        with self.assertRaises(FileExistsError):
            self.boundary.issue(self.root / "token")
        self.assertEqual(self.floor(), 1040)
        self.assertEqual(read_credential(self.root / "token"), self.token)
        self.assertEqual(len(self.boundary.audit()["capabilities"]), 1)
        self.now = 1030
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))

    def test_operation_failure_rolls_back_proposal_not_floor(self):
        raw = self.packet()
        with closing(self.workshop.connect()) as db, db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON participant_receipts BEGIN SELECT RAISE(ABORT,'injected'); END")
        self.now = 1040
        with self.assertRaises(sqlite3.DatabaseError):
            self.boundary.submit(self.token, raw)
        self.assertEqual(self.floor(), 1040)
        self.assertEqual(len(self.workshop.events()), 1)
        audit = self.boundary.audit()
        self.assertEqual((audit["receipts"], audit["capabilities"][0]["used"]), (0, 0))
        self.now = 1030
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.submit(self.token, raw))

    def test_floor_write_failure_stops_before_proposal(self):
        raw = self.packet()
        with closing(self.workshop.connect()) as db, db:
            db.execute("CREATE TRIGGER fail_floor BEFORE UPDATE ON participant_meta BEGIN SELECT RAISE(ABORT,'injected'); END")
        self.now = 1040
        with self.assertRaises(sqlite3.DatabaseError):
            self.boundary.submit(self.token, raw)
        self.assertEqual(len(self.workshop.events()), 1)
        self.assertEqual(self.floor(), 1000)
        with closing(self.workshop.connect()) as db:
            self.assertEqual(db.execute("SELECT used FROM participant_caps").fetchone()[0], 0)

    def test_operator_recovery_during_rollback_does_not_lower_floor(self):
        accepted = self.boundary.submit(self.token, self.packet())
        self.now = 1040
        self.boundary.task(self.token)
        self.now = 1020
        self.assertEqual(self.boundary.operator_receipt(self.cap["capability"], "clock-request"), accepted)
        self.boundary.revoke(self.cap["capability"])
        self.assertTrue(self.boundary.audit()["verified"])
        self.assertEqual(self.floor(), 1040)
        self.now = 1040
        self.refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))

    def test_concurrent_observations_never_lower_floor(self):
        def observe(now):
            boundary = Boundary(self.workshop.path, clock=lambda: now)
            try:
                boundary.task("wrong-token")
            except Refused as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(observe, [1010, 1030, 1020, 1050, 1040, 1061]))
        self.assertTrue(set(outcomes) <= {"UNAUTHORIZED", "CLOCK_ROLLBACK"})
        self.assertEqual(self.floor(), 1061)
        self.now = 1050
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))

    def test_concurrent_identical_submissions_retain_one_effect(self):
        raw = self.packet()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.boundary.submit(self.token, raw), range(6)))
        self.assertTrue(all(item == results[0] for item in results))
        self.assertEqual(results[0][0], 200)
        self.assertEqual(len(self.workshop.events()), 2)
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 1)

    def test_real_loopback_unknown_response_and_restart_recovery(self):
        raw = self.packet()
        def serve(boundary):
            server = Server(boundary)
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            return server, thread
        from commonwealth.participant_v1.transport import Handler
        server, thread = serve(self.boundary)
        try:
            with patch.object(Handler, "_send", side_effect=ConnectionResetError("lost reply")):
                result = request(server.url, self.token, "POST", "/proposals", raw)
            self.assertEqual(result[1]["disposition"], "UNKNOWN")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.restart()
        server, thread = serve(self.boundary)
        try:
            lookup = request(server.url, self.token, path="/receipts/clock-request")
            retry = request(server.url, self.token, "POST", "/proposals", raw)
            self.assertEqual(lookup, retry)
            self.assertEqual(retry[0], 200)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(len(self.workshop.events()), 2)
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 1)

    def test_cli_upgrade_and_audit_identify_corrected_version(self):
        # Real wall time is above injected fixture time; no bearer is printed.
        for command in ("upgrade", "audit"):
            result = subprocess.run([sys.executable, "-m", "commonwealth.participant_v1_1",
                                     command, str(self.workshop.path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["version"], VERSION)
            self.assertNotIn(self.token, result.stdout + result.stderr)

    def test_crash_after_clock_commit_does_not_restore_old_floor(self):
        original = self.workshop.connect
        class CrashAfterCommit:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                setattr(self.connection, name, value)
            def commit(self):
                self.connection.commit()
                raise RuntimeError("simulated process loss after durable clock commit")
        self.now = 1061
        with patch.object(self.workshop, "connect", side_effect=lambda: CrashAfterCommit(original())):
            # Boundary owns a different Workshop object, so patch that connection.
            with patch.object(self.boundary.workshop, "connect", side_effect=lambda: CrashAfterCommit(original())):
                with self.assertRaises(RuntimeError):
                    self.boundary.task(self.token)
        self.assertEqual(self.floor(), 1061)
        self.now = 1050
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))


    def test_time_is_resampled_after_intertransaction_delay(self):
        original = self.boundary.workshop.connect
        clock_owner = self
        class AdvanceAfterCommit:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                setattr(self.connection, name, value)
            def commit(self):
                self.connection.commit()
                clock_owner.now = 1061
        with patch.object(self.boundary.workshop, "connect", side_effect=lambda: AdvanceAfterCommit(original())):
            self.refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))
        self.assertEqual(self.floor(), 1061)
        self.now = 1050
        self.restart()
        self.refused("CLOCK_ROLLBACK", lambda: self.boundary.task(self.token))

    def test_fresh_install_failure_does_not_leave_historical_boundary(self):
        other = Workshop.create(self.root / "install-failure.sqlite")
        boundary = Boundary(other.path, clock=lambda: float("nan"))
        self.refused("CLOCK_INVALID", boundary.install)
        with closing(other.connect()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'participant_%'").fetchone()[0], 0)
        with self.assertRaises(sqlite3.OperationalError):
            B1(other.path, clock=lambda: 1000).task(self.token)
        boundary = Boundary(other.path, clock=lambda: 1000)
        self.assertEqual(boundary.install()["version"], VERSION)


    def test_upgrade_preserves_instance_receipt_and_blocks_old_operator(self):
        other = Workshop.create(self.root / "upgrade.sqlite")
        old = B1(other.path, clock=lambda: self.now)
        original = old.install()
        old.issue(self.root / "upgrade-token")
        token = read_credential(self.root / "upgrade-token")
        _, task = old.task(token)
        raw = canonical({"protocol": PROTOCOL, "request_id": "before-upgrade",
                         "view_head": task["view_head"], "proposal": task["task"]["proposal_example"]}).encode()
        accepted = old.submit(token, raw)
        before = other.verify()["head"]
        fixed = Boundary(other.path, clock=lambda: self.now)
        result = fixed.upgrade()
        self.assertEqual((result["version"], result["instance"]), (VERSION, original["instance"]))
        self.assertEqual(fixed.submit(token, raw), accepted)
        self.assertEqual(other.verify()["head"], before)
        self.assertEqual(fixed.upgrade(), result)
        self.refused("BOUNDARY_UNAVAILABLE", lambda: old.task(token))
        self.refused("BOUNDARY_UNAVAILABLE", lambda: old.revoke(self.cap["capability"]))

    def test_upgrade_refuses_unknown_version_and_rollback(self):
        self.now = 990
        self.refused("CLOCK_ROLLBACK", self.boundary.upgrade)
        self.now = 1000
        with closing(self.workshop.connect()) as db, db:
            db.execute("UPDATE participant_meta SET version='future'")
        self.refused("BOUNDARY_UNAVAILABLE", self.boundary.upgrade)

    def test_invalid_clock_does_not_change_floor_or_effects(self):
        for now in (float("nan"), float("inf"), -1, "1040"):
            self.now = now
            self.refused("CLOCK_INVALID", lambda: self.boundary.task(self.token))
        self.assertEqual(self.floor(), 1000)
        self.assertEqual(len(self.workshop.events()), 1)

    def test_pretransaction_input_rejection_does_not_claim_observation(self):
        self.now = 1040
        self.refused("BODY_TOO_LARGE", lambda: self.boundary.submit(self.token, object()))
        self.assertEqual(self.floor(), 1000)


if __name__ == "__main__":
    unittest.main()
