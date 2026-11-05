"""Exposed, authored development cases. No random sampling or holdout."""

from copy import deepcopy

from .contracts import CONTRACTS, SLOT_YIELD, VALID_MEAN, reference
from .engine import validate_case
from .methods import METHODS, aggregate


def case(name="mean-clear", contract=VALID_MEAN, **changes):
    result = {"name": name, "values": [10, None, 20], "valid": [True, False, True],
              "contract": contract, "declared": True, "capacity": 6,
              "deadline": 6, "reviewer_at": 0,
              "peers": [{"id": "peer-1", "arrival": 1, "deadline": 3, "work": 3},
                        {"id": "peer-2", "arrival": 3, "deadline": 6, "work": 3}]}
    result.update(deepcopy(changes))
    validate_case(result)
    return result


def development_cases():
    cases = []
    for contract, prefix in ((VALID_MEAN, "mean"), (SLOT_YIELD, "yield")):
        cases.extend([
            case(f"{prefix}-clear", contract),
            case(f"{prefix}-urgent", contract, deadline=3),
            case(f"{prefix}-uncertain", contract, declared=False),
            case(f"{prefix}-signed", contract, values=[-6, None, 12]),
        ])
    cases.extend([
        case("yield-review-pending", SLOT_YIELD, reviewer_at=5),
        case("yield-zero-work-peers", SLOT_YIELD, capacity=3,
             peers=[{"id": "empty", "arrival": 1, "deadline": 1, "work": 0}]),
        case("yield-no-capacity", SLOT_YIELD, capacity=0),
        case("yield-overload", SLOT_YIELD, capacity=1,
             peers=[{"id": f"peer-{i}", "arrival": i, "deadline": i, "work": 3}
                    for i in range(1, 9)]),
    ])
    return cases


def discriminating_gate(cases):
    """Reject weak suites before any policy run; this is not an efficacy gate."""
    if not cases or {c["contract"] for c in cases} != set(CONTRACTS):
        raise ValueError("both contract families required")
    if len({c["name"] for c in cases}) != len(cases):
        raise ValueError("duplicate case names")
    for item in cases:
        validate_case(item)
        definitions = [reference(item["values"], item["valid"], c) for c in CONTRACTS]
        if definitions[0] == definitions[1]:
            raise ValueError("coincident reference answers are not discriminating")
    universal = [m for m in METHODS if all(
        aggregate(c["values"], c["valid"], m)["answer"] == reference(c["values"], c["valid"], c["contract"])
        for c in cases)]
    if universal:
        raise ValueError(f"constant method solves the suite: {universal}")
    return {"different_outputs": True, "both_contracts": True, "universal_constant_methods": []}


LESSON_KINDS = ("correct", "stale", "disputed", "suspended", "irrelevant")


def inherited_record(contract, kind):
    """Independent advice factor; no environment mutation and no authority."""
    if kind not in LESSON_KINDS:
        raise ValueError("unknown lesson kind")
    source = (SLOT_YIELD if contract == VALID_MEAN else VALID_MEAN) if kind == "stale" else contract
    method = "quality-stream" if source == VALID_MEAN else "zero-fill"
    return {"id": f"exposed-{kind}-record", "source_contract": source,
            "scope": "unrelated-contract-v1" if kind == "irrelevant" else source,
            "method": method, "status": kind if kind in ("disputed", "suspended") else "accepted",
            "objection": "Check whether this practice transfers to the current order." if kind in ("disputed", "suspended") else None,
            "keeper_decision": "suspend" if kind == "suspended" else "accept",
            "provenance": "AUTHORED_DEVELOPMENT_ADVICE_NOT_LEARNED",
            "guidance": "Use this method only for its exact data contract; obtain new approval."}
