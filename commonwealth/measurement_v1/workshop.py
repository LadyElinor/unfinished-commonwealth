"""Counterfactual elapsed-time accounting on verified original workshop traces."""
from collections import Counter
from pathlib import Path

from ..experiment import evaluate
from ..store import Workshop
from ..study_v1.experiment import write_json
from . import OPERATOR_LIMIT

HORIZON = 20
RELEASES = (1, 5, 9, 13)
SCHEDULES = ("shared-lane", "independent-worker")


def charge(events, schedule):
    if schedule not in SCHEDULES:
        raise ValueError("unsupported peer schedule")
    commands = events[1:]
    if len(commands) > HORIZON or sum(e["command"]["action"] == "observe" for e in commands) != 4:
        raise ValueError("trace does not fit the frozen four-observation design")
    fixture = events[0]["command"]["fixture"]
    capacity = fixture["capacity"]
    batch = len(fixture["peer_values"])
    peers = [{"release": t, "due": t + 3, "remaining": batch, "completed": None, "missed": False}
             for t in RELEASES]
    observations = []
    primary_cost = peer_cost = 0
    for slot in range(1, HORIZON + 1):
        event = commands[slot - 1] if slot <= len(commands) else None
        action = event["command"]["action"] if event else "idle"
        available = capacity
        if action == "observe":
            obs = event["result"]["observation"]
            cost = obs["primary"]["inspections"]
            available -= cost
            primary_cost += cost
            observations.append({"slot": slot, "target": 4 * (len(observations) + 1),
                                 "correct": obs["primary_correct"], "method": obs["method"]})
        elif action != "idle" and schedule == "shared-lane":
            available = 0
        for peer in peers:
            if peer["release"] > slot or peer["completed"] is not None:
                continue
            used = min(available, peer["remaining"])
            available -= used
            peer_cost += used
            peer["remaining"] -= used
            if not peer["remaining"]:
                peer["completed"] = slot
            elif slot >= peer["due"]:
                peer["missed"] = True
    repairs = [{"wrong_at": o["slot"], "slots_until_correct": next(
        (r["slot"] - o["slot"] for r in observations if r["slot"] > o["slot"] and r["correct"]), None)}
               for o in observations if not o["correct"]]
    return {
        "schedule": schedule, "decision_slots": len(commands), "action_counts": dict(sorted(Counter(
            e["command"]["action"] for e in commands).items())), "horizon": HORIZON,
        "primary_correct": sum(o["correct"] for o in observations),
        "primary_correct_by_target": sum(o["correct"] and o["slot"] <= o["target"] for o in observations),
        "primary_observations": observations, "primary_inspections": primary_cost,
        "repair_latency": repairs, "unresolved_wrong_observations": sum(r["slots_until_correct"] is None for r in repairs),
        "peer_arrivals": len(peers), "peer_on_time": sum(p["completed"] is not None and not p["missed"] for p in peers),
        "peer_historical_misses": sum(p["missed"] for p in peers), "peer_inspections": peer_cost,
        "outstanding_peer_inspections": sum(p["remaining"] for p in peers), "peer_jobs": peers,
    }


def run(directory):
    directory = Path(directory)
    historical = evaluate(directory)
    historical["operator_limit"] = OPERATOR_LIMIT
    write_json(directory / "results.json", historical)
    rows = []
    for row in historical["runs"]:
        scenario, arm = row["scenario"], row["arm"]
        events = Workshop(directory / f"{scenario}-{arm}.sqlite").events()
        rows.append({"scenario": scenario, "arm": arm, "historical_replay": row["replay"],
                     "observation_clock": row["measures"],
                     "charged": [charge(events, s) for s in SCHEDULES]})
    return {"design": "C1c-1", "status": "EXPOSED_FIXED_TRACE_ONLY", "operator_limit": OPERATOR_LIMIT,
            "model_calls": 0, "runs": rows}
