"""Print a read-only assessment. No workshop database or signer is opened."""
import argparse
import json
import sys

from .importer import MAX_EXPORT, read_json, verify


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(read_json(args.record, MAX_EXPORT), read_json(args.checkpoint, 1024))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        print(f"Assembly import refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
