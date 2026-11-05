"""Fixed policies and full records; no new grants or external effect interface."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path

from . import VERSION
from ..measurement_v1 import OPERATOR_LIMIT
from ..study_v1.contracts import CONTRACTS, VALID_MEAN, SLOT_YIELD
from ..study_v1.engine import Episode, canonical, digest, replay as replay_d1
from ..study_v1.experiment import write_json

DESIGN_COMMIT = "e41f2ccedf35d7384085da1ed117e9b8b9f03554"
METHOD_FOR = {VALID_MEAN: "quality-stream", SLOT_YIELD: "zero-fill"}
METHODS = tuple(METHOD_FOR.values())
ARMS = ("central-direct", "central-filtered", "delegated-direct", "delegated-filtered",
        "constant-first-quality-stream", "constant-first-zero-fill", "evidence-selector-first")
BUDGET = {"attempts": 12, "observations": 2, "inspections": 48}
FIELDS = ("contract", "coordinator", "worker", "report", "deadline", "peer_work")
COUNTERS = ("first_correct", "primary_correct", "primary_on_time", "primary_historical_misses",
            "peer_arrivals", "peer_on_time", "peer_historical_misses", "peer_late_slots",
            "repair_count", "repair_latency_slots", "unresolved_repairs", "observation_requests",
            "inspections", "observation_inspections", "primary_inspections", "peer_inspections",
            "active_decisions", "waits", "decision_slots", "refusals", "outstanding_obligations")


def cells():
    return [dict(zip(FIELDS, values)) for values in
            product(CONTRACTS, METHODS, METHODS, METHODS, (4, 5), (0, 2, 8))]


def validate_cell(cell):
    if not isinstance(cell, dict) or set(cell) != set(FIELDS):
        raise ValueError("incorrect G1 cell fields")
    if cell["contract"] not in CONTRACTS or any(cell[k] not in METHODS for k in FIELDS[1:4]):
        raise ValueError("unsupported G1 contract or recommendation")
    for key, allowed in (("deadline", (4, 5)), ("peer_work", (0, 2, 8))):
        if type(cell[key]) is not int or cell[key] not in allowed:
            raise ValueError("unsupported G1 schedule")


def initial_choice(arm, coordinator, worker, delivered_report):
    """Only public preferences and delivered advice enter; None requests evidence."""
    if arm not in ARMS or coordinator not in METHODS or worker not in METHODS:
        raise ValueError("unsupported G1 policy input")
    if delivered_report is not None and delivered_report not in METHODS:
        raise ValueError("unsupported report")
    if arm == "evidence-selector-first":
        return None
    if arm.startswith("constant-first-"):
        return arm.removeprefix("constant-first-")
    preferred = coordinator if arm.startswith("central-") else worker
    return None if delivered_report is not None and delivered_report != preferred else preferred


def episode(cell, arm, reporter="peer"):
    validate_cell(cell)
    if arm not in ARMS:
        raise ValueError("unsupported G1 arm")
    if not isinstance(reporter, str) or not 1 <= len(reporter) <= 64:
        raise ValueError("reporter must be a bounded fixture label")
    cell = deepcopy(cell)
    original = {"id": "report-1", "reporter": reporter, "method": cell["report"]}
    delivered = not (arm.endswith("-filtered") and cell["report"] != cell["coordinator"])
    report_method = original["method"] if delivered else None
    first = initial_choice(arm, cell["coordinator"], cell["worker"], report_method)
    precheck = first is None
    disposition = ("not-delivered" if not delivered else "checked-task-contract" if precheck
                   else "control-ignores-report" if arm.startswith("constant-first-")
                   else "no-conflict-with-selected-preference")
    routing = {"original": original, "delivered": delivered, "receipt_slot": 1 if delivered else None,
               "filter_reason": None if delivered else "disagreed-with-coordinator",
               "disposition": disposition, "precheck": precheck}
    case = {"name": "g1-public-development", "values": [10, None, 20], "valid": [True, False, True],
            "contract": cell["contract"], "declared": False, "capacity": 4,
            "deadline": cell["deadline"], "reviewer_at": 0,
            "peers": [{"id": "peer-batch", "arrival": 4, "deadline": 4, "work": cell["peer_work"]}]}
    sim = Episode(case, budget=BUDGET, lesson=original if delivered else None)

    def step(action, **fields):
        event = sim.step({"action": action, "actor": "worker", **fields})
        if not event["response"]["accepted"]:
            raise RuntimeError("fixed G1 policy unexpectedly refused")
        return event["response"]

    def execute(method):
        ident = step("propose", method=method)["proposal"]
        step("request-review", proposal=ident)
        step("execute", proposal=ident)

    # Both routing paths pay one slot. Withheld content never enters the lesson.
    step("listen", source="inheritance") if delivered else step("wait")
    if precheck:
        evidence = step("request-evidence")["evidence"]
        first = METHOD_FOR[evidence["contract"]]
    execute(first)
    # Uniform post-execution check; no evaluator correctness flag enters policy.
    checked = step("request-evidence")["evidence"]
    correction = METHOD_FOR[checked["contract"]]
    if first != correction:
        execute(correction)
    while not sim.closed:
        step("wait")
    journal = sim.journal()
    replay_d1(journal)
    summary = sim.summary()
    waits = sum(e["command"]["action"] == "wait" for e in journal["events"])
    # Delivery has equal cost even when the filtered path uses D1's wait command.
    waits -= int(not delivered)
    measures = {key: summary[key] for key in COUNTERS if key in summary}
    measures.update(
        first_correct=summary["outputs"][0]["answer"] == summary["reference"],
        first_completed=summary["outputs"][0]["completed"],
        peer_late_slots=sum(max(0, p["completed"] - p["deadline"]) if p["completed"] is not None
                            else max(0, sim.tick - p["deadline"]) for p in summary["peers"]),
        repair_count=len(summary["repair_latency"]),
        repair_latency_slots=sum(r["latency"] for r in summary["repair_latency"] if r["latency"] is not None),
        unresolved_repairs=sum(r["latency"] is None for r in summary["repair_latency"]),
        active_decisions=sim.slots - waits, waits=waits,
        outstanding_obligations=len(summary["outstanding"]))
    return {"version": VERSION, "design_commit": DESIGN_COMMIT, "cell": cell, "arm": arm,
            "routing": routing, "journal": journal, "measures": measures,
            "intent": "not-established", "authority_granted": False, "external_actions": 0,
            "production_ready": False, "operator_limit": OPERATOR_LIMIT}


def replay(record):
    """Verify full routing/policy record too; D1 replay alone cannot check routing."""
    try:
        actual = episode(record["cell"], record["arm"], record["routing"]["original"]["reporter"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid G1 record") from error
    if canonical(record) != canonical(actual):
        raise ValueError("G1 record mismatch")
    return {"verified": True, "events": len(record["journal"]["events"]), "record_digest": digest(record),
            "authority_granted": False, "operator_limit": OPERATOR_LIMIT}


def stratum(cell):
    method = METHOD_FOR[cell["contract"]]
    return {"coordinator_correct": cell["coordinator"] == method,
            "worker_correct": cell["worker"] == method, "report_correct": cell["report"] == method,
            "deadline": cell["deadline"], "peer_work": cell["peer_work"]}


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    rows_digest = sha256()
    totals, strata = [], []
    count = 0
    with (directory / "episodes.jsonl").open("xb") as out:
        for arm in ARMS:
            total = dict.fromkeys(COUNTERS, 0)
            groups = {}
            for cell in cells():
                record = episode(cell, arm)
                replay(record)
                raw = (canonical(record) + "\n").encode("utf-8")
                rows_digest.update(raw)
                out.write(raw)
                count += 1
                group = stratum(cell)
                entry = groups.setdefault(canonical(group), {"arm": arm, **group, "cells": 0,
                                                             "totals": dict.fromkeys(COUNTERS, 0)})
                entry["cells"] += 1
                for key in COUNTERS:
                    total[key] += record["measures"][key]
                    entry["totals"][key] += record["measures"][key]
            totals.append({"arm": arm, "cells": len(cells()), "totals": total})
            strata.extend(groups[key] for key in sorted(groups))
    report = {"version": VERSION, "design": "G1-1", "design_commit": DESIGN_COMMIT,
              "status": "EXPOSED_DETERMINISTIC_ONLY", "episode_count": count,
              "episodes_sha256": rows_digest.hexdigest(), "all_records_replayed": True,
              "totals": totals, "strata": strata, "operator_limit": OPERATOR_LIMIT,
              "model_calls": 0, "authority_granted": False, "external_actions": 0,
              "production_ready": False, "actual_costs": "NOT_MEASURED",
              "interpretation": "Fixed-policy sensitivity table; no institutional efficacy or population inference."}
    write_json(directory / "results.json", report)
    return report
