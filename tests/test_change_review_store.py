from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.change_review_v1 import store


class ReviewRecords(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "change register.sqlite"
        self.new = store.initialize(self.path)
        self.submit = {"op": "submit", "register_id": self.new["register_id"], "id": "patch-17", "title": "Read release receipts",
                       "proposal": "Add a bounded receipt reader.", "evidence": ["build/replay.json"]}
        self.decision = {"op": "decide", "register_id": self.new["register_id"], "id": "patch-17", "decision": "approve",
                         "rationale": "The recorded replay matches the expected results."}
        self.get = {"op": "get", "id": "patch-17"}

    def call(self, request, uid=12, reviewer=False):
        if request.get("op") == "decide" and "submission_digest" not in request:
            # Tests that exercise other conditions bind the exact fixture proposal.
            target = {"op": "get", "id": request["id"], "owner_uid": request.get("owner_uid", 12)}
            record = store.handle(self.path, 12, False, target)["record"]
            request = {**request, "submission_digest": record["submission_digest"]}
        return store.handle(self.path, uid, reviewer, request)

    def failure(self, code, fn, *args):
        with self.assertRaises(store.DomainError) as found:
            fn(*args)
        self.assertEqual(found.exception.code, code)

    def test_creation_exclusive_private_readonly_integrity_and_register_identity(self):
        self.assertEqual(self.new, store.verify(self.path))
        self.assertEqual(self.new["records"], 0)
        self.assertRegex(self.new["register_id"], r"^[0-9a-f]{32}$")
        self.failure("already_exists", store.initialize, self.path)
        self.assertEqual(self.new, store.verify(self.path))
        if os.name == "posix":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        other = self.path.with_name("other.sqlite")
        another = store.initialize(other)
        self.assertNotEqual(another["register_id"], self.new["register_id"])
        with patch.object(store.time, "time", return_value=55):
            first = self.call(self.submit)["record"]
            second = store.handle(other, 12, False, {**self.submit, "register_id": another["register_id"]})["record"]
        self.assertNotEqual(first["submission_digest"], second["submission_digest"])
        self.assertEqual(first["register_id"], self.new["register_id"])
        snapshot = self.path.read_bytes()
        self.call(self.get)
        self.assertEqual(store.verify(self.path)["records"], 1)
        self.assertEqual(self.path.read_bytes(), snapshot)
        self.assertEqual(self.path.stat().st_nlink, 1)

    def test_scoped_reads_and_collision_free_names(self):
        one = self.call(self.submit)
        self.failure("not_found", self.call, self.get, 21)
        self.failure("not_found", self.call, {**self.get, "owner_uid": 12}, 21)
        self.failure("forbidden", self.call, {"op": "list"})
        self.failure("forbidden", self.call, self.decision, 21)
        second = self.call({**self.submit, "title": "Another contributor's work"}, 21)
        self.assertEqual(self.call(self.get, 21), second)
        self.assertEqual(self.call(self.get), one)
        self.failure("ambiguous_id", self.call, self.get, 99, True)
        self.assertEqual(self.call({**self.get, "owner_uid": 12}, 99, True), one)
        self.failure("self_review", self.call, {**self.decision, "owner_uid": 12}, 12, True)
        self.assertEqual(store.verify(self.path)["decisions"], 0)

    def test_idempotent_acceptance_conflict_and_post_decision_retry(self):
        original = self.call(self.submit, 12, True)
        self.assertEqual(self.call(self.submit), original)
        self.failure("id_conflict", self.call, {**self.submit, "evidence": ["different.txt"]})
        decided = self.call(self.decision, 38, True)
        self.assertEqual(decided["record"]["submission_digest"], original["record"]["submission_digest"])
        self.assertEqual(decided["record"]["decision"]["reviewer_uid"], 38)
        self.assertEqual(self.call(self.decision, 38, True), decided)
        self.assertEqual(self.call(self.submit), original)
        self.assertEqual(self.call(self.get), decided)
        self.failure("decision_conflict", self.call, self.decision, 40, True)
        self.failure("decision_conflict", self.call, {**self.decision, "rationale": "Changed."}, 38, True)
        self.assertEqual((store.verify(self.path)["records"], store.verify(self.path)["decisions"]), (1, 1))

    def test_exact_observed_register_and_proposal_required_even_for_retries(self):
        without_id = {key: value for key, value in self.submit.items() if key != "register_id"}
        self.failure("invalid_request", self.call, without_id)
        self.failure("register_mismatch", self.call, {**self.submit, "register_id": "0" * 32})
        checkpoint = self.path.with_name("prior.sqlite")
        shutil.copy2(self.path, checkpoint)
        receipt = self.call(self.submit)["record"]
        self.failure("invalid_request", store.handle, self.path, 81, True, self.decision)
        observed = {**self.decision, "submission_digest": receipt["submission_digest"]}
        self.failure("register_mismatch", self.call, {**observed, "register_id": "0" * 32}, 81, True)
        self.failure("submission_mismatch", self.call, {**observed, "submission_digest": "0" * 64}, 81, True)
        self.assertIsNone(self.call(self.get)["record"]["decision"])
        self.call(observed, 81, True)
        self.failure("submission_mismatch", self.call, {**observed, "submission_digest": "0" * 64}, 81, True)
        changed = store.handle(checkpoint, 12, False, {**self.submit, "title": "Different change"})["record"]
        self.assertEqual(changed["register_id"], receipt["register_id"])
        self.assertNotEqual(changed["submission_digest"], receipt["submission_digest"])
        self.failure("submission_mismatch", store.handle, checkpoint, 81, True, observed)
        self.assertEqual(store.verify(checkpoint)["decisions"], 0)

    def test_two_reviewers_cannot_both_commit_and_same_submissions_converge(self):
        with ThreadPoolExecutor(4) as pool:
            receipts = list(pool.map(lambda _: self.call(self.submit), range(8)))
            self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
            def decide(person):
                try:
                    self.call(self.decision, person, True)
                    return "committed"
                except store.DomainError as exc:
                    return exc.code
            self.assertCountEqual(pool.map(decide, (31, 32)), ("committed", "decision_conflict"))
        self.assertEqual(store.verify(self.path)["decisions"], 1)

    def test_rolled_back_commit_can_be_retried_without_partial_record(self):
        connect = sqlite3.connect
        class Interrupted(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("simulated storage error")
        def fail(*args, **kwargs):
            return connect(*args, **kwargs, factory=Interrupted)
        with patch.object(sqlite3, "connect", side_effect=fail):
            self.failure("store_unavailable", self.call, self.submit)
        self.assertEqual(store.verify(self.path)["records"], 0)
        self.assertEqual(self.call(self.submit)["record"]["seq"], 1)
        with patch.object(sqlite3, "connect", side_effect=fail):
            self.failure("store_unavailable", self.call, self.decision, 45, True)
        self.assertIsNone(self.call(self.get)["record"]["decision"])
        self.assertEqual(self.call(self.decision, 45, True)["record"]["decision"]["decision"], "approve")

    def test_pagination_and_capacity_preserve_replay_and_decision(self):
        with patch.object(store, "MAX_RECORDS", 3):
            for name in ("p1", "p2", "p3"):
                self.call({**self.submit, "id": name})
            page = self.call({"op": "list", "limit": 2}, 90, True)
            self.assertEqual([x["id"] for x in page["items"]], ["p1", "p2"])
            self.assertEqual(set(page["items"][0]), {"seq", "id", "owner_uid", "title", "state"})
            tail = self.call({"op": "list", "after": page["next_after"]}, 90, True)
            self.assertEqual([x["id"] for x in tail["items"]], ["p3"])
            self.assertIsNone(tail["next_after"])
            self.failure("capacity_reached", self.call, {**self.submit, "id": "p4"})
            self.assertEqual(self.call({**self.submit, "id": "p2"})["record"]["seq"], 2)
            self.call({**self.decision, "id": "p2", "decision": "decline"}, 90, True)
            self.assertEqual(self.call({"op": "list"}, 90, True)["items"][1]["state"], "decline")

    def test_validation_bounds_and_unknown_fields(self):
        for changed in ({"id": ""}, {"id": "r" * 81}, {"evidence": []}, {"evidence": ["doc"] * 5},
                        {"evidence": [" " * 2]}, {"title": "x\x00y"}, {"title": "猫" * 54},
                        {"evidence": [123]}, {"proposal": "x" * 2049}, {"title": "\ud800"}, {"uid": 0}):
            with self.subTest(changed=changed):
                self.failure("invalid_request", self.call, {**self.submit, **changed})
        for invalid in ({"limit": 33}, {"after": True}, {"limit": -1}, {"before": 0}):
            self.failure("invalid_request", self.call, {"op": "list", **invalid}, 31, True)
        self.assertEqual(store.verify(self.path)["records"], 0)

    def test_business_integrity_checked_beyond_sqlite_physical_checks(self):
        self.call(self.submit)
        with closing(sqlite3.connect(self.path)) as db, db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM proposals WHERE seq=1")
            db.execute("DROP TRIGGER immutable_proposals_update")
            db.execute("UPDATE proposals SET submission_digest='broken' WHERE seq=1")
            db.execute(store.SCHEMA["immutable_proposals_update"])
        self.failure("invalid_store", store.verify, self.path)
        self.failure("invalid_store", self.call, self.get)

    def test_clock_rollback_leaves_decision_pending(self):
        with patch.object(store.time, "time", return_value=1000):
            self.call(self.submit)
        with patch.object(store.time, "time", return_value=999):
            self.failure("clock_regression", self.call, self.decision, 99, True)
        self.assertIsNone(self.call(self.get)["record"]["decision"])

    @unittest.skipUnless(os.name == "posix", "POSIX private storage")
    def test_admission_refuses_public_parent_and_database(self):
        self.path.chmod(0o640)
        self.failure("invalid_store", store.ready, self.path)
        self.path.chmod(0o600)
        self.path.parent.chmod(0o750)
        try:
            self.failure("invalid_store", store.initialize, self.path.with_name("new.sqlite"))
            self.failure("invalid_store", store.ready, self.path)
        finally:
            self.path.parent.chmod(0o700)
