import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from commonwealth.experiment import change_method, demo, dispatch
from commonwealth.oversight_v1 import trace
from commonwealth.store import CorruptJournal, Workshop


class OversightTraceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "workshop.sqlite"

    def test_actual_demo_and_as_of_preserve_account_timing(self):
        workshop = demo(self.path)
        before = workshop.verify()
        early = trace(workshop, 6)
        self.assertEqual(early["accounts"][0]["acknowledgments"], [])
        packet = trace(workshop)
        self.assertEqual(workshop.verify(), before)
        self.assertEqual(before["head"], packet["prefix_head"])
        first, second, third = packet["episodes"]
        self.assertEqual([first[k]["seq"] for k in ("proposal", "approval", "execution", "observation")],
                         [2, 3, 4, 5])
        self.assertFalse(first["observation"]["peer_on_time"])
        self.assertTrue(second["observation"]["peer_on_time"])
        self.assertNotEqual(second["generation"], third["generation"])
        self.assertEqual([a["actor"] for a in packet["accounts"][0]["acknowledgments"]],
                         ["worker-1", "worker-2"])
        self.assertNotIn("Your new output", json.dumps(packet))

    def test_two_executions_before_observation_do_not_share_outcome(self):
        w = Workshop.create(self.path)
        change_method(w, "positive-only", "first")
        change_method(w, "positive-only", "second")
        dispatch(w, "observe")
        a, b = trace(w)["episodes"]
        self.assertIsNone(a["observation"])
        self.assertEqual(b["observation"]["tick"], 1)
        self.assertIsNone(trace(w, 1)["episodes"][0]["approval"])
        self.assertIsNone(trace(w, 2)["episodes"][0]["execution"])

    def test_genesis_bad_cutoff_and_corrupt_source(self):
        w = Workshop.create(self.path)
        self.assertEqual(trace(w, 0)["episodes"], [])
        for seq in (True, -1, 1):
            with self.assertRaises(ValueError):
                trace(w, seq)
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE events SET hash='bad'")
        with self.assertRaises(CorruptJournal):
            trace(w)
