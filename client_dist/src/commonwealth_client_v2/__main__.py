"""C2 standalone durable intent staging, lookup and exact-byte retry."""

import argparse
from pathlib import Path
import sqlite3
import sys

from .wire import canonical, parse_json, MAX_BODY, MAX_RESPONSE, read_credential
from .store import Outbox


def bounded(path, limit):
    with Path(path).open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input too large")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage")
    stage.add_argument("outbox")
    stage.add_argument("url")
    stage.add_argument("credential_file")
    stage.add_argument("task_file")
    stage.add_argument("request_file")
    for name in ("status", "resolve", "retry"):
        operation = sub.add_parser(name)
        operation.add_argument("outbox")
        if name != "status":
            operation.add_argument("credential_file")
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            result = Outbox.stage(args.outbox, args.url, read_credential(args.credential_file),
                                  parse_json(bounded(args.task_file, MAX_RESPONSE).decode("utf-8")),
                                  bounded(args.request_file, MAX_BODY))
        elif args.command == "status":
            result = Outbox(args.outbox).status()
        else:
            result = Outbox(args.outbox).operate(read_credential(args.credential_file), args.command)
        print(canonical(result))
        return 0 if args.command in ("stage", "status") or result["state"] == "RECORDED" else 3
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(canonical({"error": "Outbox refused; preserve the original intent and inspect local inputs. No new request ID or credential was created."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
