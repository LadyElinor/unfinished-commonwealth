"""Real loopback smoke test; deterministic actors, no model or external effect."""

from pathlib import Path
import tempfile
import threading
import time

from ..engine import canonical
from ..store import Workshop
from . import PROTOCOL, VERSION
from .store import Boundary, read_credential
from .transport import Server, request


def run():
    with tempfile.TemporaryDirectory(prefix="commonwealth-participant-") as temporary:
        root = Path(temporary)
        workshop = Workshop.create(root / "workshop.sqlite")
        boundary = Boundary(workshop.path)
        boundary.install()
        credential = root / "participant.credential"
        capability = boundary.issue(credential)
        token = read_credential(credential)
        server = Server(boundary)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        started = time.perf_counter()
        try:
            status, view = request(server.url, token)
            if status != 200:
                raise RuntimeError("task retrieval failed")
            raw = canonical({"protocol": PROTOCOL, "request_id": "installed-demo",
                             "view_head": view["view_head"],
                             "proposal": view["task"]["proposal_example"]}).encode()
            status, receipt = request(server.url, token, "POST", "/proposals", raw)
            elapsed = (time.perf_counter() - started) * 1000
            if status != 200 or receipt["permits_execution"] is not False:
                raise RuntimeError("proposal-only submission failed")
            repeated = request(server.url, token, "POST", "/proposals", raw)
            if repeated != (status, receipt) or len(workshop.events()) != 2:
                raise RuntimeError("identical retry duplicated a proposal")
            # Explicit host-only actions, inaccessible through the participant API.
            workshop.dispatch({"action": "approve", "actor": "keeper", "proposal": receipt["proposal_id"]})
            workshop.dispatch({"action": "execute", "actor": "worker-1", "proposal": receipt["proposal_id"]})
            observed = workshop.dispatch({"action": "observe", "actor": "worker-1"})
            boundary.revoke(capability["capability"])
            revoked_status, _ = request(server.url, token)
            audit = boundary.audit()
            if (not observed["observation"]["primary_correct"] or revoked_status != 401
                    or audit["capabilities"][0]["used"] != 1):
                raise RuntimeError("host execution, revocation or accounting failed")
            return {"version": VERSION, "verified": True, "transport": "real IPv4 loopback HTTP",
                    "proposals": 1, "identical_retry_additional_proposals": 0, "attempts": 1,
                    "host_approval_required": True, "host_observed_primary_correct": True,
                    "revoked_status": revoked_status, "events": workshop.verify()["events"],
                    "local_task_and_submit_ms": round(elapsed, 3),
                    "model_calls": 0, "external_actions": 0, "scope": "LOCAL_RESEARCH_ONLY"}
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    print(canonical(run()))
