"""Provider-neutral AP1 bridge. Only explicit C2 retry may send a proposal."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

from commonwealth_client_v2.store import INSTANCE, Outbox
from commonwealth_client_v2.transport import request
from commonwealth_client_v2.wire import (
    HEAD, MAX_BODY, MAX_RESPONSE, PROTOCOL, canonical, exact, parse_json, read_credential,
)

PROFILE = "unfinished-commonwealth.agent-participation.v1"
PROFILE_1_1 = "unfinished-commonwealth.agent-participation.v1.1"
TASK = "unfinished-commonwealth.proposal.v1"
SECRET = re.compile(r"ucp1\.[0-9a-f]{32}\.[0-9a-f]{64}")


def require(test, message):
    if not test:
        raise ValueError(message)


def read(path, limit):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "input exceeds bound")
    return parse_json(raw.decode("utf-8"))


def fingerprint(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def binding(review):
    """Select a reference from operator-supplied data. Never attest its provenance."""
    if review is None:
        return None
    require(isinstance(review, dict) and review.get("schema") == "unfinished-commonwealth.assembly-review.v1"
            and review.get("scope") == "LOCAL_RESEARCH_ONLY" and review.get("external_authority") == "NONE"
            and review.get("authority_granted") is False and review.get("permits_execution") is False,
            "unsupported assembly review")
    pin = review.get("checkpoint")
    exact(pin, ("head", "events", "registry"))
    require(matches(HEAD, pin["head"]) and matches(HEAD, pin["registry"])
            and type(pin["events"]) is int and 0 <= pin["events"] <= 1024, "bad docket reference")
    return {"kind": "operator-supplied-checkpoint", "checkpoint": pin}


def projected_work(view, selected):
    """Whitelist public scalar fields inside each record; do not forward future host fields."""
    def scalars(obj, names):
        require(isinstance(obj, dict), "invalid public record")
        kept = {k: obj[k] for k in names.split() if k in obj}
        require(all(type(v) in (int, bool, str) for v in kept.values()), "nested private context")
        return kept

    work = scalars(view, "worker generation revision scenario contract peer_queue_length halted successor_observation_required")
    data = view["data"]
    require(isinstance(data, dict), "invalid task data")
    values, flags = data["values"], data["valid"]
    require(isinstance(values, list) and isinstance(flags, list) and len(values) == len(flags)
            and all(x is None or type(x) is int for x in values) and all(type(x) is bool for x in flags),
            "invalid public readings")
    work["data"] = {**scalars(data, "contract capacity"), "values": values, "valid": flags}
    require(isinstance(view["recent_observations"], list) and isinstance(view["counterstory_data"], list)
            and isinstance(view["testimony_data"], dict) and isinstance(view["lessons"], dict),
            "invalid public account containers")
    work["methods"] = scalars(view["methods"], "quality-stream positive-only zero-fill")
    require(work["methods"] and all(isinstance(v, str) for v in work["methods"].values()), "invalid method offer")
    work["recent_observations"] = [scalars(o, "id tick scenario method generation new_peer_on_time peer_jobs_pending")
                                   for o in view["recent_observations"]]
    work["testimony_data"] = {k: scalars(o, "observation account actor status") for k, o in view["testimony_data"].items()}
    work["counterstory_data"] = [scalars(o, "id reference account actor") for o in view["counterstory_data"]]
    work["lessons"] = {k: scalars(o, "scope method guidance worker status review_status requires_review")
                       for k, o in view["lessons"].items()}
    require(set(work) == set(selected), "incomplete projected work")
    return work


def brief(task, review=None, profile=PROFILE):
    require(profile in (PROFILE, PROFILE_1_1), "unsupported participation profile")
    exact(task, ("protocol", "disposition", "external_authority", "instance", "view_head",
                 "attempts_remaining", "task"))
    require(task["protocol"] == PROTOCOL and task["disposition"] == "TASK"
            and task["external_authority"] == "NONE" and matches(INSTANCE, task["instance"])
            and matches(HEAD, task["view_head"]) and type(task["attempts_remaining"]) is int
            and task["attempts_remaining"] >= 0, "unsupported host task")
    view = task["task"]
    require(isinstance(view, dict) and view.get("protocol") == TASK
            and view.get("external_authority") == "NONE" and view.get("scope") == "LOCAL_RESEARCH"
            and isinstance(view.get("methods"), dict) and view["methods"]
            and type(view.get("halted")) is bool and type(view.get("successor_observation_required")) is bool,
            "unsupported workshop view")
    selected = ("worker", "generation", "revision", "scenario", "contract", "data", "methods",
                "peer_queue_length", "recent_observations", "testimony_data", "counterstory_data",
                "lessons", "successor_observation_required", "halted")
    packet = {"profile": profile, "role": "workshop-proposer", "external_authority": "NONE",
              "instance": task["instance"], "view_head": task["view_head"],
              "attempts_remaining": task["attempts_remaining"], "work": (projected_work(view, selected) if profile == PROFILE_1_1 else {k: view[k] for k in selected}),
              "assembly_reference": binding(review)}
    require(not SECRET.search(canonical(packet)), "credential-shaped text in agent brief")
    return {"brief_id": fingerprint(packet), **packet}


def interpret(packet, reply):
    require(isinstance(reply, dict) and reply.get("profile") == packet["profile"] and packet["profile"] in (PROFILE, PROFILE_1_1)
            and reply.get("brief_id") == packet["brief_id"], "response does not identify this brief")
    require(not SECRET.search(canonical(reply)), "credential-shaped text in response")
    local = ("decline", "wait", "request-evidence") if packet["profile"] == PROFILE_1_1 else ("decline",)
    if reply.get("choice") in local:
        exact(reply, ("profile", "brief_id", "choice", "reason"))
        require(isinstance(reply["reason"], str) and 0 < len(reply["reason"].strip())
                and len(reply["reason"]) <= 4000, "invalid local decision reason")
        return None
    exact(reply, ("profile", "brief_id", "choice", "method", "prediction", "purpose"))
    require(reply["choice"] == "propose" and isinstance(reply["method"], str)
            and reply["method"] in packet["work"]["methods"], "method outside offered choices")
    require(packet["attempts_remaining"] > 0 and not packet["work"]["halted"]
            and not packet["work"]["successor_observation_required"], "workshop currently unavailable")
    exact(reply["prediction"], ("primary_correct", "peer_on_time"))
    require(all(type(x) in (int, float) and 0 <= x <= 1 for x in reply["prediction"].values()),
            "predictions must be probabilities")
    require(isinstance(reply["purpose"], str) and reply["purpose"].strip()
            and len(reply["purpose"]) <= 4000, "invalid public purpose")
    proposal = {k: reply[k] for k in ("method", "prediction", "purpose")}
    return {"protocol": PROTOCOL, "request_id": "ap1-" + fingerprint(reply)[:48],
            "view_head": packet["view_head"], "proposal": proposal}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    get = commands.add_parser("observe")
    get.add_argument("url")
    get.add_argument("credential")
    for name in ("brief", "check", "stage"):
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--assembly-review")
        sub.add_argument("--profile", choices=(PROFILE, PROFILE_1_1), default=PROFILE)
        if name != "brief":
            sub.add_argument("response")
        if name == "stage":
            for arg in ("outbox", "url", "credential"):
                sub.add_argument(arg)
    args = parser.parse_args(argv)
    try:
        if args.command == "observe":
            token = read_credential(args.credential)
            status, task = request(args.url, token)
            require(status == 200, "could not retrieve authorized task")
            brief(task)
            require(not SECRET.search(canonical(task)), "credential-shaped text in host reply")
            result = task
        else:
            task = read(args.task, MAX_RESPONSE)
            review = read(args.assembly_review, MAX_RESPONSE) if args.assembly_review else None
            packet = brief(task, review, args.profile)
            result = packet
            if args.command in ("check", "stage"):
                reply = read(args.response, MAX_BODY)
                envelope = interpret(packet, reply)
                if envelope is None:
                    states = {"decline": "DECLINED_LOCALLY", "wait": "WAITING_LOCALLY",
                              "request-evidence": "EVIDENCE_REQUESTED_LOCALLY"}
                    result = {"state": states[reply["choice"]], "brief_id": packet["brief_id"],
                              "reason": reply["reason"], "external_authority": "NONE"}
                elif args.command == "check":
                    result = envelope
                else:
                    result = Outbox.stage(args.outbox, args.url, read_credential(args.credential),
                                          task, canonical(envelope).encode("utf-8"))
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError, sqlite3.Error, RecursionError):
        print("AP1 refused the input. Preserve any existing intent and inspect the original task.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
