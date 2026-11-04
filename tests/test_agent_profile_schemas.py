"""Validate the language-neutral interchange against Draft 2020-12 when installed."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AP = ROOT/"examples/agent_profile_v1"
ASSEMBLY = ROOT/"examples/assembly_v1"
sys.path.insert(0, str(ROOT/"client_dist/src"))
sys.path.insert(0, str(AP))
import adapter
import research_adapter
from commonwealth.assembly_v1.importer import verify


@unittest.skipUnless(importlib.util.find_spec("jsonschema") and importlib.util.find_spec("cryptography")
                     and shutil.which("node"), "schema conformance tools unavailable")
class SchemaTests(unittest.TestCase):
    def test_measurement_profiles_match_schema(self):
        from jsonschema import Draft202012Validator
        from commonwealth.measurement_v1.participant import brief as study_brief
        from commonwealth.study_v1.fixtures import case
        from commonwealth.study_v1.engine import Episode
        load = lambda name: json.loads((AP/name).read_text())
        work = adapter.brief(load("example_task.json"), profile=adapter.PROFILE_1_1)
        Draft202012Validator(load("brief-v1_1.schema.json")).validate(work)
        cases = [(work, "decision-v1_1.schema.json"),
                 (study_brief(Episode(case(declared=False)).view()), "study-decision.schema.json")]
        for packet, schema in cases:
            response = subprocess.check_output([sys.executable, "-I", str(AP/"python_agent.py")],
                                               input=json.dumps(packet), text=True)
            validator = Draft202012Validator(load(schema))
            validator.validate(json.loads(response))
            for choice in ("wait", "request-evidence", "decline"):
                validator.validate({"profile":packet["profile"], "brief_id":packet["brief_id"],
                                    "choice":choice, "reason":"Evidence outstanding."})

    def test_javascript_roundtrip_under_published_schemas(self):
        from jsonschema import Draft202012Validator
        def load(path):
            return json.loads(path.read_text(encoding="utf-8"))
        review = verify(load(ASSEMBLY/"research_record.json"), load(ASSEMBLY/"research_checkpoint.json"))
        packets = [
            (adapter.brief(load(AP/"example_task.json"), review), "decision.schema.json"),
            (research_adapter.research_brief(review, "J1", "research-agent", load(ASSEMBLY/"research_draft.json")),
             "research-decision.schema.json"),
        ]
        for packet, schema_file in packets:
            with self.subTest(role=packet["role"]):
                brief_schema = load(AP/"brief.schema.json")
                Draft202012Validator.check_schema(brief_schema)
                Draft202012Validator(brief_schema).validate(packet)
                raw = subprocess.check_output(["node", str(AP/"javascript_agent.mjs")],
                                              input=json.dumps(packet), text=True)
                reply = json.loads(raw)
                schema = load(AP/schema_file)
                Draft202012Validator.check_schema(schema)
                validator = Draft202012Validator(schema)
                validator.validate(reply)
                self.assertFalse(validator.is_valid({**reply, "actor": "keeper"}))
                self.assertFalse(validator.is_valid({**reply, "choice": "vote"}))
