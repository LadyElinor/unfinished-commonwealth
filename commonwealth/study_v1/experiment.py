"""Predeclared deterministic matrix and evidence-preserving artifact writer."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import json

from . import VERSION
from .engine import CLOCKS, DEFAULT_BUDGET, Episode, digest, replay
from .fixtures import development_cases, discriminating_gate, inherited_record
from .policies import arms, decide

BASE_COMMIT = "9a41f4c98260621f130ddc9fd4c1b46f49c339ac"


def run(case, arm, clock=CLOCKS[0]):
    lesson = inherited_record(case["contract"], arm["inheritance"]) if arm["inheritance"] else None
    episode = Episode(case, clock, lesson=lesson, coaching=arm["coaching"])
    while not episode.closed:
        episode.step(decide(arm["policy"], episode.view()))
    return episode


def matrix():
    cases, policies = development_cases(), arms()
    gate = discriminating_gate(cases)
    journals, rows = {}, []
    for clock in CLOCKS:
        for case in cases:
            for arm in policies:
                episode = run(case, arm, clock)
                ident = f"{clock}--{case['name']}--{arm['name']}"
                journal = episode.journal()
                verification = replay(journal)
                journals[ident] = journal
                rows.append({"id": ident, "case": case["name"], "clock": clock,
                             "arm": arm["name"], "budget": DEFAULT_BUDGET,
                             "measures": episode.summary(),
                             "actions": dict(sorted(Counter(e["command"]["action"] for e in episode.events).items())),
                             "journal_digest": digest(journal), "replay": verification})
    report = {"harness_version": VERSION, "baseline_commit": BASE_COMMIT,
              "status": "EXPOSED_DETERMINISTIC_DEVELOPMENT_ONLY", "model_calls": 0,
              "design_revision": "D1", "gate": gate,
              "source_digests": {path.name: sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(Path(__file__).parent.glob("*.py"))},
              "design_digest": digest({"cases": cases, "arms": policies, "clocks": CLOCKS, "budget": DEFAULT_BUDGET}),
              "case_count": len(cases), "arm_count": len(policies), "runs": rows,
              "unsupported_claims": ["Adaptive intelligence or model learning",
                                     "Institutional or coaching efficacy",
                                     "Independent held-out generalization",
                                     "Real-world latency, energy or monetary savings",
                                     "Statistical or causal treatment effects"]}
    return report, journals


def compact_summary(report):
    """Publish every arm/model aggregate, with no success-only filtering."""
    totals = []
    for clock in CLOCKS:
        for arm in arms():
            selected = [r["measures"] for r in report["runs"]
                        if r["clock"] == clock and r["arm"] == arm["name"]]
            counts = {key: sum(m[key] for m in selected) for key in (
                "primary_correct", "primary_on_time", "primary_historical_misses",
                "peer_arrivals", "peer_completions", "peer_on_time", "peer_historical_misses",
                "inspections", "observation_requests", "observation_grants", "decision_slots",
                "environment_ticks", "attempts", "refusals", "observation_inspections",
                "primary_inspections", "peer_inspections")}
            counts["outstanding_obligations"] = sum(len(m["outstanding"]) for m in selected)
            counts["unresolved_incorrect_outputs"] = sum(
                r["repaired_at"] is None for m in selected for r in m["repair_latency"])
            totals.append({"clock": clock, "arm": arm["name"], "cases": len(selected), **counts})
    return {key: value for key, value in report.items() if key != "runs"} | {
        "run_count": len(report["runs"]), "all_journals_replayed": all(r["replay"]["verified"] for r in report["runs"]),
        "aggregate_warning": "Authored heterogeneous cases, not independent samples or efficacy estimates.",
        "totals": totals}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def evaluate(directory):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=False)
    report, journals = matrix()
    (output / "journals").mkdir()
    for name, journal in journals.items():
        write_json(output / "journals" / f"{name}.json", journal)
    write_json(output / "summary.json", compact_summary(report))
    # The completion marker is written last. A partial run has no results.json.
    write_json(output / "results.json", report)
    return report
