from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from commonwealth.change_review_v1.__main__ import main


@unittest.skipUnless(sys.platform == "linux", "Linux recording-service profile")
class OperatorCheckTests(unittest.TestCase):
    def invoke(self, *arguments):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(map(str, arguments)))
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_retained_backup_is_bound_to_live_register_and_operator_thresholds(self):
        with TemporaryDirectory() as temp:
            d = Path(temp)
            db, other, snap, receipt = (d / name for name in ("db", "other", "snap", "receipt"))
            self.assertEqual(self.invoke("init", db)[0], 0)
            self.assertEqual(self.invoke("init", other)[0], 0)
            status, record = self.invoke("backup", db, snap)
            self.assertEqual(status, 0)
            receipt.write_text(json.dumps(record))
            limits = ("--max-backup-age-seconds", "3600", "--min-free-bytes", "1")
            for file, expected in ((db, 0), (other, 2)):
                status, result = self.invoke("check", file, snap, receipt, *limits)
                self.assertEqual(status, expected)
                self.assertEqual(result["checks"]["same_register"], file == db)
            record["completed_at"] -= 7200
            record["sha256"] = "a" * 64
            receipt.write_text(json.dumps(record))
            status, result = self.invoke("check", db, snap, receipt, *limits)
            self.assertEqual(status, 2)
            self.assertFalse(result["checks"]["snapshot_within_age"])
            self.assertFalse(result["checks"]["snapshot_digest"])
