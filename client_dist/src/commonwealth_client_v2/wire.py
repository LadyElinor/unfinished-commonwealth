"""Standalone B1 wire syntax. No workshop, evaluator or fixture imports.

JSON semantics copied from frozen workshop engine at 54199f7; credential and
wire constants from B1. This is compatibility code, not authority to execute.
"""
import json
import math
from pathlib import Path
import re

Rejected = ValueError
PROTOCOL = "unfinished-commonwealth.participant.v1"
MAX_BODY = 32768
MAX_RESPONSE = 2 * 1024 * 1024
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
TOKEN = re.compile(r"ucp1\.([0-9a-f]{32})\.([0-9a-f]{64})\Z")
HEAD = re.compile(r"[0-9a-f]{64}\Z")

def parse_json(source):
    """Read unambiguous, finite JSON with bounded container nesting."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Rejected(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise Rejected(f"nonfinite JSON number: {value}")

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            nonfinite(value)
        return parsed

    try:
        value = json.loads(source, object_pairs_hook=pairs,
                           parse_constant=nonfinite, parse_float=number)
    except RecursionError as exc:
        raise Rejected("JSON nesting exceeds 64 levels") from exc
    # Do not recurse here: a decoder may admit deeper values than deepcopy or
    # the canonical encoder can safely handle on the current Python version.
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth >= 64:
                raise Rejected("JSON nesting exceeds 64 levels")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)



def exact(obj, required, optional=()):
    if not isinstance(obj, dict):
        raise Rejected("a JSON object is required")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise Rejected(f"invalid fields: missing={sorted(missing)}, extra={sorted(extra)}")



def response(code, **fields):
    return {"protocol": PROTOCOL, "disposition": code,
            "external_authority": "NONE", **fields}


def read_credential(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(257)
    if len(raw) > 256:
        raise ValueError("invalid credential file")
    try:
        token = raw.decode("ascii").strip()
    except UnicodeError as exc:
        raise ValueError("invalid credential file") from exc
    if not TOKEN.fullmatch(token):
        raise ValueError("invalid credential file")
    return token


