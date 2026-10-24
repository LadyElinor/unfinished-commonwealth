"""Build and verify an offline source/wheel release with installed CLI smoke tests.

Requires locally available setuptools>=68, wheel, pip and venv. Never installs
build dependencies from a network or overwrites an existing output directory.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, cwd, expected=0):
    result = subprocess.run(arguments, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(
            f"Command failed ({result.returncode}, expected {expected}): {arguments!r}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def extract_source(source_archive, destination):
    # Windows temp paths may use an 8.3 alias (for example RUNNER~1).
    # Normalize BOTH the boundary and each member before comparing them.
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source_archive) as archive:
        for item in archive.getmembers():
            target = (root / item.name).resolve()
            if (not target.is_relative_to(root)
                    or not (item.isfile() or item.isdir())):
                raise RuntimeError(f"Unexpected unsafe source-archive member: {item.name!r}")
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(item) as incoming, target.open("wb") as handle:
                    shutil.copyfileobj(incoming, handle)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="new output directory for source archive, wheel and verification")
    args = parser.parse_args()
    output = Path(args.directory).resolve()
    output.mkdir(parents=True, exist_ok=False)
    run([sys.executable, "-c", "from setuptools.build_meta import build_sdist; "
         "import sys; build_sdist(sys.argv[1])", str(output)], ROOT)
    sources = list(output.glob("*.tar.gz"))
    if len(sources) != 1:
        raise RuntimeError("Expected exactly one source archive")
    with tempfile.TemporaryDirectory(prefix="commonwealth-package-") as temporary:
        temporary = Path(temporary).resolve()
        source_root = extract_source(sources[0], temporary / "source")
        roots = list(source_root.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise RuntimeError("Expected one source root")
        source = roots[0]
        for relative in ("README.md", "LICENSE", "docs/PROTOCOL.md",
                         "scripts/verify.py", "tests/test_workshop.py",
                         "commonwealth/data/scenarios.json", "docs/STUDY_V1_DESIGN.md",
                         "commonwealth/study_v1/engine.py", "tests/test_study_scheduler.py",
                         "examples/study-v1-summary.json", "commonwealth/procedure_v1/engine.py",
                         "docs/PROCEDURAL_REVIEW_V1.md", "examples/procedure-v1-results.json",
                         "commonwealth/discernment_v1/engine.py", "docs/FRAUD_DISCERNMENT_V1.md",
                         "examples/discernment-v1-summary.json", "tests/test_discernment_v1.py",
                         "commonwealth/integrity_v1/harness.py", "commonwealth/integrity_v1/claims.py",
                         "docs/INTEGRITY_V1.md", "docs/INTEGRITY_SOURCE_REVIEW.md",
                         "examples/integrity-v1-summary.json", "tests/test_integrity_v1.py",
                         "commonwealth/review_v1/engine.py", "docs/REVIEW_V1.md",
                         "examples/review-v1-summary.json", "tests/test_review_v1.py"):
            if not (source / relative).is_file():
                raise RuntimeError(f"Source archive omitted {relative}")
        # Run the same checks on what downstream source users actually receive.
        run([sys.executable, "scripts/verify.py"], source)
        run([sys.executable, "-c", "from setuptools.build_meta import build_wheel; "
             "import sys; build_wheel(sys.argv[1])", str(output)], source)
        wheels = list(output.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Expected exactly one wheel")
        with zipfile.ZipFile(wheels[0]) as archive:
            if "commonwealth/data/scenarios.json" not in archive.namelist():
                raise RuntimeError("Wheel omitted fixture data")
        environment = temporary / "venv"
        run([sys.executable, "-m", "venv", str(environment)], temporary)
        executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = environment / ("Scripts/commonwealth.exe" if os.name == "nt" else "bin/commonwealth")
        run([str(executable), "-m", "pip", "install", "--no-index", "--no-deps",
             "--no-cache-dir", str(wheels[0])], temporary)
        # This cwd has no package source: both entry points must use the wheel.
        smoke = temporary / "installed-smoke"
        smoke.mkdir()
        installed = json.loads(run([str(executable), "-c",
            "import json, commonwealth; from importlib.metadata import version; "
            "print(json.dumps({'module_version': commonwealth.__version__, "
            "'distribution_version': version('unfinished-commonwealth')}))"], smoke))
        if installed["module_version"] != installed["distribution_version"]:
            raise RuntimeError("Installed module and distribution versions disagree")
        fixtures = json.loads(run([str(command), "scenarios"], smoke))
        if set(fixtures) != {"missing", "signed", "flagged"}:
            raise RuntimeError("Installed package fixtures differ")
        run([str(executable), "-m", "commonwealth", "demo", "demo.sqlite",
             "--report", "demo.md"], smoke)
        replay = json.loads(run([str(command), "verify", "demo.sqlite"], smoke))
        if not replay["verified"] or replay["events"] != 24:
            raise RuntimeError("Installed demonstration did not replay")
        comparison = json.loads(run([str(command), "evaluate", "comparison"], smoke))
        if len(comparison["runs"]) != 15:
            raise RuntimeError("Installed comparison did not run all fixtures")
        expected_arms = {"single", "team-primary-only", "coached", "coached+casebook",
                         "constant-quality-stream"}
        expected_runs = {(scenario, arm) for scenario in fixtures for arm in expected_arms}
        if {(item["scenario"], item["arm"]) for item in comparison["runs"]} != expected_runs:
            raise RuntimeError("Installed comparison omitted a scenario/arm pair")
        study = json.loads(run([str(executable), "-m", "commonwealth.study_v1",
                               "run", "study-v1"], smoke))
        if study["runs"] != 432 or study["model_calls"] != 0:
            raise RuntimeError("Installed study harness omitted its deterministic matrix")
        study_replay = json.loads(run([str(executable), "-m", "commonwealth.study_v1",
            "replay", "study-v1/journals/decision-slots-v1--yield-urgent--always-inspect.json"], smoke))
        if study_replay["verified"] is not True or study_replay["events"] != 8:
            raise RuntimeError("Installed study failure record did not replay")
        procedure = json.loads(run([str(executable), "-m", "commonwealth.procedure_v1",
                                   "run", "procedure-v1"], smoke))
        if procedure["traces"] != 8 or procedure["model_calls"] != 0:
            raise RuntimeError("Installed procedural extension omitted a trace")
        procedure_replay = json.loads(run([str(executable), "-m", "commonwealth.procedure_v1",
            "replay", "procedure-v1/journals/terminal-appeal.json"], smoke))
        if procedure_replay["verified"] is not True:
            raise RuntimeError("Installed unresolved appeal record did not replay")
        historical = json.loads((source / "tests/data/procedure-v100-journals.json").read_text(encoding="utf-8"))["appeal-remand"]
        (smoke / "historical-procedure.json").write_text(json.dumps(historical), encoding="utf-8")
        historical_procedure = json.loads(run([str(executable), "-m", "commonwealth.procedure_v1",
            "replay", "historical-procedure.json"], smoke))
        if historical_procedure["verified"] is not True or historical_procedure["head"] != historical["terminal"]["head"]:
            raise RuntimeError("Installed historical procedural journal did not replay")
        discernment = json.loads(run([str(executable), "-m", "commonwealth.discernment_v1",
                                     "run", "discernment-v1"], smoke))
        if discernment["runs"] != 150 or discernment["model_calls"] != 0 or discernment["external_actions"] != 0:
            raise RuntimeError("Installed discernment study omitted a run or changed its boundary")
        discernment_replay = json.loads(run([str(executable), "-m", "commonwealth.discernment_v1",
            "replay", "discernment-v1/journals/compromised-trusted-roots--evidence-gate.json"], smoke))
        if discernment_replay["verified"] is not True:
            raise RuntimeError("Installed compromised-source failure did not replay")
        integrity = json.loads(run([str(executable), "-m", "commonwealth.integrity_v1",
                                   "run", "integrity-v1"], smoke))
        if integrity["runs"] != 112 or integrity["model_calls"] != 0 or integrity["external_actions"] != 0:
            raise RuntimeError("Installed integrity study omitted a run or changed its boundary")
        integrity_replay = json.loads(run([str(executable), "-m", "commonwealth.integrity_v1",
            "replay", "integrity-v1/journals/undetected-compromise--integrity-gate.json"], smoke))
        if integrity_replay["verified"] is not True:
            raise RuntimeError("Installed undetected-compromise failure did not replay")
        review = json.loads(run([str(executable), "-m", "commonwealth.review_v1", "run", "review-v1"], smoke))
        if review["traces"] != 14 or review["model_calls"] != 0 or review["external_actions"] != 0:
            raise RuntimeError("Installed balanced review omitted a trace or changed its boundary")
        review_replay = json.loads(run([str(executable), "-m", "commonwealth.review_v1", "replay",
            "review-v1/journals/new-evidence-reconsideration.json", "--parent",
            "review-v1/journals/false-but-procedurally-valid.json"], smoke))
        if review_replay["verified"] is not True or review_replay["parent_verified"] is not True:
            raise RuntimeError("Installed reconsideration failed exact-parent replay")
        readiness = json.loads(run([str(command), "readiness"], smoke, expected=2))
        if readiness["deployment_ready"] is not False:
            raise RuntimeError("Research-only readiness boundary changed")
        result = {
            "source_archive": sources[0].name, "wheel": wheels[0].name,
            "source_checks": "PASSED", "clean_install": "PASSED",
            "installed_version": installed["module_version"],
            "installed_entry_points": ["commonwealth", "python -m commonwealth"],
            "packaged_scenarios": sorted(fixtures), "demo_replay": replay,
            "comparison_runs": len(comparison["runs"]),
            "study_runs": study["runs"], "study_replay": study_replay,
            "procedure_traces": procedure["traces"], "procedure_replay": procedure_replay,
            "historical_procedure_replay": historical_procedure,
            "discernment_runs": discernment["runs"], "discernment_replay": discernment_replay,
            "integrity_runs": integrity["runs"], "integrity_replay": integrity_replay,
            "review_traces": review["traces"], "review_replay": review_replay,
            "readiness_exit": 2, "model_calls": 0,
            "scope": "LOCAL_RESEARCH_ONLY",
        }
        (output / "package-verification.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
