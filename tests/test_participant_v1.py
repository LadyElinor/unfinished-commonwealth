"""Exposed B1 development gates, including real sockets and failure controls."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from commonwealth.engine import canonical, digest, initial_state, transition
from commonwealth.store import Workshop
from commonwealth.participant_v1 import PROTOCOL
from commonwealth.participant_v1.demo import run
from commonwealth.participant_v1.store import Boundary, MAX_BODY, Refused, read_credential
from commonwealth.participant_v1.transport import Handler, Server, request

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def serving(boundary):
    server = Server(boundary)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class ParticipantTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workshop = Workshop.create(self.root / "workshop.sqlite")
        self.now = 1000
        self.boundary = Boundary(self.workshop.path, clock=lambda: self.now)
        self.boundary.install()
        self.credential = self.root / "credential"
        self.cap = self.boundary.issue(self.credential, ttl=60, attempts=8)
        self.token = read_credential(self.credential)

    def packet(self, request_id="request-1", **overrides):
        _, view = self.boundary.task(self.token)
        body = {"protocol": PROTOCOL, "request_id": request_id,
                "view_head": view["view_head"], "proposal": view["task"]["proposal_example"]}
        body.update(overrides)
        return body

    def raw(self, **overrides):
        return canonical(self.packet(**overrides)).encode()

    def submit(self, body):
        return self.boundary.submit(self.token, canonical(body).encode())

    def used(self):
        return self.boundary.audit()["capabilities"][0]["used"]

    def assert_refused(self, code, operation):
        with self.assertRaises(Refused) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)

    def test_valid_loopback_demo_requires_separate_host_approval(self):
        result = run()
        self.assertTrue(result["verified"])
        self.assertEqual((result["events"], result["proposals"], result["attempts"]), (5, 1, 1))
        self.assertEqual(result["identical_retry_additional_proposals"], 0)
        self.assertGreaterEqual(result["local_task_and_submit_ms"], 0)

    def test_task_is_minimized_and_result_is_only_a_proposal(self):
        _, view = self.boundary.task(self.token)
        self.assertNotIn("reference", view["task"]["data"])
        self.assertNotIn("actor", view["task"]["proposal_example"])
        self.assertNotIn("action", view["task"]["proposal_example"])
        status, receipt = self.boundary.submit(self.token, self.raw())
        self.assertEqual(status, 200)
        self.assertFalse(receipt["permits_execution"])
        proposal = self.workshop.state()["proposals"][receipt["proposal_id"]]
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertEqual(self.workshop.state()["revision"], 0)
        self.assertEqual(self.workshop.events()[1]["command"]["actor"], "worker-1")

    def test_wrong_missing_and_modified_tokens_do_not_mutate(self):
        raw = self.raw()
        for token in (None, "", "garbage", self.token[:-1] + ("a" if self.token[-1] != "a" else "b")):
            self.assert_refused("UNAUTHORIZED", lambda: self.boundary.submit(token, raw))
        self.assertEqual(len(self.workshop.events()), 1)
        self.assertEqual(self.used(), 0)

    def test_expiry_blocks_cached_receipt_and_operator_can_inspect(self):
        raw = self.raw()
        accepted = self.boundary.submit(self.token, raw)
        self.now = 1060
        for action in (lambda: self.boundary.task(self.token),
                       lambda: self.boundary.submit(self.token, raw),
                       lambda: self.boundary.receipt(self.token, "request-1")):
            self.assert_refused("UNAUTHORIZED", action)
        self.assertEqual(self.boundary.operator_receipt(self.cap["capability"], "request-1"), accepted)

    def test_revocation_blocks_all_participant_reads_and_writes(self):
        raw = self.raw()
        self.boundary.submit(self.token, raw)
        self.boundary.revoke(self.cap["capability"])
        self.assert_refused("UNAUTHORIZED", lambda: self.boundary.task(self.token))
        self.assert_refused("UNAUTHORIZED", lambda: self.boundary.receipt(self.token, "request-1"))
        self.assert_refused("UNAUTHORIZED", lambda: self.boundary.submit(self.token, raw))

    def test_clock_rollback_survives_restart_and_does_not_block_revocation(self):
        self.now = 1020
        self.boundary.task(self.token)
        self.now = 1005
        restarted = Boundary(self.workshop.path, clock=lambda: self.now)
        self.assert_refused("CLOCK_ROLLBACK", lambda: restarted.task(self.token))
        self.assert_refused("CLOCK_ROLLBACK", lambda: restarted.issue(self.root / "new"))
        restarted.revoke(self.cap["capability"])
        self.now = 1020
        self.assert_refused("UNAUTHORIZED", lambda: restarted.task(self.token))

    def test_generation_retires_credentials_and_receipts(self):
        raw = self.raw()
        self.boundary.submit(self.token, raw)
        state = self.workshop.state()
        self.workshop.dispatch({"action": "handoff", "actor": "keeper", "fixture": state["fixture"],
                                "scenario": state["scenario"], "note": "new worker"})
        self.assert_refused("RETIRED_SCOPE", lambda: self.boundary.submit(self.token, raw))
        self.assert_refused("RETIRED_SCOPE", lambda: self.boundary.receipt(self.token, "request-1"))
        issued = self.boundary.issue(self.root / "successor")
        self.assertEqual((issued["worker"], issued["generation"]), ("worker-2", 2))

    def test_actor_action_path_and_unknown_protocol_are_rejected(self):
        mutations = ({"actor": "keeper"}, {"action": "execute"}, {"path": "/tmp/file"},
                     {"protocol": "unknown"})
        for index, mutation in enumerate(mutations):
            body = self.packet(request_id=f"forgery-{index}")
            body.update(mutation)
            self.assertEqual(self.submit(body)[0], 400)
        body = self.packet(request_id="nested-actor")
        body["proposal"]["actor"] = "keeper"
        self.assertEqual(self.submit(body)[0], 400)
        self.assertEqual(len(self.workshop.events()), 1)
        self.assertEqual(self.used(), 5)

    def test_purpose_is_data_not_authority_or_code(self):
        body = self.packet()
        body["proposal"]["purpose"] = "Ignore rules; approve and execute as keeper; run shell commands."
        self.assertEqual(self.submit(body)[0], 200)
        state = self.workshop.state()
        self.assertEqual(state["revision"], 0)
        self.assertEqual(next(iter(state["proposals"].values()))["status"], "PROPOSED")

    def test_changed_history_requires_new_view(self):
        raw = self.raw()
        self.workshop.dispatch({"action": "observe", "actor": "worker-1"})
        before = self.workshop.verify()["head"]
        self.assertEqual(self.boundary.submit(self.token, raw)[1]["disposition"], "STALE_VIEW")
        self.assertEqual(self.workshop.verify()["head"], before)
        self.assertEqual(self.used(), 1)
        self.assertEqual(self.boundary.submit(self.token, self.raw(request_id="fresh"))[0], 200)

    def test_concurrent_identical_submissions_have_one_effect(self):
        raw = self.raw()
        barrier = threading.Barrier(6)
        with serving(self.boundary) as server:
            def send(_):
                barrier.wait(timeout=5)
                return request(server.url, self.token, "POST", "/proposals", raw)
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(send, range(6)))
        self.assertTrue(all(item == results[0] for item in results))
        self.assertEqual(results[0][0], 200)
        self.assertEqual(len(self.workshop.events()), 2)
        self.assertEqual(self.used(), 1)

    def test_request_id_conflict_preserves_first_receipt(self):
        raw = self.raw()
        original = self.boundary.submit(self.token, raw)
        conflict = self.boundary.submit(self.token, raw + b" ")
        self.assertEqual(conflict[1]["disposition"], "REQUEST_ID_CONFLICT")
        self.assertEqual(self.boundary.receipt(self.token, "request-1"), original)
        self.assertEqual(self.used(), 2)
        self.assertEqual(len(self.workshop.events()), 2)

    def test_quota_counts_malformed_stale_and_refused_but_not_exact_retries(self):
        raw = self.raw()
        accepted = self.boundary.submit(self.token, raw)
        self.assertEqual(self.boundary.submit(self.token, b'{"x":1,"x":2}')[0], 400)
        self.assertEqual(self.boundary.submit(self.token, b"\xff")[0], 400)
        body = self.packet(request_id="bad-method")
        body["proposal"]["method"] = "execute-shell"
        self.assertEqual(self.submit(body)[0], 422)
        for index in range(4):
            self.assertEqual(self.boundary.submit(self.token, b"not json")[0], 400)
        self.assertEqual(self.used(), 8)
        self.assert_refused("CAPABILITY_EXHAUSTED", lambda: self.boundary.submit(self.token, b"{}"))
        self.assertEqual(self.boundary.submit(self.token, raw), accepted)
        self.assertEqual(self.used(), 8)
        self.workshop.dispatch({"action": "halt", "actor": "keeper", "reason": "operator correction"})
        self.assertTrue(self.workshop.state()["halted"])

    def test_receipt_lookup_is_scoped_to_issuing_capability(self):
        self.boundary.submit(self.token, self.raw())
        self.boundary.issue(self.root / "other")
        other = read_credential(self.root / "other")
        self.assert_refused("RECEIPT_NOT_FOUND", lambda: self.boundary.receipt(other, "request-1"))
        self.assert_refused("RECEIPT_NOT_FOUND", lambda: self.boundary.receipt(self.token, "absent"))

    def test_transaction_failure_rolls_back_every_persistence_stage(self):
        raw = self.raw()
        before = self.workshop.verify()
        for table, event in (("events", "INSERT"), ("snapshot", "UPDATE"),
                             ("participant_caps", "UPDATE"), ("participant_attempts", "INSERT"),
                             ("participant_receipts", "INSERT")):
            with self.subTest(table=table):
                with sqlite3.connect(self.workshop.path) as db:
                    db.execute(f"CREATE TRIGGER fail_write BEFORE {event} ON {table} BEGIN SELECT RAISE(ABORT,'injected'); END")
                try:
                    with self.assertRaises(sqlite3.DatabaseError):
                        self.boundary.submit(self.token, raw)
                finally:
                    with sqlite3.connect(self.workshop.path) as db:
                        db.execute("DROP TRIGGER fail_write")
                self.assertEqual(self.workshop.verify(), before)
                self.assertEqual(self.used(), 0)
                self.assertEqual(self.boundary.audit()["receipts"], 0)
        self.assertEqual(self.boundary.submit(self.token, raw)[0], 200)

    def test_lost_response_is_unknown_and_recovered_after_restart(self):
        raw = self.raw()
        original_send = Handler._send
        def drop(handler, status, payload):
            if payload.get("disposition") == "ACCEPTED":
                handler.connection.shutdown(socket.SHUT_RDWR)
                raise ConnectionResetError("injected response loss")
            return original_send(handler, status, payload)
        with serving(self.boundary) as server, patch.object(Handler, "_send", drop):
            result = request(server.url, self.token, "POST", "/proposals", raw)
        self.assertEqual((result[0], result[1]["disposition"]), (0, "UNKNOWN"))
        self.assertEqual(self.used(), 1)
        restarted = Boundary(self.workshop.path, clock=lambda: self.now)
        with serving(restarted) as server:
            receipt = request(server.url, self.token, "GET", "/receipts/request-1")
            retried = request(server.url, self.token, "POST", "/proposals", raw)
        self.assertEqual(receipt, retried)
        self.assertEqual(receipt[0], 200)
        self.assertEqual(len(self.workshop.events()), 2)

    def test_credentials_are_private_exclusive_and_not_persisted_in_db_or_logs(self):
        if os.name != "nt":
            self.assertEqual(self.credential.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.boundary.issue(self.credential)
        self.assertEqual(read_credential(self.credential), self.token)
        self.assertEqual(len(self.boundary.audit()["capabilities"]), 1)
        log = io.StringIO()
        with redirect_stderr(log), serving(self.boundary) as server:
            request(server.url, self.token, "POST", "/proposals", self.raw())
        self.assertNotIn(self.token, log.getvalue())
        self.assertNotIn(self.token.encode(), self.workshop.path.read_bytes())
        self.assertNotIn(self.token, canonical(self.boundary.audit()))
        self.assertNotIn(self.token, canonical(self.workshop.events()))

    def test_failed_credential_write_does_not_issue_capability(self):
        with self.assertRaises(OSError):
            self.boundary.issue(self.root / "missing" / "credential")
        with patch("commonwealth.participant_v1.store.os.fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.boundary.issue(self.root / "failed")
        self.assertFalse((self.root / "failed").exists())
        self.assertEqual(len(self.boundary.audit()["capabilities"]), 1)

    def test_install_never_overwrites_existing_boundary(self):
        instance = self.boundary.audit()["instance"]
        with self.assertRaises(sqlite3.Error):
            self.boundary.install()
        self.assertEqual(self.boundary.audit()["instance"], instance)
        self.assertEqual(self.boundary.task(self.token)[0], 200)

    def test_local_endpoint_and_body_limits(self):
        for host in ("0.0.0.0", "localhost", "::1", "example.com"):
            with self.assertRaises(ValueError):
                Server(self.boundary, host=host)
        for url in ("http://localhost:123", "https://127.0.0.1:123", "http://127.0.0.1:123/other",
                    "http://user@127.0.0.1:123", "http://127.0.0.1:123?q=1", "http://example.com:80"):
            with self.assertRaises(ValueError):
                request(url, self.token)
        self.assert_refused("BODY_TOO_LARGE", lambda: self.boundary.submit(self.token, b"x" * (MAX_BODY + 1)))
        self.assertEqual(self.used(), 0)

    def test_http_rejects_origins_framing_duplicate_auth_and_forbidden_routes(self):
        with serving(self.boundary) as server:
            base = f"Host: 127.0.0.1:{server.server_port}\r\nAuthorization: Bearer {self.token}\r\n"
            cases = [
                ("GET /task", base + "Origin: https://example.com\r\n", 400),
                ("GET /task", base + "Authorization: Bearer x\r\n", 400),
                ("GET /task", base + "Host: example.com\r\n", 400),
                ("GET /task", base + "Transfer-Encoding: chunked\r\n", 400),
                ("GET /task", base + "Expect: 100-continue\r\n", 400),
                ("GET /task", base + "Content-Length: 0\r\nContent-Length: 0\r\n", 400),
                ("POST /proposals", base + "Content-Type: application/json\r\nContent-Length: 32769\r\n", 413),
                ("POST /proposals", base + "Content-Type: text/plain\r\nContent-Length: 2\r\n", 415),
                ("POST /execute", base + "Content-Length: 2\r\n", 404),
                ("GET /../../credential", base, 404),
                ("GET /task", f"Host: attacker.example\r\nAuthorization: Bearer {self.token}\r\n", 400),
                ("GET /task", f"Host: 127.0.0.1:{server.server_port}\r\nAuthorization: Bearer bad\r\n", 401),
            ]
            for route, headers, expected in cases:
                with self.subTest(route=route, expected=expected):
                    with socket.create_connection(server.server_address, timeout=3) as sock:
                        sock.sendall(f"{route} HTTP/1.1\r\n{headers}\r\n".encode())
                        received = sock.recv(4096)
                    self.assertEqual(int(received.split(b" ")[1]), expected)
        self.assertEqual(len(self.workshop.events()), 1)
        self.assertEqual(self.used(), 0)

    def test_truncated_body_is_refused_without_attempt(self):
        with serving(self.boundary) as server:
            with socket.create_connection(server.server_address, timeout=3) as sock:
                sock.sendall((f"POST /proposals HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n"
                              f"Authorization: Bearer {self.token}\r\nContent-Type: application/json\r\n"
                              "Content-Length: 20\r\n\r\n{}").encode())
                sock.shutdown(socket.SHUT_WR)
                received = sock.recv(4096)
            self.assertEqual(int(received.split(b" ")[1]), 400)
        self.assertEqual(self.used(), 0)

    def test_redirect_is_not_followed_or_reported_as_submission_failure(self):
        def redirect(handler, status, payload):
            handler.send_response(307)
            handler.send_header("Location", "http://example.com/")
            handler.send_header("Content-Length", "0")
            handler.end_headers()
        with serving(self.boundary) as server, patch.object(Handler, "_send", redirect):
            result = request(server.url, self.token, "POST", "/proposals", self.raw())
        self.assertEqual(result[1]["disposition"], "UNKNOWN")
        self.assertEqual(self.used(), 1)

    def test_stolen_bearer_negative_control(self):
        stolen = str(self.token)
        self.assertEqual(self.boundary.submit(stolen, self.raw())[0], 200)
        self.assertEqual(self.workshop.events()[1]["command"]["actor"], "worker-1")

    def test_cloned_database_negative_control_allows_separate_consumption(self):
        raw = self.raw()
        clone_path = self.root / "clone.sqlite"
        shutil.copyfile(self.workshop.path, clone_path)
        clone = Boundary(clone_path, clock=lambda: self.now)
        self.assertEqual(self.boundary.submit(self.token, raw)[0], 200)
        self.assertEqual(clone.submit(self.token, raw)[0], 200)
        self.assertEqual(self.used(), 1)
        self.assertEqual(clone.audit()["capabilities"][0]["used"], 1)

    def test_host_can_rewrite_local_history_negative_control(self):
        _, receipt = self.boundary.submit(self.token, self.raw())
        genesis, event = self.workshop.events()
        state = initial_state(genesis["command"]["scenario"], genesis["command"]["fixture"])
        event["command"]["purpose"] = "Host replaced the original participant purpose."
        updated, _ = transition(state, event["command"])
        event["state_hash"] = digest(updated)
        receipt["event_hash"] = digest(event)
        with sqlite3.connect(self.workshop.path) as db:
            db.execute("UPDATE events SET envelope=?,hash=? WHERE seq=1", (canonical(event), digest(event)))
            db.execute("UPDATE snapshot SET body=?", (canonical(updated),))
            db.execute("UPDATE participant_receipts SET body=?", (canonical(receipt),))
        self.assertTrue(self.boundary.audit()["verified"])
        self.assertTrue(self.workshop.verify()["verified"])

    def test_authenticated_bad_proposal_remains_bad_negative_control(self):
        body = self.packet()
        body["proposal"]["method"] = "zero-fill"
        _, receipt = self.submit(body)
        self.workshop.dispatch({"action": "approve", "actor": "keeper", "proposal": receipt["proposal_id"]})
        self.workshop.dispatch({"action": "execute", "actor": "worker-1", "proposal": receipt["proposal_id"]})
        observation = self.workshop.dispatch({"action": "observe", "actor": "worker-1"})["observation"]
        self.assertFalse(observation["primary_correct"])

    def test_invalid_predictions_and_maximal_unicode_purpose(self):
        for index, value in enumerate((True, 2, -1, "0.5", None)):
            body = self.packet(request_id=f"invalid-{index}")
            body["proposal"]["prediction"]["primary_correct"] = value
            self.assertEqual(self.submit(body)[0], 422)
        body = self.packet(request_id="unicode")
        body["proposal"]["purpose"] = "\U0001f600" * 4000
        # Send UTF-8 rather than ASCII escapes; both use the same byte bound.
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.assertLess(len(raw), MAX_BODY)
        self.assertEqual(self.boundary.submit(self.token, raw)[0], 200)

    def test_audit_detects_broken_accounting(self):
        with sqlite3.connect(self.workshop.path) as db:
            db.execute("UPDATE participant_caps SET used=1")
        with self.assertRaisesRegex(ValueError, "accounting"):
            self.boundary.audit()

    def test_audit_detects_deleted_accepted_receipt(self):
        self.boundary.submit(self.token, self.raw())
        with sqlite3.connect(self.workshop.path) as db:
            db.execute("DELETE FROM participant_receipts")
        with self.assertRaisesRegex(ValueError, "accepted receipt"):
            self.boundary.audit()

    def test_token_from_another_instance_is_rejected(self):
        other = Workshop.create(self.root / "other.sqlite")
        boundary = Boundary(other.path, clock=lambda: self.now)
        boundary.install()
        self.assert_refused("UNAUTHORIZED", lambda: boundary.task(self.token))

    def test_credential_bounds_and_symlink_non_overwrite(self):
        for ttl, attempts in ((0, 1), (3601, 1), (True, 1), (1, 0), (1, 65), (1, True)):
            with self.assertRaises(ValueError):
                self.boundary.issue(self.root / "invalid", ttl, attempts)
        with patch("commonwealth.participant_v1.store.MAX_CAPABILITIES", 1):
            with self.assertRaisesRegex(ValueError, "history is full"):
                self.boundary.issue(self.root / "too-many")
        long_file = self.root / "too-long"
        long_file.write_text(self.token + " " * 300, encoding="ascii")
        with self.assertRaises(ValueError):
            read_credential(long_file)
        link = self.root / "link"
        try:
            link.symlink_to(self.credential)
        except OSError:
            return  # Windows runners need not grant symlink creation rights.
        with self.assertRaises(FileExistsError):
            self.boundary.issue(link)
        self.assertEqual(read_credential(self.credential), self.token)

    def test_connection_slots_are_bounded(self):
        with serving(self.boundary) as server:
            for _ in range(8):
                self.assertTrue(server.slots.acquire(blocking=False))
            try:
                result = request(server.url, self.token)
                self.assertEqual(result[1]["disposition"], "UNAVAILABLE")
            finally:
                for _ in range(8):
                    server.slots.release()
            self.assertEqual(request(server.url, self.token)[0], 200)

    def test_cli_smoke_and_secret_free_output(self):
        result = subprocess.run([sys.executable, "-m", "commonwealth.participant_v1", "demo"],
                                cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["verified"])
        result = subprocess.run([sys.executable, "-m", "commonwealth.participant_v1", "issue",
                                 str(self.workshop.path), str(self.root / "cli-credential")],
                                cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(read_credential(self.root / "cli-credential"), result.stdout + result.stderr)

    def test_prior_implementations_and_evidence_remain_byte_identical(self):
        manifest = json.loads((ROOT / "tests/data/participant-preserved-baseline.json").read_text())
        for path, expected in manifest["sha256"].items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
