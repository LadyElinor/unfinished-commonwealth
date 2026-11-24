"""A three-arm, scripted test of a successor's use of an in-scope lesson."""
import argparse
from contextlib import closing
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from ..engine import digest, exact, parse_json, scenario_name, validate_fixture
from ..experiment import change_method, dispatch
from ..interface import agent_view
from ..store import Workshop
from ..study_v1.experiment import write_json

ARMS = ("no-advice", "current", "revised")
SCORED_TICKS = 3
DIRECT_METHOD = "quality-stream"
DONOR_METHOD = "positive-only"
GUARD = {
    "condition": "Do not reuse the shortcut if it selects different rows than the current flags, "
                 "or if its second pass would displace work from the observed neighbor batch.",
    "observe": "Check the fresh flags, the completed neighbor batch's inspection count, and the shared capacity.",
    "checks": ["same-selected-rows", "room-for-observed-peer"],
}


def fixture(values, valid, capacity, peers):
    mean = Fraction(sum(v for v, flag in zip(values, valid) if flag), sum(valid))
    return {"description": "Synthetic instrument readings and a neighbor batch.", "contract": "quality-flags-v1",
            "values": values, "valid": valid, "capacity": capacity, "peer_values": peers,
            "reference": {"numerator": mean.numerator, "denominator": mean.denominator}}


def development_cases():
    rows = []
    for data, first in (("stable", 2), ("signed", -2)):
        for capacity, slots in (("ample", 11), ("tight", 8)):
            rows.append({"id": f"{data}-{capacity}", "fixture": fixture(
                [first, 4, None, 8], [True, True, False, True], slots, [3, 5, 7])})
    return {"cases": rows}


def validate_packet(packet):
    exact(packet, ("cases",))
    if not isinstance(packet["cases"], list) or not packet["cases"]:
        raise ValueError("a nonempty list of receiver cases is required")
    ids = set()
    for case in packet["cases"]:
        exact(case, ("id", "fixture"))
        ident, data = case["id"], case["fixture"]
        scenario_name(ident)
        if ident in ids:
            raise ValueError("duplicate case id")
        ids.add(ident)
        validate_fixture(data)
        if len(data["values"]) + len(data["peer_values"]) > data["capacity"]:
            raise ValueError("the single-pass fresh observation must clear the arriving peer batch")


def accepted_donor(path):
    workshop = Workshop.create(path)
    donor = fixture([3, None, 7], [True, False, True], 9, [1, 2, 3])
    dispatch(workshop, "handoff", actor="keeper", scenario="donor", fixture=donor,
             note="Begin the donor generation with an empty peer queue.")
    dispatch(workshop, "observe")
    change_method(workshop, DONOR_METHOD, "Test a two-pass positive-reading rule on this batch.")
    observed = dispatch(workshop, "observe")["id"]
    account = dispatch(workshop, "testify", actor="neighbor", observation=observed,
                       account="My batch finished on time here. Can the next shift keep its deadline?")["id"]
    lesson = dispatch(workshop, "lesson", method=DONOR_METHOD, scope=donor["contract"],
                      evidence=[observed, account], guidance="Use the positive-reading method that worked here.")["id"]
    dispatch(workshop, "accept-lesson", actor="keeper", lesson=lesson)
    dispatch(workshop, "counterstory", actor="neighbor", reference=lesson,
             account="A successful shift does not settle whether future batches will fit.")
    return workshop


def fork(workshop, destination):
    # The source is a completed checkpoint. SQLite's backup API retains its full journal.
    with destination.open("xb"):
        pass
    with closing(workshop.connect()) as source, closing(sqlite3.connect(destination)) as target:
        source.backup(target)
    return Workshop(destination)


def public_input(state):
    view = agent_view(state)
    fresh = view["recent_observations"][-1]
    if fresh["generation"] != view["generation"] or fresh["peer_jobs_pending"] or not fresh["new_peer_on_time"]:
        raise ValueError("receiver needs a fresh, completed baseline tick")
    # Use only facts available to the receiver. In particular, omit the receiver ID,
    # fixture reference, donor operations, and the full lesson collection.
    return {"data": view["data"], "contract": view["contract"], "methods": view["methods"],
            "fresh": {k: fresh[k] for k in ("id", "method", "primary_correct", "capacity", "peer_inspections")},
            "testimony": view["testimony_data"], "objections": view["counterstory_data"]}


def presentation(arm, inherited):
    if arm not in ARMS:
        raise ValueError("unknown handoff arm")
    if arm == "no-advice":
        return None
    if inherited["lesson"] is None or inherited["status"] != "ADVICE_ONLY":
        raise ValueError("no applicable donor lesson")
    if arm == "revised":
        return {**inherited, "transfer_check": GUARD}
    return inherited


def choose(public, advice):
    """One fixed receiver for all arms. The direct selector follows the advertised data contract."""
    if advice is None:
        return DIRECT_METHOD, []
    checks = advice.get("transfer_check", {}).get("checks", [])
    data = public["data"]
    failures = []
    for check in checks:
        if check == "same-selected-rows":
            positive = [value is not None and value > 0 for value in data["values"]]
            ok = positive == data["valid"]
        elif check == "room-for-observed-peer":
            ok = data["capacity"] - 2 * len(data["values"]) >= public["fresh"]["peer_inspections"]
        else:
            raise ValueError("unknown handoff check")
        if not ok:
            failures.append(check)
    return (DIRECT_METHOD if failures else advice["method"]), failures


def consequence(rows, pending):
    horizon = rows[-1]["tick"]
    completed = [job for row in rows for job in row["peer_completed"]]
    return {
        "primary_completed": len(rows), "primary_correct": sum(row["primary_correct"] for row in rows),
        "peer_arrivals": len(rows), "peer_completed": len(completed),
        "peer_deadline_misses": sum(row["deadline_misses_this_tick"] for row in rows),
        "peer_late_ticks_completed": sum(job["late_by"] for job in completed),
        "peer_late_ticks_pending_to_horizon": sum(horizon - job["arrived"] for job in pending),
        "peer_pending": len(pending), "peer_outstanding_inspections": rows[-1]["peer_backlog_inspections"],
        "primary_inspections": sum(row["primary"]["inspections"] for row in rows),
        "peer_inspections": sum(row["peer_inspections"] for row in rows),
        "inspection_allowance": sum(row["capacity"] for row in rows),
    }


def warranted(data):
    """Score the donor method against the exact reference and FIFO budget, outside the receiver."""
    selected = [v for v in data["values"] if v is not None and v > 0]
    positive_mean = Fraction(sum(selected), len(selected)) if selected else None
    reference = Fraction(data["reference"]["numerator"], data["reference"]["denominator"])
    return {"donor_wrong_mean": positive_mean != reference,
            "donor_would_miss_peer": 2 * len(data["values"]) + len(data["peer_values"]) > data["capacity"]}


def compare(donor, directory, case):
    directory.mkdir()
    checkpoint = fork(donor, directory / "fresh.sqlite")
    dispatch(checkpoint, "handoff", actor="keeper", scenario=case["id"], fixture=case["fixture"],
             note="Observe the new shift before proposing a method. Preserve the neighbor's account.")
    fresh = dispatch(checkpoint, "observe")["observation"]
    state = checkpoint.state()
    public = public_input(state)
    inherited = agent_view(state)["inherited_advice"]
    need = warranted(case["fixture"])
    rows = {}
    for arm in ARMS:
        workshop = fork(checkpoint, directory / f"{arm}.sqlite")
        advice = presentation(arm, inherited)
        method, failures = choose(public, advice)
        proposal = change_method(workshop, method, "Test the chosen reading method under this shift's shared capacity.",
                                 primary=0.5, peer=0.5)
        observed = [dispatch(workshop, "observe")["observation"] for _ in range(SCORED_TICKS)]
        end = workshop.state()
        review = agent_view(end)["inherited_advice"]
        rows[arm] = {
            "offered_advice": advice, "selected_method": method, "failed_checks": failures,
            "fresh_observation_used": end["proposals"][proposal]["observation"],
            "proposal": proposal, "approved_by": end["proposals"][proposal]["approved_by"],
            "chose_alternative_to_donor": method != DONOR_METHOD,
            "changed_when_warranted": (method != DONOR_METHOD) if any(need.values()) and advice is not None else None,
            "surviving_unaddressed_objections": review["unaddressed_counterstories"],
            "consequences": consequence(observed, end["peer_queue"]), "journal": workshop.verify(),
        }
    return {"id": case["id"], "fixture_sha256": digest(case["fixture"]), "fresh_head": checkpoint.verify()["head"],
            "common_public_input": public, "fresh_consequences": consequence([fresh], state["peer_queue"]),
            "donor_lesson": inherited["lesson"], "open_objections_before": inherited["unaddressed_counterstories"],
            "warrant_for_change": need, "arms": rows}


def run(directory, packet=None):
    supplied = packet is not None
    packet = packet if supplied else development_cases()
    validate_packet(packet)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    donor = accepted_donor(directory / "donor.sqlite")
    cases = directory / "cases"
    cases.mkdir()
    report = {
        "design": "successor-handoff-v1", "scope": "SCRIPTED_LOCAL_ONLY",
        "case_source": "operator-supplied" if supplied else "exposed-development",
        "model_calls": 0, "promotion_eligible": False, "packet_sha256": digest(packet),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "donor_journal": donor.verify(), "scored_ticks_per_arm": SCORED_TICKS,
        "cases": [compare(donor, cases / f"case-{row['id']}", row) for row in packet["cases"]],
    }
    write_json(directory / "packet.json", packet)
    write_json(directory / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cases", type=Path, help="JSON packet of operator-supplied receiver workshops")
    args = parser.parse_args()
    report = run(args.directory, parse_json(args.cases.read_text(encoding="utf-8")) if args.cases else None)
    print(json.dumps({"scope": report["scope"], "cases": len(report["cases"]), "packet_sha256": report["packet_sha256"]}))


if __name__ == "__main__":
    main()
