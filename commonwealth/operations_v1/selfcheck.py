"""Synthetic installed-artifact check only; never a deployment acceptance test."""
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile

from ..store import Workshop
from ..participant_v1_1.store import Boundary
from ..participant_v1.store import read_credential, Refused
from . import VERSION
from .config import inspect
from .backup import backup_database, restore_database


def run():
    with tempfile.TemporaryDirectory(prefix='commonwealth-operations-') as t:
        root = Path(t).resolve()
        db = root / 'fixture.sqlite'
        Workshop.create(db)
        db.chmod(0o600)
        boundary = Boundary(db)
        boundary.install()
        boundary.issue(root / 'test-token',ttl=120)
        token = read_credential(root / 'test-token')
        settings = dict(schema=VERSION,database=str(db),host='127.0.0.1',port=8765,max_inflight=2)
        checked = inspect(settings)
        wsgi = 'NOT_RUN_UNSUPPORTED_IDENTITY_OR_PLATFORM'
        if os.name == 'posix' and os.geteuid() != 0:
            from .app import Application
            app = Application(settings)
            env = dict(REMOTE_ADDR='127.0.0.1',HTTP_HOST='127.0.0.1:8765',REQUEST_METHOD='GET',
                       PATH_INFO='/task',HTTP_AUTHORIZATION='Bearer '+token,CONTENT_LENGTH='')
            env['wsgi.url_scheme'],env['wsgi.input'] = 'http', BytesIO()
            status = []
            response = json.loads(b''.join(app(env,lambda s,h:status.append(s))))
            if status != ['200 OK'] or response['disposition'] != 'TASK' or not checked['operational_admission']:
                raise ValueError('installed WSGI prerequisite failed')
            if app.drain()['accepting']:
                raise ValueError('draining gate failed')
            wsgi = 'PASSED_SYNTHETIC_WSGI_CALL'
        snapshot = root / 'snapshot.sqlite'
        restored = root / 'restored.sqlite'
        backup_database(db,snapshot)
        recovery = restore_database(snapshot,restored)
        try:
            Boundary(restored).task(token)
        except Refused as exc:
            if exc.status != 401:
                raise
        else:
            raise ValueError('restored credential remained valid')
        if recovery['capabilities_revoked'] != 1:
            raise ValueError('restore accounting mismatch')
        return {'version':VERSION,'verified':True,'production_ready':False,'wsgi':wsgi,
                'restored_capabilities_revoked':1,'source_fencing_required':True,
                'scope':'SYNTHETIC_OPERATIONAL_PREREQUISITES','external_authority':'NONE'}
