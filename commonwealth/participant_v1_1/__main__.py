"""B1.1 operator commands with a durable refusal-resistant clock floor."""

import argparse
from pathlib import Path
import sqlite3
import sys

from ..engine import canonical
from .demo import run
from .store import Boundary
from ..participant_v1.store import MAX_BODY, read_credential
from ..participant_v1.transport import Server, request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "upgrade", "audit"):
        sub.add_parser(name).add_argument("database")
    issue = sub.add_parser("issue")
    issue.add_argument("database")
    issue.add_argument("credential_file")
    issue.add_argument("--ttl", type=int, default=300)
    issue.add_argument("--attempts", type=int, default=8)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("database")
    revoke.add_argument("capability")
    receipt = sub.add_parser("operator-receipt")
    receipt.add_argument("database")
    receipt.add_argument("capability")
    receipt.add_argument("request_id")
    serve = sub.add_parser("serve")
    serve.add_argument("database")
    serve.add_argument("--port", type=int, default=0)
    for name in ("task", "submit", "receipt"):
        client = sub.add_parser(name)
        client.add_argument("url")
        client.add_argument("credential_file")
        if name == "submit":
            client.add_argument("request_file")
        if name == "receipt":
            client.add_argument("request_id")
    sub.add_parser("demo")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = run()
        elif args.command in ("task", "submit", "receipt"):
            token = read_credential(args.credential_file)
            raw = None
            method, path = "GET", "/task"
            if args.command == "submit":
                with Path(args.request_file).open("rb") as handle:
                    raw = handle.read(MAX_BODY + 1)
                method, path = "POST", "/proposals"
            elif args.command == "receipt":
                path = "/receipts/" + args.request_id
            status, result = request(args.url, token, method, path, raw)
            print(canonical({"http_status": status, **result}))
            return 0 if status == 200 else 3 if status == 0 else 2
        else:
            boundary = Boundary(args.database)
            if args.command == "serve":
                boundary.audit()
                with Server(boundary, port=args.port) as server:
                    print(canonical({"url": server.url, "scope": "LOCAL_RESEARCH_ONLY"}), flush=True)
                    server.serve_forever()
                return 0
            if args.command == "install":
                result = boundary.install()
            elif args.command == "audit":
                result = boundary.audit()
            elif args.command == "upgrade":
                result = boundary.upgrade()
            elif args.command == "issue":
                result = boundary.issue(args.credential_file, args.ttl, args.attempts)
            elif args.command == "revoke":
                result = boundary.revoke(args.capability)
            else:
                status, result = boundary.operator_receipt(args.capability, args.request_id)
                result = {"http_status": status, **result}
        print(canonical(result))
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, sqlite3.Error):
        # Avoid exposing paths, request data or secrets through error details.
        print(canonical({"error": "Operation refused; check local inputs and operator documentation."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
