"""Child process for verification: unittest results, not parsed console claims."""

from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import unittest


class CoverageResult(unittest.TextTestResult):
    """Class/module/subtest skips are not whole started test-case skips."""
    skipped_started = 0
    active_test = None

    def startTest(self, test):
        self.active_test = test
        super().startTest(test)

    def stopTest(self, test):
        self.active_test = None
        super().stopTest(test)

    def addSkip(self, test, reason):
        if test is self.active_test:
            self.skipped_started += 1
        super().addSkip(test, reason)


def main():
    root = Path(sys.argv[1]).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    # Test prints remain visible without corrupting the result channel.
    with redirect_stdout(sys.stderr):
        suite = unittest.defaultTestLoader.discover(str(root / "tests"))
        result = unittest.TextTestRunner(verbosity=2, resultclass=CoverageResult).run(suite)
    print(json.dumps({
        "tests_run": result.testsRun,
        "tests_not_skipped": result.testsRun - result.skipped_started,
        "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "expected_failures": [test.id() for test, _ in result.expectedFailures],
        "unexpected_successes": [test.id() for test in result.unexpectedSuccesses],
        "successful": result.wasSuccessful(),
    }, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
