import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_dist/src"))
sys.path.insert(0, str(ROOT / "examples/agent_profile_v1"))
import research_adapter as adapter
from commonwealth.assembly_v1.importer import verify
from commonwealth.assembly_v1.rules_v02 import Assembly


@unittest.skipUnless(importlib.util.find_spec("cryptography"), "optional Assembly verifier unavailable")
class ResearchRoleTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / "examples/assembly_v1"
        self.record = json.loads((root/"research_record.json").read_text())
        pin = json.loads((root/"research_checkpoint.json").read_text())
        self.review = verify(self.record, pin)
        self.draft = json.loads((root/"research_draft.json").read_text())
        self.packet = adapter.research_brief(self.review, "J1", "research-agent", self.draft)

    def test_awarded_researcher_only_and_exact_draft(self):
        with self.assertRaises(ValueError):
            adapter.research_brief(self.review, "J1", "C1", self.draft)
        with self.assertRaises(ValueError):
            adapter.research_brief(self.review, "J1", "research-agent", {**self.draft, "fiscal": "changed"})
        other = adapter.research_brief(self.review, "J1", "cost-agent", self.draft)
        self.assertEqual(other["choices"], ["decline"])
        for choice in ("vote", "offer", "execute"):
            with self.assertRaises(ValueError):
                adapter.action(self.packet, dict(profile=adapter.PROFILE, brief_id=self.packet["brief_id"], choice=choice))

    def test_open_offer_completed_and_expired_award(self):
        review = copy.deepcopy(self.review)
        job = review["research_jobs"]["J1"]
        job.update(selected=None, selected_terms=None, offered_by=[])
        packet = adapter.research_brief(review, "J1", "cost-agent", self.draft)
        reply = dict(profile=adapter.PROFILE, brief_id=packet["brief_id"], choice="offer", terms="Inspect the draft.")
        self.assertEqual(adapter.action(packet, reply), {"type":"offer","args":{"job":"J1","terms":"Inspect the draft."}})
        review["exercise_day"] = job["due"]
        self.assertEqual(adapter.research_brief(review, "J1", "cost-agent", self.draft)["choices"], ["decline"])
        review["exercise_day"] = 0
        job.update(selected="research-agent", delivered=True)
        self.assertEqual(adapter.research_brief(review, "J1", "research-agent", self.draft)["choices"], ["decline"])

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_independent_agent_report_consumed_once_by_assembly_rules(self):
        raw = subprocess.check_output(["node", str(ROOT/"examples/agent_profile_v1/javascript_agent.mjs")],
                                      input=json.dumps(self.packet), text=True)
        cmd = adapter.action(self.packet, json.loads(raw))
        state = Assembly(self.record["registry"])
        for env in self.record["entries"]:
            b = env["body"]
            state.apply(b["actor"], b["command"])
        state.apply("research-agent", cmd)
        self.assertEqual(state.jobs["J1"]["result"]["draft"], self.packet["draft_digest"])
        self.assertIsNone(state.bill)
        with self.assertRaises(ValueError):
            state.apply("research-agent", cmd)
