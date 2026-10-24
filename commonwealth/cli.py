"""Local command interface, including a JSON proposal handoff for external agents."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .coach import advise, inherited_method
from .engine import Rejected, parse_json
from .experiment import demo, evaluate, write_demo_report
from .interface import agent_view
from .pipeline import scenarios
from .report import markdown, summarize
from .store import CorruptJournal, Workshop


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False))


def parser():
    root = argparse.ArgumentParser(description="The Unfinished Commonwealth: local research workshop")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("init", "demo", "status", "state", "agent-view", "observe", "coach", "inherit", "verify", "report", "events"):
        item = sub.add_parser(name)
        item.add_argument("database", help="local workshop SQLite path")
        if name == "init":
            item.add_argument("--scenario", choices=list(scenarios()), default="missing")
        if name == "demo":
            item.add_argument("--report", help="write a new Markdown report (never overwrite)")
    proposal = sub.add_parser("propose")
    proposal.add_argument("database")
    proposal.add_argument("json_file", help="strict JSON proposal; see examples/proposal.json")
    for name in ("approve", "execute"):
        item = sub.add_parser(name)
        item.add_argument("database")
        item.add_argument("proposal")
    submit = sub.add_parser("submit", help="submit another typed event; no identity authentication is implied")
    submit.add_argument("database")
    submit.add_argument("json_file")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("database")
    handoff.add_argument("--scenario", required=True, choices=list(scenarios()))
    handoff.add_argument("--note", required=True)
    for name in ("halt", "resume", "revoke"):
        item = sub.add_parser(name)
        item.add_argument("database")
        item.add_argument("--reason", required=True)
    suite = sub.add_parser("evaluate")
    suite.add_argument("directory", help="new directory for the 15 exposed scripted runs")
    sub.add_parser("scenarios")
    sub.add_parser("readiness")
    return root


def read_command(path):
    # Bound the bytes actually read, not potentially stale size metadata.
    with Path(path).open("rb") as handle:
        source = handle.read(65537)
    if len(source) > 65536:
        raise Rejected("command file exceeds 64 KiB")
    return parse_json(source.decode("utf-8"))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        command = args.command
        if command == "scenarios":
            emit(scenarios())
            return 0
        if command == "readiness":
            emit({"status": "LOCAL_RESEARCH_ONLY", "external_authority": "NONE",
                  "model_evaluation": "NOT_RUN", "independent_participants": "NOT_ESTABLISHED",
                  "deployment_ready": False})
            return 2
        if command == "evaluate":
            emit(evaluate(args.directory))
            return 0
        if command == "init":
            workshop = Workshop.create(args.database, args.scenario)
            emit(summarize(workshop.state()))
            return 0
        if command == "demo":
            # Check report destination before producing the demonstration.
            if args.report and Path(args.report).exists():
                raise FileExistsError(args.report)
            workshop = demo(args.database)
            if args.report:
                write_demo_report(workshop, args.report)
            emit(summarize(workshop.state()))
            return 0
        workshop = Workshop(args.database)
        if command == "verify":
            emit(workshop.verify())
        elif command == "events":
            emit(workshop.events())
        elif command == "report":
            print(markdown(workshop.state()), end="")
        elif command in ("state", "agent-view", "status", "coach", "inherit"):
            state = workshop.state()
            emit({"state": lambda s: s, "agent-view": agent_view, "status": summarize, "coach": advise,
                  "inherit": inherited_method}[command](state))
        elif command in ("propose", "submit"):
            record = read_command(args.json_file)
            if command == "propose" and (not isinstance(record, dict) or record.get("action") != "propose"):
                raise Rejected("propose accepts only a proposal, never an approval or execution")
            emit(workshop.dispatch(record))
        elif command in ("approve", "execute", "observe"):
            actor = "keeper" if command == "approve" else workshop.state()["worker"]
            record = {"action": command, "actor": actor}
            if command != "observe":
                record["proposal"] = args.proposal
            emit(workshop.dispatch(record))
        elif command == "handoff":
            emit(workshop.dispatch({"action": "handoff", "actor": "keeper", "scenario": args.scenario,
                                    "fixture": scenarios()[args.scenario], "note": args.note}))
        elif command in ("halt", "resume", "revoke"):
            emit(workshop.dispatch({"action": command, "actor": "keeper", "reason": args.reason}))
        return 0
    except (Rejected, CorruptJournal, OSError, sqlite3.Error, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "status": "REFUSED"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
