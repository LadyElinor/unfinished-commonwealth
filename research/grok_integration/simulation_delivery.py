"""Recoverable delivery to a separate SQLite sample ledger. No external effect adapters."""
from contextlib import closing
from dataclasses import dataclass
import hashlib
import sqlite3
import time
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
        self.path = str(path)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), name TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO identity VALUES (1,?)", (uuid4().hex,))
            self.identity = db.execute("SELECT name FROM identity WHERE id=1").fetchone()[0]
            db.execute("""CREATE TABLE IF NOT EXISTS samples (
                nonce TEXT PRIMARY KEY, digest TEXT NOT NULL, resource TEXT NOT NULL, receipt TEXT NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, isolation_level=None)

    def record(self, intent, *, now=None):
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
                return receipt
            clock = int(time.time()) if now is None else now
            if type(clock) is not int or not intent.staged_at <= clock <= intent.expires_at:
                raise ValueError("delivery window closed")
            db.execute("INSERT INTO samples VALUES (?,?,?,?)",
                       (intent.nonce, intent.digest, intent.resource, receipt))
            return receipt


def deliver_sample(gateway, ledger, nonce, *, now=None):
    """Retry an unconfirmed local intent; recover a matching prior receipt after reply loss."""
    with closing(gateway._connect()) as db:
        row = db.execute("""SELECT a.nonce, a.digest, a.resource, q.sink_id, a.consumed_at, q.expires_at, q.confirmed_receipt
                            FROM approvals a JOIN simulation_outbox q USING(nonce) WHERE a.nonce=?""",
                         (nonce,)).fetchone()
    if row is None:
        raise ValueError("no staged sample")
    intent = Intent(*row[:-1])
    if ledger.identity != intent.sink_id:
        raise ValueError("wrong sample ledger")
    if row[-1] is not None:
        return row[-1]
    receipt = ledger.record(intent, now=now)
    with closing(gateway._connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        updated = db.execute("""UPDATE simulation_outbox SET confirmed_receipt=?
                                WHERE nonce=? AND (confirmed_receipt IS NULL OR confirmed_receipt=?)""",
                             (receipt, nonce, receipt))
        if updated.rowcount != 1:
            raise ValueError("command confirmation conflict")
    return receipt
