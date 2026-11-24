"""Record and review software change proposals on a single Linux host."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys


def _object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate field")
        result[name] = value
    return result


def _read_request(path):
    limit = 64 * 1024
    if path is None:
        data = sys.stdin.buffer.read(limit + 1)
    else:
        with Path(path).open("rb") as source:
            data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError("request too large")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_object)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "verify"):
        commands.add_parser(name).add_argument("database")
    serve = commands.add_parser("serve", help="run the local kernel-authenticated socket service")
    serve.add_argument("--database", required=True)
    serve.add_argument("--socket", required=True)
    serve.add_argument("--submitter-uid", type=int, action="append", required=True)
    serve.add_argument("--reviewer-uid", type=int, action="append", required=True)
    ready = commands.add_parser("ready", help="check readiness as an admitted local account")
    ready.add_argument("--socket", required=True)
    client = commands.add_parser("request", help="read a JSON request from standard input or a file")
    client.add_argument("--socket", required=True)
    client.add_argument("--input", metavar="FILE")
    for name in ("backup", "restore"):
        item = commands.add_parser(name, help="create a new verified database file offline")
        item.add_argument("source")
        item.add_argument("destination")
        if name == "restore":
            item.add_argument("--expected-sha256", help="match a previously retained snapshot digest")
    check = commands.add_parser("check", help="verify the register, retained backup and operator thresholds")
    for name in ("database", "snapshot", "receipt"):
        check.add_argument(name)
    check.add_argument("--max-backup-age-seconds", type=int, required=True)
    check.add_argument("--min-free-bytes", type=int, required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if not sys.platform.startswith("linux"):
        print(json.dumps({"ok": False, "error": "linux_required"}), file=sys.stderr)
        return 1
    from . import monitor, recovery, service, store

    try:
        if args.command == "serve":
            service.serve(args.database, args.socket, args.submitter_uid, args.reviewer_uid)
            return 0
        if args.command in ("ready", "request"):
            try:
                payload = {"op": "ready"} if args.command == "ready" else _read_request(args.input)
            except (ValueError, RecursionError):
                print(json.dumps({"ok": False, "error": "invalid_request"}))
                return 2
            envelope = service.request(args.socket, payload)
            print(json.dumps(envelope, ensure_ascii=True, allow_nan=False))
            return 0 if envelope["ok"] else 2
        if args.command == "init":
            store.initialize(args.database)
            result = store.verify(args.database)
        elif args.command == "verify":
            result = store.verify(args.database)
        elif args.command == "check":
            result = monitor.check(args.database, args.snapshot, args.receipt,
                                   args.max_backup_age_seconds, args.min_free_bytes)
            print(json.dumps(result))
            return 0 if result["ok"] else 2
        elif args.command == "backup":
            result = recovery.backup(args.source, args.destination)
        else:
            result = recovery.restore(args.source, args.destination, expected_sha256=args.expected_sha256)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except recovery.PublicationUnconfirmed:
        error = "published_durability_unconfirmed"
    except store.DomainError as exc:
        error = exc.code
    except FileExistsError:
        error = "destination_exists"
    except PermissionError:
        error = "permission_denied"
    except (OSError, ValueError, sqlite3.Error):
        error = "operation_failed"
    print(json.dumps({"ok": False, "error": error}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
