"""Read-only review of an established fictional award and a continuing rule warning."""
from copy import deepcopy

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import digest

SCHEMA = "owed-assistance-1"
MAX_TICK = 10**12


def _rows(value):
    require(isinstance(value, list) and len(value) <= 32, "expected at most 32 entries")
    return value


def _record(item, seen, earliest, as_of):
    name = item["record"]
    text(name)
    require(name not in seen, "duplicate evidence record")
    seen.add(name)
    integer(item["at"], earliest, as_of)


def _payment(packet, seen, as_of):
    award = packet["award"]
    fields(award, "record at case recipient units decision_office paying_office")
    _record(award, seen, 0, as_of)
    for key in ("case", "recipient", "decision_office", "paying_office"):
        text(award[key])
    require(award["recipient"] not in (award["paying_office"], award["decision_office"], packet["institution"]),
            "award and institutional roles must be distinct")
    integer(award["units"], 1, 10**9)
    credited, checks, transfers = 0, [], set()
    for item in _rows(packet["transfers"]):
        fields(item, "record at transfer award recipient units status controller")
        _record(item, seen, award["at"], as_of)
        for key in ("transfer", "award", "recipient", "controller"):
            text(item[key])
        integer(item["units"], 1, 10**9)
        require(item["status"] in ("instruction-issued", "pending", "credited", "returned"), "unknown transfer status")
        require(item["transfer"] not in transfers, "expected one current record per transfer")
        transfers.add(item["transfer"])
        if item["award"] != award["record"] or item["recipient"] != award["recipient"]:
            reason = "wrong-award-or-recipient"
        elif item["status"] != "credited":
            reason = item["status"]
        elif item["controller"] in (award["decision_office"], award["paying_office"], award["recipient"]):
            reason = "separate-settlement-evidence-needed"
        else:
            credited += item["units"]
            reason = "credit-supported"
        checks.append({"record": item["record"], "assessment": reason})

    owed = award["units"]
    if credited == 0:
        status = "delivery-unverified"
    elif credited < owed:
        status = "partial-delivery-supported"
    elif credited == owed:
        status = "delivery-supported"
    else:
        status = "excess-credit-needs-review"
    return {"award_record": award["record"], "owner": award["paying_office"], "status": status, "award_units": owed,
            "supported_credit_units": credited, "units_without_delivery_evidence": max(0, owed - credited),
            "excess_units": max(0, credited - owed), "checks": checks}


def _inquiry(packet, seen, as_of):
    warning, inquiry = packet["warning"], packet["inquiry"]
    fields(warning, "record at rule account acknowledged_at")
    _record(warning, seen, 0, as_of)
    text(warning["rule"])
    text(warning["account"])
    if warning["acknowledged_at"] is not None:
        integer(warning["acknowledged_at"], warning["at"], as_of)
    fields(inquiry, "assignment inventory findings")
    assignment, inventory = inquiry["assignment"], inquiry["inventory"]
    reviewer = None
    if assignment is not None:
        fields(assignment, "record at controller")
        _record(assignment, seen, warning["at"], as_of)
        text(assignment["controller"])
        award = packet["award"]
        if assignment["controller"] not in (award["recipient"], award["decision_office"], award["paying_office"]):
            reviewer = assignment["controller"]

    files = []
    inventory_verified = False
    if inventory is not None:
        fields(inventory, "record at controller rule cases complete")
        _record(inventory, seen, warning["at"], as_of)
        text(inventory["controller"])
        text(inventory["rule"])
        require(type(inventory["complete"]) is bool, "expected inventory coverage flag")
        files = _rows(inventory["cases"])
        for case in files:
            text(case)
        require(len(files) == len(set(files)), "duplicate case in inventory")
        require(packet["award"]["case"] not in files, "other-case inventory includes original case")
        inventory_verified = (assignment is not None and reviewer == inventory["controller"]
                              and inventory["rule"] == warning["rule"] and inventory["at"] >= assignment["at"])

    accepted, unused, unresolved_records = {}, [], []
    for item in _rows(inquiry["findings"]):
        fields(item, "record at controller case result")
        _record(item, seen, warning["at"], as_of)
        text(item["case"])
        text(item["controller"])
        require(item["result"] in ("correction-owed", "no-correction-found", "inconclusive"), "unknown file finding")
        if (inventory_verified and item["case"] in files and item["controller"] == reviewer
                and item["at"] >= inventory["at"]):
            require(item["case"] not in accepted, "expected one current finding per case")
            accepted[item["case"]] = item["result"]
        else:
            unused.append(item["record"])
            if item["result"] != "no-correction-found":
                unresolved_records.append(item["record"])

    pending = [case for case in files if accepted.get(case) in (None, "inconclusive")] if inventory_verified else []
    corrections = [case for case in files if accepted.get(case) == "correction-owed"]
    if reviewer is None:
        status = "independent-assignment-needed"
    elif not inventory_verified:
        status = "rule-records-review-needed"
    elif not inventory["complete"]:
        status = "inventory-incomplete"
    elif pending:
        status = "file-findings-outstanding"
    elif corrections:
        status = "other-remedies-outstanding"
    elif unresolved_records:
        status = "finding-reconciliation-needed"
    else:
        status = "declared-inventory-reviewed"
    return {"accountable_institution": packet["institution"], "next_owner": reviewer or packet["institution"],
            "reviewer": reviewer, "status": status, "warning_record": warning["record"],
            "inventory_record_used": inventory["record"] if inventory_verified else None,
            "inventory_reported_complete": inventory["complete"] if inventory_verified else None,
            "pending_files": pending, "findings": accepted, "other_cases_owed_correction": corrections,
            "unused_finding_records": unused, "findings_to_reconcile": unresolved_records}


def _participation(packet, seen, as_of):
    choices = packet["participation"]
    activities = ("public-reconciliation", "publicity", "repeat-testimony", "further-contact")
    require(isinstance(choices, dict) and all(key in activities for key in choices), "unknown participation choice")
    for value in choices.values():
        require(value in ("accepted", "declined", "unanswered"), "unknown participation response")
    # Requests can impose a condition even when the person declines and spends zero units.
    burden = {role: {"recorded_units": 0, "unknown_cost_entries": 0, "entries": 0}
              for role in ("institution", "affected-person")}
    conditions = []
    for entry in _rows(packet["work"]):
        fields(entry, "record at obligation bearer activity required units")
        require(entry["obligation"] in ("payment", "rule-inquiry"), "unknown obligation")
        start = packet["award"]["at"] if entry["obligation"] == "payment" else packet["warning"]["at"]
        _record(entry, seen, start, as_of)
        require(entry["bearer"] in ("institution", "affected-person"), "unknown cost bearer")
        text(entry["activity"])
        require(type(entry["required"]) is bool, "expected a boolean participation condition")
        costs = burden[entry["bearer"]]
        costs["entries"] += 1
        if entry["units"] is None:
            costs["unknown_cost_entries"] += 1
        else:
            integer(entry["units"], 0, 10**9)
            costs["recorded_units"] += entry["units"]
        if entry["bearer"] == "affected-person" and entry["required"]:
            conditions.append(entry["record"])
    return {"choices": dict(choices), "required_person_work_records": conditions, "recorded_burden": burden}


def review_assistance(packet, *, as_of):
    integer(as_of, 0, MAX_TICK)
    fields(packet, "schema institution award warning participation transfers inquiry work")
    require(packet["schema"] == SCHEMA, "unsupported assistance schema")
    text(packet["institution"])
    seen = set()
    payment = _payment(packet, seen, as_of)
    inquiry = _inquiry(packet, seen, as_of)
    participation = _participation(packet, seen, as_of)
    return {"version": SCHEMA, "as_of": as_of, "payment": payment, "rule_inquiry": inquiry,
            "participation_review": participation, "packet": deepcopy(packet), "packet_digest": digest(packet),
            "assurance": "unverified-host-supplied-records", "authority_granted": False,
            "external_actions": 0, "production_ready": False}
