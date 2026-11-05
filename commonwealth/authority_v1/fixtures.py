"""Entirely fictional, exposed development examples, not political case findings."""

from copy import deepcopy
from commonwealth.study_v1.engine import digest
from .records import FIELDS, SCHEMA


def packet():
    answers = {key: "Synthetic declaration; supplied by the fixture author." for key in FIELDS}
    answers.update(case="Maintenance of fictional service A", assessment="A supplied sensor reports a fault.",
                   legitimacy="legal authority", stage="proposal", source_status="primary record reviewed",
                   authority_status="supported by cited instrument", source_record="Synthetic sensor record S1, slot 0.",
                   counterevidence="Alternative: sensor fault. Stop and reassess if a contrary observation arrives.",
                   action="Temporarily set the service A maintenance flag.", proposer="worker", decision_maker="steward",
                   authority_basis="Host-declared fictional delegation D1; no public mandate.",
                   affected_people="Service operator and service users.",
                   representation="Two host-declared representatives. Neither silence nor shared controller implies assent.",
                   trigger="Host reports the fault; an unaffected sensor would weaken the assessment.",
                   scope="One fictional maintenance flag; no external operations.", expiry="Slot 20, without automatic renewal.",
                   dissent="Affected role can preserve a challenge; reviewer addresses each challenge explicitly.",
                   reversal="Predelegated halt and independently specified remedy; keep historical costs.",
                   reviewer="Synthetic reviewer role; controller separation is host-supplied.",
                   public_language="Synthetic public statement P1: review the proposed repair.",
                   working_language="Synthetic working record W1: conditional maintenance proposal.",
                   analyst_language="No intent or real-world authority follows from these supplied labels.")
    return {"schema": SCHEMA, "answers": answers}


def case(name="bounded-authority"):
    request = {"operation": "set-maintenance", "target": "service-A", "before": False, "after": True}
    return {"name": name, "packet": packet(), "request": request,
            "mandate": {"issuer": "steward", "holder": "worker", "scope": digest(request),
                        "basis": "Fictional host delegation D1", "valid_from": 0, "valid_until": 20, "revoked_at": None},
            "controllers": {r: r + "-controller" for r in ("worker", "steward", "reviewer", "affected")},
            "affected": ["operator", "users"], "represented": ["operator", "users"],
            "selection": "Host-declared representatives; not verified public representation.",
            "trigger": {"status": "met", "record": "Synthetic sensor S1", "falsifier": "Contrary independent sensor"},
            "reviewer_available": True, "remedy_delegated": True, "warranted": True}


def statement(register):
    return {"actor": "fictional-council", "decision": "service-A", "register": register,
            "stage": "proposal", "legitimacy": "legal authority", "position": "temporary-maintenance",
            "condition": "confirmed-fault", "event_at": 10, "publication_at": 11, "version": "v1",
            "source_group": "record-" + register, "source_status": "primary record reviewed",
            "locator": "Synthetic record, paragraph 1", "account": "Consider a temporary intervention if the fault is confirmed."}


def language_cases():
    base = {register: statement(register) for register in ("public", "working", "analyst")}
    cases = {"same-position-different-tone": deepcopy(base)}
    cases["same-position-different-tone"]["working"]["account"] = "Use this opening to renew the service."
    for name, key, value in (
        ("reported-excerpt", "source_status", "reported excerpt only"),
        ("proposal-not-execution", "stage", "execution"),
        ("acceptance-not-legal-authority", "legitimacy", "public acceptance"),
        ("different-condition", "condition", "unconfirmed-fault"),
        ("different-actor", "actor", "another-council"),
        ("different-period", "event_at", 9),
        ("curated-difference", "position", "permanent-maintenance"),
        ("repeated-origin", "source_group", "record-public"),
    ):
        cases[name] = deepcopy(base)
        cases[name]["working"][key] = value
    cases["analyst-overstatement"] = deepcopy(base)
    cases["analyst-overstatement"]["analyst"].update(position="secret-takeover", stage="execution",
                                                       account="An analyst alleges that the proposal was secretly executed.")
    return cases
