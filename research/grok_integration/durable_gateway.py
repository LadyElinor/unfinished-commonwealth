"""SQLite-backed one-use approvals for synthetic, non-operational actions.

The SQLite transaction reserves a nonce and records the decision together.
This is not a hardware command executor or a production authorization service.
"""
import sqlite3
import time
from .secure_gateway import Gateway, canonical
from .gates import Decision

class DurableGateway:
    def __init__(self, database_path, key):
        self.database_path = str(database_path)
        self.key = key
        Gateway(key, set())  # validate key
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS approvals (nonce TEXT PRIMARY KEY, digest TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL, consumed_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, nonce TEXT, allowed INTEGER NOT NULL, reason TEXT NOT NULL, recorded_at INTEGER NOT NULL)")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def decide(self, request, policy, approval, signature, now=None):
        clock = int(time.time()) if now is None else now
        try:
            # Validate without consuming a nonce in memory.
            checked = Gateway(self.key, set()).decide(request, policy, approval, signature, now=clock)
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                nonce = approval.get("nonce") if isinstance(approval, dict) else None
                if checked.allowed:
                    import hashlib
                    digest = hashlib.sha256(canonical(approval)).hexdigest()
                    try:
                        db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?)", (nonce, digest, request["actor"], request["action"], request["resource"], clock))
                    except sqlite3.IntegrityError:
                        checked = Decision(False, "replayed_approval")
                db.execute("INSERT INTO decisions(nonce,allowed,reason,recorded_at) VALUES (?,?,?,?)",
                           (nonce if isinstance(nonce, str) else None, int(checked.allowed), checked.reason, clock))
                db.execute("COMMIT")
            return checked
        except (sqlite3.Error, TypeError, ValueError, OverflowError):
            return Decision(False, "persistence_or_validation_error")
