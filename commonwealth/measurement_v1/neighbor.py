"""N1: a paid warning before committing a shared processor to a contiguous job."""
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from ..study_v1.experiment import write_json
from . import OPERATOR_LIMIT

DESIGN_COMMIT = "c22ebe6a2942d40eaef6f5ec0b7dbb6a4a3b7df9"
POLICIES = ("start", "reserve", "coin", "wait-start", "ask-peer", "select-peer", "select-instrument")
COUNTERS = ("primary_completed", "primary_late_slots", "primary_misses", "peer_completed",
            "peer_late_slots", "peer_misses", "consultation_slots", "wait_slots", "reservations")


def first_action(policy, primary_due, reliable_variants, coin):
    """Only public information enters the initial decision; truth stays with the scheduler."""
    if policy in ("start", "reserve"):
        return policy
    if policy == "coin":
        return "reserve" if coin else "start"
    if policy == "wait-start":
        return "wait"
    if policy == "ask-peer":
        return "peer"
    if policy not in ("select-peer", "select-instrument"):
        raise ValueError("unsupported policy")
    if primary_due == 4:
        return "reserve"
    if primary_due == 2 or reliable_variants == 2:
        return "start"
    return "peer" if policy == "select-peer" else "instrument"


def episode(policy, primary_due, reliable_variants, urgent, variant, coin):
    action = first_action(policy, primary_due, reliable_variants, coin)
    consulted = action in ("peer", "instrument")
    warning = (urgent if variant < reliable_variants else not urgent) if consulted else None
    reserve = action == "reserve" or warning is True
    delay = int(consulted or action == "wait")

    # Slot 2 is the only possible reservation. The primary job cannot be preempted.
    primary_start = 3 if reserve else 1 + delay
    primary_end = primary_start + 1
    peer_end = next(slot for slot in range(2, 5) if not primary_start <= slot <= primary_end)
    peer_due = 2 if urgent else 4
    return {
        "policy": policy, "primary_due": primary_due, "reliable_variants": reliable_variants,
        "urgent": urgent, "variant": variant, "coin": coin, "first_action": action, "warning": warning,
        "primary_completed": primary_end, "primary_late_slots": max(0, primary_end - primary_due),
        "primary_misses": int(primary_end > primary_due), "peer_completed": peer_end,
        "peer_late_slots": max(0, peer_end - peer_due), "peer_misses": int(peer_end > peer_due),
        "consultation_slots": int(consulted), "wait_slots": int(action == "wait"), "reservations": int(reserve),
    }


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    strata = []
    rows_digest = sha256()
    with (directory / "episodes.jsonl").open("xb") as out:
        for policy, deadline, reliability in product(POLICIES, (2, 3, 4), (2, 3, 4)):
            totals = dict.fromkeys(COUNTERS, 0)
            cells = 0
            for urgent, variant, coin in product((False, True), range(4), (False, True)):
                row = episode(policy, deadline, reliability, urgent, variant, coin)
                raw = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
                out.write(raw)
                rows_digest.update(raw)
                cells += 1
                for key in COUNTERS:
                    totals[key] += row[key]
            strata.append({"policy": policy, "primary_due": deadline, "reliable_variants": reliability,
                           "cells": cells, "totals": totals})
    report = {"design": "N1-1", "design_commit": DESIGN_COMMIT, "status": "EXPOSED_DETERMINISTIC_ONLY",
              "episode_count": sum(s["cells"] for s in strata), "episodes_sha256": rows_digest.hexdigest(),
              "strata": strata, "operator_limit": OPERATOR_LIMIT, "model_calls": 0}
    write_json(directory / "results.json", report)
    return report
