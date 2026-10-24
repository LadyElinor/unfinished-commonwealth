"""Transactional state and a replayable, hash-linked event journal.

Hashes detect accidental edits against the retained chain. A host controller can
rewrite the entire database and chain. This is not independent attestation.
"""

from contextlib import closing
from pathlib import Path
import sqlite3

from .engine import Rejected, canonical, digest, exact, initial_state, parse_json, transition
from .pipeline import scenarios


class CorruptJournal(ValueError):
    pass


class Workshop:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @classmethod
    def create(cls, path, scenario="missing"):
        fixtures = scenarios()
        if scenario not in fixtures:
            raise Rejected("unknown scenario")
        workshop = cls(path)
        workshop.path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: never truncate or reset somebody else's journal.
        with workshop.path.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(workshop.path)) as connection:
                connection.executescript("""
                    CREATE TABLE events (
                        seq INTEGER PRIMARY KEY,
                        envelope TEXT NOT NULL,
                        hash TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE snapshot (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        body TEXT NOT NULL
                    );
                """)
                state = initial_state(scenario, fixtures[scenario])
                envelope = {"seq": 0, "previous": "0" * 64,
                            "command": {"action": "init", "scenario": scenario,
                                        "fixture": fixtures[scenario]},
                            "result": {"scope": "LOCAL_RESEARCH"}, "state_hash": digest(state)}
                with connection:
                    connection.execute("INSERT INTO events VALUES (?, ?, ?)",
                                       (0, canonical(envelope), digest(envelope)))
                    connection.execute("INSERT INTO snapshot VALUES (1, ?)", (canonical(state),))
        except BaseException:
            workshop.path.unlink(missing_ok=True)
            raise
        return workshop

    def connect(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @staticmethod
    def _verify(connection):
        try:
            rows = connection.execute("SELECT seq, envelope, hash FROM events ORDER BY seq").fetchall()
            if not rows or len(rows) > 257:
                raise CorruptJournal("missing or over-budget journal")
            state = None
            previous = "0" * 64
            for index, (seq, raw, recorded_hash) in enumerate(rows):
                envelope = parse_json(raw)
                exact(envelope, ("seq", "previous", "command", "result", "state_hash"))
                if (type(envelope["seq"]) is not int or seq != index
                        or envelope["seq"] != index or envelope["previous"] != previous):
                    raise CorruptJournal("broken event sequence")
                if digest(envelope) != recorded_hash:
                    raise CorruptJournal("event hash mismatch")
                if index == 0:
                    command = envelope["command"]
                    exact(command, ("action", "scenario", "fixture"))
                    if command["action"] != "init":
                        raise CorruptJournal("missing genesis")
                    state = initial_state(command["scenario"], command["fixture"])
                    expected_result = {"scope": "LOCAL_RESEARCH"}
                else:
                    state, expected_result = transition(state, envelope["command"])
                # Python equality conflates JSON booleans and numbers (and
                # integer/float encodings); replay checks must preserve types.
                if (digest(state) != envelope["state_hash"]
                        or canonical(expected_result) != canonical(envelope["result"])):
                    raise CorruptJournal("event does not replay to its claimed result")
                previous = recorded_hash
            snapshot = connection.execute("SELECT body FROM snapshot WHERE singleton=1").fetchone()
            if snapshot is None or canonical(parse_json(snapshot[0])) != canonical(state):
                raise CorruptJournal("snapshot disagrees with journal replay")
            return state, previous, len(rows)
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            if isinstance(exc, CorruptJournal):
                raise
            raise CorruptJournal(f"invalid journal: {exc}") from exc

    def verify(self):
        with closing(self.connect()) as connection:
            connection.execute("BEGIN")
            state, head, count = self._verify(connection)
            return {"verified": True, "events": count, "head": head,
                    "generation": state["generation"], "external_authority": "NONE",
                    "assurance": "local deterministic replay; not authenticated history"}

    def state(self):
        with closing(self.connect()) as connection:
            connection.execute("BEGIN")
            return self._verify(connection)[0]

    def dispatch(self, command):
        with closing(self.connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                state, head, count = self._verify(connection)
                updated, result = transition(state, command)
                envelope = {"seq": count, "previous": head, "command": command,
                            "result": result, "state_hash": digest(updated)}
                connection.execute("INSERT INTO events VALUES (?, ?, ?)",
                                   (count, canonical(envelope), digest(envelope)))
                connection.execute("UPDATE snapshot SET body=? WHERE singleton=1", (canonical(updated),))
                connection.commit()
                return result
            except BaseException:
                connection.rollback()
                raise

    def events(self):
        with closing(self.connect()) as connection:
            connection.execute("BEGIN")
            self._verify(connection)
            return [parse_json(row[0]) for row in connection.execute("SELECT envelope FROM events ORDER BY seq")]
