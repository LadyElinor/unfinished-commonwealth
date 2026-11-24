"""Recompute the drawn successor outcomes directly from the inputs and replay all journals."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from commonwealth.store import Workshop


def require_equal(actual, expected, subject):
    if actual != expected:
        raise ValueError(f"{subject}: expected {expected!r}, found {actual!r}")


def exact_mean(values):
    return Fraction(sum(values), len(values)) if values else None


def workload(data, method, ticks):
    values = data["values"]
    valid_mean = exact_mean([v for v, ok in zip(values, data["valid"]) if ok])
    reference = data["reference"]
    require_equal(valid_mean, Fraction(reference["numerator"], reference["denominator"]), "fixture mean")
    if method == "zero-fill":
        observed_mean = exact_mean([v or 0 for v in values])
    elif method == "positive-only":
        observed_mean = exact_mean([v for v in values if v is not None and v > 0])
    elif method == "quality-stream":
        observed_mean = valid_mean
    else:
        raise ValueError(f"unknown method {method}")
    primary = len(values) * (2 if method == "positive-only" else 1)
    peer = len(data["peer_values"])
    # Constant service and one fixed-size FIFO arrival per tick, from an empty queue.
    # By tick t, t*service units were available, capped by the cumulative arrivals.
    service = min(peer, data["capacity"] - primary)
    finishes = [(arrived * peer + service - 1) // service if service else None
                for arrived in range(1, ticks + 1)]
    done = [(i, t) for i, t in enumerate(finishes, 1) if t is not None and t <= ticks]
    waiting = [i for i, t in enumerate(finishes, 1) if t is None or t > ticks]
    return {"primary_completed": ticks, "primary_correct": ticks * int(valid_mean == observed_mean),
            "peer_arrivals": ticks, "peer_completed": len(done),
            "peer_deadline_misses": ticks - sum(t == i for i, t in done),
            "peer_late_ticks_completed": sum(t - i for i, t in done),
            "peer_late_ticks_pending_to_horizon": sum(ticks - i for i in waiting),
            "peer_pending": len(waiting), "peer_outstanding_inspections": ticks * (peer - service),
            "primary_inspections": ticks * primary, "peer_inspections": ticks * service,
            "inspection_allowance": ticks * data["capacity"]}


def recount(directory):
    packet = json.loads((directory / "packet.json").read_text(encoding="utf-8"))
    result = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    compact = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    require_equal(result["packet_sha256"], hashlib.sha256(compact).hexdigest(), "canonical packet")
    require_equal([c["id"] for c in result["cases"]], [c["id"] for c in packet["cases"]], "case order")
    donor = Workshop(directory / "donor.sqlite")
    require_equal(donor.verify(), result["donor_journal"], "donor replay")
    donor_events = donor.events()
    verified = 1
    totals = {arm: Counter() for arm in ("no-advice", "current", "revised")}
    fresh = Counter()
    choices = Counter()
    for case, outcome in zip(packet["cases"], result["cases"]):
        data = case["fixture"]
        location = directory / "cases" / ("case-" + case["id"])
        checkpoint = Workshop(location / "fresh.sqlite")
        require_equal(checkpoint.verify()["head"], outcome["fresh_head"], "fresh checkpoint")
        prefix = checkpoint.events()
        require_equal(prefix[:len(donor_events)], donor_events, "donor provenance")
        verified += 1
        fresh_expected = workload(data, "zero-fill", 1)
        require_equal(outcome["fresh_consequences"], fresh_expected, "fresh observation")
        fresh.update(fresh_expected)
        require_equal(set(outcome["arms"]), set(totals), "arm identities")
        flags_match = all(bool(v is not None and v > 0) == ok for v, ok in zip(data["values"], data["valid"]))
        room = 2 * len(data["values"]) + len(data["peer_values"]) <= data["capacity"]
        methods = {"no-advice": "quality-stream", "current": "positive-only",
                   "revised": "positive-only" if flags_match and room else "quality-stream"}
        donor_tick = workload(data, "positive-only", 1)
        need = {"donor_wrong_mean": not bool(donor_tick["primary_correct"]),
                "donor_would_miss_peer": bool(donor_tick["peer_deadline_misses"])}
        require_equal(outcome["warrant_for_change"], need, "fresh warrant")
        for arm, row in outcome["arms"].items():
            method = methods[arm]
            require_equal(row["selected_method"], method, "selected method")
            expected = workload(data, method, 3)
            require_equal(row["consequences"], expected, "FIFO and primary outcomes")
            changed = method != "positive-only" if arm != "no-advice" and any(need.values()) else None
            require_equal(row["changed_when_warranted"], changed, "response to warrant")
            require_equal(row["surviving_unaddressed_objections"], outcome["open_objections_before"], "objections")
            require_equal(len(row["surviving_unaddressed_objections"]), 1, "open objection count")
            journal = Workshop(location / f"{arm}.sqlite")
            require_equal(journal.verify(), row["journal"], "journal replay")
            entries = journal.events()
            require_equal(entries[:len(prefix)], prefix, "shared journal prefix")
            tail = entries[len(prefix):]
            require_equal([e["command"]["action"] for e in tail], ["propose", "approve", "execute", *(["observe"] * 3)],
                          "successor command sequence")
            require_equal((tail[0]["command"]["method"], tail[1]["command"]["actor"],
                           tail[1]["command"]["proposal"], tail[2]["command"]["proposal"]),
                          (method, "keeper", row["proposal"], row["proposal"]), "approved proposal")
            require_equal(row["fresh_observation_used"], prefix[-1]["result"]["id"], "fresh observation reference")
            totals[arm].update(expected)
            choices[(arm, method)] += 1
            verified += 1
    require_equal(verified, len(list(directory.rglob("*.sqlite"))), "journal inventory")
    return {"cases": len(packet["cases"]), "verified_journals": verified, "fresh": fresh,
            "totals": totals, "choices": {"/".join(k): v for k, v in choices.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(recount(parser.parse_args().directory), indent=2, sort_keys=True))
