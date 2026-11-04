"""Validate a bounded public export against a separately supplied checkpoint."""

from pathlib import Path

from commonwealth.engine import parse_json
from .recount_v02 import recount
from .rules_v02 import Assembly, RuleError, digest, encoded, fields, require

MAX_EVENTS = 1024
MAX_EXPORT = 2 * 1024 * 1024


def read_json(path, limit):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "input exceeds import limit")
    return parse_json(raw.decode("utf-8"))


def hex_string(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def check_pin(pin):
    fields(pin, "registry events head")
    require(hex_string(pin["registry"], 64) and hex_string(pin["head"], 64)
            and type(pin["events"]) is int and 0 <= pin["events"] <= MAX_EVENTS,
            "invalid external checkpoint")


def verify(record, pin):
    # The core installation must remain usable with no signing library installed.
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuleError("Assembly import requires the optional assembly dependency") from exc

    fields(record, "registry entries checkpoint")
    check_pin(pin)
    check_pin(record["checkpoint"])
    require(record["checkpoint"] == pin, "checkpoint mismatch")
    reg, entries = record["registry"], record["entries"]
    head = digest(reg)
    require(head == pin["registry"] and isinstance(entries, list)
            and len(entries) == pin["events"], "registry or count mismatch")
    state = Assembly(reg)
    used = set()
    for index, envelope in enumerate(entries, 1):
        fields(envelope, "body signature")
        body = envelope["body"]
        fields(body, "registry actor nonce command")
        actor = body["actor"]
        require(isinstance(actor, str) and actor in reg["people"]
                and body["registry"] == pin["registry"], "signer or instance mismatch")
        require(hex_string(body["nonce"], 32) and body["nonce"] not in used,
                "invalid or repeated action nonce")
        require(hex_string(envelope["signature"], 128), "invalid Ed25519 signature encoding")
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(reg["people"][actor]["key"]))
        try:
            public.verify(bytes.fromhex(envelope["signature"]), encoded(body))
        except InvalidSignature as exc:
            raise RuleError("invalid Ed25519 signature") from exc
        state.apply(actor, body["command"])
        head = digest([head, index, envelope])
        used.add(body["nonce"])
    require(head == pin["head"], "signed event history differs from checkpoint")
    rounds = recount(record, state)
    return {
        "schema": "unfinished-commonwealth.assembly-review.v1",
        "checkpoint": pin, "public_recount": rounds,
        "bill": ({"ref": state.bill["ref"], "phase": state.bill["phase"]}
                 if state.bill else None),
        "polities": [{"poll_ref": key, "polity": poll["polity"], "count_status": poll["phase"]}
                     for key, poll in sorted(state.polls.items())],
        "exercise_day": state.day,
        "research_agents": sorted(a for a, seat in reg["people"].items() if seat["role"] == "agent"),
        "research_jobs": {
            job: {"question": j["question"], "draft": j["draft"], "due": j["due"],
                  "offered_by": sorted(j["offers"]), "selected": j["agent"],
                  "selected_terms": j["offers"].get(j["agent"]), "delivered": j["result"] is not None}
            for job, j in state.jobs.items()
        },
        "scope": "LOCAL_RESEARCH_ONLY", "external_authority": "NONE",
        "authority_granted": False, "permits_execution": False,
        "truth_of_returns": "NOT_ESTABLISHED", "checkpoint_custody": "OPERATOR_SUPPLIED",
    }
