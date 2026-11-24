import copy
from pathlib import Path
import tempfile
import unittest

from commonwealth.measurement_v1 import handoff
from commonwealth.store import Workshop


class SuccessorHandoffTests(unittest.TestCase):
    def test_invalid_receiver_packet_rejected_before_writing(self):
        packet = handoff.development_cases()
        duplicate = {"cases": [packet["cases"][0]] * 2}
        congested = copy.deepcopy(packet)
        congested["cases"][0]["fixture"]["peer_values"] = list(range(12))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trial"
            for invalid in (duplicate, congested):
                with self.assertRaises(ValueError):
                    handoff.run(output, invalid)
                self.assertFalse(output.exists())

    def test_guard_and_scoring_treat_an_accidental_numeric_tie_separately(self):
        # Invalid positive rows can make both selected means exactly three.
        data = handoff.fixture([0, 6, 1, 2], [True, True, False, False], 12, [1])
        public = {"data": data, "fresh": {"peer_inspections": 1}}
        advice = {"method": "positive-only", "transfer_check": handoff.GUARD}
        self.assertEqual(handoff.choose(public, advice), ("quality-stream", ["same-selected-rows"]))
        self.assertFalse(any(handoff.warranted(data).values()))

    def test_siblings_share_checkpoint_and_replay_their_own_grant(self):
        packet = {"cases": [handoff.development_cases()["cases"][-1]]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "results"
            case, = handoff.run(root, packet)["cases"]
            directory = root / "cases" / ("case-" + case["id"])
            checkpoint = Workshop(directory / "fresh.sqlite")
            prefix = checkpoint.events()
            self.assertEqual(checkpoint.verify()["head"], case["fresh_head"])
            self.assertTrue(case["open_objections_before"])
            public = case["common_public_input"]
            self.assertNotIn("reference", public["data"])
            self.assertNotIn("scenario", public)
            for arm, row in case["arms"].items():
                journal = Workshop(directory / f"{arm}.sqlite")
                events = journal.events()
                self.assertEqual(events[:len(prefix)], prefix)
                self.assertEqual([e["command"]["action"] for e in events[len(prefix):]],
                                 ["propose", "approve", "execute", "observe", "observe", "observe"])
                self.assertEqual(row["journal"], journal.verify())
                self.assertEqual(row["fresh_observation_used"], public["fresh"]["id"])
                self.assertEqual(row["surviving_unaddressed_objections"], case["open_objections_before"])
                self.assertEqual(row["approved_by"], "keeper")
                self.assertEqual(row["consequences"]["inspection_allowance"], 24)
            baseline, current, revised = (case["arms"][arm] for arm in handoff.ARMS)
            self.assertIsNone(baseline["offered_advice"])
            extension = dict(revised["offered_advice"])
            self.assertEqual(extension.pop("transfer_check"), handoff.GUARD)
            self.assertEqual(extension, current["offered_advice"])
            missed = current["consequences"]
            self.assertEqual((missed["peer_deadline_misses"], missed["peer_completed"], missed["peer_pending"]),
                             (3, 0, 3))
            self.assertEqual((missed["peer_late_ticks_completed"], missed["peer_late_ticks_pending_to_horizon"]),
                             (0, 3))
            self.assertEqual(revised["consequences"], baseline["consequences"])
            with self.assertRaises(FileExistsError):
                handoff.run(root, packet)
