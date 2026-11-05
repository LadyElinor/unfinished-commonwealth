"""WSGI adapter for B1.1, requiring an externally managed trusted gateway.

No listener or deployment settings are installed. WSGI cannot inspect raw
ambiguous HTTP framing or enforce socket deadlines: those remain gateway gates.
"""
from http import HTTPStatus
import sqlite3
import threading

from ..engine import canonical
from ..participant_v1.store import MAX_BODY, MAX_RESPONSE, REQUEST_ID, TOKEN, Refused, response
from ..participant_v1_1.store import Boundary
from .config import config, inspect, private_database


class Application:
    def __init__(self, settings):
        self.settings = config(settings)
        if not inspect(self.settings)['operational_admission']:
            raise ValueError('operational prerequisites refused')
        self.boundary = Boundary(self.settings['database'])
        self.slots = threading.BoundedSemaphore(self.settings['max_inflight'])
        self.draining = threading.Event()
        self.lock = threading.Lock()
        self.active = 0

    def drain(self):
        """Refuse new calls; count routing operations, not undelivered responses.

        Gateway owns response draining, waiting, signals and shutdown.
        """
        with self.lock:
            self.draining.set()
            return {'active_operations': self.active, 'accepting': False}

    def _route(self, env):
        if (env.get('REMOTE_ADDR') != '127.0.0.1'
                or env.get('HTTP_HOST') != f"127.0.0.1:{self.settings['port']}"
                or env.get('wsgi.url_scheme') != 'http' or env.get('SCRIPT_NAME', '')
                or env.get('QUERY_STRING', '')
                or any(k in env for k in ('HTTP_ORIGIN', 'HTTP_TRANSFER_ENCODING', 'HTTP_EXPECT',
                                          'HTTP_FORWARDED', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST',
                                          'HTTP_X_FORWARDED_PROTO'))):
            raise Refused(400, 'INVALID_GATEWAY_REQUEST')
        method, path = env.get('REQUEST_METHOD'), env.get('PATH_INFO', '')
        if not isinstance(path, str) or len(path) > 160 or method not in ('GET', 'POST'):
            raise Refused(405, 'METHOD_OR_ROUTE_REFUSED')
        length = env.get('CONTENT_LENGTH', '')
        if method == 'GET' and length not in ('', '0'):
            raise Refused(400, 'UNEXPECTED_BODY')
        if method == 'GET' and path == '/health/ready':
            ready = inspect(self.settings)
            return (200 if ready['operational_admission'] else 503), ready
        authorization = env.get('HTTP_AUTHORIZATION', '')
        if not isinstance(authorization, str) or not authorization.startswith('Bearer ') or not TOKEN.fullmatch(authorization[7:]):
            raise Refused(401, 'UNAUTHORIZED')
        token = authorization[7:]
        # Recheck path admission on each request; not a defense against the owner
        # replacing files concurrently. Filesystem protection is external.
        private_database(self.settings['database'])
        if method == 'POST':
            if path != '/proposals':
                raise Refused(404, 'NOT_FOUND')
            if env.get('CONTENT_TYPE') != 'application/json':
                raise Refused(415, 'JSON_REQUIRED')
            if not isinstance(length, str) or not length.isascii() or not length.isdecimal() or len(length) > 8:
                raise Refused(400, 'INVALID_LENGTH')
            if not 0 < int(length) <= MAX_BODY:
                raise Refused(413, 'BODY_TOO_LARGE')
            raw = env['wsgi.input'].read(int(length))
            if not isinstance(raw, bytes) or len(raw) != int(length):
                raise Refused(400, 'TRUNCATED_BODY')
            return self.boundary.submit(token, raw)
        if path == '/task':
            return self.boundary.task(token)
        if path.startswith('/receipts/') and REQUEST_ID.fullmatch(path[10:]):
            return self.boundary.receipt(token, path[10:])
        raise Refused(404, 'NOT_FOUND')

    def __call__(self, environ, start_response):
        admitted = False
        with self.lock:
            if not self.draining.is_set() and self.slots.acquire(blocking=False):
                self.active += 1
                admitted = True
        if not admitted:
            status, payload = 503, response('SERVICE_UNAVAILABLE')
        else:
            try:
                status, payload = self._route(environ)
            except Refused as exc:
                status, payload = exc.status, response(exc.code)
            except Exception:
                # No request bodies, capabilities, paths or exception details in
                # the application response/log. Gateway logs need separate policy.
                status, payload = 503, response('BOUNDARY_UNAVAILABLE')
            finally:
                with self.lock:
                    self.active -= 1
                    self.slots.release()
        raw = canonical(payload).encode('utf-8')
        if len(raw) > MAX_RESPONSE:
            status, raw = 503, canonical(response('RESPONSE_TOO_LARGE')).encode()
        start_response(f'{status} {HTTPStatus(status).phrase}',
                       [('Content-Type', 'application/json'), ('Content-Length', str(len(raw))),
                        ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])
        return [raw]


def create_app(config_path):
    from .config import load
    return Application(load(config_path))
