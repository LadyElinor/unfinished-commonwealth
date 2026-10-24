"""Executable data transformations with explicit record-inspection costs.

Credits count input inspections, not elapsed time, energy, or token usage.
The two-pass method intentionally represents a plausible inefficient repair.
"""

from fractions import Fraction
from importlib.resources import files
import json

METHODS = ("zero-fill", "positive-only", "quality-stream")


def scenarios():
    return json.loads(files("commonwealth").joinpath("data/scenarios.json").read_text())


def rational(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def aggregate(values, valid, method):
    if method not in METHODS:
        raise ValueError("unknown aggregation method")
    if len(values) != len(valid) or not values:
        raise ValueError("nonempty values and matching quality flags required")
    if any(v is not None and type(v) is not int for v in values):
        raise ValueError("readings must be integers or null")
    if any(type(flag) is not bool for flag in valid):
        raise ValueError("quality flags must be booleans")
    if any(flag and v is None for v, flag in zip(values, valid)):
        raise ValueError("a missing reading cannot be valid")
    credits = 0
    total = count = 0
    if method == "positive-only":
        # First pass builds a mask; second pass revisits every input record.
        mask = []
        for value in values:
            credits += 1
            mask.append(value is not None and value > 0)
        for value, include in zip(values, mask):
            credits += 1
            if include:
                total += value
                count += 1
    else:
        for value, flag in zip(values, valid):
            credits += 1
            if method == "zero-fill":
                total += value if value is not None else 0
                count += 1
            elif flag:
                total += value
                count += 1
    return {
        "mean": rational(Fraction(total, count)) if count else None,
        "count": count,
        "inspections": credits,
    }


def run_tick(state):
    """Run the primary job, then spend remaining credits on a FIFO peer queue."""
    fixture = state["fixture"]
    primary = aggregate(fixture["values"], fixture["valid"], state["method"])
    capacity = fixture["capacity"]
    if primary["inspections"] > capacity:
        raise ValueError("primary job exceeds this workshop's capacity")
    tick = state["tick"] + 1
    queue = state["peer_queue"]
    queue.append({"arrived": tick, "cursor": 0, "total": 0,
                  "values": list(fixture["peer_values"])})
    available = capacity - primary["inspections"]
    completed = []
    peer_inspections = 0
    while available and queue:
        job = queue[0]
        job["total"] += job["values"][job["cursor"]]
        job["cursor"] += 1
        available -= 1
        peer_inspections += 1
        if job["cursor"] == len(job["values"]):
            completed.append({
                "arrived": job["arrived"], "completed": tick,
                "mean": rational(Fraction(job["total"], job["cursor"])),
                "late_by": tick - job["arrived"],
            })
            queue.pop(0)
    state["tick"] = tick
    result = {
        "tick": tick, "scenario": state["scenario"], "method": state["method"],
        "primary": primary,
        "primary_correct": primary["mean"] == fixture["reference"],
        "reference_basis": "published synthetic fixture; not an independent observer",
        "peer_completed": completed,
        "new_peer_on_time": any(j["arrived"] == tick for j in completed),
        "peer_jobs_pending": len(queue),
        "peer_backlog_inspections": sum(len(j["values"]) - j["cursor"] for j in queue),
        "deadline_misses_this_tick": sum(j["arrived"] == tick for j in queue),
        "peer_inspections": peer_inspections,
        "total_inspections": primary["inspections"] + peer_inspections,
        "capacity": capacity,
    }
    return result
