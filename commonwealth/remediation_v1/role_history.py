"""R2 exposed role-history rehearsal. Run with the public owed-assistance example."""
import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from commonwealth.study_v1.engine import digest

from .assistance import review_assistance
from .__main__ import load_packet

ROLES = ("selector", "briefer", "voter")
ARMS = ("office", "history")
CASE_SOURCES = {"signed-denial": "decision-register", "material-witness": "witness-register",
                "substantial-dependence": "funding-register"}
BASE_DIGEST = "6f0ac574c8dc6fc9d3d8547e84a93ed47de2cb813566b525e9b8f78d9d646688"
START, DUE, HORIZON = 3, 5, 8
CASE = "case-17"
DOCUMENTS = {"A": "no-correction-found", "B": "correction-owed"}


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    office: str


@dataclass(frozen=True)
class Record:
    id: str
    person: str
    kind: str
    source: str
    case: str = CASE


@dataclass
class Hearing:
    team: dict
    records: tuple
    challenge: str
    response: str | None
    reserve: tuple
    available: frozenset
    file_lists: dict
    case: str = CASE


CANDIDATE = Person("P1", "A. Reed", "appeals-desk")
ALTERNATE = Person("R1", "J. Park", "reserve-office")
# These fixture inputs are visible to both arms. The answer key is held by the scorer.
WORLDS = {
    "direct-approver": ("voter", "signed-denial"),
    "moved-approver": ("voter", "signed-denial"),
    "former-colleague": ("voter", "former-colleague"),
    "material-witness": ("briefer", "material-witness"),
    "mistaken-identity": ("voter", "same-name"),
    "nonvoting-selector": ("selector", "signed-denial"),
    "financial-dependence": ("voter", "substantial-dependence"),
    "minor-connection": ("voter", "minor-connection"),
    "disputed-allegation": ("voter", "unverified-claim"),
}


def hearing(name, reserve_available):
    role, relationship = WORLDS[name]
    candidate = CANDIDATE
    if name == "direct-approver":
        candidate = Person(candidate.id, candidate.name, "eligibility-office")
    team = {role: Person(role, role, "review-office") for role in ROLES}
    team[role] = candidate
    signer = candidate.id if relationship == "signed-denial" else "P2"
    records = [Record("decision-17", signer, "signed-denial", "decision-register")]
    if relationship == "same-name":
        records.append(Record("namesake", "P2", "same-name", "identity-register"))
    elif relationship != "signed-denial":
        source = {"material-witness": "witness-register", "substantial-dependence": "funding-register",
                  "minor-connection": "funding-register", "former-colleague": "employment-register",
                  "unverified-claim": "challenge"}[relationship]
        records.append(Record("interest-17", candidate.id, relationship, source))
    challenge, response = {
        "same-name": ("The signer has the voter's name.", "That signature belongs to P2."),
        "unverified-claim": ("I believe the voter approved the denial.", "I did not sign the decision."),
    }.get(relationship, ("Check the appointment against the case records.", "Please consult the registers."))
    file_lists = {candidate.id: ("A",)} if name == "nonvoting-selector" else {}
    return Hearing(team, tuple(records), challenge, response, (ALTERNATE,),
                   frozenset({ALTERNATE.id} if reserve_available else ()), file_lists)


def screen(person, arm, case, records, forbidden):
    if arm not in ARMS:
        raise ValueError("unknown role screening policy")
    relevant = [r for r in records if r.case == case and r.person == person.id]
    matches = [r for r in relevant if r.kind in CASE_SOURCES and CASE_SOURCES[r.kind] == r.source]
    if person.office in forbidden:
        reason, reversal = "excluded-office", "A corrected office assignment outside the excluded offices."
        if arm == "history" and matches:
            reason = "excluded-office-and-documented-conflict"
            reversal += " The case-specific disqualifying record must also be corrected."
        exclude = True
    elif arm == "history" and matches:
        reason, reversal = "documented-case-conflict", "A correction to the matched identity or case record."
        exclude = True
    else:
        reason, exclude = "eligible-under-" + arm, False
        reversal = ("An excluded office assignment." if arm == "office" else
                    "An excluded office or a verified case-specific disqualifying record.")
    return {"person": person.id, "office": person.office, "excluded": exclude, "reason": reason,
            "records_considered": [r.id for r in records if r.case == case],
            "matched_conflict_records": [r.id for r in matches] if arm == "history" else [],
            "would_change_with": reversal}


def snapshot(base, tick, events, voter, selected, ballot):
    # Pay on the environment clock, including blocked and idle ticks.
    packet = deepcopy(base)
    packet["warning"]["acknowledged_at"] = START
    packet["transfers"] = [r for r in packet["transfers"] if r["at"] <= tick]
    packet["work"] = [r for r in packet["work"] if r["at"] <= tick and
                      (r["obligation"] == "payment" or r["bearer"] == "affected-person")]
    packet["work"].extend({"record": "slot-" + str(e["at"]), "at": e["at"], "activity": e["action"],
                           "obligation": "rule-inquiry", "bearer": "institution", "required": True, "units": 1}
                          for e in events)
    by_action = {e["action"]: e["at"] for e in events}
    assignment = None
    if voter is not None:
        assignment = {"record": "panel", "at": by_action.get("replace", by_action["screen"]), "controller": voter}
    inventory = None
    if selected is not None:
        # M1 records the panel's inventory. The R2 receipts preserve its actual selector and briefer.
        inventory = {"record": "panel-files", "at": by_action["select"], "controller": voter,
                     "rule": packet["warning"]["rule"], "cases": list(selected), "complete": True}
    findings = [{"record": "finding-" + file, "at": by_action["vote"], "case": file,
                 "controller": voter, "result": decision} for file, decision in (ballot or {}).items()]
    packet["inquiry"] = dict(assignment=assignment, inventory=inventory, findings=findings)
    report = review_assistance(packet, as_of=tick)
    return {"tick": tick, "payment": report["payment"], "inquiry": report["rule_inquiry"],
            "participation": report["participation_review"], "digest": report["packet_digest"]}


def simulate(base, h, arm, budget):
    """Receive evidence and appointments only. The scorer never supplies truth to this routine."""
    if not isinstance(budget, int) or isinstance(budget, bool) or budget not in (4, 5):
        raise ValueError("the frozen run supports four or five slots")
    if h.case != base["award"]["case"]:
        raise ValueError("hearing must concern the award case")
    excluded_offices = {base["award"][key] for key in ("decision_office", "paying_office", "recipient")}
    initial, reserve_checks, events, timeline = {}, [], [], []
    team = h.team.copy()
    selected, brief, ballot = None, None, None
    active = False
    stopped = None
    phase = "screen"
    for tick in range(START, HORIZON + 1):
        if tick > START and not stopped and len(events) < budget:
            action = {"at": tick, "action": phase, "actor": "registrar"}
            if phase == "screen":
                for role, person in team.items():
                    initial[role] = screen(person, arm, h.case, h.records, excluded_offices)
                needs_reserve = any(check["excluded"] for check in initial.values())
                active = not needs_reserve
                phase = "replace" if needs_reserve else "select"
            elif phase == "replace":
                for person in h.reserve:
                    check = screen(person, arm, h.case, h.records, excluded_offices)
                    check["available"] = person.id in h.available
                    reserve_checks.append(check)
                    if check["available"] and not check["excluded"]:
                        for role in ROLES:
                            if initial[role]["excluded"]:
                                team[role] = person
                        active = True
                        break
                if active:
                    phase = "select"
                else:
                    stopped = "no-eligible-reserve"
            elif phase == "select":
                person = team["selector"]
                selected = tuple(h.file_lists.get(person.id, DOCUMENTS))
                action.update(actor=person.id, files=selected)
                phase = "brief"
            elif phase == "brief":
                person = team["briefer"]
                brief = {file: DOCUMENTS[file] for file in selected}
                action.update(actor=person.id, findings=brief)
                phase = "vote"
            else:
                person = team["voter"]
                ballot = brief.copy()
                action.update(actor=person.id, findings=ballot)
                stopped = "voted"
            events.append(action)
        voter = team["voter"].office if active else None
        timeline.append(snapshot(base, tick, events, voter, selected, ballot))
    return {"version": "role-history-rehearsal-1", "arm": arm, "budget": budget, "case": h.case,
            "challenge": h.challenge, "response": h.response, "history": [asdict(r) for r in h.records],
            "planned": {role: asdict(p) for role, p in h.team.items()}, "initial_screen": initial,
            "reserve_order": [p.id for p in h.reserve], "reserve_checks": reserve_checks,
            "authorized": {role: p.id for role, p in team.items()} if active else {},
            "events": events, "timeline": timeline, "terminal": stopped or "budget-exhausted",
            "misconduct_findings": [], "external_actions": 0}


# Hand-authored truth for the nine exposed assignments. File B alone needs correction.
CONFLICTED = {"direct-approver", "moved-approver", "material-witness",
              "nonvoting-selector", "financial-dependence"}


def score(trace, conflicted):
    end = trace["timeline"][-1]
    excluded = {r["person"] for r in trace["initial_screen"].values() if r["excluded"]}
    retained = set(trace["authorized"].values()) & conflicted
    found = set(end["inquiry"]["other_cases_owed_correction"])
    payment = next((s["tick"] for s in trace["timeline"] if s["payment"]["status"] == "delivery-supported"), None)
    vote = next((e["at"] for e in trace["events"] if e["action"] == "vote"), None)
    return {"conflicts_retained": sorted(retained), "eligible_removed": sorted(excluded - conflicted),
            "unsupported_misconduct": len(trace["misconduct_findings"]), "missed_corrections": sorted({"B"} - found),
            "unsupported_corrections": sorted(found - {"B"}), "review_elapsed": None if vote is None else vote - START,
            "reviewer_slots": len(trace["events"]), "owner": end["inquiry"]["next_owner"],
            "payment_tick": payment, "lateness": None if payment is None else max(0, payment - DUE),
            "claimant_demands": len(end["participation"]["required_person_work_records"]),
            "claimant_work": end["participation"]["recorded_burden"]["affected-person"]["recorded_units"]}


def matrix(base):
    if digest(base) != BASE_DIGEST:
        raise ValueError("the frozen matrix requires the public owed-assistance example")
    for world in WORLDS:
        conflicted = {CANDIDATE.id} if world in CONFLICTED else set()
        for reserve in (True, False):
            for budget in (5, 4):
                fixture = hearing(world, reserve)
                for arm in ARMS:
                    trace = simulate(base, fixture, arm, budget)
                    yield {"world": world, "reserve_available": reserve, "trace": trace, "score": score(trace, conflicted)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", type=Path, help="examples/owed-assistance.json from PR #8")
    args = parser.parse_args()
    for row in matrix(load_packet(args.example)):
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
