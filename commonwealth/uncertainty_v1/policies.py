"""Fixed policies see purchased packets only; no simulator or scoring imports."""

POLICIES = ("constant-M", "constant-Y", "source-majority", "origin-majority", "corroborate-or-abstain")


def validate(policy, packets):
    if policy not in POLICIES or not isinstance(packets, list) or len(packets) > 3:
        raise ValueError("unsupported policy input")
    ids = set()
    for packet in packets:
        if (not isinstance(packet, dict) or set(packet) != {"source", "origin", "claim"}
                or packet["source"] not in ("s1", "s2", "s3") or packet["source"] in ids
                or packet["origin"] not in ("a", "b", "c") or packet["claim"] not in ("M", "Y", None)):
            raise ValueError("invalid purchased packet")
        ids.add(packet["source"])


def early_agreement(packets):
    return (len(packets) == 2 and packets[0]["claim"] is not None
            and packets[0]["claim"] == packets[1]["claim"]
            and packets[0]["origin"] != packets[1]["origin"])


def wants_source(policy, packets, attempts):
    validate(policy, packets)
    if type(attempts) is not int or not 0 <= attempts <= 3 or len(packets) > attempts:
        raise ValueError("invalid source attempts")
    return (not policy.startswith("constant-") and attempts < 3
            and not (policy == "corroborate-or-abstain" and early_agreement(packets)))


def choose(policy, packets):
    validate(policy, packets)
    if policy.startswith("constant-"):
        return policy[-1]
    groups = {}
    for p in packets:
        if p["claim"] is not None:
            groups.setdefault(p["origin"], set()).add(p["claim"])
    if policy == "corroborate-or-abstain":
        claims = {p["claim"] for p in packets if p["claim"] is not None}
        return next(iter(claims)) if len(claims) == 1 and len(groups) >= 2 else None
    votes = ([p["claim"] for p in packets if p["claim"] is not None] if policy == "source-majority"
             else [next(iter(group)) for group in groups.values() if len(group) == 1])
    m, y = votes.count("M"), votes.count("Y")
    return "M" if m > y else "Y" if y > m else None
