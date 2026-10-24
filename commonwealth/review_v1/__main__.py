"""python -m commonwealth.review_v1 run DIRECTORY | replay JOURNAL [--parent JOURNAL]"""

import argparse
import json
from pathlib import Path
from commonwealth.engine import parse_json
from . import VERSION
from .engine import replay
from .experiment import evaluate


def read(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("journal exceeds 1 MiB")
    return parse_json(raw.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("directory")
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("journal")
    replay_parser.add_argument("--parent")
    args = parser.parse_args()
    try:
        if args.command == "run":
            report = evaluate(args.directory)
            result = {"version": VERSION, "traces": len(report["traces"]), "model_calls": 0,
                      "external_actions": 0, "status": report["status"]}
        else:
            result = replay(read(args.journal), parent=read(args.parent) if args.parent else None)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"review-v1: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
