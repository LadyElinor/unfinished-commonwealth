"""Run G2 or replay one bounded JSONL episode; all effects are local fixtures."""

import argparse
import json
from pathlib import Path

from .experiment import run, replay
from ..coordination_v1.__main__ import unique_fields


def load_record(path, line):
    if type(line) is not int or not 1 <= line <= 2016:
        raise ValueError("line must be between 1 and 2016")
    with path.open("rb") as handle:
        for _ in range(line):
            raw = handle.readline(1024 * 1024 + 1)
            if not raw or len(raw) > 1024 * 1024:
                raise ValueError("missing or oversized G2 record")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("run").add_argument("directory", type=Path)
    check = sub.add_parser("replay")
    check.add_argument("file", type=Path)
    check.add_argument("--line", type=int, default=1)
    args = parser.parse_args()
    if args.mode == "run":
        result = run(args.directory)
        result = {k: result[k] for k in ("design", "episode_count", "episodes_sha256", "operator_limit")}
    else:
        result = replay(load_record(args.file, args.line))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
