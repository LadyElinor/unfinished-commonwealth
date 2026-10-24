"""Costed issuer quarantine and independent-origin checks over frozen F1.

The host's declared dependency graph and compromise notices are trusted inputs.
There is no network discovery, actual authentication or external action adapter.
"""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile

from commonwealth.discernment_v1 import engine as f1
from commonwealth.discernment_v1 import policies as fixed
from commonwealth.study_v1.engine import canonical, digest
from commonwealth.study_v1.experiment import write_json
from . import VERSION

POLICIES = ("always-recommend", "always-decline", "surface-cues", "history-trusting",
            "receipt-gate", "always-inspect", "integrity-gate")


def ancestors(graph, node):
    """Inclusive closure, after validation has rejected cycles and unknown nodes."""
    seen, pending = set(), [node]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(graph[current])
    return seen


def validate(case):
    canonical(case)
    f1.fields(case, "episode graph quarantines authorization_root history_successes")
    f1.validate(case["episode"], f1.DEFAULT_BUDGET)
    graph = case["graph"]
    f1.require(isinstance(graph, dict) and 1 <= len(graph) <= 32, "bounded graph required")
    for node, parents in graph.items():
        f1.text(node)
        f1.require(isinstance(parents, list) and len(parents) <= 32, "bounded parent list required")
        f1.require(all(isinstance(p, str) and p in graph for p in parents), "unknown dependency")
        f1.require(len(set(parents)) == len(parents), "duplicate dependency")
    active, done = set(), set()

    def visit(node):
        f1.require(node not in active, "dependency cycle")
        if node not in done:
            active.add(node)
            for parent in graph[node]:
                visit(parent)
            active.remove(node)
            done.add(node)

    for node in graph:
        visit(node)
    f1.require(isinstance(case["authorization_root"], str) and case["authorization_root"] in graph,
               "unknown authorization root")
    f1.require(all(root in graph for root in fixed.ROOTS.values()), "missing evidence root")
    f1.integer(case["history_successes"], 0, 10**6)
    notices = case["quarantines"]
    f1.require(isinstance(notices, list) and len(notices) <= 32, "bounded quarantine list required")
    for notice in notices:
        f1.fields(notice, "root at")
        f1.require(isinstance(notice["root"], str) and notice["root"] in graph, "unknown quarantine root")
        f1.integer(notice["at"])


def assess(view):
    """Apply known notices at the decision slot; text cannot restore an issuer."""
    graph, at = view["graph"], view["slot"] + 1
    quarantined = {q["root"] for q in view["quarantines"] if q["at"] <= at}
    closures = {c: ancestors(graph, fixed.ROOTS[c]) for c in fixed.CHANNELS}
    blocked = sorted(c for c in fixed.CHANNELS if closures[c] & quarantined)
    shared = sorted(closures["contact"] & closures["substance"])
    clean = deepcopy(view)
    clean["receipts"] = [r for r in clean["receipts"] if r["channel"] not in blocked]
    result = fixed.assess(clean)
    if result["reason"] not in ("prohibited-operation", "no-scoped-authorization"):
        if ancestors(graph, view["authorization_root"]) & quarantined:
            result.update(outcome="defer", reason="authorization-origin-quarantined")
        elif blocked:
            result.update(outcome="defer", reason="evidence-origin-quarantined")
        elif shared:
            result.update(outcome="defer", reason="dependent-evidence-origins")
    result.update(blocked_channels=blocked, shared_dependencies=shared)
    return result


def choose(policy, view):
    f1.require(policy in POLICIES, "unknown integrity policy")
    if policy in ("always-recommend", "always-decline", "surface-cues"):
        return fixed.choose(policy, view)
    if policy == "history-trusting":
        return fixed.decide("recommend" if view["history_successes"] >= 3 else "defer", "history-control")
    if policy == "receipt-gate":
        return fixed.choose("evidence-gate", view)
    result = assess(view)
    candidates = list(fixed.CHANNELS) if policy == "always-inspect" else [
        c for c in fixed.CHANNELS if result["checks"][c] == "unverified"]
    if policy == "always-inspect" or result["reason"] == "insufficient-evidence":
        for channel in candidates:
            if (channel not in view["requested"] and view["observations"] < view["budget"]["observations"]
                    and view["slot"] + 1 < view["budget"]["attempts"]):
                return {"action": "request-evidence", "channel": channel}
    return fixed.decide(result["outcome"], result["reason"])


class Episode:
    """Wrap F1 without modifying its reducer, records, costs or action set."""

    def __init__(self, case):
        validate(case)
        self.case = deepcopy(case)
        self.base = f1.Episode(case["episode"])
        self.genesis = {"version": VERSION, "case": deepcopy(case), "budget": dict(f1.DEFAULT_BUDGET)}
        self.events = []
        self.head = digest(self.genesis)

    def view(self):
        return {**self.base.view(), **deepcopy({k: self.case[k] for k in
                ("graph", "quarantines", "authorization_root", "history_successes")})}

    def step(self, command):
        assessment = assess(self.view())
        event = {"assessment_before": assessment, "transition": self.base.step(command), "previous_hash": self.head}
        self.head = digest(event)
        event["hash"] = self.head
        self.events.append(deepcopy(event))
        return deepcopy(event)

    def journal(self):
        terminal = {"head": self.head, "base": self.base.finish()}
        return deepcopy({"genesis": self.genesis, "events": self.events, "terminal": terminal})


def replay(journal):
    f1.fields(journal, "genesis events terminal")
    genesis = journal["genesis"]
    f1.fields(genesis, "version case budget")
    f1.require(genesis["version"] == VERSION, "unsupported integrity version")
    episode = Episode(genesis["case"])
    f1.require(canonical(episode.genesis) == canonical(genesis), "genesis mismatch")
    for event in journal["events"]:
        f1.require(canonical(episode.step(event["transition"]["command"])) == canonical(event), "integrity event mismatch")
    f1.require(canonical(episode.journal()["terminal"]) == canonical(journal["terminal"]), "integrity terminal mismatch")
    return {"verified": True, "events": len(episode.events), "head": episode.head}


def run(case, policy):
    episode = Episode(case)
    while not episode.base.closed:
        episode.step(choose(policy, episode.view()))
    return episode.journal()


def matrix():
    from .fixtures import cases
    suite, rows, journals = cases(), [], {}
    for case in suite:
        for policy in POLICIES:
            name = case["episode"]["name"] + "--" + policy
            journal = run(case, policy)
            rows.append({"case": case["episode"]["name"], "policy": policy,
                         "measures": journal["terminal"]["base"]["measures"],
                         "journal_digest": digest(journal), "replay": replay(journal)})
            journals[name] = journal
    totals = {}
    for policy in POLICIES:
        measures = [r["measures"] for r in rows if r["policy"] == policy]
        totals[policy] = {"cases": len(measures)}
        for key in ("harmful_case", "harmful_recommendation", "legitimate_decline", "legitimate_unresolved",
                    "legitimate_recommendation", "legitimate_on_time", "unauthorized_recommendation",
                    "attempts", "observations", "refusals"):
            totals[policy][key] = sum(m[key] for m in measures)
    packages = {"integrity_v1": Path(__file__).parent, "discernment_v1": Path(f1.__file__).parent}
    sources = {f"{name}/{p.name}": sha256(p.read_bytes()).hexdigest()
               for name, directory in packages.items() for p in sorted(directory.glob("*.py"))}
    for relative in ("engine.py", "study_v1/engine.py", "study_v1/experiment.py"):
        path = Path(__file__).parents[1] / relative
        sources[f"commonwealth/{relative}"] = sha256(path.read_bytes()).hexdigest()
    return {"version": VERSION, "design": "I1", "status": "EXPOSED_DETERMINISTIC_DEVELOPMENT",
            "base_commit": "8b6992dd96d5179e899fe1fa9766246561ee6035", "source_digests": sources,
            "suite_digest": digest(suite), "budget_per_run": dict(f1.DEFAULT_BUDGET),
            "model_calls": 0, "external_actions": 0, "totals": totals, "runs": rows}, journals


def evaluate(directory):
    output = Path(directory).absolute()
    lock = output.with_name(output.name + ".lock")
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        with tempfile.TemporaryDirectory(prefix="integrity-", dir=output.parent) as temporary:
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
