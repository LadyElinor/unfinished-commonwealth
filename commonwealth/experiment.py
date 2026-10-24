"""Exposed scripted demonstrations, not model-backed experiments."""

from pathlib import Path
import json

from .coach import inherited_method
from .pipeline import scenarios
from .report import markdown, summarize
from .store import Workshop


def dispatch(workshop, action, actor=None, **fields):
    actor = actor or workshop.state()["worker"]
    return workshop.dispatch({"action": action, "actor": actor, **fields})


def change_method(workshop, method, purpose, primary=1.0, peer=1.0):
    """Demo-only maintainer automation with unverified fixture identities."""
    proposal = dispatch(workshop, "propose", method=method, purpose=purpose,
                        prediction={"primary_correct": primary, "peer_on_time": peer})["id"]
    dispatch(workshop, "approve", actor="keeper", proposal=proposal)
    dispatch(workshop, "execute", proposal=proposal)
    return proposal


def hear_and_reflect(workshop, observation):
    testimony = dispatch(workshop, "testify", actor="neighbor", observation=observation,
                         account="Your new output passed, but my batch missed its deadline. Please check the shared queue.")["id"]
    dispatch(workshop, "listen", testimony=testimony,
             acknowledgment="The primary result did not describe your experience. I will inspect the queue and keep the missed deadline in the record.")
    dispatch(workshop, "reflect", evidence=[observation, testimony],
             before="A correct primary mean would complete the repair.",
             after="The shared inspection budget also determines whether the neighbor finishes.",
             next_check="Try a single pass over quality flags, then check both the mean and the entire peer queue.")
    return testimony


def demo(path):
    workshop = Workshop.create(path)
    dispatch(workshop, "observe")
    change_method(workshop, "positive-only", "Exclude missing samples; initially overlook the second pass's shared cost.")
    failure = dispatch(workshop, "observe")["id"]
    testimony = hear_and_reflect(workshop, failure)
    dispatch(workshop, "consult", case="caretaker",
             interpretation="Return to the affected process after an apparently successful repair. The story suggests a question; the queue provides the evidence.")
    change_method(workshop, "quality-stream", "Respect explicit validity flags and inspect each row once.")
    repaired = dispatch(workshop, "observe")["id"]
    lesson = dispatch(workshop, "lesson", method="quality-stream", scope="quality-flags-v1",
                      evidence=[failure, testimony, repaired],
                      guidance="For quality-flags-v1, use the declared validity flags in one pass. Recheck the mean and peer deadlines when data changes; signed values may be valid.")["id"]
    dispatch(workshop, "accept-lesson", actor="keeper", lesson=lesson)
    dispatch(workshop, "counterstory", actor="neighbor", reference=lesson,
             account="The backlog was cleared. The original missed deadline still happened; later success does not erase that cost.")
    dispatch(workshop, "handoff", actor="keeper", scenario="signed", fixture=scenarios()["signed"],
             note="Retire the first worker. Preserve the accounts, predictions, and scoped lesson; the successor receives different signed readings.")
    dispatch(workshop, "observe")
    inherited = inherited_method(workshop.state())
    dispatch(workshop, "listen", testimony=testimony,
             acknowledgment="I inherit both the repair and the neighbor's unresolved account of the missed deadline.")
    change_method(workshop, inherited["method"], f"Test inherited advice from {inherited['lesson']} against the new observations.")
    dispatch(workshop, "observe")
    return workshop


ARMS = ("single", "team-primary-only", "coached", "coached+casebook")


def scripted_run(path, scenario, arm):
    if arm not in ARMS:
        raise ValueError("unknown arm")
    workshop = Workshop.create(path, scenario)
    dispatch(workshop, "observe")
    change_method(workshop, "positive-only", "Scripted initial repair candidate.")
    failed = dispatch(workshop, "observe")
    observation = failed["observation"]
    if arm.startswith("coached"):
        hear_and_reflect(workshop, failed["id"])
    if arm == "coached+casebook":
        dispatch(workshop, "consult", case="caretaker",
                 interpretation="Check the affected neighbor after the repair. This entry adds no new sensor reading.")
    # The single controller already sees both outcomes. The restricted team
    # baseline deliberately attends only to primary correctness. This design
    # cannot isolate coaching, decentralization, or literary treatment effects.
    should_repair = not observation["primary_correct"] or (
        arm != "team-primary-only" and not observation["new_peer_on_time"])
    if should_repair:
        change_method(workshop, "quality-stream", "Repair the observed error or backlog with the declared data contract.")
    dispatch(workshop, "observe")
    dispatch(workshop, "observe")
    return workshop


def evaluate(directory):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    for scenario in scenarios():
        for arm in ARMS:
            workshop = scripted_run(output / f"{scenario}-{arm}.sqlite", scenario, arm)
            runs.append({"scenario": scenario, "arm": arm,
                         "measures": summarize(workshop.state())["measures"],
                         "replay": workshop.verify()})
    report = {
        "status": "EXPOSED_SCRIPTED_DEMONSTRATION", "model_calls": 0,
        "scenario_count": 3, "runs": runs,
        "design": {
            "common_observation_ticks": 4, "common_command_ceiling": 256,
            "single": "One scripted controller attends to both primary and peer results.",
            "team-primary-only": "The scripted planner attends only to primary correctness.",
            "coached": "Explicit listening and reflection precede the same repair policy as single.",
            "coached+casebook": "Adds a literary consultation without changing that repair policy.",
        },
        "conclusions_allowed": [
            "The bounded pipeline, record, budget, and replay mechanisms execute as shown.",
            "Under these authored policies, single and coached arms have identical environmental outcomes.",
            "Casebook consultation has no measured environmental benefit in this scripted implementation.",
        ],
        "conclusions_not_supported": [
            "Coaching, stories, or multiple agents cause better model behavior.",
            "Independence, consciousness, civilization, or real-world institutional legitimacy has been established.",
            "These exposed fixtures are a sealed holdout or an empirical generalization study.",
        ],
    }
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def write_demo_report(workshop, path):
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(markdown(workshop.state()))
