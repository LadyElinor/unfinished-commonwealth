"""Single-attempt literal loopback client; no listener, redirects or retries.

Request implementation copied from B1 at 54199f7, with standalone wire imports.
"""
import http.client
from urllib.parse import urlsplit
from .wire import PROTOCOL, MAX_BODY, MAX_RESPONSE, REQUEST_ID, TOKEN, parse_json, response


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
