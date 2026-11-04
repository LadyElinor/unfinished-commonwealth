import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from commonwealth.experiment import scripted_run
from commonwealth.measurement_v1 import participant, workshop
from commonwealth.study_v1.engine import Episode
from commonwealth.study_v1.experiment import run as reference_run
from commonwealth.study_v1.fixtures import case
from commonwealth.study_v1.policies import arms

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "examples/agent_profile_v1/python_agent.py"


class ChargedMeasurement(unittest.TestCase):
    def test_costed_deliberation_keeps_fifo_misses_and_original_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = scripted_run(Path(tmp) / "shared.db", "missing", "coached+casebook")
            before = w.verify()
            shared, independent = (workshop.charge(w.events(), name) for name in workshop.SCHEDULES)
            self.assertEqual(w.verify(), before)
            self.assertEqual([o["slot"] for o in shared["primary_observations"]], [1,5,13,14])
            self.assertEqual(shared["repair_latency"][0]["slots_until_correct"], 4)
            self.assertEqual(shared["peer_historical_misses"], 2)
            self.assertEqual(independent["peer_historical_misses"], 0)
            self.assertEqual(shared["outstanding_peer_inspections"], 0)
            self.assertEqual(shared["peer_inspections"], independent["peer_inspections"])
            self.assertEqual(sum(shared["action_counts"].values()), 14)
            self.assertLessEqual(shared["primary_inspections"]+shared["peer_inspections"], 20*20)

    def test_decline_wait_and_evidence_act_on_real_d1_clock(self):
        sim = Episode(case(declared=False))
        for choice, command in (("wait","wait"), ("request-evidence","request-evidence"), ("decline","halt")):
            packet = participant.brief(sim.view())
            reply = dict(profile=participant.PROFILE, brief_id=packet["brief_id"], choice=choice, reason="Test.")
            action = participant.interpret(packet, reply)
            self.assertEqual(action["action"], command)
            sim.step(action)
        self.assertEqual(sim.tick, 3)
        self.assertTrue(sim.closed)
        self.assertEqual(sim.grants, 1)
        self.assertTrue(sim.summary()["outstanding"])

    def test_hidden_twins_and_nested_private_fields(self):
        from commonwealth.study_v1.contracts import SLOT_YIELD
        first = Episode(case(declared=False)).view()
        second = Episode(case(contract=SLOT_YIELD, declared=False)).view()
        self.assertEqual(participant.brief(first), participant.brief(second))
        contaminated = copy.deepcopy(first)
        contaminated["expected"] = "DO_NOT_SHOW"
        contaminated["schedule"]["peers"][0]["private_context"] = "DO_NOT_SHOW"
        contaminated["budget"]["private_account"] = "DO_NOT_SHOW"
        self.assertEqual(participant.brief(contaminated), participant.brief(first))
        packet = participant.brief(first)
        with self.assertRaises(ValueError):
            participant.interpret(packet, dict(profile=participant.PROFILE, brief_id=packet["brief_id"],
                                               choice="approve", method="quality-stream"))

    def test_unregistered_fixture_is_refused_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "agent.py"
            marker = Path(temp) / "executed"
            path.write_text(f"open({str(marker)!r}, 'w').close()")
            with self.assertRaisesRegex(ValueError, "recorded fixture"):
                participant.ask(path, participant.brief(Episode(case()).view()))
            self.assertFalse(marker.exists())

    def test_external_policy_reproduces_selector_on_ambiguous_case(self):
        c = case(declared=False)
        external, decisions = participant.episode(c, AGENT)
        selector = next(a for a in arms() if a["name"]=="evidence-selector")
        self.assertEqual(external.journal(), reference_run(c, selector).journal())
        self.assertEqual([d["reply"]["choice"] for d in decisions], ["request-evidence","propose"])

    @unittest.skipUnless(shutil.which("node"), "requires Node for independent check")
    def test_reference_audit_rejects_false_expected_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = case()
            selector = next(a for a in arms() if a["name"]=="evidence-selector")
            journal = reference_run(c, selector).journal()
            path = Path(tmp)/"journal.json"
            path.write_text(json.dumps(journal))
            cmd = ["node", str(ROOT/"scripts/audit_measurement.mjs"), "study", tmp]
            self.assertEqual(json.loads(subprocess.check_output(cmd))["journals"], 1)
            journal["terminal"]["measures"]["reference"]["value"]["numerator"] += 1
            path.write_text(json.dumps(journal))
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    @unittest.skipUnless(shutil.which("node"), "requires Node for independent check")
    def test_recount_of_public_sample_and_duplicate_ballot(self):
        src = ROOT/"examples/assembly_v1/public_record.json"
        cmd = ["node", str(ROOT/"scripts/audit_measurement.mjs"), "assembly"]
        output = json.loads(subprocess.check_output([*cmd, str(src)]))["closed_rounds"]
        self.assertEqual([r["chambers"]["duration"]["abstain"] for r in output], [1, 0])
        self.assertEqual([r["chambers"]["commons"]["yes"] for r in output], [2, 2])
        record = json.loads(src.read_text())
        i = next(i for i,e in enumerate(record["entries"]) if e["body"]["command"]["type"] == "vote")
        record["entries"].insert(i, record["entries"][i])
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp)/"votes.json"
            bad.write_text(json.dumps(record))
            self.assertNotEqual(subprocess.run([*cmd, str(bad)], capture_output=True).returncode, 0)
