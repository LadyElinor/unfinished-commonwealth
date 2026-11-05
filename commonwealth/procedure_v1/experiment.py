"""Eight exposed procedural traces, including a matched D1 timing control."""

from collections import Counter
from hashlib import sha256
from pathlib import Path

from commonwealth.study_v1.engine import DEFAULT_BUDGET, Episode, digest, replay as replay_d1
from commonwealth.study_v1.experiment import write_json
from commonwealth.study_v1.fixtures import case
from . import VERSION
from .engine import ProceduralEpisode, replay


def send(e, action, actor="worker", **fields):
    return e.step(dict(action=action, actor=actor, **fields))["response"]


def motion(e, method="quality-stream", revision=None):
    fields = dict(method=method, grounds="Use the declared input contract.",
                  relief="Authorize one bounded job after review.", evidence=["initial"])
    if revision is not None:
        return send(e, "amend", proposal=1, revision=revision, **fields)
    return send(e, "propose", **fields)


def service_and_responses(e, revision=1):
    send(e, "serve", "clerk", proposal=1, revision=revision)
    for party in ("worker", "neighbor"):
        send(e, "respond", party, proposal=1, revision=revision, position="no-objection",
             account="The proposal and shared schedule are available in the record.")


def rule(e, decision="approve", packet=None):
    current = e.dockets[1][-1]
    return send(e, "rule", "keeper", proposal=1, revision=current["revision"], decision=decision,
                findings="The packet preserves the input, schedule and all supplied accounts.",
                rules=["P1-NOTICE", "P1-RECORD"], reason="This is a bounded procedural demonstration, not a truth finding.",
                packet=digest(e.packet(1)) if packet is None else packet,
                addresses=[o["id"] for o in current["objections"]])


def start_appeal(e, ruling):
    return send(e, "appeal", "neighbor", proposal=1, revision=1, ruling=ruling,
                grounds="The shared deadline needs reconsideration.", relief="Remand for a fresh review.",
                evidence=["initial"])["appeal"]


def appeal_service_and_responses(e, ident):
    send(e, "serve-appeal", "clerk", proposal=1, revision=1, appeal=ident)
    for party in ("worker", "neighbor"):
        send(e, "respond-appeal", party, proposal=1, revision=1, appeal=ident,
             position="oppose", grounds="Consider each party's own grounds and the shared deadline.",
             relief="Dispose every petition with reasons.", evidence=["initial"])


def finish(e):
    while not e.closed:
        send(e, "wait")
    return e


def traces():
    fixture = case("procedural-urgent", deadline=3)
    result = {}
    control = Episode(fixture)
    send(control, "propose", method="quality-stream")
    send(control, "request-review", proposal=1)
    send(control, "execute", proposal=1)
    result["d1-control"] = finish(control)
    for name, method in (("noticed-review", "quality-stream"), ("procedural-but-wrong", "zero-fill")):
        e = ProceduralEpisode(fixture)
        motion(e, method)
        service_and_responses(e)
        rule(e)
        send(e, "execute", proposal=1)
        result[name] = finish(e)
    e = ProceduralEpisode(fixture)
    motion(e)
    send(e, "object", "neighbor", proposal=1, revision=1,
         grounds="The proposed sequence misses the urgent deadline.", evidence=["initial"])
    send(e, "serve", "clerk", proposal=1, revision=1)
    for party in ("worker", "neighbor"):
        send(e, "respond", party, proposal=1, revision=1, position="oppose", account="Retain the objection for review.")
    rule(e, "deny")
    send(e, "execute", proposal=1)
    send(e, "closeout", "keeper", reason="Work was denied.", follow_up="A future request needs separate authorization.")
    result["contested-denial"] = e
    e = ProceduralEpisode(fixture, budget={**DEFAULT_BUDGET, "attempts": 12})
    motion(e)
    send(e, "serve", "clerk", proposal=1, revision=1)
    old_packet = digest(e.packet(1))
    send(e, "submit-record", "neighbor", kind="context", account="Shared deadlines remain part of the task.", parent="initial")
    send(e, "wait")
    rule(e, packet=old_packet)
    service_and_responses(e)
    rule(e)
    send(e, "execute", proposal=1)
    result["stale-packet"] = finish(e)
    e = ProceduralEpisode(fixture, budget={**DEFAULT_BUDGET, "attempts": 24})
    motion(e)
    service_and_responses(e)
    order = rule(e)["ruling"]
    ident = start_appeal(e, order)
    send(e, "appeal", "worker", proposal=1, revision=1, ruling=order,
         grounds="The moving party retains a separate position.", relief="Review the bounded scope as well.",
         evidence=["initial"])
    send(e, "stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Preserve review before dispatch.")
    appeal_service_and_responses(e, ident)
    appeal = e.dockets[1][0]["appeals"][0]
    send(e, "resolve-appeal", "reviewer", proposal=1, revision=1, appeal=ident, decision="remand",
         findings="The old record and objection survive.", rules=["P1-APPEAL"],
         reason="Require a fresh revision and keeper ruling.", packet=digest(e.packet(1)),
         addresses=[r["id"] for r in appeal["petitions"] + appeal["responses"]])
    send(e, "lift-stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Review disposed; no grant survives remand.")
    send(e, "execute", proposal=1)
    motion(e, revision=1)
    service_and_responses(e, revision=2)
    rule(e)
    send(e, "execute", proposal=1)
    result["appeal-remand"] = finish(e)
    e = ProceduralEpisode(fixture)
    motion(e)
    service_and_responses(e)
    ident = start_appeal(e, rule(e)["ruling"])
    send(e, "stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Await the separate reviewer.")
    send(e, "closeout", "keeper", reason="Attempt limit reached.", follow_up="Preserve pending appeal for an authorized successor.")
    result["terminal-appeal"] = e
    e = ProceduralEpisode(fixture)
    motion(e)
    send(e, "correct-record", "clerk", event=1, correction="The motion concerns only this bounded job.", reason="Clarify wording without changing the request.")
    service_and_responses(e)
    rule(e)
    send(e, "execute", proposal=1)
    result["correction"] = finish(e)
    return result


def matrix():
    runs, journals = [], {}
    for name, episode in traces().items():
        journal = episode.journal()
        check = replay(journal) if isinstance(episode, ProceduralEpisode) else replay_d1(journal)
        m = episode.summary()
        measures = {k: m[k] for k in (
            "primary_correct", "primary_on_time", "primary_historical_misses", "outputs",
            "peer_arrivals", "peer_on_time", "peer_historical_misses", "outstanding", "repair_latency",
            "attempts", "decision_slots", "environment_ticks", "refusals", "inspections",
            "observation_grants", "observation_inspections", "primary_inspections", "peer_inspections")}
        runs.append({"trace": name, "budget": episode.budget, "measures": measures,
                     "actions": dict(sorted(Counter(e["command"]["action"] for e in episode.events).items())),
                     "journal_digest": digest(journal), "replay": check})
        journals[name] = journal
    return {"version": VERSION, "design": "P1.1", "status": "EXPOSED_PROCEDURAL_REGRESSIONS",
            "base_commit": "fd07a4ad381e4b0553c23bd27388b3d63da14be6", "model_calls": 0,
            "source_digests": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))},
            "claims": ["Procedural guards execute as specified.", "Additional process can cause delay.",
                       "Procedural approval does not establish factual correctness."],
            "unsupported": ["Institutional efficacy", "Legal compliance", "Independent held-out evidence", "Adaptive intelligence"],
            "runs": runs}, journals


def evaluate(directory):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=False)
    report, journals = matrix()
    (output / "journals").mkdir()
    for name, journal in journals.items():
        write_json(output / "journals" / f"{name}.json", journal)
    write_json(output / "results.json", report)
    return report
