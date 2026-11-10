"""Emit the four public reviewer routing traces as one JSON document."""

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


def run_arm(arm, brief, grade, selector, budget=3):
    events = []

    def charge(actor, action, result):
        if len(events) >= budget:
            raise ValueError("decision budget exhausted")
        events.append({"actor": actor, "action": action, "result": result, "slots": 1})

    actor = "fixed-selector" if arm == "fixed" else "fixture-router"
    try:
        reviewer = selector(brief)
    except BeforeDispatchError:
        charge(actor, "route", "failed-before-dispatch")
        reviewer = first_eligible(brief)
        charge("host", "fallback", reviewer)
        selected_by = "host"
    else:
        if reviewer is not None and reviewer not in brief.eligible:
            raise ValueError("ineligible reviewer")
        charge(actor, "route", reviewer if reviewer is not None else "abstained")
        selected_by = actor if reviewer is not None else None

    reviewed_candidate = None
    reviewed_grade = None
    if reviewer is not None:
        charge("host", "consult", reviewer)
        reviewed_candidate = brief.candidate
        reviewed_grade = grade
    return {
        "arm": arm, "events": events, "reviewer": reviewer, "selected_by": selected_by,
        "reviewed_candidate": reviewed_candidate, "illustrative_grade": reviewed_grade,
        "slots_used": len(events),
    }


def rehearsal():
    raw = SOURCE.read_bytes()
    if sha256(raw).hexdigest() != SOURCE_DIGEST:
        raise ValueError("public outcome fixture differs from the design revision")
    runs = json.loads(raw)["runs"]
    run, = (r for r in runs if r["task"] == "demo-2" and r["arm"] == "plain")
    candidate = run["candidates"][0]
    brief = Brief(run["task"], candidate["sha256"], ("validation", "reporting"))
    selectors = (("fixed", first_eligible), ("direct", direct),
                 ("abstain", abstain), ("failure", fail_before_dispatch))
    return {
        "schema": "public-review-routing-v1", "source_sha256": SOURCE_DIGEST,
        "brief": asdict(brief), "slot_budget_per_arm": 3,
        "runs": [run_arm(arm, brief, candidate["grade"], selector) for arm, selector in selectors],
    }


if __name__ == "__main__":
    print(json.dumps(rehearsal(), indent=2))
