"""Verified, bounded SQLite copies for a trusted local operator.

Source connections are read-only. Publication uses an exclusive hard link from a
private same-directory staging file; unsupported filesystems fail closed. Restore
revokes every retained capability, but cannot fence the original host or clones.
Receipt instance IDs remain historical and unchanged. Not a power-loss guarantee.
"""
from contextlib import closing, contextmanager
import math
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import time

from ..participant_v1_1.store import Boundary
from ..participant_v1_1 import VERSION

MAX_DATABASE_BYTES = 128 * 1024 * 1024


def _path(value, *, source=False):
    path = Path(os.path.abspath(value))
    # resolve() alone would silently follow symlinks. Fail closed before opening.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlink paths are not supported")
    if not path.parent.is_dir():
        raise ValueError("parent directory must already exist")
    if source and not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("source must be a regular file")
    return path


def _connect(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1)
    db.execute('PRAGMA query_only=ON')
    return db


class _ReadOnlyBoundary(Boundary):
    @contextmanager
    def _transaction(self, allow_rollback=False):
        with closing(_connect(self.workshop.path)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            if (db.execute('PRAGMA page_count').fetchone()[0]
                    * db.execute('PRAGMA page_size').fetchone()[0] > MAX_DATABASE_BYTES):
                raise ValueError('database exceeds operational copy bound')
            if db.execute('PRAGMA quick_check(1)').fetchone()[0] != 'ok':
                raise ValueError('database integrity check failed')
            state, head, count = self.workshop._verify(db)
            meta = db.execute('SELECT * FROM participant_meta WHERE singleton=1').fetchone()
            if not meta or meta['version'] != VERSION or state['schema'] != 2:
                raise ValueError('only verified B1.1 databases are supported')
            if type(meta['last_wall']) is not int or not 0 <= meta['last_wall'] < 2**53:
                raise ValueError('invalid retained clock floor')
            yield db, state, head, count, meta, meta['last_wall']


def inspect_database(path):
    """Verify accounting and replay without advancing the source clock floor."""
    path = _path(path, source=True)
    if path.stat().st_size > MAX_DATABASE_BYTES:
        raise ValueError('database exceeds operational copy bound')
    return _ReadOnlyBoundary(path).audit()


def _copy(source, destination, *, restore, clock, timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError('timeout must be finite and in (0,60]')
    source, destination = _path(source, source=True), _path(destination)
    if destination.exists():
        raise FileExistsError('destination already exists')
    if source.stat().st_size > MAX_DATABASE_BYTES:
        raise ValueError('database exceeds operational copy bound')
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise TimeoutError('backup deadline exceeded')
        if total * page_size > MAX_DATABASE_BYTES:
            raise ValueError('database exceeds operational copy bound')

    descriptor, name = tempfile.mkstemp(prefix='.commonwealth-copy-', suffix='.sqlite', dir=destination.parent)
    staging = Path(name)
    os.close(descriptor)
    try:
        with closing(_connect(source)) as incoming, closing(sqlite3.connect(staging)) as outgoing:
            page_size = incoming.execute('PRAGMA page_size').fetchone()[0]
            incoming.backup(outgoing, pages=64, progress=progress, sleep=0.01)
        # Verify the actual consistent copied snapshot, not an earlier source view.
        before = inspect_database(staging)
        if restore:
            now = clock()
            if type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now < 2**53:
                raise ValueError('invalid restore clock')
            now = int(now)
            with closing(sqlite3.connect(staging)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                floor = db.execute('SELECT last_wall FROM participant_meta WHERE singleton=1').fetchone()[0]
                if now < floor:
                    raise ValueError('restore clock is behind retained floor')
                db.execute('UPDATE participant_caps SET revoked=1')
                db.execute('UPDATE participant_meta SET last_wall=? WHERE singleton=1', (now,))
            after = inspect_database(staging)
            if any(cap['revoked'] != 1 for cap in after['capabilities']):
                raise ValueError('restore did not invalidate every capability')
        else:
            after = before
        if time.monotonic() >= deadline:
            raise TimeoutError('copy verification deadline exceeded')
        # SQLite handles are closed; synchronize bytes before atomic publication.
        # Windows _commit requires a writable descriptor even with no pending writes.
        with staging.open('r+b') as handle:
            os.fsync(handle.fileno())
        # No replace/rename: concurrent existing destinations must be preserved.
        os.link(staging, destination)
        return {'operation': 'restore' if restore else 'backup', 'verified': True,
                'version': VERSION, 'instance': after['instance'], 'events': after['events'],
                'head': after['head'], 'receipts': after['receipts'],
                'capabilities_revoked': len(after['capabilities']) if restore else 0,
                'source_fencing_required': bool(restore), 'external_authority': 'NONE',
                'assurance': 'local verified snapshot; trusted storage; no independent attestation'}
    finally:
        # Only remove our private staging name, never a destination supplied by
        # another process. A crash may leave staging files for operator cleanup.
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass


def backup_database(source, destination, *, timeout=10):
    """Create a new verified snapshot. Never alter source or replace destination."""
    return _copy(source, destination, restore=False, clock=time.time, timeout=timeout)


def restore_database(source, destination, *, clock=time.time, timeout=10):
    """Create a new verified copy with all old bearers revoked, preserving receipts.

The original host must be stopped/fenced separately. Instance IDs are retained
because historical receipts bind them. No new credentials are issued here.
"""
    return _copy(source, destination, restore=True, clock=clock, timeout=timeout)
