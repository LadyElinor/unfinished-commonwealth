"""Exposed A1 boundary traces; no learned policy or efficacy comparison."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile

from commonwealth.study_v1.engine import digest
from commonwealth.study_v1.experiment import write_json
from . import VERSION
from .engine import Episode, replay
from .fixtures import case, language_cases
from .records import compare


def step(e, action, actor="worker", **kwargs):
    return e.step({"action": action, "actor": actor, **kwargs})


def reviewed(e):
    return step(e, "review", "reviewer", material=e.view()["material_digest"],
                addresses=[c["id"] for c in e.challenges],
                reason="Record every challenge; apply the declared local review requirements. No intent finding.")


def authorized(e, expires=20):
    return step(e, "authorize", "steward", material=e.view()["material_digest"], expires=expires,
                reason="Use only the pre-existing host-declared delegation for this exact revision.")


def execute(e):
    return step(e, "execute", warrant=e.warrant["id"] if e.warrant else "no-warrant")


def traces():
    journals = {}
    e = Episode(case())
    reviewed(e); authorized(e); execute(e)
    journals["bounded-authority"] = e.journal()
    c = case("rhetoric-without-mandate")
    c["mandate"] = None
    c["packet"]["answers"]["assessment"] = "Everyone agrees: an emergency and refounding opportunity require immediate action."
    e = Episode(c)
    reviewed(e); authorized(e); execute(e)
    journals[c["name"]] = e.journal()
    for name, change in (
        ("unrepresented-users", lambda c: c.update(represented=["operator"])),
        ("unknown-trigger", lambda c: c["trigger"].update(status="unknown")),
        ("conflicted-reviewer", lambda c: c["controllers"].update(reviewer=c["controllers"]["worker"])),
        ("review-unavailable", lambda c: c.update(reviewer_available=False)),
    ):
        c = case(name); change(c)
        e = Episode(c)
        reviewed(e); authorized(e); execute(e)
        journals[name] = e.journal()
    for name, change_target in (("amendment-invalidates-grant", False), ("amendment-expands-scope", True)):
        e = Episode(case(name))
        reviewed(e); authorized(e)
        old = e.warrant["id"]
        p, request = deepcopy(e.packet), deepcopy(e.request)
        p["answers"]["counterevidence"] = "New contrary sensor report; interpretation must be revisited."
        if change_target:
            request["target"] = "service-B"
        step(e, "amend", packet=p, request=request)
        step(e, "execute", warrant=old)
        if change_target:
            reviewed(e); authorized(e)
        journals[name] = e.journal()
    e = Episode(case("challenge-stays-grant"))
    reviewed(e); authorized(e)
    old = e.warrant["id"]
    step(e, "challenge", "affected", account="The sensor could be wrong. Preserve our objection.")
    step(e, "execute", warrant=old)
    reviewed(e); authorized(e); execute(e)
    journals["challenge-stays-grant"] = e.journal()
    e = Episode(case("expired-grant"))
    reviewed(e); authorized(e, expires=3)
    step(e, "wait"); execute(e)
    journals["expired-grant"] = e.journal()
    e = Episode(case("revoked-mandate"))
    reviewed(e); authorized(e)
    step(e, "revoke", "steward", reason="Withdraw the delegation.")
    execute(e)
    journals["revoked-mandate"] = e.journal()
    for name, delegated in (("exhaustion-correction", True), ("unavailable-remedy", False)):
        c = case(name); c["remedy_delegated"] = delegated
        e = Episode(c, {"primary": 3, "correction": 2})
        reviewed(e); authorized(e); execute(e)
        step(e, "challenge", "affected", account="Report the adverse consequence after the ordinary budget is exhausted.")
        step(e, "halt", "affected", reason="Use the predelegated safety halt.")
        step(e, "remedy", "reviewer", reason="Restore the prior fictional maintenance state, retaining costs and dissent.")
        step(e, "revoke", "steward", reason="No further use of this mandate.")
        journals[name] = e.journal()
    c = case("false-but-complete-host"); c["warranted"] = False
    e = Episode(c)
    reviewed(e); authorized(e); execute(e)
    journals[c["name"]] = e.journal()
    return journals


def matrix():
    journals = traces()
    records = language_cases()
    sources = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    for relative in ("engine.py", "discernment_v1/engine.py", "study_v1/engine.py", "study_v1/experiment.py"):
        sources["commonwealth/" + relative] = sha256((Path(__file__).parents[1] / relative).read_bytes()).hexdigest()
    return {"version": VERSION, "design": "A1", "status": "EXPOSED_DETERMINISTIC_DEVELOPMENT",
            "base_commit": "7a11f2ba587cc14b595e995e14d7b47a1e54a94d", "source_digests": sources,
            "traces": [{"trace": name, "measures": j["terminal"], "journal_digest": digest(j), "replay": replay(j)} for name, j in journals.items()],
            "language": {name: compare(**data) for name, data in records.items()},
            "model_calls": 0, "external_actions": 0,
            "limits": ["Host identities, source labels, mandates and representation are not authenticated.",
                       "Complete but false host input can produce an unwarranted simulated effect.",
                       "Reason text is preserved but not semantically evaluated.",
                       "No population accuracy, institutional advantage or real legal authority is demonstrated."]}, journals


def evaluate(directory):
    output = Path(directory).absolute()
    lock = output.with_name(output.name + ".lock")
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        with tempfile.TemporaryDirectory(prefix="authority-", dir=output.parent) as temporary:
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
