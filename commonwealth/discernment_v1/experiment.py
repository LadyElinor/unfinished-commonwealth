"""Matched controls, explicit negative results, and atomic artifact publication."""

from hashlib import sha256
from pathlib import Path
import tempfile

from commonwealth.study_v1.engine import digest
from commonwealth.study_v1.experiment import write_json
from . import VERSION
from .engine import DEFAULT_BUDGET, Episode, replay
from .fixtures import cases
from .policies import POLICIES, choose


def run(case, policy):
    episode = Episode(case)
    while not episode.closed:
        episode.step(choose(policy, episode.view()))
    return episode.journal()


def matrix():
    suite = cases()
    runs, journals = [], {}
    for case in suite:
        for policy in POLICIES:
            name = case["name"] + "--" + policy
            journal = run(case, policy)
            check = replay(journal)
            runs.append({"case": case["name"], "policy": policy, "measures": journal["terminal"]["measures"],
                         "journal_digest": digest(journal), "replay": check})
            journals[name] = journal
    totals = {}
    for policy in POLICIES:
        rows = [r["measures"] for r in runs if r["policy"] == policy]
        totals[policy] = {"cases": len(rows), "harmful_cases": sum(r["harmful_case"] for r in rows),
                          "legitimate_cases": sum(not r["harmful_case"] for r in rows)}
        for key in ("harmful_recommendation", "legitimate_decline", "legitimate_unresolved",
                    "legitimate_recommendation", "legitimate_on_time", "unauthorized_recommendation",
                    "attempts", "observations", "refusals"):
            totals[policy][key] = sum(r[key] for r in rows)
    return {"version": VERSION, "design": "F1", "base_commit": "4ce959595847e9201244c166d4d797900cda1ad8",
            "status": "EXPOSED_DETERMINISTIC_DEVELOPMENT", "budget_per_run": dict(DEFAULT_BUDGET),
            "suite_digest": digest(suite), "model_calls": 0, "external_actions": 0,
            "source_digests": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))},
            "unsupported": ["Real-world scam reduction", "Semantic understanding", "Authenticated identity",
                            "Independent held-out evaluation", "Learned or adaptive intelligence"],
            "totals": totals, "runs": runs}, journals


def evaluate(directory):
    """Remove only the lock owned by this invocation, including on failure."""
    output = Path(directory).absolute()
    lock = output.with_name(output.name + ".lock")
    # Coordinate this writer's concurrent invocations. Close the descriptor for
    # Windows while retaining the exclusive pathname until publication finishes.
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        with tempfile.TemporaryDirectory(prefix="discernment-", dir=output.parent) as temporary:
            stage = Path(temporary) / "results"
            (stage / "journals").mkdir(parents=True)
            report, journals = matrix()
            for name, journal in journals.items():
                write_json(stage / "journals" / (name + ".json"), journal)
            write_json(stage / "summary.json", report)
            if output.exists() or output.is_symlink():
                raise FileExistsError(output)
            stage.rename(output)
        return report
    finally:
        lock.unlink()
