"""Draw the prespecified synthetic successor cohort from one published 256-bit seed."""

import argparse
from fractions import Fraction
import json
import random
import re
from pathlib import Path


def draw(seed):
    if not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("seed must be 64 lowercase hexadecimal characters")
    rng = random.Random(int(seed, 16))
    cells = [(pattern, tight) for pattern in ("compatible", "zero", "negative", "flagged")
             for tight in (False, True) for _ in range(3)]
    rng.shuffle(cells)
    cases = []
    for index, (pattern, tight) in enumerate(cells, 1):
        size = rng.randint(4, 10)
        peer_size = rng.randint(3, 12)
        rows = [(rng.randint(2, 25), True) for _ in range(size - 2)]
        rows.append((None, False))
        if pattern == "compatible":
            extra = (rng.randint(2, 25), True)
        elif pattern == "zero":
            extra = (0, True)
        elif pattern == "negative":
            extra = (-rng.randint(1, 15), True)
        else:
            extra = (rng.randint(31, 60), False)
        rows.append(extra)
        rng.shuffle(rows)
        eligible = [value for value, valid in rows if valid]
        mean = Fraction(sum(eligible), len(eligible))
        two_pass_with_peer = 2 * size + peer_size
        if tight:
            capacity = rng.randint(max(2 * size, size + peer_size), two_pass_with_peer - 1)
        else:
            capacity = two_pass_with_peer + rng.randint(0, 4)
        fixture = {
            "description": "Synthetic paired successor workshop.",
            "contract": "quality-flags-v1",
            "capacity": capacity,
            "values": [value for value, _ in rows],
            "valid": [valid for _, valid in rows],
            "reference": {"numerator": mean.numerator, "denominator": mean.denominator},
            "peer_values": [rng.randint(-19, 25) for _ in range(peer_size)],
        }
        cases.append({"id": f"draw-{index:02d}", "fixture": fixture})
    return {"cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    packet = draw(args.seed)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(packet, indent=2) + "\n")


if __name__ == "__main__":
    main()
