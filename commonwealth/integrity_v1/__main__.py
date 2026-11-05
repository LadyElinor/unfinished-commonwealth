"""python -m commonwealth.integrity_v1 run DIRECTORY | replay JOURNAL"""

import argparse
import json
from pathlib import Path
from commonwealth.engine import parse_json
from . import VERSION
from .harness import evaluate, replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("directory")
    sub.add_parser("replay").add_argument("journal")
    args = parser.parse_args()
    try:
        if args.command == "run":
            report = evaluate(args.directory)
            result = {"version": VERSION, "runs": len(report["runs"]), "model_calls": 0,
                      "external_actions": 0, "status": report["status"]}
        else:
            with Path(args.journal).open("rb") as handle:
                raw = handle.read(1048577)
            if len(raw) > 1048576:
                raise ValueError("journal exceeds 1 MiB")
            result = replay(parse_json(raw.decode("utf-8")))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"integrity-v1: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
