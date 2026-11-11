"""SQLite-backed one-use approvals for synthetic, non-operational actions.

The SQLite transaction reserves a nonce and records the decision together.
This is not a hardware command executor or a production authorization service.
"""
from contextlib import closing
from copy import deepcopy
import hashlib
import sqlite3
import time
from .secure_gateway import Gateway, canonical
from .gates import Decision

class DurableGateway:
    def __init__(self, database_path, key):
        self.database_path = str(database_path)
        self.key = key
        Gateway(key, set())  # validate key
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS approvals (nonce TEXT PRIMARY KEY, digest TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL, consumed_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, nonce TEXT, allowed INTEGER NOT NULL, reason TEXT NOT NULL, recorded_at INTEGER NOT NULL)")

            db.execute("""CREATE TABLE IF NOT EXISTS simulation_outbox (
                nonce TEXT PRIMARY KEY REFERENCES approvals(nonce), sink_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL, confirmed_receipt TEXT)""")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def decide(self, request, policy, approval, signature, now=None):
        return self._decide(request, policy, approval, signature, now, stage=False)

    def stage_simulation(self, request, policy, approval, signature, now=None):
        """Consume the grant and journal a local sample-record intent in one transaction."""
        return self._decide(request, policy, approval, signature, now, stage=True)

    def _decide(self, request, policy, approval, signature, now, stage):
        try:
            # Use one snapshot for signature verification, scope checks and persistence.
            request, policy, approval = deepcopy((request, policy, approval))
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                clock = int(time.time()) if now is None else now
                checked = Gateway(self.key, set()).decide(request, policy, approval, signature, now=clock)
                nonce = approval.get("nonce") if isinstance(approval, dict) else None
                if checked.allowed and stage:
                    # This version supports exactly one argument-free, local operation.
                    # Both the destination and protocol must be part of the signed grant.
                    grant_fields = {"actor", "action", "resource", "approved", "nonce", "issued_at",
                                    "expires_at", "delivery_protocol", "sink_id"}
                    if (set(approval) != grant_fields or set(request) != {"actor", "action", "resource"} or request["action"] != "simulate"
                            or approval.get("delivery_protocol") != "local-sample-v1"
                            or not isinstance(approval.get("sink_id"), str) or not approval["sink_id"]):
                        checked = Decision(False, "invalid_simulation_intent")
                if checked.allowed:
                    digest = hashlib.sha256(canonical(approval)).hexdigest()
                    inserted = db.execute(
                        "INSERT INTO approvals(nonce,digest,actor,action,resource,consumed_at) "
                        "VALUES (?,?,?,?,?,?) ON CONFLICT(nonce) DO NOTHING",
                        (nonce, digest, request["actor"], request["action"], request["resource"], clock),
                    )
                    if inserted.rowcount == 0:
                        checked = Decision(False, "replayed_approval")
                    elif stage:
                        db.execute("INSERT INTO simulation_outbox(nonce,sink_id,expires_at) VALUES (?,?,?)",
                                   (nonce, approval["sink_id"], approval["expires_at"]))
                        checked = Decision(True, "simulation_staged")
                db.execute("INSERT INTO decisions(nonce,allowed,reason,recorded_at) VALUES (?,?,?,?)",
                           (nonce if isinstance(nonce, str) else None, int(checked.allowed), checked.reason, clock))
            return checked
        except (sqlite3.Error, TypeError, ValueError, OverflowError):
            return Decision(False, "persistence_or_validation_error")
