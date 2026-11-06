"""Run from any directory; disclose coverage and optionally retain a new receipt."""

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def source_state(root):
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip())
        return {"commit": head, "dirty": dirty, "authenticated": False}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None, "authenticated": False}


def verify(root=ROOT, *, require_no_skips=False, report_path=None):
    root = Path(root).resolve()
    started = time.perf_counter_ns()
    report = {
        "schema": "unfinished-commonwealth.verification.v1",
        "scope": "LOCAL_RESEARCH_ONLY", "external_authority": "NONE",
        "operator_limit": "The operator can rewrite code, tests, inputs and receipts together.",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "source": source_state(root),
        "require_no_skips": require_no_skips, "tests": None,
        "artifacts": {"status": "NOT_RUN", "json_files": 0, "documentation_links": 0},
        "problems": [],
    }
    try:
        run = subprocess.run([sys.executable, str(Path(__file__).with_name("verification_tests.py")), str(root)],
                             cwd=root, stdout=subprocess.PIPE, text=True, encoding="utf-8", timeout=600)
        tests = json.loads(run.stdout)
        # A missing/crashed result channel is not a zero-test success.
        fields = {"tests_run", "tests_not_skipped", "skipped", "failures", "errors", "expected_failures", "unexpected_successes", "successful"}
        if (type(tests) is not dict or set(tests) != fields or type(tests["tests_run"]) is not int
                or tests["tests_run"] < 0 or type(tests["successful"]) is not bool
                or type(tests["tests_not_skipped"]) is not int or not 0 <= tests["tests_not_skipped"] <= tests["tests_run"]
                or any(type(tests[k]) is not list for k in fields - {"tests_run", "tests_not_skipped", "successful"})):
            raise ValueError("malformed unittest result")
        report["tests"] = tests
        if run.returncode != 0 or not tests["successful"] or tests["failures"] or tests["errors"] or tests["unexpected_successes"]:
            report["problems"].append("TEST_FAILURE")
        if tests["tests_run"] == 0 and not tests["skipped"]:
            report["problems"].append("NO_TESTS_DISCOVERED")
        elif tests["tests_not_skipped"] == 0:
            report["problems"].append("ALL_TESTS_SKIPPED")
        if require_no_skips and tests["skipped"]:
            report["problems"].append("SKIPS_NOT_ALLOWED")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report["problems"].append("TEST_RUNNER_ERROR: " + str(exc))

    if not report["problems"]:
        checks = report["artifacts"]
        checks["status"] = "PASSED"
        try:
            for path in sorted(root.rglob("*.json")):
                if any(part in {".local", ".git", ".venv"} for part in path.relative_to(root).parts):
                    continue
                if report_path is not None and path.resolve() == Path(report_path).resolve():
                    continue
                json.loads(path.read_text(encoding="utf-8"))
                checks["json_files"] += 1
            for path in [root / "README.md", root / "ROADMAP.md", root / "CONTRIBUTING.md", *sorted((root / "docs").glob("*.md"))]:
                for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                    if "://" not in target and not target.startswith("#"):
                        destination = path.parent / target.split("#", 1)[0]
                        if not destination.exists():
                            raise ValueError(f"Broken local documentation link: {path.name}: {target}")
                        checks["documentation_links"] += 1
        except (OSError, ValueError) as exc:
            checks["status"] = "FAILED"
            report["problems"].append("ARTIFACT_CHECK_FAILED: " + str(exc))
    report["elapsed_ns"] = time.perf_counter_ns() - started
    report["status"] = ("FAILED" if report["problems"] else
                        "PASSED_WITH_SKIPS" if report["tests"]["skipped"] else "PASSED")
    report["all_tests_executed"] = bool(report["tests"] and report["tests"]["tests_run"] > 0
                                       and not report["tests"]["skipped"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="New JSON receipt path; existing files are never overwritten")
    parser.add_argument("--require-no-skips", action="store_true", help="Fail if any test is skipped")
    args = parser.parse_args(argv)
    try:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
        # Reserve before testing. An interrupted run may leave an incomplete
        # receipt; only a complete JSON report states an observed outcome.
        with args.report.open("x", encoding="utf-8") if args.report else nullcontext() as receipt:
            report = verify(require_no_skips=args.require_no_skips, report_path=args.report)
            if receipt is not None:
                json.dump(report, receipt, indent=2, sort_keys=True)
                receipt.write("\n")
                receipt.flush()
    except OSError as exc:
        print(f"VERIFICATION_RECEIPT_REFUSED: {exc}", file=sys.stderr)
        return 2
    tests = report["tests"]
    print(f"Verification: {report['status']}; tests={tests['tests_run'] if tests else 'unknown'}; "
          f"skipped={len(tests['skipped']) if tests else 'unknown'}; artifacts={report['artifacts']['status']}.")
    for problem in report["problems"]:
        print(problem, file=sys.stderr)
    print("Scope: local research; the operator can rewrite code, inputs and receipts; no external authority.")
    return 1 if report["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
