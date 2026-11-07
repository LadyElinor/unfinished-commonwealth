"""Assess a curated Relay-inspired packet; print advisory JSON, never execute."""

import argparse
import json
from pathlib import Path

from .assistance import SCHEMA as ASSISTANCE_SCHEMA
from .review import review


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field: " + key)
        result[key] = value
    return result


def load_packet(path):
    # Reject ambiguity before JSON can silently replace warnings or findings.
    with path.open("rb") as handle:
        data = handle.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("packet exceeds 1 MiB")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--as-of", type=int, required=True, help="inclusive observation time in fixture units")
    args = parser.parse_args()
    result = review(load_packet(args.packet), as_of=args.as_of)
    if result["version"] == ASSISTANCE_SCHEMA:
        # The local input retains the person's account. Keep it out of routine CLI output.
        del result["packet"]
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
