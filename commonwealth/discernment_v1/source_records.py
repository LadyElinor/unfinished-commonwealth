"""Preserve attributed evidentiary status; do not promote it to a guilt label."""

from copy import deepcopy

from .engine import fields, integer, require, text

STATUSES = {
    "allegation": "Allegation; no finding of guilt established by this record.",
    "guilty-plea": "Reported guilty plea, limited to the named party and specified counts.",
    "jury-verdict": "Reported jury verdict, limited to the named party and specified counts.",
    "sentence": "Reported sentence following conviction, limited to specified counts.",
    "acquittal": "Reported acquittal on specified counts.",
    "unresolved-counts": "No verdict reported on these counts.",
    "settlement": "Reported settlement; not by itself a criminal conviction or admission.",
    "deferred-prosecution": "Reported deferred prosecution agreement; preserve separately specified admissions.",
    "administrative-action": "Reported administrative action; not a criminal conviction.",
    "estimate": "Attributed estimate; not an adjudicated loss or actual recovery.",
    "improper-payment": "Payment error category; intentional fraud is not established by this category alone.",
}
METRICS = ("alleged-loss", "estimated-loss", "annualized-savings", "settlement-amount",
           "restitution-ordered", "actual-recovery", "improper-payment")


def describe(record):
    fields(record, "subject scope status source as_of")
    for key in ("subject", "scope", "source", "as_of"):
        text(record[key])
    require(isinstance(record["status"], str) and record["status"] in STATUSES, "unknown source status")
    return {**deepcopy(record), "qualification": STATUSES[record["status"]]}


def sum_comparable(records):
    """Sum only declared disjoint coverage with identical units and time basis.

    Coverage and attribution must be supplied by a curator; this helper cannot
    discover undisclosed overlap or verify that a reported recovery occurred.
    """
    require(isinstance(records, list) and bool(records), "nonempty records required")
    group, covered, total = None, set(), 0
    for record in records:
        fields(record, "metric currency period amount_minor coverage source")
        require(record["metric"] in METRICS, "unknown metric")
        for key in ("currency", "period", "source"):
            text(record[key])
        integer(record["amount_minor"], 0, 10**18)
        coverage = record["coverage"]
        require(isinstance(coverage, list) and bool(coverage), "explicit disjoint coverage required")
        for member in coverage:
            text(member)
        require(len(set(coverage)) == len(coverage) and not covered.intersection(coverage), "overlapping coverage")
        key = (record["metric"], record["currency"], record["period"])
        require(group is None or group == key, "incompatible metric, currency or period")
        group = key
        covered.update(coverage)
        total += record["amount_minor"]
    return {"metric": group[0], "currency": group[1], "period": group[2], "amount_minor": total,
            "coverage": sorted(covered), "sources": sorted({r["source"] for r in records}),
            "assurance": "ARITHMETIC_ONLY_ON_CURATOR_DECLARED_DISJOINT_COVERAGE"}
