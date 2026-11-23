"""Recoverable delivery to a separate SQLite sample ledger. No external effect adapters."""
from contextlib import closing
from dataclasses import dataclass
import hashlib
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from .secure_gateway import canonical


@dataclass(frozen=True)
class Intent:
    nonce: str
    digest: str
    resource: str
    sink_id: str
    staged_at: int
    expires_at: int


class SampleLedger:
    """A local fixture. The sample row itself is the entire effect."""

    def __init__(self, path):
        self.path = str(Path(path).resolve())
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO identity VALUES (1,?)", (uuid4().hex,))
            self.identity = db.execute("SELECT name FROM identity WHERE id=1").fetchone()[0]
            db.execute("""CREATE TABLE IF NOT EXISTS samples (
                nonce TEXT PRIMARY KEY, digest TEXT NOT NULL, resource TEXT NOT NULL, receipt TEXT NOT NULL)""")

            db.execute("""CREATE TABLE IF NOT EXISTS closed_samples (
                nonce TEXT PRIMARY KEY, digest TEXT NOT NULL, resource TEXT NOT NULL)""")

    def connect(self):
        return sqlite3.connect(Path(self.path).as_uri() + "?mode=rw", uri=True, isolation_level=None)

    def record(self, intent, *, now=None):
        status, receipt = self._resolve(intent, now, deliver=True)
        if status == "expired_no_effect":
            raise WindowClosed("delivery window closed")
        return receipt

    def inspect(self, intent, *, now=None):
        """Reconcile without inserting a sample. Seal verified absence after expiry."""
        return self._resolve(intent, now, deliver=False)

    def _resolve(self, intent, now, *, deliver):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            identity = db.execute("SELECT name FROM identity WHERE id=1").fetchone()[0]
            if identity != intent.sink_id:
                raise ValueError("wrong sample ledger")
            receipt = hashlib.sha256(canonical(["local-sample-v1", identity, intent.nonce,
                                                intent.digest, intent.resource])).hexdigest()
            existing = db.execute("SELECT digest, resource, receipt FROM samples WHERE nonce=?",
                                  (intent.nonce,)).fetchone()
            if existing is not None:
                if existing != (intent.digest, intent.resource, receipt):
                    raise ValueError("conflicting sample record")
                return "confirmed", receipt
            closed = db.execute("SELECT digest, resource FROM closed_samples WHERE nonce=?", (intent.nonce,)).fetchone()
            if closed is not None:
                if closed != (intent.digest, intent.resource):
                    raise ValueError("conflicting closed sample")
                return "expired_no_effect", None
            clock = int(time.time()) if now is None else now
            if type(clock) is not int or clock < intent.staged_at:
                raise ValueError("invalid delivery clock")
            if clock > intent.expires_at:
                db.execute("INSERT INTO closed_samples VALUES (?,?,?)", (intent.nonce, intent.digest, intent.resource))
                return "expired_no_effect", None
            if not deliver:
                return "pending", None
            db.execute("INSERT INTO samples VALUES (?,?,?,?)",
                       (intent.nonce, intent.digest, intent.resource, receipt))
            return "confirmed", receipt


class WindowClosed(ValueError):
    pass


def _staged(db, nonce):
    row = db.execute("""SELECT a.nonce,a.digest,a.resource,q.sink_id,a.consumed_at,q.expires_at,
                        q.confirmed_receipt,f.finding FROM approvals a JOIN simulation_outbox q USING(nonce)
                        LEFT JOIN simulation_findings f USING(nonce) WHERE a.nonce=?""", (nonce,)).fetchone()
    if row is None:
        raise ValueError("no staged sample")
    return Intent(*row[:6]), ("confirmed" if row[6] else row[7] or "pending"), row[6]


def delivery_status(gateway, nonce):
    """Durable observation only. A delivery outcome grants no authority or relief."""
    with closing(gateway._connect()) as db:
        _, status, receipt = _staged(db, nonce)
        return {"outcome": status, "receipt": receipt, "obligations": "not_assessed"}


def _save(gateway, nonce, finding, receipt=None):
    # Serialize writers. Late unknown/pending observations cannot erase terminal evidence.
    with closing(gateway._connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _, status, existing = _staged(db, nonce)
        if status in ("confirmed", "expired_no_effect"):
            if finding in ("confirmed", "expired_no_effect") and (status, existing) != (finding, receipt):
                raise ValueError("conflicting terminal outcome")
            return status, existing
        if finding == "confirmed":
            db.execute("UPDATE simulation_outbox SET confirmed_receipt=? WHERE nonce=?", (receipt, nonce))
            db.execute("DELETE FROM simulation_findings WHERE nonce=?", (nonce,))
        elif finding == "pending":
            # A lack of confirmation still leaves an earlier ambiguous delivery unresolved.
            return status, existing
        else:
            db.execute("INSERT OR REPLACE INTO simulation_findings VALUES (?,?)", (nonce, finding))
        return finding, receipt


def reconcile_sample(gateway, ledger, nonce, *, now=None):
    """Check the bound sink without delivering; missing/conflicting evidence stays unknown."""
    with closing(gateway._connect()) as db:
        intent, status, _ = _staged(db, nonce)
    if status not in ("confirmed", "expired_no_effect"):
        try:
            if ledger is None or ledger.identity != intent.sink_id:
                raise ValueError("missing or different sample ledger")
            finding, receipt = ledger.inspect(intent, now=now)
        except (OSError, sqlite3.Error, ValueError):
            finding, receipt = "unknown", None
        _save(gateway, nonce, finding, receipt)
    return delivery_status(gateway, nonce)


def deliver_sample(gateway, ledger, nonce, *, now=None):
    """Deliver or recover the original receipt; never renew expired authority."""
    with closing(gateway._connect()) as db:
        intent, status, receipt = _staged(db, nonce)
    if ledger.identity != intent.sink_id:
        _save(gateway, nonce, "unknown")
        raise ValueError("wrong sample ledger")
    if status == "confirmed":
        return receipt
    if status == "expired_no_effect":
        raise WindowClosed("delivery window closed")
    try:
        receipt = ledger.record(intent, now=now)
    except WindowClosed:
        _save(gateway, nonce, "expired_no_effect")
        raise
    except (OSError, sqlite3.Error, ValueError):
        _save(gateway, nonce, "unknown")
        raise
    _save(gateway, nonce, "confirmed", receipt)
    return receipt
