"""O1 prerequisite regression gates, not deployment or real-workflow acceptance."""
from concurrent.futures import ThreadPoolExecutor
import copy
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

from commonwealth.engine import canonical
from commonwealth.store import Workshop
from commonwealth.participant_v1_1.store import Boundary
from commonwealth.participant_v1.store import read_credential
from commonwealth.operations_v1 import VERSION
from commonwealth.operations_v1.config import config, inspect, load
from commonwealth.operations_v1.app import Application


@unittest.skipUnless(os.name == 'posix' and os.geteuid() != 0, 'operational admission requires unprivileged POSIX identity')
class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / 'host.sqlite'
        Workshop.create(self.db)
        self.db.chmod(0o600)
        self.boundary = Boundary(self.db)
        self.boundary.install()
        self.cap = self.boundary.issue(self.root / 'credential', ttl=60)
        self.token = read_credential(self.root / 'credential')
        self.settings = dict(schema=VERSION, database=str(self.db), host='127.0.0.1', port=8765, max_inflight=2)
        self.app = Application(self.settings)

    def call(self, path='/task', method='GET', raw=b'', validated=True, **extra):
        env = {}
        setup_testing_defaults(env)
        env.update(REMOTE_ADDR='127.0.0.1', HTTP_HOST='127.0.0.1:8765', PATH_INFO=path,
                   REQUEST_METHOD=method, QUERY_STRING='', CONTENT_LENGTH=str(len(raw)),
                   CONTENT_TYPE='application/json', HTTP_AUTHORIZATION='Bearer ' + self.token)
        errors = StringIO()
        env['wsgi.input'], env['wsgi.errors'] = BytesIO(raw), errors
        env.update(extra)
        received = []
        iterator = (validator(self.app) if validated else self.app)(env, lambda status, headers: received.append((status, headers)))
        try:
            payload = b''.join(iterator)
        finally:
            if hasattr(iterator, 'close'):
                iterator.close()
        self.assertEqual(errors.getvalue(), '')
        self.assertNotIn(self.token.encode(), payload)
        return int(received[0][0][:3]), json.loads(payload)

    def packet(self):
        task = self.boundary.task(self.token)[1]
        return canonical(dict(protocol=task['protocol'], request_id='o1-request', view_head=task['view_head'], proposal=task['task']['proposal_example'])).encode()

    def test_preflight_read_only_and_never_production_ready(self):
        before = self.db.read_bytes()
        result = inspect(self.settings)
        self.assertTrue(result['operational_admission'])
        self.assertFalse(result['production_ready'])
        self.assertIn('real_workflow_not_implemented', result['blockers'])
        self.assertEqual(before, self.db.read_bytes())

    def test_strict_config_refuses_scope_expansion(self):
        for delta in ({'host':'0.0.0.0'}, {'port':True}, {'port':0}, {'max_inflight':9},
                      {'database':'relative.sqlite'}, {'schema':'old'}, {'production_ready':True}):
            with self.assertRaises(ValueError):
                config({**self.settings, **delta})

    def test_config_is_copied_and_bounded(self):
        settings = config(self.settings)
        self.settings['port'] = 99
        self.assertEqual(settings['port'],8765)
        path = self.root / 'config'
        path.write_text('x' * 4097)
        with self.assertRaises(ValueError):
            load(path)

    def test_missing_db_does_not_create(self):
        missing = self.root / 'absent.sqlite'
        result = inspect({**self.settings, 'database':str(missing)})
        self.assertFalse(result['operational_admission'])
        self.assertFalse(missing.exists())

    def test_world_readable_storage_refuses_without_repair(self):
        self.db.chmod(0o644)
        self.assertFalse(inspect(self.settings)['operational_admission'])
        with self.assertRaises(ValueError):
            Application(self.settings)
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o644)

    def test_root_service_admission_is_refused(self):
        with patch('commonwealth.operations_v1.config.os.geteuid',return_value=0):
            self.assertFalse(inspect(self.settings)['operational_admission'])

    def test_shared_parent_refuses_without_repair(self):
        self.root.chmod(0o755)
        self.assertFalse(inspect(self.settings)['operational_admission'])
        self.root.chmod(0o700)

    def test_symlink_refused(self):
        link = self.root / 'link.sqlite'
        link.symlink_to(self.db)
        self.assertFalse(inspect({**self.settings, 'database':str(link)})['operational_admission'])

    def test_readiness_detects_corruption_and_returns_no_paths(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE snapshot SET body='{}'")
        status, payload = self.call('/health/ready')
        self.assertEqual(status,503)
        self.assertFalse(payload['production_ready'])
        self.assertNotIn(str(self.db),canonical(payload))

    def test_clock_rollback_and_wrong_boundary_refuse(self):
        self.assertFalse(inspect(self.settings, clock=lambda:0)['operational_admission'])
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE participant_meta SET version='participant-1.0.0'")
        self.assertFalse(inspect(self.settings)['operational_admission'])

    def test_task_submit_retry_and_receipt_wsgi_contract(self):
        self.assertEqual(self.call()[0],200)
        raw = self.packet()
        first = self.call('/proposals','POST',raw)
        self.assertEqual(first[0],200)
        self.assertFalse(first[1]['permits_execution'])
        self.assertEqual(self.call('/proposals','POST',raw),first)
        self.assertEqual(self.call('/receipts/o1-request'),first)
        self.assertEqual(self.boundary.audit()['events'],2)

    def test_gateway_scope_and_framing_refusals(self):
        for extra in ({'REMOTE_ADDR':'8.8.8.8'}, {'HTTP_HOST':'evil'}, {'HTTP_ORIGIN':''},
                      {'HTTP_FORWARDED':'for=127.0.0.1'}, {'HTTP_X_FORWARDED_FOR':'127.0.0.1'},
                      {'HTTP_TRANSFER_ENCODING':'chunked'}, {'HTTP_EXPECT':'100-continue'},
                      {'SCRIPT_NAME':'/prefix'}, {'QUERY_STRING':'x=1'}, {'wsgi.url_scheme':'https'}):
            self.assertEqual(self.call(**extra)[0],400)
        self.assertEqual(self.call(CONTENT_LENGTH='1')[0],400)

    def test_invalid_bearer_refused_without_attempt(self):
        self.assertEqual(self.call(HTTP_AUTHORIZATION='Bearer nope')[0],401)
        self.assertEqual(self.boundary.audit()['capabilities'][0]['used'],0)

    def test_request_limits_and_routes(self):
        for length, expected in [('32769',413),('0',413),('-1',400),('1,1',400),('x',400)]:
            self.assertEqual(self.call('/proposals','POST',CONTENT_LENGTH=length,validated=False)[0],expected)
        self.assertEqual(self.call('/proposals','POST',b'x',CONTENT_LENGTH='2')[0],400)
        self.assertEqual(self.call('/proposals','POST',b'x',CONTENT_TYPE='text/plain')[0],415)
        self.assertEqual(self.call('/keeper')[0],404)
        self.assertEqual(self.call('/task','DELETE')[0],405)

    def test_failed_storage_returns_sanitized_unavailable(self):
        with patch.object(self.app.boundary,'submit',side_effect=sqlite3.OperationalError(self.token)):
            self.assertEqual(self.call('/proposals','POST',self.packet())[0],503)
        self.assertEqual(self.boundary.audit()['events'],1)

    def test_receipt_insert_failure_rolls_back_proposal(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TRIGGER full_receipts BEFORE INSERT ON participant_receipts BEGIN SELECT RAISE(ABORT,'disk full simulation'); END")
        self.assertEqual(self.call('/proposals','POST',self.packet())[0],503)
        self.assertEqual(self.boundary.audit()['events'],1)
        with sqlite3.connect(self.db) as db:
            db.execute('DROP TRIGGER full_receipts')
        self.assertEqual(self.call('/proposals','POST',self.packet())[0],200)

    def test_drain_refuses_new_requests_but_retains_inflight_result(self):
        entered, release = threading.Event(), threading.Event()
        original = self.app.boundary.task
        def delayed(token):
            entered.set()
            release.wait(5)
            return original(token)
        with patch.object(self.app.boundary,'task',side_effect=delayed), ThreadPoolExecutor() as pool:
            future = pool.submit(self.call)
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.app.drain(),{'active_operations':1,'accepting':False})
            self.assertEqual(self.call()[0],503)
            release.set()
            self.assertEqual(future.result()[0],200)
        self.assertEqual(self.app.active,0)

    def test_concurrency_limit_releases_after_exception(self):
        self.app.slots.acquire()
        self.app.slots.acquire()
        self.assertEqual(self.call()[0],503)
        self.app.slots.release()
        self.app.slots.release()
        with patch.object(self.app.boundary,'task',side_effect=RuntimeError('secret')):
            self.assertEqual(self.call()[0],503)
        self.assertEqual(self.call()[0],200)

    def test_separate_auth_clock_correction_still_applies(self):
        with patch.object(self.app.boundary,'clock',return_value=0):
            self.assertEqual(self.call()[1]['disposition'],'CLOCK_ROLLBACK')


    def test_real_loopback_test_gateway_compatibility(self):
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        from commonwealth.participant_v1.transport import request
        class Quiet(WSGIRequestHandler):
            def log_message(self, *args):
                pass
        server = make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        server.set_app(Application({**self.settings,'port':server.server_port}))
        thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01})
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(request(url,self.token)[0],200)
            self.assertEqual(request(url,self.token,'POST','/proposals',self.packet())[0],200)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(self.boundary.audit()['events'],2)


class PortableConfigTests(unittest.TestCase):
    def test_prior_runtime_and_evidence_are_unchanged(self):
        import hashlib
        root = Path(__file__).resolve().parents[1]
        record = json.loads((root / 'tests/data/operations-preserved-baseline.json').read_text())
        for name, expected in record['sha256'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected,name)


    def test_unsupported_platform_never_claims_admission(self):
        with patch('commonwealth.operations_v1.config.private_database',side_effect=ValueError('unsupported')):
            result = inspect(dict(schema=VERSION,database=str(Path('/db').absolute()),host='127.0.0.1',port=10,max_inflight=1))
        self.assertFalse(result['operational_admission'])
        self.assertFalse(result['production_ready'])

if __name__ == '__main__':
    unittest.main()
