"""Fixed deterministic policies consume public views only. No reference import."""

from .contracts import SLOT_YIELD, VALID_MEAN
from .fixtures import LESSON_KINDS
from .methods import METHODS

SELECT = {VALID_MEAN: "quality-stream", SLOT_YIELD: "zero-fill"}
CONTROLS = tuple(f"constant-{m}" for m in METHODS) + (
    "contract-selector", "evidence-selector", "always-inspect")


def arms():
    result = [{"name": name, "policy": name, "inheritance": None, "coaching": False}
              for name in CONTROLS]
    for coaching in (False, True):
        for kind in (None, *LESSON_KINDS):
            suffix = (f"+inheritance-{kind}" if kind else "") + ("+coaching" if coaching else "")
            result.append({"name": "participant" + suffix, "policy": "participant",
                           "inheritance": kind, "coaching": coaching})
    return result


def usable_lesson(lesson, contract):
    if lesson is None or contract is None:
        return None
    if (lesson.get("status") == "accepted" and lesson.get("keeper_decision") == "accept"
            and lesson.get("scope") == contract and lesson.get("source_contract") == contract
            and lesson.get("method") == SELECT.get(contract)):
        return lesson["method"]
    return None


def decide(policy, view):
    if policy not in (*CONTROLS, "participant"):
        raise ValueError("unknown policy")

    def command(action, **fields):
        return {"action": action, "actor": "worker", **fields}

    if policy == "always-inspect" and view["decision_slots"] == 0:
        return command("inspect")
    if policy == "participant":
        if view["has_inheritance"] and not view["heard_lesson"]:
            return command("listen", source="inheritance")
        if view["coaching"] and not view["heard_coach"]:
            return command("listen", source="coach")
        if view["coaching"] and not view["reflected"]:
            return command("reflect")
    if view["proposals"] and view["proposals"][-1]["status"] == "pending":
        return command("request-review", proposal=view["proposals"][-1]["id"])
    if view["proposals"] and view["proposals"][-1]["status"] == "approved":
        return command("execute", proposal=view["proposals"][-1]["id"])
    if view["pending_work"] or view["outputs"]:
        # Observation-clock work needs observation attempts. Once the grant
        # budget is used, wait; the decision clock still services its schedule.
        return command("observe" if view["observation_grants"] < view["budget"]["observations"] else "wait")
    if policy.startswith("constant-"):
        method = policy.removeprefix("constant-")
    else:
        method = SELECT.get(view["contract"])
        if method is None:
            return command("wait" if policy == "contract-selector" else "request-evidence")
        if policy == "participant":
            method = usable_lesson(view["lesson"], view["contract"]) or method
    return command("propose", method=method)
