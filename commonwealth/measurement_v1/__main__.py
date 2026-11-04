"""Run the frozen, exposed C1c comparison from a checkout, or packaged source with a supplied policy."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from ..study_v1.experiment import write_json
from . import OPERATOR_LIMIT, participant, workshop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("readiness")
    run = sub.add_parser("run")
    run.add_argument("directory", type=Path)
    run.add_argument("--fixture-agent", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "readiness":
        print(json.dumps({"status": "LOCAL_RESEARCH_ONLY", "deployment_ready": False, "operator_limit": OPERATOR_LIMIT}))
        return 2
    agent = args.fixture_agent.resolve(strict=True)
    args.directory.mkdir(parents=True, exist_ok=False)
    historical = workshop.run(args.directory / "historical")
    comparison = participant.run(args.directory / "external", agent)
    result = {"design": "C1c-1", "design_commit": "2a23d1fecd25445e5fd9f6ae08648ed4f0efe400", "operator_limit": OPERATOR_LIMIT,
              "fixture_agent_sha256": sha256(agent.read_bytes()).hexdigest(), "workshop": historical,
              "external_study": comparison, "model_calls": 0}
    write_json(args.directory / "results.json", result)
    print(json.dumps({"workshop_rows": len(historical["runs"]), "external_rows": len(comparison["cases"]),
                      "operator_limit": OPERATOR_LIMIT}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
