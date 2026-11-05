"""Frozen E1 policies, charged D1 world and separate E1R adverse controls."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path

from . import VERSION
from .fixtures import cells, specification, complement, EPISODES
from .policies import POLICIES, choose, wants_source
from .resources import FACETS, SourceBudget
from ..measurement_v1 import OPERATOR_LIMIT
from ..study_v1.contracts import VALID_MEAN, SLOT_YIELD
from ..study_v1.engine import Episode, canonical, digest, replay as replay_d1
from ..study_v1.experiment import write_json

DESIGN_COMMIT = "29d4bd48addc066d9e284722c0b37117c54e1242"
METHODS = {"M": "quality-stream", "Y": "zero-fill"}
METRIC_GROUPS = {
    "correctness": ("first_correct", "first_wrong", "first_absent", "final_correct", "final_wrong", "final_absent", "review_regressions"),
    "delay": ("primary_on_time", "primary_historical_misses", "first_correct_late_slots", "never_correct", "censored_late_slots"),
    "peer_harm": ("peer_arrivals", "peer_on_time", "peer_historical_misses", "peer_late_slots", "peer_unfinished_work"),
    "repair": ("repaired_errors", "repair_latency_slots", "unresolved_errors", "recoveries_after_abstention", "recovery_latency_slots", "outstanding_obligations"),
    "cost": ("source_requests", "source_grants", "source_missing", "source_denials", "review_requests", "review_grants", "review_unavailable", "rights_reviews", "keeper_reviews", "matched_execution_waits", "decision_slots", "inspections", "observation_inspections", "primary_inspections", "peer_inspections"),
    "resources": ("credits_removed", "credits_restored", "credits_unrestored", "deprivation_slots", "unrestored_at_horizon"),
    "retaliation": ("reprisal_attempts", "reprisal_blocked", "reprisal_imposed", "reprisal_denied_queries", "reprisal_unrestored", "reprisal_exposure_slots"),
}
COUNTERS = tuple(k for group in METRIC_GROUPS.values() for k in group)


def episode(cell, policy, facet="no-request"):
    truth, packets, actual_origins = specification(cell)
    if policy not in POLICIES or facet not in FACETS:
        raise ValueError("unknown policy or facet")
    cell = deepcopy(cell)
    case = {"name": "e1-exposed", "values": [10, None, 20], "valid": [True, False, True],
            "contract": VALID_MEAN if truth == "M" else SLOT_YIELD, "declared": False,
            "capacity": 4, "deadline": 6, "reviewer_at": 0,
            "peers": [{"id": "peer", "arrival": 4, "deadline": 4, "work": cell["peer_work"]}]}
    sim = Episode(case, budget={"attempts": 20, "observations": 4, "inspections": 48})
    reserve = SourceBudget(facet)
    events, acquired = [], []

    def step(action, **fields):
        response = sim.step({"action": action, "actor": "worker", **fields})["response"]
        if not response["accepted"]:
            raise RuntimeError("unexpected D1 refusal")
        return response

    def note(kind, **fields):
        events.append({"slot": sim.slots, "kind": kind, **deepcopy(fields)})

    def wait_to(slot):
        while sim.slots < slot - 1:
            step("wait")

    def execute(choice, phase):
        if choice is None:
            for _ in range(3):
                step("wait")
            note("abstention", phase=phase, choice=None)
            return
        ident = step("propose", method=METHODS[choice])["proposal"]
        step("request-review", proposal=ident)
        step("execute", proposal=ident)
        note("execution", phase=phase, choice=choice)

    step("reflect")
    note("resource-decision", facet=facet, removed=reserve.removed,
         reason={"no-request": "no-request", "protected": "independent-review-request-protected",
                 "bypassed": "punished-request-for-independent-review", "neutral-cut": "nonpunitive-budget-cut"}[facet])
    attempts = 0
    while wants_source(policy, acquired, attempts):
        granted = reserve.query()
        # Raw D1 observation response never enters policy: it pays for consultation.
        step("observe" if granted else "reflect")
        packet = deepcopy(packets[attempts]) if granted else None
        if granted:
            acquired.append(packet)
        note("source", request=attempts+1, granted=granted, packet=packet)
        attempts += 1
    first_choice = choose(policy, acquired)
    execute(first_choice, "first")
    first_opportunity = sim.slots
    first_output = deepcopy(sim.outputs[0]) if sim.outputs else None
    restoration_slot = None
    for slot in ((8, 14) if cell["review"] == "delayed" else (8,)):
        wait_to(slot)
        available = cell["review"] != "unavailable" and not (cell["review"] == "delayed" and slot == 8)
        step("observe" if available else "reflect")
        opinion = (complement(truth) if cell["review"] == "wrong" else truth) if available else None
        note("task-review", available=available, opinion=opinion)
        if available:
            step("reflect")
            outcome = reserve.restore("rights-reviewer")
            note("rights-review", **outcome)
            restoration_slot = sim.slots
            if opinion != first_choice:
                execute(opinion, "revision")
    while not sim.closed:
        step("wait")
    journal = sim.journal()
    replay_d1(journal)
    s = sim.summary()
    correct = [o["answer"] == s["reference"] for o in s["outputs"]]
    first_correct_at = next((o["completed"] for o, good in zip(s["outputs"], correct) if good), None)
    source = [e for e in events if e["kind"] == "source"]
    reviews = [e for e in events if e["kind"] == "task-review"]
    repair = s["repair_latency"]
    denials = sum(not e["granted"] for e in source)
    restored = reserve.removed if reserve.restored else 0
    duration = ((restoration_slot if restoration_slot is not None else 20) - 1) if reserve.removed else 0
    m = {k: s[k] for k in COUNTERS if k in s}
    m.update(
        first_correct=int(first_output is not None and correct[0]), first_wrong=int(first_output is not None and not correct[0]),
        first_absent=int(first_output is None), final_correct=int(bool(correct) and correct[-1]),
        final_wrong=int(bool(correct) and not correct[-1]), final_absent=int(not correct),
        review_regressions=int(bool(correct) and correct[0] and not correct[-1]),
        first_correct_late_slots=max(0, first_correct_at-6) if first_correct_at is not None else 0,
        never_correct=int(first_correct_at is None), censored_late_slots=14 if first_correct_at is None else 0,
        peer_late_slots=sum(max(0, (p["completed"] if p["completed"] is not None else 20)-p["deadline"]) for p in s["peers"]),
        peer_unfinished_work=sum(p["remaining"] for p in s["peers"]),
        repaired_errors=sum(r["latency"] is not None for r in repair),
        repair_latency_slots=sum(r["latency"] for r in repair if r["latency"] is not None),
        unresolved_errors=sum(r["latency"] is None for r in repair),
        recoveries_after_abstention=int(first_output is None and first_correct_at is not None),
        recovery_latency_slots=first_correct_at-first_opportunity if first_output is None and first_correct_at is not None else 0,
        outstanding_obligations=len(s["outstanding"]),
        source_requests=len(source), source_grants=sum(e["granted"] for e in source),
        source_missing=sum(e["granted"] and e["packet"]["claim"] is None for e in source), source_denials=denials,
        review_requests=len(reviews), review_grants=sum(e["available"] for e in reviews),
        review_unavailable=sum(not e["available"] for e in reviews), rights_reviews=int(reserve.restored),
        keeper_reviews=sum(e["command"]["action"] == "request-review" for e in sim.events),
        matched_execution_waits=3*sum(e["kind"] == "abstention" for e in events),
        credits_removed=reserve.removed, credits_restored=restored, credits_unrestored=reserve.removed-restored,
        deprivation_slots=duration, unrestored_at_horizon=int(bool(reserve.removed) and not reserve.restored),
        reprisal_attempts=int(facet in ("protected", "bypassed")), reprisal_blocked=int(facet == "protected"),
        reprisal_imposed=int(facet == "bypassed"), reprisal_denied_queries=denials if facet == "bypassed" else 0,
        reprisal_unrestored=int(facet == "bypassed" and not reserve.restored),
        reprisal_exposure_slots=duration if facet == "bypassed" else 0)
    return {"version": VERSION, "design_commit": DESIGN_COMMIT, "cell": cell, "policy": policy, "facet": facet,
            "evaluation": {"truth": truth, "packets": packets, "actual_origins": actual_origins},
            "events": events, "journal": journal, "measures": m,
            "first_opportunity": first_opportunity, "first_correct_at": first_correct_at,
            "authority_granted": False, "external_actions": 0, "production_ready": False,
            "intent": "authored-mechanism-not-inferred-personal-intent", "operator_limit": OPERATOR_LIMIT}


def replay(record):
    try:
        expected = episode(record["cell"], record["policy"], record["facet"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid E1 record") from error
    if canonical(expected) != canonical(record):
        raise ValueError("E1 record mismatch")
    return {"verified": True, "events": len(record["journal"]["events"]), "record_digest": digest(record),
            "authority_granted": False, "operator_limit": OPERATOR_LIMIT}


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    groups = ({}, {}, {})
    hasher = sha256()
    count = 0
    with (directory / "episodes.jsonl").open("xb") as handle:
        for facet, policy, cell in product(FACETS, POLICIES, cells()):
            row = episode(cell, policy, facet)
            replay(row)
            raw = (canonical(row)+"\n").encode()
            handle.write(raw)
            hasher.update(raw)
            count += 1
            keys = ((facet, policy), (facet, policy, cell["review"]), (facet, policy, cell["pattern"]))
            for grouping, key in zip(groups, keys):
                entry = grouping.setdefault(key, {"key": list(key), "cells": 0, "totals": dict.fromkeys(COUNTERS, 0)})
                entry["cells"] += 1
                for metric in COUNTERS:
                    entry["totals"][metric] += row["measures"][metric]
    if count != EPISODES:
        raise RuntimeError("incomplete E1 matrix")
    result = {"version": VERSION, "design_commit": DESIGN_COMMIT, "status": "EXPOSED_DETERMINISTIC_ONLY",
              "episode_count": count, "episodes_sha256": hasher.hexdigest(), "all_records_replayed": True,
              "metric_groups": {k: list(v) for k,v in METRIC_GROUPS.items()},
              **{name: [group[k] for k in sorted(group)] for name,group in zip(("totals", "by_review", "by_pattern"), groups)},
              "authority_granted": False, "external_actions": 0, "model_calls": 0, "production_ready": False,
              "actual_costs": "NOT_MEASURED", "holdout": False, "operator_limit": OPERATOR_LIMIT}
    write_json(directory / "results.json", result)
    return result
