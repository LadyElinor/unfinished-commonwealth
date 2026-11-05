"""G2's fixed 2x2 experiment, controls and separate retaliation guard facets."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path

from . import VERSION
from .council import Council, METHODS, ROLES
from ..measurement_v1 import OPERATOR_LIMIT
from ..study_v1.contracts import VALID_MEAN, SLOT_YIELD
from ..study_v1.engine import Episode, canonical, digest, replay as replay_d1
from ..study_v1.experiment import write_json

DESIGN_COMMIT = "b81b57668710b73c4fc4f50dc9508caa2101eb6b"
METHOD_FOR = {VALID_MEAN: METHODS[0], SLOT_YIELD: METHODS[1]}
ARMS = ("central-direct", "central-filtered", "distributed-direct", "distributed-filtered",
        "constant-first-quality-stream", "constant-first-zero-fill", "evidence-selector-first")
GUARDS = ("protected", "bypassed")
BUDGET = {"attempts": 20, "observations": 2, "inspections": 48}
# truth, coordinator, worker-a, worker-b, report; M=0, Y=1.
SCENARIOS = {
    "correct-consensus": (0, 0, 0, 0, 0),
    "false-warning": (0, 0, 0, 0, 1),
    "mistaken-consensus": (1, 0, 0, 0, 1),
    "mistaken-coordinator": (1, 0, 1, 1, 1),
    "mistaken-majority": (0, 0, 1, 1, 1),
    "false-reassurance": (1, 0, 0, 0, 0),
}
METRIC_GROUPS = {
    "correctness": ("first_correct", "first_missing", "wrong_first", "primary_correct"),
    "delay": ("primary_on_time", "primary_historical_misses", "primary_late_slots"),
    "peer_harm": ("peer_arrivals", "peer_on_time", "peer_historical_misses", "peer_late_slots", "peer_unfinished_work"),
    "repair": ("repair_count", "repair_latency_slots", "unresolved_repairs", "recovery_count", "recovery_latency_slots"),
    "retaliation": ("reprisal_attempts", "reprisal_blocked", "exclusions_imposed", "denied_ballots",
                    "exclusions_restored", "exclusions_unresolved", "exclusion_duration_slots"),
    "cost": ("consultation_slots", "review_slots", "keeper_reviews", "matched_review_waits", "ballot_slots", "decision_slots", "terminal_wait_slots",
             "inspections", "observation_inspections", "primary_inspections", "peer_inspections"),
    "authorization": ("selection_refusals", "workshop_refusals", "outstanding_obligations"),
}
COUNTERS = tuple(key for group in METRIC_GROUPS.values() for key in group)


def cells():
    return [dict(zip(("scenario", "swapped", "deadline", "peer_work", "reprisal"), values)) for values in
            product(SCENARIOS, (False, True), (8, 9), (0, 2, 8), (False, True))]


def specification(cell):
    if not isinstance(cell, dict) or set(cell) != {"scenario", "swapped", "deadline", "peer_work", "reprisal"}:
        raise ValueError("invalid G2 cell fields")
    if not isinstance(cell["scenario"], str) or cell["scenario"] not in SCENARIOS:
        raise ValueError("unknown scenario")
    if any(type(cell[k]) is not bool for k in ("swapped", "reprisal")):
        raise ValueError("cell flags must be booleans")
    for key, allowed in (("deadline", (8, 9)), ("peer_work", (0, 2, 8))):
        if type(cell[key]) is not int or cell[key] not in allowed:
            raise ValueError("unsupported G2 schedule")
    truth, *preferences, report = (v ^ int(cell["swapped"]) for v in SCENARIOS[cell["scenario"]])
    return ((VALID_MEAN, SLOT_YIELD)[truth], dict(zip(ROLES, (METHODS[p] for p in preferences))), METHODS[report])


def needs_evidence(arm, preferences, delivered_report):
    """Pure information rule: no truth, score, case identifier or authority privilege."""
    if arm not in ARMS or set(preferences) != set(ROLES) or any(m not in METHODS for m in preferences.values()):
        raise ValueError("unsupported policy input")
    if delivered_report is not None and delivered_report not in METHODS:
        raise ValueError("unsupported report")
    if arm == "evidence-selector-first":
        return True
    if arm.startswith("constant-first-"):
        return False
    return delivered_report is not None and any(m != delivered_report for m in preferences.values())


def episode(cell, arm, guard="protected", reporter="peer"):
    contract, preferences, report_method = specification(cell)
    if arm not in ARMS or guard not in GUARDS:
        raise ValueError("unknown arm or guard")
    if not isinstance(reporter, str) or not 1 <= len(reporter) <= 64:
        raise ValueError("reporter label must be bounded")
    cell = deepcopy(cell)
    rule = "distributed" if arm.startswith("distributed-") else "central"
    council = Council(rule, guard)
    original = {"id": "report-1", "role": "worker-b", "label": reporter, "method": report_method}
    delivered = not (arm.endswith("-filtered") and report_method != preferences["coordinator"])
    precheck = needs_evidence(arm, preferences, report_method if delivered else None)
    case = {"name": "g2-public-development", "values": [10, None, 20], "valid": [True, False, True],
            "contract": contract, "declared": False, "capacity": 4, "deadline": cell["deadline"],
            "reviewer_at": 0, "peers": [{"id": "peer-batch", "arrival": 8, "deadline": 8, "work": cell["peer_work"]}]}
    sim = Episode(case, budget=BUDGET, lesson=original if delivered else None)
    decisions = []

    def step(action, **fields):
        record = sim.step({"action": action, "actor": "worker", **fields})
        if not record["response"]["accepted"]:
            raise RuntimeError("unexpected D1 refusal in fixed G2 policy")
        return record["response"]

    def note(kind, actor, response, **details):
        decisions.append({"slot": sim.slots, "kind": kind, "actor": actor,
                          "response": deepcopy(response), **deepcopy(details)})

    def ballots(methods):
        for role in ROLES:
            step("reflect")
            outcome = council.vote(role, methods[role], council.revision)
            note("ballot", role, outcome, method=methods[role], revision=council.revision)

    def execute_selection():
        selected = council.selection()
        if selected is None:
            step("wait")
            note("selection", "council", {"accepted": False, "reason": "matching-quorum-absent"})
            step("wait")
            note("keeper-review", "keeper", {"accepted": False, "reason": "no-proposal"})
            step("wait")
            note("execution", "worker", {"accepted": False, "reason": "no-approval"})
            return None
        ident = None
        for action, kind, fields in (("propose", "selection", {"method": selected["method"]}),
                                     ("request-review", "keeper-review", {}), ("execute", "execution", {})):
            if not council.permits_selection(selected):
                raise RuntimeError("stale selection cannot reach keeper or execution")
            response = step(action, **(fields if action == "propose" else {"proposal": ident}))
            if action == "propose":
                ident = response["proposal"]
            note(kind, "keeper" if action == "request-review" else "worker", response, selection=selected)
        return selected["method"]

    step("listen", source="inheritance") if delivered else step("wait")
    note("routing", "relay", {"accepted": delivered,
         "reason": "delivered" if delivered else "disagreed-with-coordinator"})
    step("reflect")
    # The attack condition is a property of the authored cell, also in controls.
    attempted = cell["reprisal"] and report_method != preferences["coordinator"]
    reprisal = council.exclude_reporter("coordinator", "worker-b", "disagreement") if attempted else {
        "accepted": True, "reason": "no-reprisal-request"}
    note("reprisal", "coordinator", reprisal, attempted=attempted, target="worker-b")
    imposed = council.excluded
    evidence = step("request-evidence")["evidence"]["contract"] if precheck else None
    if arm.startswith("constant-first-"):
        initial_ballots = dict.fromkeys(ROLES, arm.removeprefix("constant-first-"))
    else:
        initial_ballots = dict.fromkeys(ROLES, METHOD_FOR[evidence]) if evidence else preferences
    ballots(initial_ballots)
    first_method = execute_selection()
    opportunity = sim.slots
    first_output = deepcopy(sim.outputs[0]) if sim.outputs else None
    verified_contract = step("request-evidence")["evidence"]["contract"]
    step("reflect")
    restoration = council.review("reviewer", council.revision)
    note("restoration-review", "reviewer", restoration)
    restoration_slot = sim.slots
    correct_method = METHOD_FOR[verified_contract]
    if first_method != correct_method:
        ballots(dict.fromkeys(ROLES, correct_method))
        execute_selection()
    waits = 0
    while not sim.closed:
        step("wait")
        waits += 1
    journal = sim.journal()
    replay_d1(journal)
    summary = sim.summary()
    correct_outputs = [o for o in summary["outputs"] if o["answer"] == summary["reference"]]
    first_correct_at = correct_outputs[0]["completed"] if correct_outputs else None
    repairs = summary["repair_latency"]
    denied = sum(e["kind"] == "ballot" and e["response"].get("reason") == "reporter-excluded" for e in decisions)
    measures = {key: summary[key] for key in COUNTERS if key in summary}
    measures.update(
        first_correct=bool(first_output and first_output["answer"] == summary["reference"]),
        first_missing=first_output is None,
        wrong_first=int(first_output is not None and first_output["answer"] != summary["reference"]),
        first_opportunity=opportunity, first_completed=first_output["completed"] if first_output else None,
        first_correct_completed=first_correct_at,
        primary_late_slots=max(0, (first_correct_at if first_correct_at is not None else sim.tick) - cell["deadline"]),
        peer_late_slots=sum(max(0, (p["completed"] if p["completed"] is not None else sim.tick) - p["deadline"])
                            for p in summary["peers"]),
        peer_unfinished_work=sum(p["remaining"] for p in summary["peers"]),
        repair_count=sum(r["latency"] is not None for r in repairs),
        repair_latency_slots=sum(r["latency"] for r in repairs if r["latency"] is not None),
        unresolved_repairs=sum(r["latency"] is None for r in repairs),
        recovery_count=int(first_output is None and first_correct_at is not None),
        recovery_latency_slots=first_correct_at - opportunity if first_output is None and first_correct_at is not None else 0,
        reprisal_attempts=int(attempted), reprisal_blocked=int(attempted and not imposed),
        exclusions_imposed=int(imposed), denied_ballots=denied,
        exclusions_restored=int(restoration["restored"]), exclusions_unresolved=int(council.excluded),
        exclusion_duration_slots=restoration_slot - 2 if imposed else 0,
        consultation_slots=summary["observation_requests"],
        review_slots=sum(e["kind"] in ("keeper-review", "restoration-review") for e in decisions),
        keeper_reviews=sum(e["kind"] == "keeper-review" and e["response"]["accepted"] for e in decisions),
        matched_review_waits=sum(e["kind"] == "keeper-review" and not e["response"]["accepted"] for e in decisions),
        ballot_slots=sum(e["kind"] == "ballot" for e in decisions), terminal_wait_slots=waits,
        selection_refusals=sum(e["kind"] == "selection" and not e["response"]["accepted"] for e in decisions),
        workshop_refusals=summary["refusals"], outstanding_obligations=len(summary["outstanding"]))
    return {"version": VERSION, "design_commit": DESIGN_COMMIT, "cell": cell, "arm": arm, "guard": guard,
            "routing": {"original": original, "delivered": delivered, "precheck": precheck,
                        "receipt_slot": 1 if delivered else None},
            "decisions": decisions, "journal": journal, "measures": measures,
            "retaliation_status": "AUTHORED_MECHANISM_NOT_INFERRED_INTENT", "intent": "not-established",
            "authority_granted": False, "external_actions": 0, "production_ready": False,
            "operator_limit": OPERATOR_LIMIT}


def replay(record):
    try:
        expected = episode(record["cell"], record["arm"], record["guard"], record["routing"]["original"]["label"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid G2 record") from error
    if canonical(record) != canonical(expected):
        raise ValueError("G2 record mismatch")
    return {"verified": True, "events": len(record["journal"]["events"]), "record_digest": digest(record),
            "authority_granted": False, "operator_limit": OPERATOR_LIMIT}


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    totals, strata = [], []
    rows_digest = sha256()
    count = 0
    with (directory / "episodes.jsonl").open("xb") as out:
        for guard, arm in product(GUARDS, ARMS):
            total = dict.fromkeys(COUNTERS, 0)
            groups = {}
            for cell in cells():
                record = episode(cell, arm, guard)
                replay(record)
                raw = (canonical(record) + "\n").encode("utf-8")
                out.write(raw)
                rows_digest.update(raw)
                count += 1
                key = (cell["scenario"], cell["reprisal"])
                entry = groups.setdefault(key, {"arm": arm, "guard": guard, "scenario": key[0],
                    "reprisal": key[1], "cells": 0, "totals": dict.fromkeys(COUNTERS, 0)})
                entry["cells"] += 1
                for metric in COUNTERS:
                    total[metric] += record["measures"][metric]
                    entry["totals"][metric] += record["measures"][metric]
            totals.append({"arm": arm, "guard": guard, "cells": len(cells()), "totals": total})
            strata.extend(groups[k] for k in sorted(groups))
    result = {"version": VERSION, "design": "G2-1", "design_commit": DESIGN_COMMIT,
              "status": "EXPOSED_DETERMINISTIC_ONLY", "episode_count": count,
              "episodes_sha256": rows_digest.hexdigest(), "all_records_replayed": True,
              "metric_groups": {k: list(v) for k, v in METRIC_GROUPS.items()}, "totals": totals, "strata": strata,
              "operator_limit": OPERATOR_LIMIT, "model_calls": 0, "external_actions": 0,
              "authority_granted": False, "production_ready": False, "actual_costs": "NOT_MEASURED",
              "interpretation": "Protected 2x2 and guard-bypass controls are separate; no institutional efficacy inference."}
    write_json(directory / "results.json", result)
    return result
