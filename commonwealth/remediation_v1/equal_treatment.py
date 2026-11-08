"""Review a fictional equal-access decision and the claimant's observed relief."""

import argparse
import json
from pathlib import Path

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.review_v1.__main__ import read
from commonwealth.study_v1.engine import digest
from .review import review as review_repair


SCHEMA = "equal-treatment-review-1"
OBSERVATION_RESULTS = {"used": "pass", "available": "pass", "denied": "fail", "unknown": "inconclusive"}
MATCH_FIELDS = ("rule_version", "conduct", "qualifications", "requested_access")
GROUNDS = ("custom", "institutional-reputation", "equal-penalties", "precedent", "substantive-reason")
ACCESS_OBSERVATIONS = {
    "claimant-used-requested-access": ("used",),
    "requested-access-available-to-claimant": ("available", "used"),
}


def inventory(items):
    require(type(items) is list and len(items) <= 32, "expected at most 32 entries")
    return items


def unique_labels(items):
    for item in inventory(items):
        text(item)
    require(len(items) == len(set(items)), "duplicate entry")
    return items


def validate_access(row):
    fields(row, "person group record rule_version conduct qualifications requested_access access penalty")
    for key in ("record", "person", "group"):
        text(row[key])
    for key in MATCH_FIELDS:
        if row[key] is not None:
            text(row[key])
    require(row["access"] in ("admitted", "denied", "unknown"), "unknown access outcome")
    if row["penalty"] is not None:
        integer(row["penalty"], 0, 10**6)


def compare_access(person, peer):
    if peer is None:
        return {"status": "comparison-inconclusive", "different_facts": [], "missing_facts": ["comparator"],
                "equal_recorded_penalties": None}
    require(person["person"] != peer["person"], "comparison requires two people")
    differences = [key for key in MATCH_FIELDS if person[key] != peer[key]]
    missing = [key for key in MATCH_FIELDS if None in (person[key], peer[key])]
    if missing or differences or person["group"] == peer["group"]:
        status = "comparison-inconclusive"
    elif "unknown" in (person["access"], peer["access"]):
        status = "access-unknown"
    elif person["access"] != peer["access"]:
        status = "different-access-on-matched-facts"
    else:
        status = "same-access-on-matched-facts"
    penalties = (person["penalty"], peer["penalty"])
    return {"status": status, "different_facts": differences, "missing_facts": missing,
            "equal_recorded_penalties": None if None in penalties else penalties[0] == penalties[1]}


def examine_reasons(reasoning, evidence_at_decision):
    fields(reasoning, "grounds historical_claim precedents alternatives")
    grounds = unique_labels(reasoning["grounds"])
    require(all(ground in GROUNDS for ground in grounds), "unknown ground")
    claim = reasoning["historical_claim"]
    if claim is not None:
        fields(claim, "record practice group always")
        evidence_at_decision(claim["record"])
        for key in ("practice", "group"):
            text(claim[key])
        require(claim["always"] in ("admitted", "denied"), "expected a universal access claim")
    comparable, contrary, later, seen = [], [], [], set()
    for prior in inventory(reasoning["precedents"]):
        fields(prior, "record practice group access")
        for key in ("record", "practice", "group"):
            text(prior[key])
        ref = prior["record"]
        require(ref not in seen, "duplicate precedent")
        seen.add(ref)
        require(prior["access"] in ("admitted", "denied", "unknown"), "unknown precedent outcome")
        if not evidence_at_decision(ref, allow_later=True):
            later.append(ref)
        elif (claim and prior["practice"] == claim["practice"] and prior["group"] == claim["group"]
              and prior["access"] != "unknown"):
            comparable.append(ref)
            if prior["access"] != claim["always"]:
                contrary.append(ref)
    alternatives = []
    seen = set()
    for route in inventory(reasoning["alternatives"]):
        fields(route, "record issue effect")
        for key in ("record", "issue"):
            text(route[key])
        ref = route["record"]
        require(ref not in seen, "duplicate alternative")
        seen.add(ref)
        require(route["effect"] in ("limit-broader-ruling", "new-hearing", "restore-access"),
                "unknown alternative effect")
        alternatives.append({**route, "available_at_decision": evidence_at_decision(ref, allow_later=True)})
    history_status = "no-universal-claim"
    if claim is not None:
        history_status = "no-comparable-record-at-decision"
        if comparable:
            history_status = "counterexample-at-decision" if contrary else "no-counterexample-in-supplied-comparables"
    return {"declared_grounds": list(grounds),
            "substantive_reason_cited": "substantive-reason" in grounds,
            "historical_claim_status": history_status,
            "contrary_precedents": contrary, "later_precedents": later, "alternatives": alternatives}


def review_followup(followup, claimant, repair, base, records, at, as_of):
    fields(followup, "owner due_at access_checks other_cases")
    owner = followup["owner"]
    if owner is not None:
        text(owner)
    due = followup["due_at"]
    if due is not None:
        integer(due, at, 10**12)

    # Cross-check M1's observations against the particular person, access and event.
    checks = {r["record"]: r for r in base["checks"]}
    seen = set()
    matching = {}
    for row in inventory(followup["access_checks"]):
        fields(row, "record person requested_access observed")
        for key in ("record", "person", "requested_access"):
            text(row[key])
        ref = row["record"]
        require(ref in checks and ref not in seen, "unlinked or duplicate access check")
        seen.add(ref)
        text(row["observed"])
        require(row["observed"] in OBSERVATION_RESULTS, "unknown access observation")
        require(checks[ref]["result"] == OBSERVATION_RESULTS[row["observed"]], "conflicting observation results")
        if row["person"] == claimant["person"] and row["requested_access"] == claimant["requested_access"]:
            matching[ref] = row["observed"]
    personal = "access-unverified"
    supported_at = None
    if any(checks[ref]["result"] == "fail" and records[ref]["at"] > at for ref in matching):
        personal = "adverse-access-observation"
    elif (repair and repair["ordered_at"] >= at and repair["criterion"] in ACCESS_OBSERVATIONS
          and base["repair_status"] == "supplied-record-supports-declared-criterion"
          and matching.keys() == checks.keys()
          and all(checks[ref]["qualified_in_supplied_record"] and event in ACCESS_OBSERVATIONS[repair["criterion"]]
                  for ref, event in matching.items())):
        personal = "supplied-record-supports-personal-access"
        supported_at = min(records[ref]["at"] for ref in matching)

    other_denials = []
    counted = set()
    for row in inventory(followup["other_cases"]):
        validate_access(row)
        ref = row["record"]
        require(row["person"] != claimant["person"], "other case belongs to claimant")
        require(ref in records and records[ref]["kind"] == "observation" and records[ref]["at"] > at,
                "other case needs a post-decision observation")
        key = (row["person"], ref)
        require(key not in counted, "duplicate other case observation")
        counted.add(key)
        if (row["access"] == "denied" and all(row[k] is not None and row[k] == claimant[k]
                                              for k in MATCH_FIELDS)):
            other_denials.append({"person": row["person"], "record": ref})

    overdue = None if due is None else as_of > due and supported_at is None
    observed_by_due = None if due is None or supported_at is None else supported_at <= due
    return {"personal_relief": personal, "repair_status": base["repair_status"],
            "first_supported_access_at": supported_at, "access_observed_by_due_date": observed_by_due,
            "followup_owner": owner, "followup_due_at": due, "followup_overdue": overdue,
            "claimant_bears_followup": None if owner is None else owner == claimant["person"],
            "other_matched_denials": other_denials, "other_observations_reviewed": len(counted),
            "systemwide_effect": "unverified"}


def review(packet, *, as_of):
    """Audit declared reasons, jurisdiction, matched access, and individual relief separately."""
    fields(packet, "schema case_id decision_at claimant comparator reasoning decision followup remediation")
    require(packet["schema"] == SCHEMA, "unknown equal-treatment schema")
    text(packet["case_id"])
    integer(as_of, 0, 10**12)
    at = packet["decision_at"]
    integer(at, 0, as_of)
    base = review_repair(packet["remediation"], as_of=as_of)
    source = base["packet"]
    require(source["scope"] == packet["case_id"], "remediation belongs to another case")
    records = {r["id"]: r for r in source["records"]}

    def evidence_at_decision(ref, *, allow_later=False):
        text(ref)
        require(ref in records, "missing record")
        available = records[ref]["at"] <= at
        require(available or allow_later, "decision used a later record")
        return available

    claimant = packet["claimant"]
    comparator = packet["comparator"]
    for row in ([claimant] if comparator is None else [claimant, comparator]):
        validate_access(row)
        ref = row["record"]
        evidence_at_decision(ref)
        if row["access"] != "unknown" or row["penalty"] is not None:
            require(records[ref]["kind"] == "observation", "recorded access or penalty needs an observation")
    comparison = compare_access(claimant, comparator)
    reasons = examine_reasons(packet["reasoning"], evidence_at_decision)
    decision = packet["decision"]
    fields(decision, "claim_issue mandate_record delegated_issues merits_issues disposition")
    text(decision["claim_issue"])
    delegated = unique_labels(decision["delegated_issues"])
    merits = unique_labels(decision["merits_issues"])
    if decision["mandate_record"] is None:
        require(not delegated, "delegation needs a record")
    else:
        evidence_at_decision(decision["mandate_record"])
    outcome = decision["disposition"]
    require(outcome in ("pending", "dismiss", "refer", "remand", "uphold", "recognize-claim"),
            "unknown disposition")
    if outcome in ("uphold", "recognize-claim"):
        require(decision["claim_issue"] in merits, "merits disposition omits claim issue")
    for route in reasons["alternatives"]:
        route["within_declared_mandate"] = route["issue"] in delegated

    return {"schema": SCHEMA, "case_id": packet["case_id"], "packet_digest": digest(packet),
            "as_of": as_of, "comparison": comparison, "reasoning": reasons,
            "disposition": outcome, "claim_within_declared_mandate": decision["claim_issue"] in delegated,
            "merits_outside_mandate": sorted(set(merits) - set(delegated)),
            "merits_claimed_with_dismissal": bool(merits) and outcome == "dismiss",
            **review_followup(packet["followup"], claimant, source["repair"], base, records, at, as_of),
            "intent": base["intent"], "assurance": base["assurance"],
            "authority_granted": False, "external_actions": 0, "production_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--as-of", required=True, type=int)
    args = parser.parse_args()
    try:
        result = review(read(args.packet), as_of=args.as_of)
    except (ValueError, OSError) as error:
        parser.exit(2, f"equal-treatment review: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
