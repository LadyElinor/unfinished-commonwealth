"""Adversarial input and strict JSON replay regressions."""

from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.cli import main, read_command
from commonwealth.engine import Rejected, canonical, digest, parse_json
from commonwealth.pipeline import scenarios
from commonwealth.store import CorruptJournal, Workshop


class IntegrityRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "workshop.sqlite"
        self.workshop = Workshop.create(self.database)

    def assert_cli_refused_unchanged(self, source, error):
        before = self.workshop.verify()
        command = self.root / "command.json"
        command.write_text(source, encoding="utf-8")
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["propose", str(self.database), str(command)])
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        refusal = json.loads(errors.getvalue())
        self.assertEqual(refusal["status"], "REFUSED")
        self.assertIn(error, refusal["error"])
        self.assertEqual(before, self.workshop.verify())

    def test_oversized_integer_probabilities_are_cli_refusals(self):
        for value in (10 ** 400, -(10 ** 400)):
            with self.subTest(value=str(value)[:12]):
                command = {"action": "propose", "actor": "worker-1",
                           "method": "quality-stream", "purpose": "Invalid forecast.",
                           "prediction": {"primary_correct": value, "peer_on_time": 1}}
                self.assert_cli_refused_unchanged(json.dumps(command), "finite probabilities")

    def test_nonfinite_numeric_forms_are_refused_by_parser(self):
        for number in ("NaN", "Infinity", "-Infinity", "1e9999", "-1e9999"):
            with self.subTest(number=number):
                self.assert_cli_refused_unchanged('{"number":' + number + '}', "nonfinite JSON")

    def test_deep_json_is_a_cli_refusal_not_a_recursion_crash(self):
        for levels in (65, 20000):
            with self.subTest(levels=levels):
                self.assert_cli_refused_unchanged("[" * levels + "0" + "]" * levels,
                                                  "JSON nesting exceeds 64 levels")

    def test_json_depth_boundary_and_nested_duplicate_fields(self):
        value = parse_json("[" * 64 + "0" + "]" * 64)
        for _ in range(64):
            value = value[0]
        self.assertEqual(value, 0)
        command = self.root / "duplicate.json"
        command.write_text('{"prediction":{"peer_on_time":0,"peer_on_time":1}}')
        with self.assertRaisesRegex(Rejected, "duplicate JSON field: peer_on_time"):
            read_command(command)

    def test_command_size_limit_counts_actual_bytes(self):
        command = self.root / "sized.json"
        for source in ("{}" + " " * 65534,
                       '{"text":"' + "é" * 32762 + '"} '):
            with self.subTest(multibyte="é" in source):
                self.assertEqual(len(source.encode("utf-8")), 65536)
                command.write_bytes(source.encode("utf-8"))
                self.assertEqual(read_command(command), json.loads(source))
                command.write_bytes((source + " ").encode("utf-8"))
                with self.assertRaisesRegex(Rejected, "command file exceeds 64 KiB"):
                    read_command(command)

    def test_command_read_is_bounded_even_without_file_size_metadata(self):
        class TrackingReader(io.BytesIO):
            def __init__(self):
                super().__init__(b"{}" + b" " * 100000)
                self.requested_sizes = []

            def read(self, size=-1):
                self.requested_sizes.append(size)
                return super().read(size)

        handle = TrackingReader()
        with patch("commonwealth.cli.Path.open", return_value=handle):
            with self.assertRaisesRegex(Rejected, "command file exceeds 64 KiB"):
                read_command(self.root / "not-a-regular-file")
        self.assertEqual(handle.requested_sizes, [65537])
        self.assertTrue(handle.closed)

    def test_snapshot_numeric_type_drift_is_detected(self):
        original = self.workshop.state()
        for field, replacement in (("tick", False), ("generation", True),
                                   ("generation", 1.0), ("halted", 0)):
            with self.subTest(field=field, replacement=replacement):
                changed = dict(original, **{field: replacement})
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    connection.execute("UPDATE snapshot SET body=?", (canonical(changed),))
                with self.assertRaisesRegex(CorruptJournal, "snapshot disagrees with journal replay"):
                    self.workshop.verify()

    def test_result_numeric_type_drift_is_detected_after_rehash(self):
        self.workshop.dispatch({"action": "observe", "actor": "worker-1"})
        with closing(sqlite3.connect(self.database)) as connection, connection:
            raw = connection.execute("SELECT envelope FROM events WHERE seq=1").fetchone()[0]
        for field, replacement in (("primary_correct", 0), ("tick", True), ("tick", 1.0)):
            with self.subTest(field=field, replacement=replacement):
                envelope = json.loads(raw)
                envelope["result"]["observation"][field] = replacement
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    connection.execute("UPDATE events SET envelope=?, hash=? WHERE seq=1",
                                       (canonical(envelope), digest(envelope)))
                with self.assertRaisesRegex(CorruptJournal, "event does not replay to its claimed result"):
                    self.workshop.verify()

    def test_boolean_or_float_event_sequence_is_not_an_integer(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            raw = connection.execute("SELECT envelope FROM events WHERE seq=0").fetchone()[0]
        for value in (False, 0.0):
            with self.subTest(value=value):
                envelope = json.loads(raw)
                envelope["seq"] = value
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    connection.execute("UPDATE events SET envelope=?, hash=? WHERE seq=0",
                                       (canonical(envelope), digest(envelope)))
                with self.assertRaisesRegex(CorruptJournal, "broken event sequence"):
                    self.workshop.verify()

    def test_duplicate_journal_keys_are_not_normalized_away(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            raw = connection.execute("SELECT envelope FROM events WHERE seq=0").fetchone()[0]
            # The last value still matches the recorded hash; a permissive
            # decoder would silently discard the first, conflicting value.
            connection.execute("UPDATE events SET envelope=? WHERE seq=0", ('{"seq":false,' + raw[1:],))
        with self.assertRaisesRegex(CorruptJournal, "duplicate JSON field: seq"):
            self.workshop.verify()

    def test_duplicate_snapshot_keys_are_not_normalized_away(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            raw = connection.execute("SELECT body FROM snapshot").fetchone()[0]
            connection.execute("UPDATE snapshot SET body=?", ('{"tick":false,' + raw[1:],))
        with self.assertRaisesRegex(CorruptJournal, "duplicate JSON field: tick"):
            self.workshop.verify()

    def test_deep_journal_and_snapshot_report_corruption(self):
        deep = "[" * 20000 + "0" + "]" * 20000
        with closing(sqlite3.connect(self.database)) as connection, connection:
            raw = connection.execute("SELECT envelope FROM events WHERE seq=0").fetchone()[0]
            connection.execute("UPDATE events SET envelope=? WHERE seq=0", (deep,))
        with self.assertRaisesRegex(CorruptJournal, "JSON nesting exceeds 64 levels"):
            self.workshop.verify()
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE events SET envelope=? WHERE seq=0", (raw,))
            connection.execute("UPDATE snapshot SET body=?", (deep,))
        with self.assertRaisesRegex(CorruptJournal, "JSON nesting exceeds 64 levels"):
            self.workshop.verify()

    def test_fixture_description_is_bounded_text(self):
        before = self.workshop.verify()
        for description in ({"unexpected": "object"}, "", " " * 2, "x" * 4001):
            with self.subTest(description_type=type(description).__name__):
                fixture = scenarios()["signed"]
                fixture["description"] = description
                with self.assertRaisesRegex(Rejected, "description: a nonempty string"):
                    self.workshop.dispatch({"action": "handoff", "actor": "keeper",
                                            "scenario": "signed", "fixture": fixture,
                                            "note": "Malformed fixture."})
                self.assertEqual(before, self.workshop.verify())

    def test_valid_historical_demo_hash_is_unchanged(self):
        # Frozen data was exported by 0.1.1, not regenerated by today's demo.
        history = json.loads((Path(__file__).parent / "data/legacy-demo.json").read_text())
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM events")
            for envelope in history["events"]:
                connection.execute("INSERT INTO events VALUES (?, ?, ?)",
                                   (envelope["seq"], canonical(envelope), digest(envelope)))
            connection.execute("UPDATE snapshot SET body=?", (canonical(history["snapshot"]),))
        self.assertEqual(self.workshop.verify()["head"],
                         "8c462114644fb93db2347d25ded1d8be77829289e6be71394cbc9e411ebb09b8")
        self.assertEqual(self.workshop.state()["version"], "0.1.0")
        self.assertEqual(self.workshop.state()["schema"], 1)


if __name__ == "__main__":
    unittest.main()
