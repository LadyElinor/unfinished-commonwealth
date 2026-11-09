"""Compare a recorded change condition with original and supplementary evidence."""

import argparse
from fractions import Fraction
import json
from pathlib import Path

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.remediation_v1.__main__ import load_packet
from commonwealth.study_v1.engine import canonical, digest


ROUTES = {
    "inquiry": ("open-inquiry",),
    "merits": ("reconsider-finding",),
    "procedure": ("renew-notice", "rehear-disputed-issue", "seek-independent-review"),
    "authority": ("refer-for-mandate-review",),
    "remedy": ("verify-individual-relief",),
}
METHOD_FIELDS = {
    "observation": "",
    "relative-rate": "comparison before after",
    "joined-reason": "panel",
    "impact-cap": "unit",
    "mandate": "issuer actor action",
    "supervision": "decision_controller interested_controller",
}
MAX_TIME = 10**12


def _list(value, limit, name):
    require(type(value) is list and len(value) <= limit, f"invalid {name} list")


def _names(value):
    _list(value, 64, "names")
    for name in value:
        text(name)
    require(len(value) == len(set(value)), "duplicate name")


def _bool(value):
    require(type(value) is bool, "boolean required")


def _rule(rule):
    fields(rule, "id premise rival scope stage criterion method parameters change_when on_change")
    for key in ("id", "premise", "rival", "scope", "stage", "criterion", "method", "on_change"):
        text(rule[key])
    require(rule["on_change"] in ROUTES.get(rule["stage"], ()), "route outside decision stage")
    _bool(rule["change_when"])
    method, params = rule["method"], rule["parameters"]
    require(method in METHOD_FIELDS, "unknown test method")
    require((rule["stage"] == "authority") == (method == "mandate"), "authority review requires a mandate test")
    if method == "mandate":
        require(rule["change_when"] is True, "test for a matching mandate, not its absence")
    fields(params, METHOD_FIELDS[method])
    if method == "joined-reason":
        _names(params["panel"])
        require(params["panel"], "empty deciding panel")
    elif method == "relative-rate":
        text(params["comparison"])
        require(params["comparison"] != rule["scope"], "comparison must be a different cohort")
        integer(params["before"], 0, MAX_TIME)
        integer(params["after"], params["before"] + 1, MAX_TIME)
    else:
        for value in params.values():
            text(value)


def _rate(pair):
    _list(pair, 2, "rate")
    require(len(pair) == 2, "rate needs numerator and denominator")
    hits, total = pair
    integer(total, 1, MAX_TIME)
    integer(hits, 0, total)
    return Fraction(hits, total)


def _measure(record, rule, decided_at):
    """Return the recorded test value or None and the basis for that result."""
    method, data, params = record["kind"], record["data"], rule["parameters"]
    if method == "context":
        fields(data, "")
        return None, "context-only"
    if method == "observation":
        fields(data, "value")
        value = data["value"]
        if value is not None:
            _bool(value)
        return value, "curated-observation"
    if method == "relative-rate":
        fields(data, "comparison before after treated_before treated_after comparison_before comparison_after")
        text(data["comparison"])
        integer(data["before"], 0, MAX_TIME)
        integer(data["after"], data["before"] + 1, MAX_TIME)
        require(data["after"] == record["event_at"], "rate event must end at the declared after time")
        values = [_rate(data[key]) if data[key] is not None else None for key in
                  ("treated_before", "treated_after", "comparison_before", "comparison_after")]
        if not all(data[key] == params.get(key) for key in ("comparison", "before", "after")):
            return None, "different-cohort-or-time-window"
        if None in values:
            return None, "missing-rate"
        treated_before, treated_after, control_before, control_after = values
        difference = (treated_after - treated_before) - (control_after - control_before)
        return difference > 0, f"relative-change={difference}"
    if method == "impact-cap":
        fields(data, "unit imposed attributable")
        text(data["unit"])
        integer(data["imposed"], 0, MAX_TIME)
        if data["attributable"] is not None:
            integer(data["attributable"], 0, MAX_TIME)
        if data["unit"] != params.get("unit") or data["attributable"] is None:
            return None, "attributable-impact-unmeasured-in-same-unit"
        excess = data["imposed"] - data["attributable"]
        return excess > 0, f"excess-over-declared-impact={excess}"
    if method == "joined-reason":
        fields(data, "part joined")
        require(data["part"] in ("reasons", "syllabus", "judgment-only", "separate-writing"),
                "unknown source part")
        _names(data["joined"])
        if data["part"] != "reasons":
            return None, "no-joint-reasons-in-this-part"
        panel = params.get("panel", [])
        if not set(data["joined"]).issubset(panel):
            return None, "different-deciding-panel"
        return 2 * len(data["joined"]) > len(panel), "joins-on-this-proposition"
    if method == "mandate":
        fields(data, "issuer actor action starts ends")
        for key in ("issuer", "actor", "action"):
            text(data[key])
        integer(data["starts"], 0, MAX_TIME)
        integer(data["ends"], data["starts"], MAX_TIME)
        if any(data[key] != params.get(key) for key in ("issuer", "actor", "action")):
            return None, "different-delegation"
        valid = record["event_at"] <= decided_at and data["starts"] <= decided_at <= data["ends"]
        if not valid:
            return None, "instrument-not-in-force-at-original-decision"
        return True, "this-instrument-at-original-decision"
    require(method == "supervision", "unknown evidence kind")
    fields(data, "reviewer_controller examined_merits can_reverse")
    controller = data["reviewer_controller"]
    if controller is not None:
        text(controller)
    for key in ("examined_merits", "can_reverse"):
        if data[key] is not None:
            _bool(data[key])
    if controller is not None and controller in (params.get("decision_controller"), params.get("interested_controller")):
        return False, "interested-or-original-controller"
    if data["examined_merits"] is False or data["can_reverse"] is False:
        return False, "supervision-missing-substance-or-reversal-power"
    if None in data.values():
        return None, "supervision-incomplete"
    return True, "declared-substantive-review"


def _assessment(records):
    matching = {r["event_at"] for r in records if r["result"] == "matches-change-condition"}
    opposing = {r["event_at"] for r in records if r["result"] == "opposes-change-condition"}
    if matching & opposing:
        return "conflicting-records"
    if matching and opposing:
        return "different-results-over-time"
    if matching:
        return "change-condition-reported"
    if opposing:
        return "condition-not-shown-by-tested-records"
    return "unresolved"


def review(decision, supplement=None, *continuations):
    """Recompute the original assessment and retain evidence by its time and scope."""
    fields(decision, "schema case decided_at disposition rules records")
    require(decision["schema"] == "decision-premises-1", "unsupported decision schema")
    for key in ("case", "disposition"):
        text(decision[key])
    decided_at = decision["decided_at"]
    integer(decided_at, 0, MAX_TIME)
    _list(decision["rules"], 32, "rules")
    require(decision["rules"], "at least one review question required")
    rules = {}
    for rule in decision["rules"]:
        _rule(rule)
        require(rule["id"] not in rules, "duplicate rule ID")
        rules[rule["id"]] = rule

    require(len(canonical(decision).encode()) <= 1024**2, "decision exceeds 1 MiB")
    parent = digest(decision)
    as_of = decided_at
    batches = [(True, decided_at, decision["records"])]
    supplement_digests = []
    require(supplement is not None or not continuations, "missing first supplement")
    supplements = () if supplement is None else (supplement, *continuations)
    require(len(supplements) <= 8, "at most eight supplements per review")
    previous = None
    for packet in supplements:
        fields(packet, "schema decision_digest previous_digest as_of records")
        require(packet["schema"] == "premise-evidence-1", "unsupported supplement schema")
        require(packet["decision_digest"] == parent, "supplement identifies a different decision")
        require(packet["previous_digest"] == previous, "supplement predecessor mismatch")
        require(len(canonical(packet).encode()) <= 1024**2, "supplement exceeds 1 MiB")
        integer(packet["as_of"], as_of, MAX_TIME)
        as_of = packet["as_of"]
        previous = digest(packet)
        supplement_digests.append(previous)
        batches.append((False, as_of, packet["records"]))

    seen = set()
    findings = {key: [] for key in rules}
    for original, evidence_cutoff, records in batches:
        _list(records, 128, "records")
        for record in records:
            fields(record, "id rule scope stage criterion kind source account event_at available_at data")
            for key in ("id", "rule", "scope", "stage", "criterion", "kind", "source", "account"):
                text(record[key])
            require(record["id"] not in seen, "duplicate record ID")
            seen.add(record["id"])
            require(record["rule"] in rules, "unknown rule reference")
            require(record["stage"] in ROUTES, "unknown evidence stage")
            integer(record["event_at"], 0, MAX_TIME)
            integer(record["available_at"], record["event_at"], evidence_cutoff)
            rule = rules[record["rule"]]
            value, reason = _measure(record, rule, decided_at)
            gaps = [key for key in ("scope", "stage", "criterion") if rule[key] != record[key]]
            if record["kind"] != rule["method"]:
                gaps.append("method")
            if gaps:
                value = None
                reason = "different-" + "-".join(gaps)
            if original:
                timing = "original-record"
            elif record["event_at"] > decided_at:
                timing = "subsequent-event"
            elif record["available_at"] > decided_at:
                timing = "later-disclosed-original-event"
            else:
                timing = "available-then-omitted"
            result = "inconclusive"
            if value is not None:
                result = "matches-change-condition" if value == rule["change_when"] else "opposes-change-condition"
            findings[rule["id"]].append({"id": record["id"], "event_at": record["event_at"], "timing": timing,
                                         "result": result, "basis": reason})

    questions = []
    for key, rule in rules.items():
        records = findings[key]
        original = [r for r in records if r["timing"] == "original-record"]
        historical = [r for r in records if r["timing"] != "subsequent-event"]
        later = [r for r in records if r["timing"] == "subsequent-event"]
        status = _assessment(historical)
        route = {"change-condition-reported": rule["on_change"],
                 "conflicting-records": "review-conflicting-evidence",
                 "different-results-over-time": "review-change-over-time",
                 "unresolved": "seek-relevant-evidence",
                 "condition-not-shown-by-tested-records": "no-change-trigger-shown"}[status]
        later_status = _assessment(later)
        later_route = None
        if later_status in ("change-condition-reported", "conflicting-records", "different-results-over-time"):
            later_route = rule["on_change"] if rule["stage"] == "remedy" else "review-subsequent-event"
        questions.append({"id": key, "stage": rule["stage"], "original": _assessment(original),
                          "historical_review": status, "historical_followup": route,
                          "subsequent_events": later_status, "subsequent_followup": later_route, "records": records})
    return {"schema": "decision-premise-report-1", "case": decision["case"], "as_of": as_of,
            "decision_digest": parent, "supplement_digests": supplement_digests,
            "questions": questions, "intent": "not-established", "authority_granted": False,
            "external_actions": 0, "production_ready": False, "assurance": "unverified-host-supplied-records"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decision", type=Path)
    parser.add_argument("supplements", nargs="*", type=Path)
    args = parser.parse_args()
    try:
        decision = load_packet(args.decision)
        require(len(args.supplements) <= 8, "at most eight supplements per review")
        supplements = [load_packet(path) for path in args.supplements]
        require(all(isinstance(s, dict) for s in supplements), "supplement must be an object")
        report = review(decision, *supplements)
    except (ValueError, OSError, RecursionError) as error:
        parser.exit(2, f"Invalid review input: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
