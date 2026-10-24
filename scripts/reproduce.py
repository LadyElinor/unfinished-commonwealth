"""Produce new deterministic artifacts without overwriting earlier runs."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commonwealth.experiment import demo, evaluate, write_demo_report
from commonwealth.report import summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    args = parser.parse_args()
    output = Path(args.directory)
    output.mkdir(parents=True, exist_ok=False)
    workshop = demo(output / "demo.sqlite")
    write_demo_report(workshop, output / "demo.md")
    (output / "demo-summary.json").write_text(json.dumps(summarize(workshop.state()), indent=2) + "\n")
    (output / "demo-events.json").write_text(json.dumps(workshop.events(), indent=2) + "\n")
    (output / "replay.json").write_text(json.dumps(workshop.verify(), indent=2) + "\n")
    report = evaluate(output / "comparison")
    print(json.dumps({"demo": str(output / "demo.md"), "replay": workshop.verify(),
                      "comparison_runs": len(report["runs"]), "model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
