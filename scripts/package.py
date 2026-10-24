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
        temporary = Path(temporary)
        source_root = temporary / "source"
        source_root.mkdir()
        with tarfile.open(sources[0]) as archive:
            for item in archive.getmembers():
                destination = (source_root / item.name).resolve()
                if (not destination.is_relative_to(source_root)
                        or not (item.isfile() or item.isdir())):
                    raise RuntimeError("Unexpected unsafe source-archive member")
                if item.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(item) as incoming, destination.open("wb") as target:
                        shutil.copyfileobj(incoming, target)
        roots = list(source_root.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise RuntimeError("Expected one source root")
        source = roots[0]
        for relative in ("README.md", "LICENSE", "docs/PROTOCOL.md",
                         "scripts/verify.py", "tests/test_workshop.py",
                         "commonwealth/data/scenarios.json"):
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
        if len(comparison["runs"]) != 12:
            raise RuntimeError("Installed comparison did not run all fixtures")
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
            "readiness_exit": 2, "model_calls": 0,
            "scope": "LOCAL_RESEARCH_ONLY",
        }
        (output / "package-verification.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
