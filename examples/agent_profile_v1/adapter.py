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


def brief(task, review=None):
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
    packet = {"profile": PROFILE, "role": "workshop-proposer", "external_authority": "NONE",
              "instance": task["instance"], "view_head": task["view_head"],
              "attempts_remaining": task["attempts_remaining"], "work": {k: view[k] for k in selected},
              "assembly_reference": binding(review)}
    require(not SECRET.search(canonical(packet)), "credential-shaped text in agent brief")
    return {"brief_id": fingerprint(packet), **packet}


def interpret(packet, reply):
    require(isinstance(reply, dict) and reply.get("profile") == PROFILE
            and reply.get("brief_id") == packet["brief_id"], "response does not identify this brief")
    require(not SECRET.search(canonical(reply)), "credential-shaped text in response")
    if reply.get("choice") == "decline":
        exact(reply, ("profile", "brief_id", "choice", "reason"))
        require(isinstance(reply["reason"], str) and 0 < len(reply["reason"].strip())
                and len(reply["reason"]) <= 4000, "invalid decline reason")
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
            packet = brief(task, review)
            result = packet
            if args.command in ("check", "stage"):
                reply = read(args.response, MAX_BODY)
                envelope = interpret(packet, reply)
                if envelope is None:
                    result = {"state": "DECLINED_LOCALLY", "brief_id": packet["brief_id"],
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
