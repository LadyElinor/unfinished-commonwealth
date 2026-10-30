"""python -m commonwealth.procedure_v1 run DIRECTORY | replay JOURNAL"""

import argparse
import json
from pathlib import Path

from commonwealth.study_v1.__main__ import unique_object
from commonwealth.study_v1.engine import replay as replay_d1
from . import VERSION
from .engine import replay
from .experiment import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("directory")
    sub.add_parser("replay").add_argument("journal")
    args = parser.parse_args()
    try:
        if args.command == "run":
            report = evaluate(args.directory)
            result = {"version": VERSION, "traces": len(report["runs"]),
                      "model_calls": 0, "status": report["status"]}
        else:
            journal = json.loads(Path(args.journal).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
            if not isinstance(journal, dict) or not isinstance(journal.get("genesis"), dict):
                raise ValueError("journal object and genesis required")
            result = (replay(journal) if journal["genesis"].get("version") in (VERSION, "procedure-1.0.0")
                      else replay_d1(journal))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"procedure-v1: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
