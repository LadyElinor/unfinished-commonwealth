"""Exposed C1 recovery gates against B1.1; no held-out or power-loss claim."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from commonwealth.engine import canonical
from commonwealth.store import Workshop
from commonwealth.participant_v1 import PROTOCOL
from commonwealth.participant_v1.store import read_credential
from commonwealth.participant_v1.transport import Handler, Server
from commonwealth.participant_v1_1.store import Boundary
from commonwealth.client_outbox_v1.store import Outbox, fingerprint


class OutboxTests(unittest.TestCase):
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
        self.server = Server(self.boundary)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.task = self.boundary.task(self.token)[1]
        self.packet = {"protocol": PROTOCOL, "request_id": "c1-request", "view_head": self.task["view_head"],
                       "proposal": self.task["task"]["proposal_example"]}
        self.raw = canonical(self.packet).encode()
        self.path = self.root / "outbox.sqlite"
        Outbox.stage(self.path, self.server.url, self.token, self.task, self.raw)
        self.outbox = Outbox(self.path)

    def stop_server(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def counts(self):
        audit = self.boundary.audit()
        return audit["events"], audit["capabilities"][0]["used"]

    def test_prior_runtime_and_evidence_remain_byte_identical(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((root / "tests/data/client-outbox-preserved-baseline.json").read_text(encoding="utf-8"))
        for name, expected in record["sha256"].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected, name)


    def test_stage_is_unresolved_and_does_not_send(self):
        status = self.outbox.status()
        self.assertEqual((status["state"], status["operations_started"]), ("UNRESOLVED", 0))
        self.assertEqual(self.counts(), (1, 0))
        self.assertNotIn(self.token.encode(), self.path.read_bytes())

    def test_bearer_in_intent_is_refused_even_when_json_escaped(self):
        body = copy.deepcopy(self.packet)
        body["proposal"]["purpose"] = self.token
        for raw in (canonical(body).encode(), canonical(body).replace("ucp1", "\\u0075cp1").encode()):
            with self.assertRaises(ValueError):
                Outbox.stage(self.root / "secret.sqlite", self.server.url, self.token, self.task, raw)
        self.assertFalse((self.root / "secret.sqlite").exists())


    def test_stage_never_overwrites_existing_intent(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            Outbox.stage(self.path, self.server.url, self.token, self.task, self.raw + b" ")
        self.assertEqual(self.path.read_bytes(), before)

    def test_retry_records_one_proposal_and_cached_record_is_historical(self):
        first = self.outbox.operate(self.token, "retry")
        self.assertEqual(first["state"], "RECORDED")
        self.assertFalse(first["recorded"]["receipt"]["permits_execution"])
        self.boundary.revoke(self.cap["capability"])
        with patch("commonwealth.client_outbox_v1.store.request", side_effect=AssertionError("no network")):
            self.assertEqual(self.outbox.operate(self.token, "retry"), first)
        self.assertEqual(self.counts(), (2, 1))

    def test_crash_before_send_keeps_intent_and_incomplete_operation(self):
        with patch("commonwealth.client_outbox_v1.store.request", side_effect=RuntimeError("process interruption")):
            with self.assertRaises(RuntimeError):
                self.outbox.operate(self.token, "retry")
        status = Outbox(self.path).status()
        self.assertEqual((status["state"], status["operations_started"], status["operations_observed"]), ("UNRESOLVED", 1, 0))
        self.assertEqual(Outbox(self.path).operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (2, 1))

    def test_crash_after_host_commit_recovers_exact_bytes_once(self):
        def commit_then_interrupt(*args, **kwargs):
            self.boundary.submit(self.token, args[4])
            raise RuntimeError("lost process after host commit")
        with patch("commonwealth.client_outbox_v1.store.request", side_effect=commit_then_interrupt):
            with self.assertRaises(RuntimeError):
                self.outbox.operate(self.token, "retry")
        status = Outbox(self.path).operate(self.token, "resolve")
        self.assertEqual((status["state"], status["latest_observation"]), ("UNRESOLVED", "RECEIPT_REQUIRES_EXACT_RETRY"))
        self.assertEqual(Outbox(self.path).operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (2, 1))

    def test_abrupt_child_exit_after_real_post_recovers_without_duplicate(self):
        code = """
import os, sys
import commonwealth.client_outbox_v1.store as client
from commonwealth.participant_v1.store import read_credential
original = client.request
def exit_after_request(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(73)
client.request = exit_after_request
client.Outbox(sys.argv[1]).operate(read_credential(sys.argv[2]), 'retry')
"""
        result = subprocess.run([sys.executable, "-c", code, str(self.path), str(self.root / "token")],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 73, result.stderr)
        status = Outbox(self.path).status()
        self.assertEqual((status["state"], status["operations_started"], status["operations_observed"]),
                         ("UNRESOLVED", 1, 0))
        self.assertEqual(Outbox(self.path).operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (2, 1))


    def test_dropped_http_reply_remains_unknown_until_exact_retry(self):
        with patch.object(Handler, "_send", side_effect=ConnectionResetError("lost reply")):
            self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "UNRESOLVED")
        self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (2, 1))

    def test_missing_receipt_does_not_prove_no_submission(self):
        status = self.outbox.operate(self.token, "resolve")
        self.assertEqual(status["state"], "UNRESOLVED")
        self.assertEqual(self.counts(), (1, 0))

    def test_wrong_capability_refuses_before_network(self):
        self.boundary.issue(self.root / "other-token")
        other = read_credential(self.root / "other-token")
        with patch("commonwealth.client_outbox_v1.store.request", side_effect=AssertionError("no network")):
            for token in (other, self.token[:-1] + ("0" if self.token[-1] != "0" else "1")):
                with self.assertRaises(ValueError):
                    self.outbox.operate(token, "retry")
        self.assertEqual(self.outbox.status()["operations_started"], 0)

    def test_reused_request_id_lookup_does_not_bind_different_bytes(self):
        different = copy.deepcopy(self.packet)
        different["proposal"]["purpose"] = "Different original intent"
        self.boundary.submit(self.token, canonical(different).encode())
        status = self.outbox.operate(self.token, "resolve")
        self.assertEqual(status["state"], "UNRESOLVED")
        status = self.outbox.operate(self.token, "retry")
        self.assertEqual(status["state"], "UNRESOLVED")
        self.assertEqual(self.counts(), (2, 2))

    def test_expired_after_commit_cannot_be_resolved_by_new_capability(self):
        self.boundary.submit(self.token, self.raw)
        self.now = 1061
        for kind in ("resolve", "retry"):
            self.assertEqual(self.outbox.operate(self.token, kind)["state"], "UNRESOLVED")
        self.assertEqual(self.counts(), (2, 1))
        self.assertEqual(self.boundary.operator_receipt(self.cap["capability"], "c1-request")[0], 200)

    def test_revoked_after_commit_stays_unresolved(self):
        self.boundary.submit(self.token, self.raw)
        self.boundary.revoke(self.cap["capability"])
        self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "UNRESOLVED")
        self.assertEqual(self.counts(), (2, 1))

    def test_stale_view_receipt_is_recorded_as_refusal(self):
        self.workshop.dispatch({"action": "observe", "actor": "worker-1"})
        status = self.outbox.operate(self.token, "retry")
        self.assertEqual(status["state"], "RECORDED")
        self.assertEqual(status["recorded"]["receipt"]["disposition"], "STALE_VIEW")
        self.assertEqual(status["recorded"]["http_status"], 409)

    def test_malformed_or_unbound_success_never_records(self):
        _, receipt = self.boundary.submit(self.token, self.raw)
        alterations = ({"request_id": "wrong"}, {"instance": "0" * 32},
                       {"external_authority": "FULL"}, {"permits_execution": True},
                       {"event_seq": True}, {"event_hash": "bad"}, {"proposal_id": "bad"},
                       {"extra": "untrusted"}, {"disposition": "TASK"})
        for changes in alterations:
            payload = {**receipt, **changes}
            with patch("commonwealth.client_outbox_v1.store.request", return_value=(200, payload)):
                self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "UNRESOLVED")
        with patch("commonwealth.client_outbox_v1.store.request", return_value=(200, {"protocol": PROTOCOL})):
            self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "UNRESOLVED")

    def test_status_disposition_mismatch_never_records(self):
        receipt = self.boundary.submit(self.token, self.raw)[1]
        for status in (True, 201, 400, 409, 422):
            with patch("commonwealth.client_outbox_v1.store.request", return_value=(status, receipt)):
                self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "UNRESOLVED")

    def test_corrupted_intent_refuses_before_network(self):
        with closing(self.outbox.connect()) as db, db:
            db.execute("UPDATE intent SET body=replace(body,'c1-request','c2-request')")
        with patch("commonwealth.client_outbox_v1.store.request", side_effect=AssertionError("no network")):
            with self.assertRaises(ValueError):
                self.outbox.operate(self.token, "retry")

    def test_internal_binding_mismatch_refuses_even_with_recomputed_digest(self):
        with closing(self.outbox.connect()) as db, db:
            body = json.loads(db.execute("SELECT body FROM intent").fetchone()[0])
            body["request_id"] = "different"
            db.execute("UPDATE intent SET body=?, digest=?", (canonical(body), fingerprint(body)))
        with self.assertRaises(ValueError):
            self.outbox.status()

    def test_receipt_persistence_failure_leaves_recoverable_unknown(self):
        with closing(self.outbox.connect()) as db, db:
            db.execute("CREATE TRIGGER fail_record BEFORE INSERT ON recorded BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.outbox.operate(self.token, "retry")
        self.assertEqual(self.outbox.status()["state"], "UNRESOLVED")
        with closing(self.outbox.connect()) as db, db:
            db.execute("DROP TRIGGER fail_record")
        self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (2, 1))

    def test_concurrent_recovery_records_one_effect(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: Outbox(self.path).operate(self.token, "retry"), range(6)))
        self.assertTrue(all(result["state"] == "RECORDED" for result in results))
        self.assertEqual(self.counts(), (2, 1))

    def test_host_forgery_negative_control_remains_possible(self):
        forged = {"protocol": PROTOCOL, "disposition": "ACCEPTED", "external_authority": "NONE",
                  "request_id": "c1-request", "instance": self.task["instance"], "event_seq": 1,
                  "event_hash": "0" * 64, "proposal_id": "propose-1", "permits_execution": False}
        with patch("commonwealth.client_outbox_v1.store.request", return_value=(200, forged)):
            self.assertEqual(self.outbox.operate(self.token, "retry")["state"], "RECORDED")
        self.assertEqual(self.counts(), (1, 0))  # Structure is not attestation.

    def test_unvalidated_server_text_is_not_persisted(self):
        payload = {"protocol": PROTOCOL, "disposition": self.token}
        with patch("commonwealth.client_outbox_v1.store.request", return_value=(200, payload)):
            self.outbox.operate(self.token, "retry")
        self.assertNotIn(self.token.encode(), self.path.read_bytes())

    def test_cli_stages_without_network_and_status_is_secret_free(self):
        task_file, request_file = self.root / "task.json", self.root / "request.json"
        task_file.write_text(canonical(self.task), encoding="utf-8")
        request_file.write_bytes(self.raw)
        path = self.root / "cli.sqlite"
        arguments = ["stage", str(path), self.server.url, str(self.root / "token"), str(task_file), str(request_file)]
        for args in (arguments, ["status", str(path)], ["retry", str(path), str(self.root / "token")]):
            result = subprocess.run([sys.executable, "-m", "commonwealth.client_outbox_v1", *args], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(self.token, result.stdout + result.stderr)
        self.assertEqual(Outbox(path).status()["state"], "RECORDED")

    def test_bounded_history_refusal_keeps_intent_unresolved(self):
        with patch("commonwealth.client_outbox_v1.store.MAX_OPERATIONS", 1):
            self.outbox.operate(self.token, "resolve")
            with self.assertRaises(ValueError):
                self.outbox.operate(self.token, "retry")
        self.assertEqual(self.outbox.status()["state"], "UNRESOLVED")
        self.assertEqual(self.counts(), (1, 0))


if __name__ == "__main__":
    unittest.main()
