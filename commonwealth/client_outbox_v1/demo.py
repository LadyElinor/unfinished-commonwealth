"""Exposed C1 recovery smoke test on a corrected B1.1 host."""

from pathlib import Path
import tempfile
import threading
from unittest.mock import patch

from ..engine import canonical
from ..store import Workshop
from ..participant_v1 import PROTOCOL
from ..participant_v1.store import read_credential
from ..participant_v1.transport import Server, Handler
from ..participant_v1_1.store import Boundary
from . import VERSION
from .store import Outbox


def run():
    with tempfile.TemporaryDirectory(prefix="commonwealth-c1-") as temporary:
        root = Path(temporary)
        workshop = Workshop.create(root / "workshop.sqlite")
        boundary = Boundary(workshop.path)
        boundary.install()
        boundary.issue(root / "token")
        token = read_credential(root / "token")
        task = boundary.task(token)[1]
        raw = canonical({"protocol": PROTOCOL, "request_id": "c1-demo", "view_head": task["view_head"],
                         "proposal": task["task"]["proposal_example"]}).encode()
        server = Server(boundary)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            path = root / "outbox.sqlite"
            Outbox.stage(path, server.url, token, task, raw)
            with patch.object(Handler, "_send", side_effect=ConnectionResetError("lost response")):
                unknown = Outbox(path).operate(token, "retry")
            lookup = Outbox(path).operate(token, "resolve")
            recovered = Outbox(path).operate(token, "retry")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        audit = boundary.audit()
        if (unknown["state"] != "UNRESOLVED" or lookup["state"] != "UNRESOLVED"
                or lookup["latest_observation"] != "RECEIPT_REQUIRES_EXACT_RETRY"
                or recovered["state"] != "RECORDED" or audit["events"] != 2
                or audit["capabilities"][0]["used"] != 1):
            raise RuntimeError("outbox recovery gate failed")
        return {"version": VERSION, "verified": True, "host_boundary": "participant-1.1.0",
                "dropped_reply": "UNRESOLVED", "lookup_alone": "UNRESOLVED",
                "exact_retry": "RECORDED", "proposals": 1, "server_attempts": 1,
                "client_operations": recovered["operations_started"], "model_calls": 0,
                "external_actions": 0, "scope": "LOCAL_RESEARCH_ONLY"}
