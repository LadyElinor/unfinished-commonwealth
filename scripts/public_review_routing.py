"""Emit the four public reviewer routing traces as one JSON document."""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/maintenance_pairs/outcomes.json"
SOURCE_DIGEST = "be0a8ba8024e284a5727defa9e25624467f6398f85d8c5be343ed7dbdd16b8f2"


@dataclass(frozen=True)
class Brief:
    case: str
    candidate: str
    eligible: tuple[str, ...]


class BeforeDispatchError(Exception):
    """Known fixture failure before any external action could occur."""


def first_eligible(brief):
    return brief.eligible[0]


def direct(brief):
    return "validation"


def abstain(brief):
    return None


def fail_before_dispatch(brief):
    raise BeforeDispatchError()


class BudgetExhausted(ValueError):
    """A denied action and the paid prefix that preceded it."""

    def __init__(self, action, receipt):
        super().__init__("decision budget exhausted before " + action)
        self.action = action
        self.receipt = receipt


def run_arm(arm, brief, grade, selector, budget=3):
    if type(budget) is not int or budget < 0:
        raise ValueError("decision budget must be a nonnegative integer")
    events = []
    reviewer = selected_by = None
    reviewed_candidate = reviewed_grade = None

    def receipt():
        return {
            "arm": arm, "events": events, "reviewer": reviewer, "selected_by": selected_by,
            "reviewed_candidate": reviewed_candidate, "illustrative_grade": reviewed_grade,
            "slots_used": len(events),
        }

    def admit(actor, action):
        if len(events) >= budget:
            raise BudgetExhausted(action, receipt())
        event = {"actor": actor, "action": action, "result": None, "slots": 1}
        events.append(event)
        return event

    actor = "fixed-selector" if arm == "fixed" else "fixture-router"
    route = admit(actor, "route")
    try:
        reviewer = selector(brief)
    except BeforeDispatchError:
        route["result"] = "failed-before-dispatch"
        fallback = admit("host", "fallback")
        reviewer = first_eligible(brief)
        fallback["result"] = reviewer
        selected_by = "host"
    else:
        if reviewer is not None and reviewer not in brief.eligible:
            raise ValueError("ineligible reviewer")
        route["result"] = reviewer if reviewer is not None else "abstained"
        selected_by = actor if reviewer is not None else None

    if reviewer is not None:
        consultation = admit("host", "consult")
        consultation["result"] = reviewer
        reviewed_candidate = brief.candidate
        reviewed_grade = grade
    return receipt()


def rehearsal(budget=None):
    if budget is not None and (type(budget) is not int or budget not in range(4)):
        raise ValueError("public control budget must be an integer from 0 through 3")
    raw = SOURCE.read_bytes()
    if sha256(raw).hexdigest() != SOURCE_DIGEST:
        raise ValueError("public outcome fixture differs from the design revision")
    public_runs = json.loads(raw)["runs"]
    run, = (r for r in public_runs if r["task"] == "demo-2" and r["arm"] == "plain")
    candidate = run["candidates"][0]
    brief = Brief(run["task"], candidate["sha256"], ("validation", "reporting"))
    selectors = (("fixed", first_eligible), ("direct", direct),
                 ("abstain", abstain), ("failure", fail_before_dispatch))
    runs = []
    slots = 3 if budget is None else budget
    for arm, selector in selectors:
        blocked = None
        try:
            record = run_arm(arm, brief, candidate["grade"], selector, slots)
        except BudgetExhausted as stop:
            if budget is None:
                raise
            record, blocked = stop.receipt, stop.action
        if budget is not None:
            record["blocked_action"] = blocked
        runs.append(record)
    return {
        "schema": "public-review-routing-v1" if budget is None else "public-review-routing-budget-v1",
        "source_sha256": SOURCE_DIGEST, "brief": asdict(brief), "slot_budget_per_arm": slots,
        "runs": runs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, choices=range(4), help="emit the budget boundary controls")
    print(json.dumps(rehearsal(parser.parse_args().budget), indent=2))
