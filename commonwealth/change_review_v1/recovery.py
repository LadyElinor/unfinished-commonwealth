"""Offline, create-only recovery for the Linux change-review recording service.

Only the operator should have access to the two private directories. The service
fence excludes cooperating processes on these paths, not other copies or hosts.
"""
from contextlib import closing
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import time

from . import store


COPY_SECONDS = 60


class PublicationUnconfirmed(OSError):
    """Destination was published, but directory synchronization failed."""


def _check_time(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("change-review copy deadline exceeded")


def _snapshot(source, staging, deadline):
    uri = source.as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=1)) as incoming:
        incoming.execute("PRAGMA query_only=ON")
        page_size = incoming.execute("PRAGMA page_size").fetchone()[0]

        def progress(status, remaining, total):
            _check_time(deadline)
            if total * page_size > store.MAX_DATABASE_BYTES:
                raise ValueError("snapshot exceeds the database limit")

        with closing(sqlite3.connect(staging)) as outgoing:
            incoming.backup(outgoing, pages=64, progress=progress, sleep=.01)
            # Require a standalone, closed snapshot for publication.
            if outgoing.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                raise ValueError("snapshot is not standalone")


def _restore_bytes(source, staging, deadline):
    with source.open("rb") as incoming, staging.open("wb") as outgoing:
        copied = 0
        while chunk := incoming.read(1024 * 1024):
            _check_time(deadline)
            copied += len(chunk)
            if copied > store.MAX_DATABASE_BYTES:
                raise ValueError("snapshot exceeds the database limit")
            outgoing.write(chunk)


def _has_sidecars(path):
    return any(os.path.lexists(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm"))


def publish_new_file(staging, destination):
    """Atomically publish a synced private staging file in its own directory."""
    if staging.parent != destination.parent:
        raise ValueError("staging and destination must share a directory")
    # renameat2 with RENAME_NOREPLACE atomically moves a single name. A crash
    # cannot strand a second hard link that would fail private-storage admission.
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    directory_fd = os.open(destination.parent, os.O_DIRECTORY | os.O_RDONLY)
    try:
        if rename(directory_fd, os.fsencode(staging.name),
                  directory_fd, os.fsencode(destination.name), 1):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            raise PublicationUnconfirmed("published_durability_unconfirmed") from exc
    finally:
        os.close(directory_fd)


def _copy(source, destination, operation, expected_sha256=None):
    if sys.platform != "linux":
        raise OSError(errno.ENOTSUP, "change-review recovery requires Linux")
    from .service import exclusive_database

    source, destination = Path(source), Path(destination)
    if source == destination:
        raise ValueError("source and destination must differ")
    if expected_sha256 is not None and not re.fullmatch("[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    deadline = time.monotonic() + COPY_SECONDS
    with exclusive_database(source), exclusive_database(destination):
        info = source.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise ValueError("source must be a private, single-link regular file")
        if info.st_size > store.MAX_DATABASE_BYTES:
            raise ValueError("source exceeds the database limit")
        if os.path.lexists(destination) or _has_sidecars(destination):
            raise FileExistsError("destination or SQLite sidecar already exists")
        if operation == "restore" and _has_sidecars(source):
            raise ValueError("restore requires a standalone snapshot")
        fd, name = tempfile.mkstemp(prefix=".change-review-copy-", dir=destination.parent)
        os.close(fd)
        staging = Path(name)
        try:
            if operation == "backup":
                _snapshot(source, staging, deadline)
            else:
                _restore_bytes(source, staging, deadline)
            with staging.open("rb") as copied:
                digest = hashlib.file_digest(copied, "sha256").hexdigest()
            if expected_sha256 is not None and expected_sha256 != digest:
                raise ValueError("snapshot digest differs from retained digest")
            report = store.verify(staging)
            if _has_sidecars(staging):
                raise ValueError("verified copy is not standalone")
            _check_time(deadline)
            size = staging.stat().st_size
            with staging.open("rb") as copied:
                os.fsync(copied.fileno())
            publish_new_file(staging, destination)
            return {**report, "operation": operation, "completed_at": int(time.time()),
                    "bytes": size, "sha256": digest}
        finally:
            staging.unlink(missing_ok=True)


def backup(source, destination):
    """Create a verified snapshot while both paths are exclusively fenced."""
    return _copy(source, destination, "backup")


def restore(source, destination, *, expected_sha256=None):
    """Restore a standalone snapshot into a fresh file in a private directory."""
    return _copy(source, destination, "restore", expected_sha256)
