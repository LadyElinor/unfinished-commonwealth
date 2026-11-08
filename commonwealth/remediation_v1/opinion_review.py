"""Review a fictional panel's reasons and proposed remedies against a specific case."""

import argparse
from collections import Counter
import json
from pathlib import Path

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.review_v1.__main__ import read
from commonwealth.study_v1.engine import digest
from .equal_treatment import inventory, review as review_case, unique_labels


SCHEMA = "opinion-review-1"
OUTCOMES = ("dismiss", "refer", "remand", "uphold", "recognize-claim")
STAGES = ("jurisdiction", "standing", "justiciability", "merits", "remedy")
EVIDENCE_KINDS = {
    "fact": ("observation", "testimony"),
    "causal-link": ("observation", "analysis", "testimony"),
    "governing-standard": ("rule",),
    "institutional-authority": ("mandate",),
}
SOURCE_KINDS = ("opinion", "summary", "observation", "testimony", "analysis", "rule", "mandate")
ACTION_FIELDS = ("office", "act", "procedure", "reach")


def indexed(rows, keys):
    by_id = {}
    for row in inventory(rows):
        fields(row, keys)
        text(row["id"])
        require(row["id"] not in by_id, "duplicate ID in inventory")
        by_id[row["id"]] = row
    return by_id


def source_at(sources, ref, *, latest, kinds):
    text(ref)
    require(ref in sources, "unknown source")
    source = sources[ref]
    require(source["at"] <= latest and source["kind"] in kinds, "ineligible source or date")
    return source


def review_panel(panel, passages, sources, at):
    fields(panel, "record members ballots")
    source_at(sources, panel["record"], latest=at, kinds=("opinion",))
    members = unique_labels(panel["members"])
    require(bool(members), "empty reviewing panel")
    ballots = panel["ballots"]
    require(type(ballots) is dict and set(ballots) == set(members), "ballots must cover the roster")
    for vote in ballots.values():
        require(vote in (*OUTCOMES, "abstain", "unknown"), "unknown ballot")
    threshold = len(members) // 2 + 1
    counts = Counter(ballots.values())
    judgment = next((vote for vote in OUTCOMES if counts[vote] >= threshold), None)

    views = {}
    for key, passage in passages.items():
        form, part, outcome = passage["form"], passage["part"], passage["for_result"]
        require(form in ("signed", "per-curiam", "seriatim", "concurrence", "dissent", "syllabus"),
                "unknown opinion form")
        require(part in ("body", "footnote"), "unknown passage location")
        source_kind = "summary" if form == "syllabus" else "opinion"
        source_at(sources, passage["record"], latest=at, kinds=(source_kind,))
        text(passage["pinpoint"])
        text(passage["proposition"])
        joined = unique_labels(passage["joined_by"])
        require(set(joined) <= set(members), "unknown passage signer")
        if form == "syllabus":
            require(not joined and outcome is None, "editorial summary cannot carry a vote")
        else:
            require(outcome in OUTCOMES, "opinion requires a proposed disposition")
        agreeing = sorted(m for m in joined if judgment is not None and ballots[m] == judgment)
        majority_reason = (judgment is not None and outcome == judgment and form != "dissent"
                           and len(agreeing) >= threshold)
        views[key] = {"record": passage["record"], "form": form, "part": part,
                      "pinpoint": passage["pinpoint"], "proposition": passage["proposition"],
                      "for_result": outcome, "joined_by": sorted(joined),
                      "majority_for_judgment_joined_passage": majority_reason}
    return {"record": panel["record"], "judgment": judgment, "ballots": dict(ballots), "threshold": threshold,
            "passages": views, "majority_reasons": sorted(k for k, v in views.items()
                                                         if v["majority_for_judgment_joined_passage"])}


def review_hearing(hearing, panel, sources, at):
    fields(hearing, "opportunity record compensation")
    opportunity = hearing["opportunity"]
    require(opportunity in ("heard", "offered", "excluded", "unknown"), "unknown testimony opportunity")
    if hearing["record"] is None:
        require(opportunity == "unknown", "testimony opportunity needs a record")
    else:
        record = source_at(sources, hearing["record"], latest=at, kinds=("observation", "testimony"))
        require(record["topic"] == "claimant-testimony", "wrong testimony topic")
    compensation = {}
    for term in inventory(hearing["compensation"]):
        fields(term, "member record amounts")
        member = term["member"]
        text(member)
        require(member in panel["ballots"] and member not in compensation, "unknown or duplicate payee")
        record = source_at(sources, term["record"], latest=at, kinds=("rule", "mandate"))
        require(record["topic"] == "panel-compensation", "wrong compensation topic")
        amounts = term["amounts"]
        require(type(amounts) is dict and 2 <= len(amounts) <= len(OUTCOMES), "need comparable fee terms")
        for outcome, amount in amounts.items():
            require(outcome in OUTCOMES, "unknown fee outcome")
            integer(amount, 0, 10**9)
        compensation[member] = {"record": term["record"], "amounts": dict(amounts),
                                "varies_by_listed_outcome": len(set(amounts.values())) > 1}
    return {"testimony_opportunity": opportunity, "testimony_record": hearing["record"],
            "compensation": compensation,
            "members_without_fee_information": sorted(set(panel["ballots"]) - compensation.keys())}


def bearing(support, challenge):
    if support and challenge:
        return "contested"
    if challenge:
        return "challenge-recorded"
    if support:
        return "support-recorded"
    return "no-matching-material"


def review_premises(premises, passages, sources, at, as_of):
    results = {}
    for key, premise in premises.items():
        passage = premise["passage"]
        text(passage)
        require(passage in passages and passages[passage]["form"] != "syllabus",
                "premise requires an opinion passage")
        stage, kind = premise["stage"], premise["kind"]
        require(stage in STAGES, "unknown stage")
        text(kind)
        require(kind in EVIDENCE_KINDS, "unknown premise kind")
        require(premise["test_origin"] in ("passage", "reviewer-proposal"), "unknown test origin")
        for field in ("topic", "criterion", "next_step"):
            text(premise[field])
        before = {"supports": [], "challenges": []}
        later = {"supports": [], "challenges": []}
        unmatched = {}
        seen = set()
        for entry in inventory(premise["evidence"]):
            fields(entry, "record bearing")
            ref, direction = entry["record"], entry["bearing"]
            record = source_at(sources, ref, latest=as_of, kinds=SOURCE_KINDS)
            require(ref not in seen and direction in ("supports", "challenges"), "invalid evidence entry")
            seen.add(ref)
            if record["topic"] != premise["topic"]:
                unmatched[ref] = "different-topic"
            elif record["kind"] not in EVIDENCE_KINDS[kind]:
                unmatched[ref] = "different-kind"
            else:
                bucket = before if record["at"] <= at else later
                bucket[direction].append(ref)
        results[key] = {
            "passage": passage, "stage": stage, "kind": kind, "topic": premise["topic"],
            "test_origin": premise["test_origin"], "criterion": premise["criterion"], "proposed_next_step": premise["next_step"],
            "at_decision": bearing(before["supports"], before["challenges"]),
            "as_of": bearing(before["supports"] + later["supports"], before["challenges"] + later["challenges"]),
            "then_records": before, "later_records": later, "unmatched_records": unmatched,
        }
    return results


def review_actions(packet, sources, at, as_of):
    terms = indexed(packet["mandates"], "id record office act procedure reach position")
    for term in terms.values():
        for key in ACTION_FIELDS:
            text(term[key])
        require(term["position"] in ("permits", "forbids"), "unknown mandate position")
        source = source_at(sources, term["record"], latest=as_of, kinds=("mandate",))
        require(source["topic"] == term["act"], "mandate source covers a different act")
    actions = indexed(packet["proposals"], "id office act procedure reach")
    results = {}
    for key, action in actions.items():
        for field in ACTION_FIELDS:
            text(action[field])
        matched = {"permits": [], "forbids": []}
        later, partial = [], {}
        for identifier, term in terms.items():
            if term["act"] != action["act"]:
                continue
            differences = [field for field in ACTION_FIELDS if action[field] != term[field]]
            if differences:
                partial[identifier] = differences
            elif sources[term["record"]]["at"] > at:
                later.append(identifier)
            else:
                matched[term["position"]].append(identifier)
        if matched["permits"] and matched["forbids"]:
            status = "conflicting-terms"
        elif matched["forbids"]:
            status = "expressly-forbidden"
        elif matched["permits"]:
            status = "within-declared-terms"
        else:
            status = "no-matching-term"
        results[key] = {"at_decision": status, "matching_terms": matched,
                        "later_exact_terms": later, "partial_terms": partial}
    return results


def review(case, packet, *, as_of):
    """Return passage votes, premise-specific challenges and case-bound remedy findings."""
    base = review_case(case, as_of=as_of)
    fields(packet, "schema case_digest panel_at sources panel hearing passages premises mandates proposals")
    require(packet["schema"] == SCHEMA, "unknown opinion review schema")
    require(packet["case_digest"] == base["packet_digest"], "parent case digest mismatch")
    at = packet["panel_at"]
    integer(at, case["decision_at"], as_of)
    sources = indexed(packet["sources"], "id kind topic at locator")
    for record in sources.values():
        require(record["kind"] in SOURCE_KINDS, "unknown source kind")
        integer(record["at"], 0, as_of)
        text(record["topic"])
        text(record["locator"])
    passages = indexed(packet["passages"], "id record pinpoint proposition form part for_result joined_by")
    panel = review_panel(packet["panel"], passages, sources, at)
    premises = indexed(packet["premises"], "id passage stage kind topic test_origin criterion next_step evidence")
    return {"schema": SCHEMA, "case_id": base["case_id"], "case_digest": base["packet_digest"],
            "review_digest": digest(packet), "panel_at": at, "as_of": as_of, "panel": panel,
            "hearing": review_hearing(packet["hearing"], panel, sources, at),
            "premises": review_premises(premises, passages, sources, at, as_of),
            "proposals": review_actions(packet, sources, at, as_of),
            "original_decision": base, "authority_granted": False, "external_actions": 0,
            "intent": base["intent"], "assurance": base["assurance"], "production_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("review_packet", type=Path)
    parser.add_argument("--as-of", type=int, required=True)
    args = parser.parse_args()
    try:
        result = review(read(args.case), read(args.review_packet), as_of=args.as_of)
    except (ValueError, OSError) as error:
        parser.exit(2, f"opinion review: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
