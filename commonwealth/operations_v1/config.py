"""Strict, non-mutating configuration and local readiness inspection."""
from contextlib import closing, contextmanager
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

from ..measurement_v1 import OPERATOR_LIMIT
from ..engine import exact, parse_json
from ..participant_v1_1 import VERSION as BOUNDARY_VERSION
from ..participant_v1_1.store import Boundary
from . import VERSION

BLOCKERS = ["real_workflow_not_implemented", "production_gateway_not_selected_or_tested",
            "deployment_access_policy_not_verified", "load_and_recovery_acceptance_not_observed"]


def config(value):
    exact(value, ("schema", "database", "host", "port", "max_inflight"))
    if (value['schema'] != VERSION or value['host'] != '127.0.0.1'
            or type(value['port']) is not int or not 1 <= value['port'] <= 65535
            or type(value['max_inflight']) is not int or not 1 <= value['max_inflight'] <= 8
            or not isinstance(value['database'], str) or not value['database']
            or not Path(value['database']).is_absolute()):
        raise ValueError('invalid operational configuration')
    # Copy prevents caller mutation of the admitted configuration.
    return dict(value)


def load(path):
    with Path(path).open('rb') as source:
        raw = source.read(4097)
    if len(raw) > 4096:
        raise ValueError('configuration too large')
    return config(parse_json(raw.decode('utf-8')))


def private_database(path):
    """Check, never repair, POSIX owner-only file and immediate parent."""
    if os.name != 'posix' or os.geteuid() == 0:
        raise ValueError('unprivileged POSIX permission admission required')
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('absolute non-symlink path required')
    for candidate, directory in ((path, False), (path.parent, True)):
        s = candidate.stat()
        if (s.st_uid != os.geteuid() or s.st_mode & 0o077
                or (not stat.S_ISDIR(s.st_mode) if directory else not stat.S_ISREG(s.st_mode))):
            raise ValueError('private owner-only storage required')
    return path


class ReadOnlyBoundary(Boundary):
    @contextmanager
    def _transaction(self, allow_rollback=False):
        # Reuse frozen audit checks inside a genuine read-only snapshot. No clock
        # update, auth, proposal, or startup migration occurs during inspection.
        with closing(sqlite3.connect(self.workshop.path.as_uri() + '?mode=ro', uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            if (db.execute('PRAGMA page_count').fetchone()[0] * db.execute('PRAGMA page_size').fetchone()[0] > 128 * 1024 * 1024
                    or db.execute('PRAGMA quick_check(1)').fetchone()[0] != 'ok'):
                raise ValueError('storage admission bound or integrity failure')
            state, head, count = self.workshop._verify(db)
            meta = db.execute('SELECT * FROM participant_meta WHERE singleton=1').fetchone()
            now = self.clock()
            if (type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now < 2**53
                    or not meta or meta['version'] != BOUNDARY_VERSION or state['schema'] != 2
                    or int(now) < meta['last_wall']):
                raise ValueError('invalid boundary or clock')
            yield db, state, head, count, meta, int(now)


def inspect(value, clock=time.time):
    """Operational prerequisites only; production readiness remains blocked."""
    result = {'version': VERSION, 'operational_admission': False, 'production_ready': False,
              'blockers': list(BLOCKERS), 'external_authority': 'NONE', 'operator_limit': OPERATOR_LIMIT}
    try:
        value = config(value)
        path = private_database(value['database'])
        result['boundary'] = ReadOnlyBoundary(path, clock=clock).audit()['version']
        result['operational_admission'] = True
        result['status'] = 'LOCAL_PREREQUISITES_VERIFIED'
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        result['status'] = 'LOCAL_PREREQUISITES_REFUSED'
    return result
