"""Persist clock observations independently of refused proposal transactions.

B1.1 retains B1's tables, wire protocol and trusted-host assumptions. It does not
make wall time trustworthy. An explicit metadata upgrade makes historical B1 refuse the upgraded database.
The workshop journal and participant table layout are unchanged.
"""

from contextlib import contextmanager
import sqlite3
import secrets

from ..participant_v1 import VERSION as HISTORICAL_VERSION
from . import VERSION as STORAGE_VERSION
from ..participant_v1.store import Boundary as HistoricalBoundary, Refused


class Boundary(HistoricalBoundary):
    def install(self):
        # Fresh creation is atomic and never exposes historical metadata.
        connection = self.workshop.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state, _, _ = self.workshop._verify(connection)
            if state["schema"] != 2:
                raise ValueError("participant boundary requires protocol 2")
            for statement in (
                "CREATE TABLE participant_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version TEXT NOT NULL, instance TEXT NOT NULL, last_wall INTEGER NOT NULL)",
                "CREATE TABLE participant_caps (id TEXT PRIMARY KEY, token_digest TEXT NOT NULL UNIQUE, worker TEXT NOT NULL, generation INTEGER NOT NULL, issued INTEGER NOT NULL, expires INTEGER NOT NULL, ceiling INTEGER NOT NULL, used INTEGER NOT NULL, revoked INTEGER NOT NULL)",
                "CREATE TABLE participant_attempts (seq INTEGER PRIMARY KEY, cap TEXT NOT NULL, request_id TEXT, fingerprint TEXT NOT NULL, status INTEGER NOT NULL, received INTEGER NOT NULL)",
                "CREATE TABLE participant_receipts (cap TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(cap, request_id))",
            ):
                connection.execute(statement)
            instance = secrets.token_hex(16)
            connection.execute("INSERT INTO participant_meta VALUES (1,?,?,?)",
                               (STORAGE_VERSION, instance, self._now()))
            connection.commit()
            return {"version": STORAGE_VERSION, "instance": instance, "external_authority": "NONE"}
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upgrade(self):
        """Opt into B1.1 and make historical B1 fail closed on this database."""
        connection = self.workshop.connect()
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            state, _, _ = self.workshop._verify(connection)
            meta = connection.execute("SELECT * FROM participant_meta WHERE singleton=1").fetchone()
            if (not meta or meta["version"] not in (HISTORICAL_VERSION, STORAGE_VERSION)
                    or state["schema"] != 2):
                raise Refused(503, "BOUNDARY_UNAVAILABLE")
            now = self._now()
            if now < meta["last_wall"]:
                raise Refused(503, "CLOCK_ROLLBACK")
            connection.execute("UPDATE participant_meta SET version=?, last_wall=? WHERE singleton=1",
                               (STORAGE_VERSION, max(now, meta["last_wall"])))
            connection.commit()
            return {"version": STORAGE_VERSION, "instance": meta["instance"],
                    "external_authority": "NONE"}
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def audit(self):
        result = super().audit()
        result["version"] = STORAGE_VERSION
        return result

    @contextmanager
    def _transaction(self, allow_rollback=False):
        connection = self.workshop.connect()
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            state, _, _ = self.workshop._verify(connection)
            meta = connection.execute("SELECT * FROM participant_meta WHERE singleton=1").fetchone()
            if not meta or meta["version"] != STORAGE_VERSION or state["schema"] != 2:
                raise Refused(503, "BOUNDARY_UNAVAILABLE")
            now = self._now()
            if now < meta["last_wall"] and not allow_rollback:
                raise Refused(503, "CLOCK_ROLLBACK")
            # Commit only the clock floor before authentication or operation work.
            # A refusal or later write failure must not erase observed expiry.
            connection.execute("UPDATE participant_meta SET last_wall=? WHERE singleton=1",
                               (max(now, meta["last_wall"]),))
            instance = meta["instance"]
            connection.commit()

            connection.execute("BEGIN IMMEDIATE")
            state, head, count = self.workshop._verify(connection)
            meta = connection.execute("SELECT * FROM participant_meta WHERE singleton=1").fetchone()
            if (not meta or meta["version"] != STORAGE_VERSION or state["schema"] != 2
                    or meta["instance"] != instance):
                raise Refused(503, "BOUNDARY_UNAVAILABLE")
            # Observe again after acquiring the operation lock: waiting must not
            # authorize an already expired capability using the earlier time.
            now = self._now()
            if now < meta["last_wall"] and not allow_rollback:
                raise Refused(503, "CLOCK_ROLLBACK")
            connection.execute("UPDATE participant_meta SET last_wall=? WHERE singleton=1",
                               (max(now, meta["last_wall"]),))
            connection.execute("SAVEPOINT participant_operation")
            try:
                yield connection, state, head, count, meta, now
            except BaseException:
                # Retain the second clock observation, but no failed operation
                # writes. If this cannot commit, propagate failure, never success.
                connection.execute("ROLLBACK TO participant_operation")
                connection.execute("RELEASE participant_operation")
                connection.commit()
                raise
            connection.execute("RELEASE participant_operation")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
