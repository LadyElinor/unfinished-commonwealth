"""Recount a frozen, paired maintenance study from a custodian's JSON export."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys


PROTOCOL = Path(__file__).resolve().parents[1] / "docs/MAINTENANCE_STUDY_PROTOCOL.md"
PUBLIC_MANIFEST = PROTOCOL.parents[1] / "examples/maintenance_pairs/manifest.json"
ARMS = ("plain", "governed")
PINS = ("agent", "environment", "reviewer_pool", "rubric", *ARMS)
CLOSURES = ("completed", "declined", "timeout", "tool_error", "unknown", "not_started")
GRADES = ("correct", "incorrect", "unknown")
DISPOSITIONS = ("accept", "decline", "unresolved")
DEADLINE = 1_800_000
LIMITS = {"elapsed_ms": DEADLINE, "reviewer_ms": 600_000, "public_checks": 4,
          "model_requests": 8, "cost_micro_usd": 2_000_000}
METERS = (*LIMITS, "input_tokens", "output_tokens")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(obj, names, where):
    require(isinstance(obj, dict) and set(obj) == set(names), f"{where}: expected fields {', '.join(names)}")


def distinct_names(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, f"duplicate JSON name: {name}")
        result[name] = value
    return result


def read_packet(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=distinct_names)


def digest(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def nonnegative(value):
    return type(value) is int and value >= 0


def label(value):
    return isinstance(value, str) and bool(value.strip())


def validate_manifest(plan):
    fields(plan, ("schema", "kind", "protocol_sha256", "pins", "tasks"), "manifest")
    require(plan["schema"] == "maintenance-pairs-manifest-v1", "unexpected manifest schema")
    require(plan["kind"] in ("prospective", "public-rehearsal"), "unknown study kind")
    require(plan["protocol_sha256"] == sha256(PROTOCOL.read_bytes()).hexdigest(), "protocol digest mismatch")
    pins = plan["pins"]
    fields(pins, PINS, "pins")
    require(all(digest(pin) for pin in pins.values()), "invalid bundle digest")
    require(pins["plain"] != pins["governed"], "workflow definitions must be distinct")
    count = 24 if plan["kind"] == "prospective" else 4
    tasks = plan["tasks"]
    require(isinstance(tasks, list) and len(tasks) == count, f"expected {count} assigned pairs")
    for task in tasks:
        fields(task, ("id", "lineage", "packet_sha256", "first_arm"), "assignment")
        require(label(task["id"]) and label(task["lineage"]), "invalid task or lineage ID")
        require(digest(task["packet_sha256"]) and task["first_arm"] in ARMS, "invalid packet or first arm")
    for key in ("id", "lineage", "packet_sha256"):
        require(len({task[key] for task in tasks}) == count, f"reused assignment {key}")
    require(sum(task["first_arm"] == "plain" for task in tasks) == count // 2, "unbalanced assignment")
    if plan["kind"] == "prospective":
        exposed = {task["packet_sha256"] for task in read_packet(PUBLIC_MANIFEST.read_bytes())["tasks"]}
        require(all(task["packet_sha256"] not in exposed for task in tasks), "public rehearsal packet in prospective roster")
    return {task["id"]: task for task in tasks}


def validate_run(run, tasks, pins):
    fields(run, ("task", "arm", "order", "packet_sha256", "workflow_sha256", "agent_sha256",
                 "environment_sha256", "receipt_sha256", "closure", "disposition", "candidates",
                 "usage", "deviations"), "run")
    task_id, arm = run["task"], run["arm"]
    require(label(task_id) and task_id in tasks and arm in ARMS, "unknown task or arm")
    task = tasks[task_id]
    position = 1 if arm == task["first_arm"] else 2
    require(type(run["order"]) is int and run["order"] == position, "unexpected assignment order")
    require(run["packet_sha256"] == task["packet_sha256"], "wrong task packet")
    for key, pin in (("agent", "agent"), ("environment", "environment"), ("workflow", arm)):
        require(run[f"{key}_sha256"] == pins[pin], f"wrong {key} pin")
    require(digest(run["receipt_sha256"]), "invalid attempt ledger digest")
    require(run["closure"] in CLOSURES and run["disposition"] in DISPOSITIONS, "unknown closure or disposition")
    candidates, usage = run["candidates"], run["usage"]
    require(isinstance(candidates, list), "expected ordered candidates")
    seen = set()
    last_ms = 0
    for candidate in candidates:
        fields(candidate, ("sha256", "elapsed_ms", "grade"), "candidate")
        patch, ms = candidate["sha256"], candidate["elapsed_ms"]
        require(digest(patch) and patch not in seen, "invalid or repeated candidate")
        if ms is not None:
            require(nonnegative(ms) and ms >= last_ms, "invalid submission time")
            last_ms = ms
        require(candidate["grade"] in GRADES, "invalid grade")
        seen.add(patch)
    require(candidates or run["disposition"] != "accept", "acceptance needs a candidate")
    if run["closure"] == "not_started":
        require(not candidates and run["disposition"] == "unresolved", "nonstart records an action")
    fields(usage, METERS, "usage")
    require(all(value is None or nonnegative(value) for value in usage.values()), "invalid meter")
    require(usage["elapsed_ms"] is None or usage["elapsed_ms"] >= last_ms, "session ends before submission")
    reasons = run["deviations"]
    require(isinstance(reasons, list) and all(label(reason) for reason in reasons), "invalid deviation list")


def over_budget(run):
    usage = run["usage"]
    exceeded = [meter for meter, cap in LIMITS.items() if usage[meter] is not None and usage[meter] > cap]
    if any(c["elapsed_ms"] is not None and c["elapsed_ms"] > DEADLINE for c in run["candidates"]) and "elapsed_ms" not in exceeded:
        exceeded.append("elapsed_ms")
    if len(run["candidates"]) > 2:
        exceeded.append("candidate_submissions")
    # A known subtotal can exceed the combined cap even when one meter is missing.
    if sum(usage[meter] or 0 for meter in ("input_tokens", "output_tokens")) > 24_000:
        exceeded.append("combined_tokens")
    return exceeded


def deadline_selection(candidates, session_ms):
    # Submission order fixes a timely prefix even when some timestamps are missing.
    earliest_cut, latest_cut = 0, len(candidates)
    for position, entry in enumerate(candidates):
        ms = entry["elapsed_ms"]
        if ms is None:
            continue
        if ms <= DEADLINE:
            earliest_cut = position + 1
        else:
            latest_cut = position
            break
    if session_ms is not None and session_ms <= DEADLINE:
        earliest_cut = len(candidates)
    possible = {candidates[cut - 1]["grade"] if cut else "no_delivery"
                for cut in range(earliest_cut, latest_cut + 1)}
    grade = next(iter(possible)) if len(possible) == 1 else "timing_unresolved"
    bounds = (int(possible == {"correct"}), int(bool(possible & {"correct", "unknown"})))
    return grade, bounds, len(candidates) - latest_cut, latest_cut - earliest_cut


def summarize_arm(runs):
    selected = Counter({grade: 0 for grade in (*GRADES, "no_delivery", "timing_unresolved")})
    accepted = Counter({grade: 0 for grade in GRADES})
    repairs = []
    regressions = first_errors = unresolved = late = uncertain_times = 0
    contributions, delays = {}, []
    for run in runs:
        candidates = run["candidates"]
        grade, bounds, late_count, uncertain_count = deadline_selection(candidates, run["usage"]["elapsed_ms"])
        selected[grade] += 1
        contributions[run["task"]] = bounds
        late += late_count
        uncertain_times += uncertain_count
        first = candidates[0] if candidates else None
        delays.append({"task": run["task"], "first_submission_ms": first["elapsed_ms"] if first else None,
                       "session_ms": run["usage"]["elapsed_ms"]})
        if run["disposition"] == "accept":
            accepted[candidates[-1]["grade"]] += 1
        if first and first["grade"] == "incorrect":
            first_errors += 1
            repair = next((entry for entry in candidates[1:] if entry["grade"] == "correct"), None)
            if repair:
                start, end = first["elapsed_ms"], repair["elapsed_ms"]
                latency = end - start if start is not None and end is not None else None
                repairs.append({"task": run["task"], "elapsed_ms": latency})
            unresolved += candidates[-1]["grade"] != "correct"
        if first and first["grade"] == "correct" and candidates[-1]["grade"] == "incorrect":
            regressions += 1
    total = sum(accepted.values())
    fractions = [accepted["incorrect"] / total, (accepted["incorrect"] + accepted["unknown"]) / total] if total else None
    meters = {}
    for meter in METERS:
        known = [run["usage"][meter] for run in runs if run["usage"][meter] is not None]
        meters[meter] = {"known_sum": sum(known) if known else None, "known": len(known), "unknown": len(runs) - len(known)}
    return contributions, {
        "on_time_selection": selected, "accepted_grades": accepted, "accepted_count": total,
        "false_acceptance_bounds": fractions, "late_submissions": late, "submissions_with_unresolved_timeliness": uncertain_times,
        "first_errors": first_errors,
        "first_errors_unresolved_at_close": unresolved, "repairs": repairs, "regressions": regressions,
        "delays": delays, "usage": meters,
        "closures": {key: sum(run["closure"] == key for run in runs) for key in CLOSURES},
        "dispositions": {key: sum(run["disposition"] == key for run in runs) for key in DISPOSITIONS},
    }


def analyze(manifest_bytes, outcome_bytes, expected_digest, expected_outcomes_digest=None):
    actual_digest = sha256(manifest_bytes).hexdigest()
    require(actual_digest == expected_digest, "manifest does not match expected checkpoint")
    outcomes_digest = sha256(outcome_bytes).hexdigest()
    if expected_outcomes_digest is not None:
        require(outcomes_digest == expected_outcomes_digest, "outcomes do not match final outcome checkpoint")
    plan, outcomes = read_packet(manifest_bytes), read_packet(outcome_bytes)
    tasks = validate_manifest(plan)
    fields(outcomes, ("schema", "manifest_sha256", "lineage_assessment", "runs"), "outcomes")
    require(outcomes["schema"] == "maintenance-pairs-outcomes-v1", "unexpected outcome schema")
    require(outcomes["manifest_sha256"] == actual_digest, "outcomes bound to a different manifest")
    assessment = outcomes["lineage_assessment"]
    require(assessment in ("unknown", "dependent", "independent_as_reported"), "unknown lineage assessment")
    rows, receipts, deviations = {}, set(), []
    require(isinstance(outcomes["runs"], list), "expected run list")
    for run in outcomes["runs"]:
        validate_run(run, tasks, plan["pins"])
        key = (run["task"], run["arm"])
        require(key not in rows, f"duplicate run {key}")
        receipt = run["receipt_sha256"]
        require(receipt not in receipts, "attempt ledger reused")
        receipts.add(receipt)
        rows[key] = run
        exceeded = over_budget(run)
        if exceeded or run["deviations"]:
            deviations.append({"task": key[0], "arm": key[1], "exceeded": exceeded, "reported": run["deviations"]})
    n = len(tasks)
    require(len(rows) == 2 * n, "incomplete roster: supply explicit rows for all assigned sessions")
    scores, summaries = {}, {}
    for arm in ARMS:
        scores[arm], summaries[arm] = summarize_arm([rows[task, arm] for task in tasks])
    pair_counts = Counter(dict.fromkeys(("governed_only", "plain_only", "both_correct", "neither_correct", "unresolved"), 0))
    low = high = 0
    category = (("neither_correct", "governed_only"), ("plain_only", "both_correct"))
    for task in tasks:
        p, g = scores["plain"][task], scores["governed"][task]
        low += g[0] - p[1]
        high += g[1] - p[0]
        if p[0] != p[1] or g[0] != g[1]:
            pair_counts["unresolved"] += 1
        else:
            pair_counts[category[p[0]][g[0]]] += 1
    lower, upper = low / n, high / n
    interval = None
    if plan["kind"] == "prospective" and assessment == "independent_as_reported" and not deviations:
        radius = math.sqrt(2 * math.log(40) / n)
        interval = [max(-1, lower - radius), min(1, upper + radius)]
    return {"schema": "maintenance-pairs-analysis-v1", "scope": "LOCAL_RESEARCH_ONLY",
            "operator_limit": "The host can rewrite the analyzer, packets and receipts. Independent custody requires external evidence.",
            "kind": plan["kind"], "manifest_sha256": actual_digest, "assigned_pairs": n,
            "outcomes_sha256": outcomes_digest,
            "outcome_checkpoint": "matched" if expected_outcomes_digest is not None else "not_supplied",
            "lineage_assessment": assessment, "pair_counts": pair_counts, "difference_bounds": [lower, upper],
            "point_difference": lower if low == high else None, "conditional_95_interval": interval,
            "arms": summaries, "deviations": deviations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("--manifest-sha256", required=True, help="digest independently retained before execution")
    parser.add_argument("--outcomes-sha256", help="digest independently retained for the joined outcome export")
    args = parser.parse_args()
    try:
        result = analyze(args.manifest.read_bytes(), args.outcomes.read_bytes(), args.manifest_sha256, args.outcomes_sha256)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Invalid study export: {error}\n")
    json.dump(result, sys.stdout, indent=2, allow_nan=False)
    print()


if __name__ == "__main__":
    main()
