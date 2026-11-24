"""Bounded Linux Unix-socket transport for the change review database."""
from collections import Counter
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import sqlite3
import stat
import struct
import sys
import time

from ..engine import parse_json
from . import store


PACKET_BYTES = 64 * 1024
INFLIGHT = 32
PER_UID = 4
IDLE_SECONDS = 3
_PEER = struct.Struct("iII")


def _linux():
    if sys.platform != "linux":
        raise ValueError("change review service requires Linux")


def _directory(path, *, shared=False):
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError("expected absolute path without symlinks")
    info = path.parent.stat()
    forbidden = 0o027 if shared else 0o077
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & forbidden or not info.st_mode & stat.S_IXUSR):
        raise ValueError("ineligible parent ownership or permissions")
    if shared and info.st_gid != os.getegid():
        raise ValueError("socket directory must use the service group")
    return path


def _private_file(info):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and not info.st_mode & 0o077 and info.st_nlink == 1)


@contextmanager
def _lock(path):
    import fcntl

    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not _private_file(os.fstat(fd)):
            raise ValueError("ineligible lock file")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


@contextmanager
def exclusive_database(db):
    """Hold the service's nonblocking lifetime fence. Never unlink its lock file."""
    _linux()
    path = _directory(db)
    if path.name.lower().endswith(("-journal", "-wal", "-shm", ".service-lock", ".socket-lock")):
        raise ValueError("reserved database filename")
    with _lock(path.with_name("." + path.name + ".service-lock")):
        yield


def _uid(sock):
    data = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, _PEER.size)
    return _PEER.unpack(data)[1]


def _wire(value):
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(data) > PACKET_BYTES:
        raise ValueError("record exceeds packet size")
    return data


def _receive(sock):
    data, _, flags, _ = sock.recvmsg(PACKET_BYTES)
    if not data or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
        raise ValueError("incomplete packet")
    return parse_json(data.decode("utf-8"))


def _send(sock, value):
    data = _wire(value)
    if sock.send(data) != len(data):
        raise OSError("incomplete packet send")


def request(socket_path, payload):
    """Submit a single JSON record. A lost response can leave the write outcome unknown."""
    _linux()
    path = Path(socket_path)
    if (not path.is_absolute() or ".." in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError("expected absolute socket path without symlinks")
    parent, endpoint = path.parent.stat(), path.lstat()
    if (not stat.S_ISSOCK(endpoint.st_mode) or stat.S_IMODE(endpoint.st_mode) != 0o660
            or parent.st_uid != endpoint.st_uid or parent.st_gid != endpoint.st_gid
            or parent.st_mode & 0o027):
        raise ValueError("ineligible service endpoint")
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as conn:
        conn.settimeout(10)
        conn.connect(str(path))
        if _uid(conn) != endpoint.st_uid:
            raise ValueError("service UID differs from endpoint owner")
        try:
            _send(conn, payload)
        except BrokenPipeError:
            # A full admission queue can return a busy receipt immediately.
            pass
        reply = _receive(conn)
        if not isinstance(reply, dict) or type(reply.get("ok")) is not bool:
            raise ValueError("invalid service response")
        return reply


def _unlink_same(path, owned):
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if os.path.samestat(current, owned):
        path.unlink()


def _clear_stale(path):
    try:
        original = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(original.st_mode) or original.st_uid != os.geteuid():
        raise ValueError("socket path already occupied")
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as probe:
        probe.setblocking(False)
        if probe.connect_ex(str(path)) != errno.ECONNREFUSED:
            raise ValueError("socket endpoint already in use")
    _unlink_same(path, original)


@contextmanager
def _listener(path):
    # The endpoint and database have independent fences: another database may
    # have been configured with this same endpoint. The parent is owner-writable.
    with _lock(path.with_name("." + path.name + ".socket-lock")):
        _clear_stale(path)
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as server:
            server.bind(str(path))
            bound = path.lstat()
            try:
                os.chmod(path, 0o660)
                server.setblocking(False)
                server.listen(INFLIGHT)
                yield server
            finally:
                _unlink_same(path, bound)


def _roles(submitters, reviewers):
    submitters, reviewers = set(submitters), set(reviewers)
    ids = submitters | reviewers
    if (not submitters or not reviewers or submitters & reviewers or os.geteuid() in ids
            or any(type(uid) is not int or not 0 < uid < 2**32 - 1 for uid in ids)):
        raise ValueError("configure distinct non-root submitter, reviewer and service identities")
    return submitters, reviewers


def _error(code):
    return {"ok": False, "error": code}


def _dispatch(db, uid, submitters, reviewers, payload):
    if uid not in submitters and uid not in reviewers:
        return _error("permission_denied")
    if not isinstance(payload, dict) or not isinstance(payload.get("op"), str):
        return _error("invalid_request")
    if payload == {"op": "ready"}:
        # Check the live store. No records leave the health response.
        health = store.ready(db)
        return {"ok": True, "result": {"ready": True, "register_id": health["register_id"]}}
    if (payload["op"] == "submit" and uid not in submitters
            or payload["op"] == "decide" and uid not in reviewers):
        return _error("permission_denied")
    return {"ok": True, "result": store.handle(db, uid, uid in reviewers, payload)}


def _answer(conn, db, uid, submitters, reviewers):
    try:
        payload = _receive(conn)
        response = _dispatch(db, uid, submitters, reviewers, payload)
    except store.DomainError as exc:
        response = _error(exc.code)
    except (UnicodeError, ValueError, RecursionError):
        response = _error("invalid_request")
    except sqlite3.Error:
        response = _error("storage_unavailable")
    _send(conn, response)


def _run(server, db, submitters, reviewers, stopping):
    # Idle sockets never enter a blocking read. Limit pending clients per UID
    # as well as globally, and expire them even with no additional traffic.
    pending = {}
    counts = Counter()
    with selectors.DefaultSelector() as poll:
        poll.register(server, selectors.EVENT_READ)

        def close_client(conn):
            uid, _ = pending.pop(conn)
            counts[uid] -= 1
            if not counts[uid]:
                del counts[uid]
            poll.unregister(conn)
            conn.close()

        try:
            while not stopping():
                for event, _ in poll.select(0.2):
                    if stopping():
                        break
                    conn = event.fileobj
                    if conn is server:
                        try:
                            client, _ = server.accept()
                        except (BlockingIOError, ConnectionAbortedError):
                            continue
                        client.setblocking(False)
                        try:
                            uid = _uid(client)
                            if len(pending) >= INFLIGHT or counts[uid] >= PER_UID:
                                # No request has been consumed or committed.
                                _send(client, _error("busy"))
                                client.close()
                                continue
                            poll.register(client, selectors.EVENT_READ)
                            pending[client] = (uid, time.monotonic() + IDLE_SECONDS)
                            counts[uid] += 1
                        except OSError:
                            client.close()
                    else:
                        try:
                            _answer(conn, db, pending[conn][0], submitters, reviewers)
                        except OSError:
                            # Peer may have closed after submitting a durable action.
                            pass
                        finally:
                            close_client(conn)
                expired = [conn for conn, (_, until) in pending.items() if until <= time.monotonic()]
                for conn in expired:
                    close_client(conn)
        finally:
            for conn in list(pending):
                close_client(conn)


def serve(db, socket_path, submitters, reviewers):
    """Serve in the foreground; SIGTERM/SIGINT finish the current handler and stop."""
    _linux()
    if os.geteuid() == 0:
        raise ValueError("service requires an unprivileged dedicated UID")
    submitters, reviewers = _roles(submitters, reviewers)
    path = _directory(db)
    endpoint = _directory(socket_path, shared=True)
    with exclusive_database(path):
        if not _private_file(path.lstat()):
            raise ValueError("ineligible database ownership, links or permissions")
        store.verify(path)
        stopping = False

        def stop(_signum, _frame):
            nonlocal stopping
            stopping = True

        signals = (signal.SIGTERM, signal.SIGINT)
        previous = {s: signal.getsignal(s) for s in signals}
        try:
            for sig in signals:
                signal.signal(sig, stop)
            with _listener(endpoint) as server:
                _run(server, path, submitters, reviewers, lambda: stopping)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
