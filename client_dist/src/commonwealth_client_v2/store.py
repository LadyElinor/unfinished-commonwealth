"""One immutable, bounded participant intent and explicit recovery operations.

The local filesystem, SQLite and host are trusted. A digest detects accidental
changes, not malicious rewriting. No bearer or unvalidated server text is saved.
"""

from contextlib import closing
import hashlib
import hmac
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from .wire import canonical, exact, parse_json, PROTOCOL, MAX_BODY, TOKEN, REQUEST_ID, HEAD
from .transport import request
from . import VERSION

INSTANCE = re.compile(r"[0-9a-f]{32}\Z")
MAX_OPERATIONS = 256
DISPOSITIONS = {400: "INVALID_REQUEST", 409: "STALE_VIEW", 422: "PROPOSAL_REFUSED"}


def endpoint(url):
    p = urlsplit(url)
    if (p.scheme != "http" or p.hostname != "127.0.0.1" or p.username is not None
            or p.password is not None or p.path not in ("", "/") or p.query or p.fragment
            or p.netloc != f"127.0.0.1:{p.port}" or not p.port):
        raise ValueError("invalid endpoint")
    return f"http://127.0.0.1:{p.port}"


def credential(token):
    match = TOKEN.fullmatch(token) if isinstance(token, str) else None
    if not match:
        raise ValueError("invalid credential")
    return match[1], hashlib.sha256(token.encode("ascii")).hexdigest()


def envelope(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BODY:
        raise ValueError("invalid intent size")
    body = parse_json(raw.decode("utf-8"))
    exact(body, ("protocol", "request_id", "view_head", "proposal"))
    exact(body["proposal"], ("method", "prediction", "purpose"))
    if (body["protocol"] != PROTOCOL or not isinstance(body["request_id"], str)
            or not REQUEST_ID.fullmatch(body["request_id"])
            or not isinstance(body["view_head"], str) or not HEAD.fullmatch(body["view_head"])):
        raise ValueError("invalid intent envelope")
    return body


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class Outbox:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def connect(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)

    @classmethod
    def stage(cls, path, url, token, task, raw):
        """Persist intent before network. Task is caller-supplied host data."""
        body = envelope(raw)
        cap, token_digest = credential(token)
        if token in raw.decode("utf-8") or token in canonical(body):
            raise ValueError("credential must not appear in intent")
        if (not isinstance(task, dict) or task.get("protocol") != PROTOCOL
                or task.get("disposition") != "TASK" or task.get("external_authority") != "NONE"
                or not isinstance(task.get("instance"), str) or not INSTANCE.fullmatch(task["instance"])
                or task.get("view_head") != body["view_head"]):
            raise ValueError("task does not bind intent")
        intent = {"version": VERSION, "url": endpoint(url), "capability": cap,
                  "credential_digest": token_digest, "instance": task["instance"],
                  "request_id": body["request_id"], "raw_hex": raw.hex(),
                  "raw_sha256": hashlib.sha256(raw).hexdigest()}
        target = cls(path)
        # Exclusive creation; never replace another intent or credential file.
        fd = os.open(target.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            with closing(target.connect()) as db, db:
                db.execute("CREATE TABLE intent (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL, digest TEXT NOT NULL)")
                db.execute("CREATE TABLE operations (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, observation TEXT)")
                db.execute("CREATE TABLE recorded (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL, digest TEXT NOT NULL)")
                db.execute("INSERT INTO intent VALUES (1,?,?)", (canonical(intent), fingerprint(intent)))
            return target.status()
        except BaseException:
            target.path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _read(db):
        row = db.execute("SELECT body,digest FROM intent WHERE singleton=1").fetchone()
        if not row or len(row[0]) > 2 * MAX_BODY + 2048:
            raise ValueError("invalid retained intent")
        intent = parse_json(row[0])
        exact(intent, ("version", "url", "capability", "credential_digest", "instance", "request_id", "raw_hex", "raw_sha256"))
        if fingerprint(intent) != row[1] or intent["version"] != VERSION:
            raise ValueError("retained intent integrity mismatch")
        raw = bytes.fromhex(intent["raw_hex"])
        body = envelope(raw)
        if (endpoint(intent["url"]) != intent["url"] or body["request_id"] != intent["request_id"]
                or hashlib.sha256(raw).hexdigest() != intent["raw_sha256"]
                or not INSTANCE.fullmatch(intent["instance"]) or not INSTANCE.fullmatch(intent["capability"])
                or not HEAD.fullmatch(intent["credential_digest"])):
            raise ValueError("invalid retained binding")
        saved = db.execute("SELECT body,digest FROM recorded WHERE singleton=1").fetchone()
        receipt = None
        if saved:
            if len(saved[0]) > 2048:
                raise ValueError("invalid retained receipt")
            receipt = parse_json(saved[0])
            if fingerprint(receipt) != saved[1] or not Outbox._valid_receipt(intent, receipt["http_status"], receipt["receipt"]):
                raise ValueError("retained receipt integrity mismatch")
        return intent, raw, receipt

    @staticmethod
    def _valid_receipt(intent, status, payload):
        if type(status) is not int or not isinstance(payload, dict):
            return False
        common = {"protocol", "disposition", "external_authority", "request_id"}
        if (payload.get("protocol") != PROTOCOL or payload.get("external_authority") != "NONE"
                or payload.get("request_id") != intent["request_id"]):
            return False
        if status == 200:
            if set(payload) != common | {"instance", "event_seq", "event_hash", "proposal_id", "permits_execution"}:
                return False
            return (payload["disposition"] == "ACCEPTED" and payload["instance"] == intent["instance"]
                    and type(payload["event_seq"]) is int and payload["event_seq"] >= 1
                    and isinstance(payload["event_hash"], str) and bool(HEAD.fullmatch(payload["event_hash"]))
                    and isinstance(payload["proposal_id"], str) and bool(re.fullmatch(r"propose-[0-9]{1,8}", payload["proposal_id"]))
                    and payload["permits_execution"] is False)
        return status in DISPOSITIONS and payload.get("disposition") == DISPOSITIONS[status] and set(payload) == common

    def status(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            intent, _, receipt = self._read(db)
            started = db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
            observed = db.execute("SELECT COUNT(*) FROM operations WHERE observation IS NOT NULL").fetchone()[0]
            return {"version": VERSION, "state": "RECORDED" if receipt else "UNRESOLVED",
                    "request_id": intent["request_id"], "instance": intent["instance"],
                    "operations_started": started, "operations_observed": observed,
                    "latest_observation": (db.execute("SELECT observation FROM operations ORDER BY id DESC LIMIT 1").fetchone() or [None])[0],
                    "recorded": receipt, "external_authority": "NONE",
                    "assurance": "local retained observation, not current authorization or independent attestation"}

    def operate(self, token, kind):
        """One explicit lookup or exact-byte retry; never renew or replace intent."""
        if kind not in ("resolve", "retry"):
            raise ValueError("invalid recovery operation")
        cap, token_digest = credential(token)
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            intent, raw, receipt = self._read(db)
            if cap != intent["capability"] or not hmac.compare_digest(token_digest, intent["credential_digest"]):
                raise ValueError("credential does not match retained intent")
            if receipt:
                db.rollback()
                return self.status()
            if db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] >= MAX_OPERATIONS:
                raise ValueError("outbox operation history exhausted; outcome remains unresolved")
            operation = db.execute("INSERT INTO operations(kind) VALUES (?)", (kind,)).lastrowid
            db.commit()  # A crash after this point leaves a visible incomplete operation.
            db.execute("BEGIN IMMEDIATE")
            intent, raw, receipt = self._read(db)
            if receipt:
                observation = "NOT_SENT_ALREADY_RECORDED"
            else:
                if kind == "resolve":
                    status, payload = request(intent["url"], token, path="/receipts/" + intent["request_id"])
                else:
                    status, payload = request(intent["url"], token, "POST", "/proposals", raw)
                if kind == "resolve" and self._valid_receipt(intent, status, payload):
                    # B1 GET receipts omit the original request fingerprint.
                    # Lookup alone cannot bind the receipt to our exact bytes.
                    observation = "RECEIPT_REQUIRES_EXACT_RETRY"
                elif self._valid_receipt(intent, status, payload):
                    saved = {"http_status": status, "receipt": payload}
                    db.execute("INSERT INTO recorded VALUES (1,?,?)", (canonical(saved), fingerprint(saved)))
                    observation = "RECORDED"
                else:
                    # Persist controlled labels only, never unvalidated server text.
                    observation = "UNRESOLVED"
            db.execute("UPDATE operations SET observation=? WHERE id=?", (observation, operation))
            db.commit()
        return self.status()
