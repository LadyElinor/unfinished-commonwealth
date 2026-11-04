"""AP1 research role. Produce an unsigned, scoped action for the Assembly 0.2 custodian."""
import argparse
import json
import sys

from adapter import PROFILE, SECRET, binding, fingerprint, read, require
from commonwealth_client_v2.wire import MAX_RESPONSE, canonical, exact

ROLE = "assembly-researcher"


def research_brief(review, job, actor, draft):
    reference = binding(review)
    require(reference and actor in review["research_agents"] and job in review["research_jobs"],
            "unknown registered research agent or assignment")
    item = review["research_jobs"][job]
    require(isinstance(draft, dict) and fingerprint(draft) == item["draft"], "different draft")
    available = []
    if review["exercise_day"] < item["due"] and not item["delivered"]:
        if item["selected"] == actor:
            available.append("deliver")
        elif item["selected"] is None and actor not in item["offered_by"]:
            available.append("offer")
    packet = {
        "profile": PROFILE, "role": ROLE, "external_authority": "NONE", "actor": actor, "job": job,
        "assembly_reference": reference, "question": item["question"], "source_draft": draft,
        "draft_digest": item["draft"], "due": item["due"], "terms": item["selected_terms"],
        "choices": available + ["decline"],
    }
    require(not SECRET.search(canonical(packet)), "credential-shaped text in research brief")
    return {"brief_id": fingerprint(packet), **packet}


def action(packet, reply):
    require(isinstance(reply, dict) and reply.get("profile") == PROFILE
            and reply.get("brief_id") == packet["brief_id"] and reply.get("choice") in packet["choices"],
            "response outside assignment or for a different brief")
    choice = reply["choice"]
    parts = {"offer": ("terms",), "deliver": ("report", "sources", "limits"), "decline": ("reason",)}[choice]
    exact(reply, ("profile", "brief_id", "choice", *parts))
    require(all(isinstance(reply[k], str) and reply[k].strip() and len(reply[k]) <= 16000 for k in parts)
            and not SECRET.search(canonical(reply)), "invalid research content")
    if choice == "decline":
        return {"state": "DECLINED_LOCALLY", "reason": reply["reason"], "external_authority": "NONE"}
    args = {"job": packet["job"], **{k: reply[k] for k in parts}}
    if choice == "deliver":
        args["draft"] = packet["draft_digest"]
    return {"type": choice, "args": args}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "job", "actor", "draft"):
        parser.add_argument(name)
    parser.add_argument("--response")
    args = parser.parse_args(argv)
    try:
        packet = research_brief(read(args.review, MAX_RESPONSE), args.job, args.actor,
                                read(args.draft, MAX_RESPONSE))
        result = action(packet, read(args.response, 128 * 1024)) if args.response else packet
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        print("Research role refused the input. Check the award, review and draft.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
