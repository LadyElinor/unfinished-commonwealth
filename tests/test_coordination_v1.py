"""Hand-calculated G1 schedules, trust boundaries and full-record reproduction."""

from copy import deepcopy
from fractions import Fraction
from hashlib import sha1, sha256
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.coordination_v1 import experiment as g1
from commonwealth.coordination_v1.__main__ import load_record
from commonwealth.study_v1.contracts import VALID_MEAN, SLOT_YIELD
from commonwealth.study_v1.engine import Episode

ROOT = Path(__file__).resolve().parents[1]


def cell(**changes):
    return {"contract": VALID_MEAN, "coordinator": "quality-stream", "worker": "quality-stream",
            "report": "quality-stream", "deadline": 4, "peer_work": 2} | changes


class CoordinationCore(unittest.TestCase):
    def test_independent_arithmetic_and_four_slot_execution(self):
        row = g1.episode(cell(), "central-direct")
        summary = row["journal"]["terminal"]["measures"]
        first = summary["outputs"][0]
        # Hand definitions, no candidate or D1 reference call.
        mean, yield_ = Fraction(10 + 20, 2), Fraction(10 + 20, 3)
        self.assertNotEqual(mean, yield_)
        self.assertEqual(first["answer"]["value"], {"numerator": mean.numerator, "denominator": mean.denominator})
        self.assertEqual(first["completed"], 4)
        self.assertEqual(summary["peers"][0]["completed"], 5)
        self.assertEqual(row["measures"]["peer_late_slots"], 1)
        self.assertEqual(row["measures"]["peer_historical_misses"], 1)
        self.assertTrue(row["measures"]["primary_on_time"])

    def test_false_warning_cost_is_retained(self):
        case = cell(report="zero-fill")
        direct = g1.episode(case, "central-direct")
        filtered = g1.episode(case, "central-filtered")
        self.assertTrue(direct["measures"]["first_correct"])
        self.assertEqual(direct["measures"]["first_completed"], 5)
        self.assertFalse(direct["measures"]["primary_on_time"])
        self.assertEqual(direct["measures"]["observation_requests"], 2)
        self.assertEqual(direct["measures"]["peer_on_time"], 1)
        self.assertEqual(filtered["measures"]["first_completed"], 4)
        self.assertTrue(filtered["measures"]["primary_on_time"])
        self.assertEqual(filtered["routing"]["original"]["method"], "zero-fill")
        self.assertEqual(filtered["routing"]["disposition"], "not-delivered")

    def test_true_warning_suppression_and_four_slot_repair_latency(self):
        case = cell(contract=SLOT_YIELD, report="zero-fill")
        direct = g1.episode(case, "central-direct")
        filtered = g1.episode(case, "central-filtered")
        self.assertTrue(direct["measures"]["first_correct"])
        self.assertFalse(filtered["measures"]["first_correct"])
        self.assertTrue(filtered["measures"]["primary_correct"])
        self.assertEqual(filtered["intent"], "not-established")
        terminal = filtered["journal"]["terminal"]["measures"]
        self.assertEqual([o["answer"]["value"]["numerator"] for o in terminal["outputs"]], [15, 10])
        self.assertEqual([o["completed"] for o in terminal["outputs"]], [4, 8])
        self.assertEqual(terminal["repair_latency"], [{"failed_at": 4, "repaired_at": 8, "latency": 4}])
        self.assertEqual(terminal["primary_historical_misses"], 1)
        self.assertEqual(terminal["peer_historical_misses"], 1)
        self.assertIsNone(filtered["journal"]["genesis"]["lesson"])
        self.assertIsNone(filtered["routing"]["receipt_slot"])
        self.assertFalse(terminal["outstanding"])

    def test_delegation_does_not_assume_worker_superiority(self):
        # The same public recommendations are available to both arrangements.
        for contract in (VALID_MEAN, SLOT_YIELD):
            case = cell(contract=contract, worker="zero-fill")
            central = g1.episode(case, "central-direct")
            delegated = g1.episode(case, "delegated-direct")
            self.assertEqual(central["routing"]["original"], delegated["routing"]["original"])
            self.assertFalse(central["routing"]["precheck"])
            self.assertTrue(delegated["routing"]["precheck"])
            self.assertEqual(central["measures"]["first_correct"], contract == VALID_MEAN)
            self.assertTrue(delegated["measures"]["first_correct"])

    def test_identity_and_dissent_labels_cannot_change_choices_or_costs(self):
        for arm in g1.ARMS:
            rows = [g1.episode(cell(contract=SLOT_YIELD, report="zero-fill"), arm, label)
                    for label in ("agreeable-participant", "dissenting-participant")]
            self.assertEqual(rows[0]["measures"], rows[1]["measures"])
            self.assertEqual([e["command"] for e in rows[0]["journal"]["events"]],
                             [e["command"] for e in rows[1]["journal"]["events"]])
            for row in rows:
                self.assertFalse(row["authority_granted"])
                self.assertFalse(row["production_ready"])
                self.assertEqual(row["external_actions"], 0)
                self.assertTrue(g1.replay(row)["verified"])

    def test_all_arms_have_same_evidence_cost_and_keeper_boundary(self):
        for arm in g1.ARMS:
            row = g1.episode(cell(), arm)
            genesis = row["journal"]["genesis"]
            self.assertEqual(genesis["budget"], g1.BUDGET)
            self.assertFalse(genesis["case"]["declared"])
            sim = Episode(**{k: genesis[k] for k in ("case", "clock", "budget", "lesson", "coaching")})
            self.assertIsNone(sim.view()["contract"])
            sim.step({"action": "propose", "actor": "worker", "method": "quality-stream"})
            refused = sim.step({"action": "execute", "actor": "worker", "proposal": 1})
            self.assertFalse(refused["response"]["accepted"])
            wrong_role = sim.step({"action": "request-review", "actor": "coordinator", "proposal": 1})
            self.assertFalse(wrong_role["response"]["accepted"])
            sim.step({"action": "wait", "actor": "worker"})
            self.assertEqual(sim.proposals[0]["status"], "pending")
            self.assertEqual(sim.summary()["refusals"], 2)
            self.assertEqual(sim.tick, 4)

    def test_zero_work_and_overload_continue_during_deliberation(self):
        for precheck, work in product((False, True), (0, 2, 8)):
            row = g1.episode(cell(peer_work=work, report="zero-fill" if precheck else "quality-stream"),
                             "central-direct")
            peer = row["journal"]["terminal"]["measures"]["peers"][0]
            expected = 4 if work == 0 or work == 2 and precheck else 5 if work == 2 else 6
            self.assertEqual(peer["completed"], expected)
            self.assertEqual(peer["missed"], expected > 4)
            self.assertEqual(row["measures"]["peer_inspections"], work)
            self.assertEqual(row["measures"]["decision_slots"], 12)
            self.assertEqual(row["measures"]["active_decisions"] + row["measures"]["waits"], 12)

    def test_policies_cannot_receive_hidden_reference_or_case_identifier(self):
        # Pure selection API has no evaluator input. Unsolicited truth is refused.
        with self.assertRaises(TypeError):
            g1.initial_choice("central-direct", "quality-stream", "zero-fill", None, contract=VALID_MEAN)
        self.assertEqual(g1.initial_choice("central-direct", "quality-stream", "zero-fill", None), "quality-stream")
        self.assertIsNone(g1.initial_choice("central-direct", "quality-stream", "zero-fill", "zero-fill"))
        self.assertEqual(g1.initial_choice("delegated-direct", "quality-stream", "zero-fill", "zero-fill"), "zero-fill")

    def test_replay_detects_routing_and_policy_edits(self):
        row = g1.episode(cell(), "central-filtered")
        self.assertTrue(g1.replay(row)["verified"])
        mutations = [lambda r: r["routing"].update(delivered=False),
                     lambda r: r["routing"].update(disposition="verified"),
                     lambda r: r["routing"]["original"].update(method="zero-fill"),
                     lambda r: r.update(arm="evidence-selector-first"),
                     lambda r: r["journal"]["events"][1]["command"].update(method="zero-fill"),
                     lambda r: r["measures"].update(first_correct=False),
                     lambda r: r.update(authority_granted=True),
                     lambda r: r.update(version="coordination-unknown")]
        for mutation in mutations:
            altered = deepcopy(row)
            mutation(altered)
            with self.assertRaises(ValueError):
                g1.replay(altered)

    def test_invalid_cells_arms_and_types_are_rejected(self):
        for bad in (cell(peer_work=True), cell(deadline=True), cell(deadline=6), cell(report="invented"),
                    cell(contract="other"), cell(extra="authority")):
            with self.assertRaises(ValueError):
                g1.episode(bad, "central-direct")
        with self.assertRaises(ValueError):
            g1.episode(cell(), "unregistered-arm")
        with self.assertRaises(ValueError):
            g1.episode(cell(), "central-direct", "")

    def test_jsonl_input_rejects_ambiguity_truncation_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "record.jsonl"
            path.write_text('{"a": 1, "a": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_record(path, 1)
            for number in (0, True, 673, 2):
                with self.assertRaises(ValueError):
                    load_record(path, number)
            path.write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "oversized"):
                load_record(path, 1)


class CoordinationReproduction(unittest.TestCase):
    def test_local_design_freeze_record_identifies_original_git_commit(self):
        record = json.loads((ROOT / "examples/coordination-v1-design-freeze.json").read_text())
        raw = record["raw_commit"].encode()
        self.assertEqual(sha1(b"commit " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), g1.DESIGN_COMMIT)
        self.assertEqual(record["commit_sha"], g1.DESIGN_COMMIT)
        self.assertTrue(record["raw_commit"].startswith("tree " + record["tree_sha"] + "\n"))

    def test_full_matrix_complete_replayed_and_matches_published_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "g1"
            result = g1.run(out)
            expected = json.loads((ROOT / "examples/coordination-v1-results.json").read_text())
            self.assertEqual(result, expected)
            raw = (out / "episodes.jsonl").read_bytes()
            self.assertEqual(sha256(raw).hexdigest(), result["episodes_sha256"])
            rows = [json.loads(line) for line in raw.splitlines()]
            keys = {(row["arm"], *(row["cell"][k] for k in g1.FIELDS)) for row in rows}
            self.assertEqual(len(rows), 672)
            self.assertEqual(len(keys), 672)
            self.assertEqual(sum(s["cells"] for s in result["strata"]), 672)
            self.assertTrue(result["all_records_replayed"])
            self.assertEqual(load_record(out / "episodes.jsonl", 672), rows[-1])
            for total in result["totals"]:
                selected = [r for r in rows if r["arm"] == total["arm"]]
                for metric in g1.COUNTERS:
                    self.assertEqual(total["totals"][metric], sum(r["measures"][metric] for r in selected))
            with self.assertRaises(FileExistsError):
                g1.run(out)

    def test_historical_implementations_and_results_unchanged(self):
        snapshot = json.loads((ROOT / "tests/data/coordination-preserved-baseline.json").read_text())
        for relative, expected in snapshot["files"].items():
            with self.subTest(path=relative):
                self.assertEqual(sha256((ROOT / relative).read_bytes()).hexdigest(), expected)
