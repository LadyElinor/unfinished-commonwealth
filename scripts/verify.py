"""Run from any directory. No installation, API keys, or network needed."""

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    if run.returncode:
        return run.returncode
    for path in ROOT.rglob("*.json"):
        if ".local" in path.parts or ".git" in path.parts:
            continue
        json.loads(path.read_text(encoding="utf-8"))
    for path in [ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("#"):
                destination = path.parent / target.split("#", 1)[0]
                if not destination.exists():
                    raise SystemExit(f"Broken local documentation link: {path.name}: {target}")
    print("Behavioral tests, packaged JSON, and local documentation links passed.")
    print("Scope: local research; no model-backed evaluation or external authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
