"""Exposed evaluator-owned cases. Never passed to a policy."""

from itertools import product
from .policies import POLICIES
from .resources import FACETS

REVIEWS = ("accurate", "delayed", "wrong", "unavailable")
# truth, three claims, claimed origins, actual origins
PATTERNS = {
    "agreement": ("M", ("M", "M", "M"), ("a", "b", "c"), ("a", "b", "c")),
    "lone-error": ("M", ("Y", "M", "M"), ("a", "b", "c"), ("a", "b", "c")),
    "disclosed-copy": ("M", ("Y", "Y", "M"), ("a", "a", "c"), ("a", "a", "c")),
    "concealed-copy": ("M", ("Y", "Y", "M"), ("a", "b", "c"), ("a", "a", "c")),
    "sparse": ("M", (None, "M", None), ("a", "b", "c"), ("a", "b", "c")),
    "silent": ("M", (None, None, None), ("a", "b", "c"), ("a", "b", "c")),
    "ambiguous-M": ("M", ("M", "Y", None), ("a", "b", "c"), ("a", "b", "c")),
    "ambiguous-Y": ("Y", ("M", "Y", None), ("a", "b", "c"), ("a", "b", "c")),
}


def complement(claim):
    return {None: None, "M": "Y", "Y": "M"}[claim]


def cells():
    return [dict(zip(("pattern", "swapped", "peer_work", "review"), values)) for values in
            product(PATTERNS, (False, True), (0, 4, 8), REVIEWS)]


def specification(cell):
    if (not isinstance(cell, dict) or set(cell) != {"pattern", "swapped", "peer_work", "review"}
            or not isinstance(cell["pattern"], str) or cell["pattern"] not in PATTERNS
            or type(cell["swapped"]) is not bool or type(cell["peer_work"]) is not int
            or cell["peer_work"] not in (0, 4, 8)
            or not isinstance(cell["review"], str) or cell["review"] not in REVIEWS):
        raise ValueError("invalid E1 cell")
    truth, claims, origins, actual = PATTERNS[cell["pattern"]]
    if cell["swapped"]:
        truth, claims = complement(truth), tuple(map(complement, claims))
    packets = [{"source": f"s{i+1}", "origin": origin, "claim": claim}
               for i, (claim, origin) in enumerate(zip(claims, origins))]
    return truth, packets, list(actual)


EPISODES = len(cells()) * len(POLICIES) * len(FACETS)
