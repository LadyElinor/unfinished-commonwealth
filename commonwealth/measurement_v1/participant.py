"""Compare a JSON-only external fixture with the existing D1 evidence selector."""
import json
from pathlib import Path
import subprocess
import sys

from ..engine import parse_json
from ..study_v1.engine import CLOCKS, Episode, digest, replay
from ..study_v1.experiment import run as run_control, write_json
from ..study_v1.fixtures import development_cases
from ..study_v1.policies import arms
from . import OPERATOR_LIMIT

PROFILE = "unfinished-commonwealth.study-decision.v1"
# Deliberately omit case ID, hidden labels, expected answers, scoring, keeper state and other accounts.
VISIBLE = ("values", "valid", "contract", "evidence_available", "schedule", "clock",
           "budget", "decision_slots", "environment_ticks", "observation_grants", "inspections")


def brief(view):
    body = {"profile": PROFILE, "role": "study-proposer", "external_authority": "NONE",
            "work": {k: view[k] for k in VISIBLE}}
    sched = view["schedule"]
    body["work"]["schedule"] = {key: sched[key] for key in ("capacity", "deadline", "reviewer_at")}
    body["work"]["schedule"]["peers"] = [
        {key: peer[key] for key in ("id", "arrival", "deadline", "work")} for peer in sched["peers"]]
    body["work"]["budget"] = {k: view["budget"][k] for k in ("attempts", "observations", "inspections")}
    return {"brief_id": digest(body), **body}


def interpret(packet, reply):
    if not isinstance(reply, dict) or reply.get("profile") != PROFILE or reply.get("brief_id") != packet["brief_id"]:
        raise ValueError("decision is not bound to this study brief")
    choices = {"propose": "propose", "wait": "wait", "decline": "halt", "request-evidence": "request-evidence"}
    choice = reply.get("choice")
    if not isinstance(choice, str) or choice not in choices:
        raise ValueError("unsupported decision")
    field = "method" if choice == "propose" else "reason"
    if set(reply) != {"profile", "brief_id", "choice", field} or not isinstance(reply[field], str) or not reply[field].strip():
        raise ValueError("malformed decision")
    command = {"actor": "worker", "action": choices[choice]}
    if choice == "propose":
        command["method"] = reply["method"]
    return command


def ask(script, packet):
    proc = subprocess.run([sys.executable, "-I", str(script)], input=json.dumps(packet),
                          capture_output=True, text=True, encoding="utf-8", timeout=5, check=True)
    if len(proc.stdout) > 32768:
        raise ValueError("oversized fixture reply")
    return parse_json(proc.stdout)


def episode(case, script):
    sim = Episode(case, CLOCKS[0])
    decisions = []
    while not sim.closed:
        view = sim.view()
        if view["proposals"] and view["proposals"][-1]["status"] in ("pending", "approved"):
            last = view["proposals"][-1]
            action = "request-review" if last["status"] == "pending" else "execute"
            cmd = {"actor": "worker", "action": action, "proposal": last["id"]}
        elif view["pending_work"] or view["outputs"]:
            cmd = {"actor": "worker", "action": "observe" if view["observation_grants"] < view["budget"]["observations"] else "wait"}
        else:
            packet = brief(view)
            answer = ask(script, packet)
            cmd = interpret(packet, answer)
            decisions.append({"slot": sim.slots + 1, "brief": packet, "reply": answer})
        sim.step(cmd)
    return sim, decisions


def run(directory, script):
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    selector = next(a for a in arms() if a["name"] == "evidence-selector")
    rows = []
    for case in development_cases():
        sim, decisions = episode(case, script)
        control = run_control(case, selector)
        observed, baseline = sim.summary(), control.summary()
        different = [k for k in observed if observed[k] != baseline[k]]
        journal = sim.journal()
        write_json(directory / (case["name"] + ".json"),
                   {"journal": journal, "decisions": decisions, "replay": replay(journal), "operator_limit": OPERATOR_LIMIT})
        rows.append({"case": case["name"], "measures": observed, "different_measures": different,
                     "identical_journal": journal == control.journal(), "briefs_sent": len(decisions)})
    return {"status": "EXPOSED_PROCESS_INTERCHANGE_CONTROL", "operator_limit": OPERATOR_LIMIT,
            "matched_control": "evidence-selector", "model_calls": 0, "cases": rows}
