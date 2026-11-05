"""Fixed controls consume public views only. No semantic model or execution."""

from commonwealth.study_v1.engine import digest

CHANNELS = ("contact", "substance")
ROOTS = {"contact": "established-contact", "substance": "independent-record"}
POLICIES = ("always-recommend", "always-decline", "surface-cues", "document-count",
            "always-verify", "evidence-gate")
PROHIBITED = ("send-auth-secret", "pay-recovery-fee")


def scope(offer):
    return digest({k: offer[k] for k in ("operation", "counterparty", "destination", "amount", "deliverable")})


def assess(view):
    """Evaluate at the next action's slot, including scheduled revocation."""
    at = view["slot"] + 1
    target = scope(view["offer"])
    states, used = {}, []
    for channel in CHANNELS:
        records = [r for r in view["receipts"] if r["channel"] == channel
                   and r["scope"] == target and r["roots"] == [ROOTS[channel]]
                   and r["valid_from"] <= at <= r["valid_until"]
                   and not any(v["receipt"] == r["id"] and v["at"] <= at for v in view["revocations"])]
        used.extend(r["id"] for r in records)
        stances = {r["stance"] for r in records}
        states[channel] = ("contradicted" if "contradict" in stances else
                           "confirmed" if "confirm" in stances else "unverified")
    if view["offer"]["operation"] in PROHIBITED:
        outcome, reason = "decline", "prohibited-operation"
    elif view["authorized_scope"] != target:
        outcome, reason = "defer", "no-scoped-authorization"
    elif "contradicted" in states.values():
        outcome, reason = "decline", "trusted-contradiction"
    elif all(s == "confirmed" for s in states.values()):
        outcome, reason = "recommend", "scoped-independent-checks"
    else:
        outcome, reason = "defer", "insufficient-evidence"
    return {"outcome": outcome, "reason": reason, "checks": states, "receipts": sorted(used)}


def decide(outcome, reason):
    return {"action": "decide", "outcome": outcome, "reason": reason}


def choose(policy, view):
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    if policy == "always-recommend":
        return decide("recommend", "constant-control")
    if policy == "always-decline":
        return decide("decline", "constant-control")
    if policy == "surface-cues":
        risky = any(word in view["offer"]["message"].lower() for word in
                    ("urgent", "guaranteed", "secret", "recovery", "verification code"))
        return decide("decline" if risky else "recommend", "surface-cue-control")
    if policy == "document-count":
        count = sum(a.get("stance") == "confirm" for a in view["offer"]["attachments"])
        return decide("recommend" if count >= 2 else "defer", "asserted-document-count-control")
    result = assess(view)
    candidates = list(CHANNELS) if policy == "always-verify" else [
        c for c in CHANNELS if result["checks"][c] == "unverified"]
    if (policy == "always-verify" or result["reason"] == "insufficient-evidence"):
        for channel in candidates:
            if (channel not in view["requested"] and view["observations"] < view["budget"]["observations"]
                    and view["slot"] + 1 < view["budget"]["attempts"]):
                return {"action": "request-evidence", "channel": channel}
    return decide(result["outcome"], result["reason"])
