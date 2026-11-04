"""Presentation layer for the installed CLI; retain the frozen original module for historical replay."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys

from .. import cli
from ..study_v1.experiment import write_json
from . import OPERATOR_LIMIT


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("evaluate", "readiness", "report"):
        return cli.main(argv)
    parsed = cli.parser().parse_args(argv)  # Preserve help and usage output before capturing a report.
    capture = StringIO()
    with redirect_stdout(capture):
        status = cli.main(argv)
    original = capture.getvalue()
    if not original:
        return status
    if argv[0] == "report":
        print(original.rstrip() + "\n\n" + OPERATOR_LIMIT)
    else:
        result = json.loads(original)
        result["operator_limit"] = OPERATOR_LIMIT
        if argv[0] == "evaluate":
            directory = Path(parsed.directory)
            write_json(directory / "results.json", result)
        cli.emit(result)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
