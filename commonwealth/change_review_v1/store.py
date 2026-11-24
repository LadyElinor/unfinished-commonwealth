"""SQLite records for the change review service. Identity comes from the transport."""
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import time
import unicodedata
import uuid

from ..engine import canonical, digest
from . import VERSION

MAX_RECORDS = 10_000
MAX_DATABASE_BYTES = 128 * 1024 * 1024
APPLICATION_ID = 0x43575231
MAX_UID = 2**32 - 2  # Linux reserves (uid_t)-1.
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")

SCHEMA = {
    "registry": """CREATE TABLE registry (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), register_id TEXT NOT NULL)""",
    "proposals": """CREATE TABLE proposals (
        seq INTEGER PRIMARY KEY CHECK(seq > 0),
        id TEXT NOT NULL, owner_uid INTEGER NOT NULL, title TEXT NOT NULL,
        proposal TEXT NOT NULL, evidence TEXT NOT NULL, submitted_at INTEGER NOT NULL,
        submission_digest TEXT NOT NULL, UNIQUE(owner_uid,id))""",
    "proposal_ids": "CREATE INDEX proposal_ids ON proposals(id)",
    "decisions": """CREATE TABLE decisions (
        proposal_seq INTEGER PRIMARY KEY REFERENCES proposals(seq),
        reviewer_uid INTEGER NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('approve','decline')),
        rationale TEXT NOT NULL, decided_at INTEGER NOT NULL, decision_digest TEXT NOT NULL)""",
}
for table in ("registry", "proposals", "decisions"):
    for action in ("UPDATE", "DELETE"):
        name = f"immutable_{table}_{action.lower()}"
        SCHEMA[name] = (f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN "
                        "SELECT RAISE(ABORT, 'immutable record'); END")

SELECT_RECORD = """
    SELECT p.*, r.register_id, d.reviewer_uid, d.decision, d.rationale, d.decided_at, d.decision_digest
    FROM proposals p JOIN registry r ON r.singleton=1 LEFT JOIN decisions d ON d.proposal_seq = p.seq
"""


class DomainError(ValueError):
    """Stable, content-free application failure for the local client."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() <= set(required) | set(optional):
        raise DomainError("invalid_request")


def _text(value, maximum, multiline=False):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(unicodedata.category(ch) in {"Cc", "Cf", "Cs"} and
                   not (multiline and ch in "\t\n") for ch in value)
            or len(value.encode("utf8")) > maximum):
        raise DomainError("invalid_request")


def _submission(request):
    ident = request["id"]
    if not isinstance(ident, str) or not SLUG.fullmatch(ident):
        raise DomainError("invalid_request")
    _text(request["title"], 160)
    _text(request["proposal"], 2048, multiline=True)
    evidence = request["evidence"]
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 4:
        raise DomainError("invalid_request")
    for citation in evidence:
        _text(citation, 256)


def _valid_decision(record):
    if record["decision"] not in ("approve", "decline"):
        raise DomainError("invalid_request")
    _text(record["rationale"], 1024, multiline=True)


def _register(db):
    row = db.execute("SELECT register_id FROM registry WHERE singleton=1").fetchone()
    if (row is None or not isinstance(row[0], str)
            or not re.fullmatch(r"[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}", row[0])):
        raise DomainError("invalid_store")
    return row[0]


def _schema(db):
    if (db.execute("PRAGMA journal_mode").fetchone()[0] != "delete"
            or db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or db.execute("PRAGMA user_version").fetchone()[0] != 1
            or dict(db.execute("SELECT name,sql FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*'")) != SCHEMA):
        raise DomainError("invalid_store")
    _register(db)


def _database_error(exc):
    code = getattr(exc, "sqlite_errorcode", 0) or 0
    return DomainError({sqlite3.SQLITE_BUSY: "store_busy", sqlite3.SQLITE_LOCKED: "store_busy",
                        sqlite3.SQLITE_FULL: "storage_full", sqlite3.SQLITE_NOTADB: "invalid_store",
                        sqlite3.SQLITE_CORRUPT: "invalid_store"}.get(code & 255, "store_unavailable"))


def _private_parent(path):
    if os.name != "posix":
        return
    st = path.parent.stat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077 or st.st_uid != os.geteuid()
            or any(parent.is_symlink() for parent in path.parents)):
        raise DomainError("invalid_store")


@contextmanager
def _transaction(path, *, writing=False):
    path = Path(path).absolute()
    try:
        _private_parent(path)
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_DATABASE_BYTES or
                (os.name == "posix" and (st.st_mode & 0o077 or st.st_uid != os.geteuid()))):
            raise DomainError("invalid_store")
        uri = path.as_uri() + ("?mode=rw" if writing else "?mode=ro")
        with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA foreign_keys=ON")
            if writing:
                db.execute("PRAGMA synchronous=FULL")
                page_size = db.execute("PRAGMA page_size").fetchone()[0]
                db.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}")
            else:
                db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
            _schema(db)
            yield db
            db.commit()
    except sqlite3.Error as exc:
        raise _database_error(exc) from exc
    except OSError as exc:
        raise DomainError("store_unavailable") from exc


def initialize(path):
    """Publish a complete, private database under a previously unused name."""
    destination = Path(path).absolute()
    stage = None
    try:
        _private_parent(destination)
        fd, stage = tempfile.mkstemp(prefix=".change-review-", suffix=".sqlite", dir=destination.parent)
        os.close(fd)
        with closing(sqlite3.connect(stage)) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA.values():
                db.execute(statement)
            db.execute("INSERT INTO registry VALUES (1,?)", (uuid.uuid4().hex,))
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute("PRAGMA user_version=1")
        report = verify(stage)
        with open(stage, "r+b") as file:
            os.fsync(file.fileno())
        if sys.platform.startswith("linux"):
            # Recovery and initialization use the same durable no-replace publication.
            from .recovery import PublicationUnconfirmed, publish_new_file
            try:
                publish_new_file(Path(stage), destination)
            except PublicationUnconfirmed as exc:
                raise DomainError("publication_unconfirmed") from exc
        else:
            os.link(stage, destination)
            os.unlink(stage)
            if os.name == "posix":
                directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                except OSError as exc:
                    raise DomainError("publication_unconfirmed") from exc
                finally:
                    os.close(directory)
        return report
    except FileExistsError as exc:
        raise DomainError("already_exists") from exc
    except sqlite3.Error as exc:
        raise _database_error(exc) from exc
    except OSError as exc:
        raise DomainError("store_unavailable") from exc
    finally:
        if stage is not None:
            Path(stage).unlink(missing_ok=True)


def _fingerprint(kind, fields):
    return digest({"schema": VERSION, "kind": kind, "fields": fields})


def _record(row):
    """Decode and check both content digests before exposing a full record."""
    fields = {key: row[key] for key in ("register_id", "seq", "id", "owner_uid", "title", "proposal", "submitted_at")}
    try:
        fields["evidence"] = json.loads(row["evidence"])
        _submission(fields)
        if (not _integer(fields["owner_uid"], 0, MAX_UID) or not _integer(fields["seq"], 1, MAX_RECORDS)
                or not _integer(fields["submitted_at"], 0, 2**63 - 1)
                or _fingerprint("submission", fields) != row["submission_digest"]):
            raise DomainError("invalid_store")
        fields["submission_digest"] = row["submission_digest"]
        record = {**fields, "decision": None}
        if row["decision"] is not None:
            choice = {key: row[key] for key in ("reviewer_uid", "decision", "rationale", "decided_at")}
            _valid_decision(choice)
            expected = _fingerprint("decision", {**choice, "submission_digest": row["submission_digest"]})
            if (not _integer(choice["reviewer_uid"], 0, MAX_UID) or choice["reviewer_uid"] == fields["owner_uid"]
                    or not _integer(choice["decided_at"], fields["submitted_at"], 2**63 - 1)
                    or expected != row["decision_digest"]):
                raise DomainError("invalid_store")
            record["decision"] = {**choice, "decision_digest": expected}
        return record
    except (ValueError, TypeError, RecursionError) as exc:
        raise DomainError("invalid_store") from exc


def ready(path):
    """Read schema and one index entry in a local read-only transaction."""
    with _transaction(path) as db:
        db.execute("SELECT seq FROM proposals ORDER BY seq LIMIT 1").fetchone()
        return {"ok": True, "schema": VERSION, "register_id": _register(db)}


def verify(path):
    """Check the full schema, every immutable receipt and all foreign keys in a read snapshot."""
    with _transaction(path) as db:
        if (db.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok"
                or db.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise DomainError("invalid_store")
        count = decisions = 0
        for row in db.execute(SELECT_RECORD + " ORDER BY p.seq"):
            record = _record(row)
            count += 1
            decisions += record["decision"] is not None
            if record["seq"] != count:
                raise DomainError("invalid_store")
        return {"ok": True, "records": count, "decisions": decisions, "schema": VERSION, "register_id": _register(db)}


def _expect_register(db, request):
    expected = request["register_id"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{32}", expected):
        raise DomainError("invalid_request")
    if _register(db) != expected:
        raise DomainError("register_mismatch")
    return expected


def _submit(db, uid, request):
    _fields(request, ("op", "id", "title", "proposal", "evidence", "register_id"))
    register_id = _expect_register(db, request)
    _submission(request)
    row = db.execute(SELECT_RECORD + " WHERE p.owner_uid=? AND p.id=?", (uid, request["id"])).fetchone()
    if row is not None:
        record = _record(row)
        if any(record[key] != request[key] for key in ("title", "proposal", "evidence")):
            raise DomainError("id_conflict")
        return {"record": {**record, "decision": None}}
    seq = db.execute("SELECT coalesce(max(seq),0)+1 FROM proposals").fetchone()[0]
    if seq > MAX_RECORDS:
        raise DomainError("capacity_reached")
    fields = {key: request[key] for key in ("id", "title", "proposal", "evidence")}
    now = int(time.time())
    if not _integer(now, 0, 2**63 - 1):
        raise DomainError("clock_regression")
    fields.update(register_id=register_id, seq=seq, owner_uid=uid, submitted_at=now)
    stamp = _fingerprint("submission", fields)
    db.execute("""INSERT INTO proposals (seq,id,owner_uid,title,proposal,evidence,submitted_at,submission_digest)
                  VALUES (:seq,:id,:owner_uid,:title,:proposal,:evidence,:submitted_at,:stamp)""",
               {**fields, "evidence": canonical(fields["evidence"]), "stamp": stamp})
    return {"record": {**fields, "submission_digest": stamp, "decision": None}}


def _lookup(db, uid, reviewer, request):
    ident = request["id"]
    if not isinstance(ident, str) or not SLUG.fullmatch(ident):
        raise DomainError("invalid_request")
    owner = request.get("owner_uid")
    if "owner_uid" in request and not _integer(owner, 0, MAX_UID):
        raise DomainError("invalid_request")
    if not reviewer and owner is not None and owner != uid:
        raise DomainError("not_found")
    if not reviewer:
        owner = uid
    if owner is None:
        rows = db.execute(SELECT_RECORD + " WHERE p.id=? LIMIT 2", (ident,)).fetchall()
        if len(rows) > 1:
            raise DomainError("ambiguous_id")
    else:
        rows = db.execute(SELECT_RECORD + " WHERE p.id=? AND p.owner_uid=?", (ident, owner)).fetchall()
    if not rows:
        raise DomainError("not_found")
    return _record(rows[0])


def _decide(db, uid, request, record):
    expected = request["submission_digest"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise DomainError("invalid_request")
    if expected != record["submission_digest"]:
        raise DomainError("submission_mismatch")
    if record["owner_uid"] == uid:
        raise DomainError("self_review")
    _valid_decision(request)
    choice = {"reviewer_uid": uid, "decision": request["decision"], "rationale": request["rationale"]}
    previous = record["decision"]
    if previous is not None:
        if any(previous[key] != value for key, value in choice.items()):
            raise DomainError("decision_conflict")
        return {"record": record}
    choice["decided_at"] = int(time.time())
    if choice["decided_at"] < record["submitted_at"]:
        raise DomainError("clock_regression")
    choice["decision_digest"] = _fingerprint("decision", {**choice, "submission_digest": record["submission_digest"]})
    db.execute("""INSERT INTO decisions (proposal_seq,reviewer_uid,decision,rationale,decided_at,decision_digest)
                  VALUES (:seq,:reviewer_uid,:decision,:rationale,:decided_at,:decision_digest)""",
               {**choice, "seq": record["seq"]})
    return {"record": {**record, "decision": choice}}


def _list(db, request):
    _fields(request, ("op",), ("after", "limit"))
    after, limit = request.get("after", 0), request.get("limit", 20)
    if not _integer(after, 0, MAX_RECORDS) or not _integer(limit, 1, 32):
        raise DomainError("invalid_request")
    rows = db.execute(SELECT_RECORD + " WHERE p.seq>? ORDER BY p.seq LIMIT ?", (after, limit + 1)).fetchall()
    items = []
    for row in rows[:limit]:
        record = _record(row)
        item = {key: record[key] for key in ("seq", "id", "owner_uid", "title")}
        item["state"] = record["decision"]["decision"] if record["decision"] is not None else "pending"
        items.append(item)
    return {"register_id": _register(db), "items": items,
            "next_after": items[-1]["seq"] if len(rows) > limit else None}


def handle(path, uid, reviewer, request):
    """The service supplies authenticated uid/role independently of the request."""
    if not _integer(uid, 0, MAX_UID) or type(reviewer) is not bool or not isinstance(request, dict):
        raise DomainError("invalid_request")
    op = request.get("op")
    if op not in ("submit", "get", "decide", "list"):
        raise DomainError("invalid_request")
    if op in ("decide", "list") and not reviewer:
        raise DomainError("forbidden")
    with _transaction(path, writing=op in ("submit", "decide")) as db:
        if op == "submit":
            return _submit(db, uid, request)
        if op == "list":
            return _list(db, request)
        extra = ("decision", "rationale", "register_id", "submission_digest") if op == "decide" else ()
        _fields(request, ("op", "id", *extra), ("owner_uid",))
        if op == "decide":
            _expect_register(db, request)
        record = _lookup(db, uid, reviewer, request)
        return _decide(db, uid, request, record) if op == "decide" else {"record": record}
