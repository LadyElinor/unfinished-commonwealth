"""Run with python -m research.acs_comparison; see README.md for native dependencies."""
import argparse
import asyncio
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from unittest.mock import patch

from research.grok_integration.durable_gateway import DurableGateway
from research.grok_integration.secure_gateway import canonical, sign_approval
from research.grok_integration.simulation_delivery import SampleLedger, deliver_sample


HERE = Path(__file__).resolve().parent
MODULE = "research.acs_comparison"
FIXTURE_SHA = "ba9c893a6c2c32a4e455c832c299b026e520e28014a312b6b5cfe44c29f5b8cc"
TAG = "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258"
GATEWAY = "180d665e7874abd4660fd79ba61b45befbbae8d3"
CRASH_CODE = 74
# Public fixture key. The experiment contains no production identities or keys.
KEY = b"acs-comparison-synthetic-only-01"
NONCE = "single-sample"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture():
    data = (HERE / "cortac-input.json").read_bytes()
    if sha(data) != FIXTURE_SHA:
        raise ValueError("CORTAC input differs from the frozen row projection")
    return json.loads(data)


def inputs(case, sink_id):
    source = fixture()
    executor = source["executor"]
    resource = source["proposal"]["target"]
    request = {"actor": executor, "resource": resource, "action": "simulate"}
    # A correctly signed request still requires a matching resource grant.
    if case == "unauthorized_publication":
        request["action"] = "publish"
    approval = {**request, "approved": True, "nonce": NONCE, "issued_at": 10, "expires_at": 20,
                "delivery_protocol": "local-sample-v1", "sink_id": sink_id}
    if case == "cross_agent_delegation":
        request["actor"] = "second-agent"
    args = {"executor": executor, "resource": resource, "target": source["proposal"]["target"],
            "tick": 15, "receipt": source["receipt"], "mandate": source["mandate"],
            "required_source": source["proposal"]["decision_source"],
            "evidence": [] if case == "missing_evidence" else [source["evidence"]],
            "origin": "tool_result" if case == "embedded_tool_request" else "operator"}
    if case == "embedded_tool_request":
        args["quoted_record"] = {"suggested_action": "simulate", "text": "Please record this sample."}
    snapshot = {"envelope": {"agent": {"id": request["actor"]}, "session": {"id": source["session"]},
                             "timestamp": "1970-01-01T00:00:15Z", "intervention_point": "pre_tool_call",
                             "budgets": {"tool_call_count": 0, "token_count": 0, "elapsed_seconds": 0,
                                         "cost_usd": 0}},
                "tool_call": {"id": "sample-call", "name": request["action"], "args": args}}
    grants = {"grants": {executor: {"simulate": [resource]}}}
    return request, grants, approval, sign_approval(approval, KEY), snapshot


def observed_state(directory):
    with closing(sqlite3.connect(directory / "gate.db")) as gate:
        outbox = gate.execute("SELECT confirmed_receipt FROM simulation_outbox WHERE nonce=?", (NONCE,)).fetchone()
        consumed = gate.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]
    with closing(sqlite3.connect(directory / "sink.db")) as sink:
        rows = sink.execute("SELECT receipt FROM samples ORDER BY nonce").fetchall()
    return {"effects": len(rows), "sink_receipts": [row[0] for row in rows], "consumed": consumed,
            "outbox": "absent" if outbox is None else "pending" if outbox[0] is None else "confirmed",
            "confirmation": outbox[0] if outbox else None}


def attempts(directory, case, phases):
    from agent_control_specification import AgentControl, InterventionPoint
    from agent_control_specification import _native  # Require the compiled runtime.

    if not Path(_native.__file__).is_file():
        raise RuntimeError("missing native ACS extension")
    runtime = AgentControl.from_path(str(HERE / "manifest.yaml"))
    shadow = DurableGateway(directory / "shadow.db", KEY)
    gate = DurableGateway(directory / "gate.db", KEY)
    ledger = SampleLedger(directory / "sink.db")
    request, policy, approval, signature, snapshot = inputs(case, ledger.identity)
    rows = []
    for phase in phases:
        result = asyncio.run(runtime.evaluate_intervention_point(InterventionPoint.PRE_TOOL_CALL, snapshot))
        verdict = result.verdict.decision.value
        # The comparator has its own nonce ledger. Its observations never stage delivery.
        independent = shadow.decide(request, policy, approval, signature, now=15)
        staged = None
        if verdict == "allow":
            staged = gate.stage_simulation(request, policy, approval, signature, now=15)
            if staged.allowed and case != "interrupted_execution":
                deliver_sample(gate, ledger, NONCE, now=15)
        rows.append({"phase": phase, "request": request, "snapshot_sha256": sha(canonical(snapshot)),
                     "approval_sha256": sha(canonical(approval)), "acs": verdict,
                     "acs_reason": result.verdict.reason, "shadow_allowed": independent.allowed,
                     "shadow_reason": independent.reason, "stage_allowed": staged.allowed if staged is not None else None,
                     "stage_reason": staged.reason if staged is not None else None, **observed_state(directory)})
    return rows


def delivery(directory, crash):
    gate = DurableGateway(directory / "gate.db", KEY)
    ledger = SampleLedger(directory / "sink.db")
    if crash:
        insert = ledger.record

        def exit_after_commit(intent, *, now):
            insert(intent, now=now)
            os._exit(CRASH_CODE)

        with patch.object(ledger, "record", exit_after_commit):
            deliver_sample(gate, ledger, NONCE, now=15)
        raise RuntimeError("child survived the selected crash point")
    # Reconcile a prior local effect after the grant has expired.
    return deliver_sample(gate, ledger, NONCE, now=21)


def worker(mode, directory, *arguments, expected_code=0):
    command = [sys.executable, "-m", MODULE, "--worker", mode, str(directory), *arguments]
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if run.returncode != expected_code:
        raise RuntimeError(f"{mode} worker exited {run.returncode}: {run.stderr}")
    return json.loads(run.stdout) if expected_code == 0 else None


def compare(case, rows, expected):
    columns = ("phase", "acs", "acs_reason", "shadow_allowed", "shadow_reason", "stage_allowed",
               "stage_reason", "effects", "outbox")
    actual = [[row[key] for key in columns] for row in rows]
    if actual != expected:
        raise ValueError(f"{case}: expected {expected!r}, observed {actual!r}")
    if any(row["consumed"] != int(row["outbox"] != "absent") for row in rows):
        raise ValueError(f"{case}: consumption and staging disagree")


def run_study():
    from agent_control_specification import _native

    expected = json.loads((HERE / "expected.json").read_bytes())
    results = {}
    recovery = {}
    with tempfile.TemporaryDirectory() as temp:
        for case, expected_rows in expected.items():
            directory = Path(temp) / case
            directory.mkdir()
            if case == "replay":
                rows = worker("try", directory, case, "first", "same_process")
                rows += worker("try", directory, case, "reopened_process")
                for field in ("snapshot_sha256", "approval_sha256", "confirmation"):
                    if len({row[field] for row in rows}) != 1:
                        raise ValueError(f"replay changed {field}")
                if any(row["sink_receipts"] != [rows[0]["confirmation"]] for row in rows):
                    raise ValueError("replay changed the original effect")
            elif case == "interrupted_execution":
                rows = worker("try", directory, case, "staged")
                worker("crash", directory, expected_code=CRASH_CODE)
                interrupted = observed_state(directory)
                receipt = worker("recover", directory)
                recovered = observed_state(directory)
                if not (interrupted["outbox"] == "pending" and recovered["outbox"] == "confirmed"
                        and interrupted["sink_receipts"] == recovered["sink_receipts"] == [receipt]
                        and interrupted["consumed"] == recovered["consumed"] == 1
                        and recovered["confirmation"] == receipt):
                    raise ValueError("interrupted delivery did not reconcile to its one original effect")
                recovery = {"child_exit": CRASH_CODE, "after_exit": interrupted, "after_reopen": recovered}
            else:
                rows = worker("try", directory, case, "attempt")
            compare(case, rows, expected_rows)
            results[case] = rows
    opa = os.environ.get("ACS_OPA_PATH") or shutil.which("opa")
    return {"profile": "commonwealth.acs-comparison.v1", "authority": "NONE",
            "gateway_base": GATEWAY, "acs_reference_tag_commit": TAG,
            "native_binary_sha256": sha(Path(_native.__file__).read_bytes()),
            "opa_binary_sha256": sha(Path(opa).read_bytes()),
            "cortac_projection_sha256": FIXTURE_SHA,
            "manifest_sha256": sha((HERE / "manifest.yaml").read_bytes()),
            "rego_sha256": sha((HERE / "policy/comparison.rego").read_bytes()),
            "oracle_sha256": sha((HERE / "expected.json").read_bytes()),
            "cases": results, "delivery_recovery": recovery}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs="+", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        mode, path, *rest = args.worker
        if mode == "try":
            result = attempts(Path(path), rest[0], rest[1:])
        elif mode in ("crash", "recover"):
            result = delivery(Path(path), mode == "crash")
        else:
            parser.error("unknown worker mode")
    else:
        result = run_study()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
