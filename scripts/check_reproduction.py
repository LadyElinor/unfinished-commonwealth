"""Compare the three first-reproduction summaries with the published files."""

import argparse
from pathlib import Path


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SUMMARIES = (
    ("d1/summary.json", "study-v1-summary.json"),
    ("neighbor/results.json", "neighbor-timing-results.json"),
    ("charged/results.json", "charged-workshop-results.json"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="parent of the d1, neighbor and charged outputs")
    directory = parser.parse_args().directory
    failed = False
    for relative, published in SUMMARIES:
        try:
            observed = (directory / relative).read_bytes()
            expected = (EXAMPLES / published).read_bytes()
        except OSError as error:
            print(f"UNREADABLE {relative} ({error})")
            failed = True
            continue
        if observed == expected:
            print(f"MATCH {relative}")
        else:
            print(f"DIFFER {relative} (reference: examples/{published})")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
