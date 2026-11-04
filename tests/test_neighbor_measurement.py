import hashlib
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.measurement_v1 import neighbor

ROOT = Path(__file__).resolve().parents[1]


class NeighborStudy(unittest.TestCase):
    def test_complete_matrix_and_rows_digest_reproduce(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "n1"
            result = neighbor.run(out)
            self.assertEqual(result, json.loads((ROOT/"examples/neighbor-timing-results.json").read_text()))
            raw = (out/"episodes.jsonl").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), result["episodes_sha256"])
            rows = [json.loads(line) for line in raw.splitlines()]
            cells = {(r["policy"], r["primary_due"], r["reliable_variants"], r["urgent"], r["variant"], r["coin"])
                     for r in rows}
            self.assertEqual(len(rows), result["episode_count"])
            self.assertEqual(len(cells), 1008)
            with self.assertRaises(FileExistsError):
                neighbor.run(out)

    def test_jobs_fit_and_misses_survive_completion(self):
        for policy, due, truth in product(neighbor.POLICIES, (2, 3, 4), (False, True)):
            row = neighbor.episode(policy, due, 3, truth, 3, True)
            end = row["primary_completed"]
            peer_slot = row["peer_completed"]
            self.assertNotIn(peer_slot, (end-1, end))
            self.assertIn(peer_slot, (2, 3, 4))
            self.assertEqual(row["peer_misses"], int(truth and peer_slot > 2))
            self.assertEqual(row["primary_misses"], int(end > due))
            if row["consultation_slots"] or row["wait_slots"]:
                self.assertGreater(end-1, 1)
            if row["reservations"]:
                self.assertEqual(peer_slot, 2)
        # A false negative defers primary to slots 2 and 3; the late peer completes at 4.
        failure = neighbor.episode("ask-peer", 3, 3, True, 3, False)
        self.assertEqual((failure["warning"], failure["primary_completed"], failure["peer_late_slots"]),
                         (False, 3, 2))

    def test_fixed_reservations_and_information_control(self):
        for reliability, expected_peer_misses in [(2,4), (3,2), (4,0)]:
            sums = {}
            for policy in ("coin", "ask-peer"):
                rows = [neighbor.episode(policy, 3, reliability, truth, variant, coin)
                        for truth, variant, coin in product((False,True), range(4), (False,True))]
                sums[policy] = tuple(sum(r[k] for r in rows) for k in ("reservations","primary_misses","peer_misses"))
            self.assertEqual(sums["coin"], (8,8,4))
            self.assertEqual(sums["ask-peer"], (8,8,expected_peer_misses))

    def test_matched_signal_sources_and_no_free_look(self):
        for args in product((2,3,4), (2,3,4), (False,True), range(4), (False,True)):
            peer = neighbor.episode("select-peer", *args)
            instrument = neighbor.episode("select-instrument", *args)
            self.assertEqual({k:peer[k] for k in neighbor.COUNTERS}, {k:instrument[k] for k in neighbor.COUNTERS})
            self.assertEqual(peer["warning"], instrument["warning"])
            if peer["consultation_slots"] == 0:
                self.assertIsNone(peer["warning"])
