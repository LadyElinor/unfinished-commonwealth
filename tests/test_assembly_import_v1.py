import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.assembly_v1.importer import read_json, verify

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/assembly_v1"


class InputTests(unittest.TestCase):
    def test_duplicate_oversized_and_excessively_nested_inputs(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"record"
            for content, limit in ((b'{"n":1,"n":2}', 100), (b"12345", 4),
                                   (b"["*100+b"]"*100, 1000)):
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    read_json(path, limit)


@unittest.skipUnless(importlib.util.find_spec("cryptography"), "optional signature verifier unavailable")
class ImportTests(unittest.TestCase):
    def setUp(self):
        self.pin = json.loads((EXAMPLES/"checkpoint.json").read_text(encoding="utf-8"))
        self.record = json.loads((EXAMPLES/"public_record.json").read_text(encoding="utf-8"))

    def test_replay_and_recount_have_no_authority(self):
        result = verify(self.record, self.pin)
        self.assertIs(result["permits_execution"], False)
        self.assertIs(result["authority_granted"], False)
        self.assertEqual(result["bill"]["phase"], "PUBLISHED_IN_SIMULATION")
        self.assertEqual([r["chambers"]["commons"]["yes"] for r in result["public_recount"]], [2,2])
        self.assertEqual([r["chambers"]["duration"]["abstain"] for r in result["public_recount"]], [1,0])
        self.assertEqual({p["count_status"] for p in result["polities"]}, {"COUNT_CONFIRMED_YES","COUNT_CONFIRMED_NO"})
        self.assertEqual(result["truth_of_returns"], "NOT_ESTABLISHED")

    def test_pin_truncation_signed_vote_and_registry_tampering(self):
        with self.assertRaises(ValueError):
            verify(self.record, {**self.pin, "events": 37})
        for attack in ("truncated","vote","registry","boolean_count","nonce"):
            record = copy.deepcopy(self.record)
            if attack == "truncated":
                record["entries"].pop()
            elif attack == "vote":
                vote = next(e for e in record["entries"] if e["body"]["command"]["type"]=="vote")
                vote["body"]["command"]["args"]["choice"] = "abstain"
            elif attack == "registry":
                record["registry"]["instance"] += "x"
            elif attack == "boolean_count":
                record["checkpoint"]["events"] = True
            else:
                record["entries"][1] = record["entries"][0]
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                verify(record, self.pin)
