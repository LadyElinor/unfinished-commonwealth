"""Run/replay synthetic A1 traces, review a Relay/Terra packet, or compare curated statements."""

import argparse
import json
from pathlib import Path

from commonwealth.engine import parse_json
from . import VERSION
from .engine import replay
from .experiment import evaluate
from .records import compare, review


def read(path, maximum=16 * 1048576):
    with Path(path).open("rb") as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("input exceeds byte limit")
    return parse_json(raw.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("directory")
    for name in ("replay", "review", "compare"):
        sub.add_parser(name).add_argument("file")
    args = parser.parse_args()
    try:
        if args.command == "run":
            report = evaluate(args.directory)
            result = {"version": VERSION, "traces": len(report["traces"]), "language_cases": len(report["language"]),
                      "model_calls": 0, "external_actions": 0, "status": report["status"]}
        elif args.command == "review":
            result = review(read(args.file, 120000))
        elif args.command == "compare":
            result = compare(**read(args.file, 120000))
        else:
            result = replay(read(args.file))
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"authority-v1: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
