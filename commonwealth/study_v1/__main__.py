"""python -m commonwealth.study_v1 run DIRECTORY | replay JOURNAL"""

import argparse
import json
from pathlib import Path

from .engine import replay
from .experiment import evaluate


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run").add_argument("directory")
    sub.add_parser("replay").add_argument("journal")
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = evaluate(args.directory)
            result = {"status": result["status"], "runs": len(result["runs"]),
                      "design_digest": result["design_digest"], "model_calls": 0}
        else:
            text = Path(args.journal).read_text(encoding="utf-8")
            result = replay(json.loads(text, object_pairs_hook=unique_object))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"study-v1: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
