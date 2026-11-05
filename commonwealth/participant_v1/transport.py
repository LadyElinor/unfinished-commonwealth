"""Bounded loopback HTTP, with no redirects or automatic submission retries."""

import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
from urllib.parse import urlsplit

from ..engine import canonical, parse_json
from . import PROTOCOL
from .store import MAX_BODY, MAX_RESPONSE, REQUEST_ID, TOKEN, Refused, response


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = False

    def __init__(self, boundary, host="127.0.0.1", port=0):
        if host != "127.0.0.1" or type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("only literal 127.0.0.1 and a valid port are supported")
        self.boundary = boundary
        self.slots = threading.BoundedSemaphore(8)
        super().__init__((host, port), Handler)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Never dump request data, credentials or internal tracebacks to clients/logs.
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "CommonwealthParticipant/1"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self._send(code, response("HTTP_REFUSED"))

    def _send(self, status, payload):
        encoded = canonical(payload).encode("utf-8")
        if len(encoded) > MAX_RESPONSE:
            status, encoded = 503, canonical(response("RESPONSE_TOO_LARGE")).encode()
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def _header(self, name, required=True):
        values = self.headers.get_all(name, [])
        if (required and len(values) != 1) or len(values) > 1:
            raise Refused(400, "INVALID_HEADERS")
        return values[0] if values else None

    def _request(self):
        if len(self.path) > 160 or self.headers.get_all("Origin") or self.headers.get_all("Transfer-Encoding") or self.headers.get_all("Expect"):
            raise Refused(400, "INVALID_HEADERS")
        if self._header("Host") != f"127.0.0.1:{self.server.server_port}":
            raise Refused(400, "INVALID_HOST")
        authorization = self._header("Authorization")
        if len(authorization) > 128 or not authorization.startswith("Bearer "):
            raise Refused(401, "UNAUTHORIZED")
        token = authorization[7:]
        length = self._header("Content-Length", required=self.command == "POST")
        if self.command == "POST":
            if self.path != "/proposals":
                raise Refused(404, "NOT_FOUND")
            if self._header("Content-Type") != "application/json":
                raise Refused(415, "JSON_REQUIRED")
            if not length or not length.isascii() or not length.isdecimal() or len(length) > 8:
                raise Refused(400, "INVALID_LENGTH")
            if not 0 < int(length) <= MAX_BODY:
                raise Refused(413, "BODY_TOO_LARGE")
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                raise Refused(400, "TRUNCATED_BODY")
            return self.server.boundary.submit(token, raw)
        if length not in (None, "0"):
            raise Refused(400, "UNEXPECTED_BODY")
        if self.path == "/task":
            return self.server.boundary.task(token)
        if self.path.startswith("/receipts/") and REQUEST_ID.fullmatch(self.path[10:]):
            return self.server.boundary.receipt(token, self.path[10:])
        raise Refused(404, "NOT_FOUND")

    def _handle(self):
        try:
            status, payload = self._request()
        except Refused as exc:
            status, payload = exc.status, response(exc.code)
        except (OSError, ValueError):
            status, payload = 503, response("BOUNDARY_UNAVAILABLE")
        except Exception:
            status, payload = 503, response("BOUNDARY_UNAVAILABLE")
        try:
            self._send(status, payload)
        except (OSError, ValueError):
            pass

    do_GET = _handle
    do_POST = _handle


def request(url, token, method="GET", path="/task", raw=None, timeout=5):
    """One attempt only. A transport failure after POST has an UNKNOWN outcome."""
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise ValueError("invalid credential")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.netloc != f"127.0.0.1:{parsed.port}" or not parsed.port):
        raise ValueError("endpoint must be http://127.0.0.1:PORT")
    if method not in ("GET", "POST") or not (path == "/task" or path == "/proposals" or
            (path.startswith("/receipts/") and REQUEST_ID.fullmatch(path[10:]))):
        raise ValueError("unsupported participant route")
    if raw is not None and (not isinstance(raw, bytes) or len(raw) > MAX_BODY):
        raise ValueError("request body exceeds bound")
    connection = http.client.HTTPConnection("127.0.0.1", parsed.port, timeout=timeout)
    try:
        connection.request(method, path, body=raw, headers={"Authorization": f"Bearer {token}",
                           "Content-Type": "application/json", "Connection": "close"})
        incoming = connection.getresponse()
        body = incoming.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE or incoming.status in range(300, 400):
            raise ValueError("invalid or redirect response")
        if incoming.getheader("Content-Type") != "application/json":
            raise ValueError("invalid response type")
        payload = parse_json(body.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("protocol") != PROTOCOL:
            raise ValueError("invalid response protocol")
        return incoming.status, payload
    except (OSError, http.client.HTTPException, ValueError):
        return 0, response("UNKNOWN" if method == "POST" else "UNAVAILABLE",
                           resolution="Look up the original request ID or retry identical bytes; do not invent a new ID.")
    finally:
        connection.close()
