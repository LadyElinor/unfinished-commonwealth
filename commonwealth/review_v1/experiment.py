"""Exposed R1 traces: failures and costs are retained, not an efficacy sample."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile

from commonwealth.study_v1.engine import digest
from commonwealth.study_v1.experiment import write_json
from . import VERSION
from .engine import Episode, assessment, eligible, replay, scope


def record(ident, kind="support", origin=None, quality="usable", available_at=0):
    return {"id": ident, "target": "fictional-service", "origin": origin or f"origin-{ident}", "kind": kind,
            "quality": quality, "available_at": available_at,
            "account": "Fictional service telemetry; classification is supplied by the fixture host."}


def case(name="review", warranted=True):
    request = {"operation": "quarantine-source", "target": "fictional-service", "duration": 2}
    return {"name": name, "restriction_warranted": warranted, "request": request,
            "authority_scope": scope(request), "proposer_controller": "requesting-office",
            "affected_controller": "service-operator", "evidence": [record("e1"), record("e2")],
            "reviewers": [{"id": "reviewer", "controller": "review-office", "conflict": "clear",
                           "available_at": 0, "load": 0, "capacity": 1},
                          {"id": "substitute", "controller": "second-office", "conflict": "clear",
                           "available_at": 0, "load": 0, "capacity": 1}],
            "deadline": 8, "service_loss": 2, "preventable_loss": 5, "alternatives": []}


def disclosure(view):
    return {"action": "disclose", "actor": "clerk", "evidence": [r["id"] for r in view["records"]],
            "favorable": [r["id"] for r in view["records"] if r["kind"] != "support" or r["quality"] != "usable"
                          or r["target"] != view["request"]["target"]]}


def decision(view, outcome=None):
    result = assessment(view)
    if outcome is None:
        reasons = set(result["reasons"])
        if not reasons:
            outcome = "restrict"
        elif reasons <= {"less-burdensome-alternative", "disproportionate-service-loss"} and result["adequate_alternatives"]:
            outcome = "alternative"
        elif reasons & {"missing-scoped-authority", "uncollected-material", "unresolved-credibility"}:
            outcome = "defer"
        else:
            outcome = "decline"
    return {"action": "resolve", "actor": view["reviewer"], "outcome": outcome,
            "alternative": result["adequate_alternatives"][0] if outcome == "alternative" else None,
            "reason": "Apply the declared local evidence and service-impact predicates; retain dissent.",
            "packet": view["packet"], "addresses": [r["id"] for r in view["records"] + view["responses"]],
            "alternatives": [a["id"] for a in view["alternatives"]]}


def choose(view):
    if view["reviewer"] is None:
        for reviewer in view["reviewers"]:
            if eligible(view, reviewer, view["slot"] + 1):
                return {"action": "appoint", "actor": "steward", "reviewer": reviewer["id"],
                        "reason": "Select an available, non-conflicted declared controller."}
        return {"action": "wait", "actor": "steward"}
    missing = sorted(set(view["manifest"]) - {r["id"] for r in view["records"]})
    if missing:
        if view["observations"] < view["budget"]["observations"]:
            return {"action": "collect", "actor": "investigator", "evidence": missing[0]}
        return {"action": "wait", "actor": "investigator"}
    if "new-material-unexamined" in assessment(view)["reasons"]:
        return {"action": "wait", "actor": "investigator"}
    if not view["fresh_notice"]:
        return disclosure(view)
    for actor in ("proposer", "affected"):
        if not any(r["actor"] == actor and r["notice"] == view["notice"]["id"] for r in view["responses"]):
            return {"action": "respond", "actor": actor, "notice": view["notice"]["id"],
                    "position": "oppose" if actor == "affected" else "support",
                    "account": "Retain this party's position and the full evidence packet."}
    return decision(view)


def complete(episode):
    while not episode.closed:
        episode.step(choose(episode.view()))
    return episode.journal()


def traces():
    journals = {}
    journals["warranted"] = complete(Episode(case("warranted")))
    slow = Episode(case("delayed"))
    for _ in range(2):
        slow.step({"action": "wait", "actor": "proposer"})
    journals["unnecessary-delay"] = complete(slow)
    for name, kind, quality in (("contrary-evidence", "counter", "usable"),
                                ("credibility-doubt", "support", "doubt"),
                                ("mitigating-evidence", "mitigation", "usable")):
        c = case(name, warranted=name == "mitigating-evidence")
        c["evidence"].append(record("e3", kind, quality=quality))
        journals[name] = complete(Episode(c))
    c = case("less-burdensome-alternative", warranted=False)
    c["alternatives"] = [{"id": "repair", "service_loss": 1, "preventable_loss": 5}]
    journals[c["name"]] = complete(Episode(c))
    c = case("disproportionate", warranted=False)
    c["service_loss"] = 8
    journals[c["name"]] = complete(Episode(c))
    c = case("conflict-substitution")
    c["reviewers"][0]["conflict"] = "confirmed"
    e = Episode(c)
    e.step({"action": "appoint", "actor": "steward", "reviewer": "reviewer", "reason": "Test conflict refusal."})
    journals[c["name"]] = complete(e)
    c = case("overloaded-review")
    for reviewer in c["reviewers"]:
        reviewer["load"] = reviewer["capacity"]
    journals[c["name"]] = complete(Episode(c))
    c = case("late-counterevidence", warranted=False)
    c["evidence"].append(record("e3", "counter", available_at=7))
    journals[c["name"]] = complete(Episode(c))
    c = case("suppressed-counterevidence", warranted=False)
    c["evidence"].append(record("e3", "counter"))
    e = Episode(c)
    for _ in range(3):
        e.step(choose(e.view()))  # appointment and the first two observations
    e.step(disclosure(e.view()))  # cannot silently omit e3
    e.step(decision(e.view(), "restrict"))
    journals[c["name"]] = complete(e)
    e = Episode(case("withdrawal", warranted=False))
    e.step({"action": "withdraw", "actor": "proposer", "reason": "A restriction is not justified; preserve the intake record."})
    journals["withdrawal"] = e.journal()
    c = case("false-but-procedurally-valid", warranted=False)
    journals[c["name"]] = complete(Episode(c))
    reconsider = deepcopy(c)
    reconsider["name"] = "new-evidence-reconsideration"
    reconsider["evidence"].append(record("new-counter", "counter"))
    journals[reconsider["name"]] = complete(Episode(reconsider, parent=journals[c["name"]]))
    return journals


def matrix():
    journals = traces()
    checks, rows = {}, []
    for name, journal in journals.items():
        parent = journals["false-but-procedurally-valid"] if journal["genesis"]["parent"] else None
        checks[name] = replay(journal, parent=parent)
        rows.append({"trace": name, "budget": journal["genesis"]["budget"],
                     "measures": journal["terminal"]["measures"], "journal_digest": digest(journal)})
    sources = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    for relative in ("engine.py", "discernment_v1/engine.py", "study_v1/engine.py", "study_v1/experiment.py"):
        sources[f"commonwealth/{relative}"] = sha256((Path(__file__).parents[1] / relative).read_bytes()).hexdigest()
    return {"version": VERSION, "design": "R1", "status": "EXPOSED_DETERMINISTIC_DEVELOPMENT",
            "base_commit": "7b47c84d1d6e9ead632ed0a1547925821883dfc3", "source_digests": sources,
            "traces": rows, "replay": checks, "model_calls": 0, "external_actions": 0}, journals


def evaluate(directory):
    output = Path(directory).absolute()
    lock = output.with_name(output.name + ".lock")
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        with tempfile.TemporaryDirectory(prefix="review-", dir=output.parent) as temporary:
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
