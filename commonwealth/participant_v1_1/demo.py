"""One exposed B1.1 loopback and clock-refusal check, not OS isolation evidence."""

from pathlib import Path
import tempfile
import threading

from ..engine import canonical
from ..store import Workshop
from ..participant_v1 import PROTOCOL
from ..participant_v1.store import Refused, read_credential
from ..participant_v1.transport import Server, request
from . import VERSION
from .store import Boundary


def run():
    with tempfile.TemporaryDirectory(prefix="commonwealth-b11-") as temporary:
        root = Path(temporary)
        workshop = Workshop.create(root / "workshop.sqlite")
        clock = [1000]
        boundary = Boundary(workshop.path, clock=lambda: clock[0])
        boundary.install()
        boundary.issue(root / "token", ttl=60)
        token = read_credential(root / "token")
        server = Server(boundary)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            status, task = request(server.url, token)
            if status != 200:
                raise RuntimeError("task failed")
            raw = canonical({"protocol": PROTOCOL, "request_id": "b11-demo",
                             "view_head": task["view_head"],
                             "proposal": task["task"]["proposal_example"]}).encode()
            first = request(server.url, token, "POST", "/proposals", raw)
            if first[0] != 200 or request(server.url, token, "POST", "/proposals", raw) != first:
                raise RuntimeError("idempotent proposal failed")
            clock[0] = 1061
            if request(server.url, token)[1]["disposition"] != "UNAUTHORIZED":
                raise RuntimeError("expired token accepted")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        clock[0] = 1050
        restarted = Boundary(workshop.path, clock=lambda: clock[0])
        try:
            restarted.task(token)
        except Refused as exc:
            if exc.code != "CLOCK_ROLLBACK":
                raise RuntimeError("unexpected rollback refusal") from exc
        else:
            raise RuntimeError("expired bearer revived")
        audit = restarted.audit()
        if audit["capabilities"][0]["used"] != 1 or audit["events"] != 2:
            raise RuntimeError("accounting changed")
        return {"version": VERSION, "verified": True, "expiry_refusal_retained": True,
                "restart_rollback_refused": True, "proposals": 1, "attempts": 1,
                "model_calls": 0, "external_actions": 0,
                "scope": "LOCAL_RESEARCH_ONLY", "clock": "injected", "os_isolation": "NOT_TESTED"}
