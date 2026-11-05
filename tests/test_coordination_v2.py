"""G2 exact schedules, collective authority, retaliation and retained evidence."""

from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.coordination_v2 import experiment as g2
from commonwealth.coordination_v2.council import Council, ROLES
from commonwealth.coordination_v2.__main__ import load_record
from commonwealth.study_v1.engine import Episode

ROOT = Path(__file__).resolve().parents[1]


def cell(scenario="correct-consensus", **changes):
    return {"scenario": scenario, "swapped": False, "deadline": 8, "peer_work": 2, "reprisal": False} | changes


class CollectiveAuthority(unittest.TestCase):
    def test_coordinator_cannot_replace_distributed_quorum(self):
        c = Council("distributed", "protected")
        self.assertTrue(c.vote("coordinator", "quality-stream", 0)["accepted"])
        self.assertIsNone(c.selection())
        self.assertFalse(c.vote("coordinator", "quality-stream", 0)["accepted"])
        self.assertFalse(c.vote("invented-role", "quality-stream", 0)["accepted"])
        self.assertIsNone(c.selection())
        c.vote("worker-a", "zero-fill", 0)
        c.vote("worker-b", "zero-fill", 0)
        self.assertEqual(c.selection()["method"], "zero-fill")
        self.assertTrue(c.permits_selection(c.selection()))

    def test_two_workers_can_select_without_coordinator(self):
        for rule in ("central", "distributed"):
            c = Council(rule, "protected")
            for role in ("worker-a", "worker-b"):
                c.vote(role, "zero-fill", 0)
            self.assertEqual(c.selection() is not None, rule == "distributed")

    def test_revision_invalidates_ballots_and_selections(self):
        c = Council("distributed", "protected")
        for role in ROLES:
            c.vote(role, "quality-stream", 0)
        selection = c.selection()
        self.assertTrue(c.review("reviewer", 0)["accepted"])
        self.assertIsNone(c.selection())
        self.assertFalse(c.permits_selection(selection))
        for rev in (0, True, "1"):
            self.assertFalse(c.vote("worker-a", "quality-stream", rev)["accepted"])
        c.vote("worker-a", "quality-stream", 1)
        c.vote("worker-b", "quality-stream", 1)
        current = c.selection()
        forged = dict(current, method="zero-fill")
        self.assertFalse(c.permits_selection(forged))
        c.vote("coordinator", "zero-fill", 1)
        self.assertFalse(c.permits_selection(current))

    def test_restoration_requires_distinct_declared_role_and_current_revision(self):
        c = Council("distributed", "bypassed")
        c.exclude_reporter("coordinator", "worker-b", "disagreement")
        self.assertFalse(c.vote("worker-b", "zero-fill", 0)["accepted"])
        for actor, rev in (("coordinator", 0), ("worker-a", 0), ("reviewer", 1), ("reviewer", False)):
            self.assertFalse(c.review(actor, rev)["accepted"])
            self.assertTrue(c.excluded)
        self.assertTrue(c.review("reviewer", 0)["restored"])
        self.assertTrue(c.vote("worker-b", "zero-fill", 1)["accepted"])

    def test_protection_and_scope_apply_even_to_coordinator(self):
        for guard in g2.GUARDS:
            c = Council("central", guard)
            for args in (("worker-a", "worker-b", "disagreement"),
                         ("coordinator", "worker-a", "disagreement"),
                         ("coordinator", "worker-b", "emergency")):
                self.assertFalse(c.exclude_reporter(*args)["accepted"])
                self.assertFalse(c.excluded)
            result = c.exclude_reporter("coordinator", "worker-b", "disagreement")
            self.assertEqual(result["accepted"], guard == "bypassed")

    def test_collective_selection_is_not_keeper_approval(self):
        record = g2.episode(cell(), "distributed-direct")
        genesis = record["journal"]["genesis"]
        sim = Episode(**{k: genesis[k] for k in ("case", "clock", "budget", "lesson", "coaching")})
        c = Council("distributed", "protected")
        for role in ROLES:
            c.vote(role, "quality-stream", 0)
        sim.step({"action": "propose", "actor": "worker", "method": c.selection()["method"]})
        denied = sim.step({"action": "execute", "actor": "worker", "proposal": 1})
        self.assertFalse(denied["response"]["accepted"])
        self.assertEqual(sim.tick, 2)
        self.assertFalse(sim.outputs)


class G2Schedules(unittest.TestCase):
    def test_hand_arithmetic_and_eight_slot_execution(self):
        for swapped, expected in ((False, Fraction(10+20, 2)), (True, Fraction(10+20, 3))):
            row = g2.episode(cell(swapped=swapped), "central-direct")
            output = row["journal"]["terminal"]["measures"]["outputs"][0]
            self.assertEqual(output["answer"]["value"], {"numerator": expected.numerator, "denominator": expected.denominator})
            self.assertEqual(output["completed"], 8)
            self.assertEqual(row["measures"]["peer_late_slots"], 1)
            self.assertEqual(row["measures"]["primary_late_slots"], 0)

    def test_false_warning_charges_consultation_and_can_miss_deadline(self):
        for arm in ("central-direct", "distributed-direct"):
            row = g2.episode(cell("false-warning"), arm)
            m = row["measures"]
            self.assertTrue(m["first_correct"])
            self.assertEqual(m["first_completed"], 9)
            self.assertEqual(m["primary_historical_misses"], 1)
            self.assertEqual(m["primary_late_slots"], 1)
            self.assertEqual(m["consultation_slots"], 2)
            self.assertEqual(m["ballot_slots"], 3)
            self.assertEqual(m["peer_on_time"], 1)
        filtered = g2.episode(cell("false-warning"), "central-filtered")
        self.assertTrue(filtered["measures"]["primary_on_time"])
        self.assertIsNone(filtered["journal"]["genesis"]["lesson"])

    def test_wrong_output_repair_preserves_first_error_and_eight_slot_latency(self):
        row = g2.episode(cell("mistaken-consensus"), "central-filtered")
        summary = row["journal"]["terminal"]["measures"]
        self.assertEqual([o["answer"]["value"]["numerator"] for o in summary["outputs"]], [15, 10])
        self.assertEqual([o["completed"] for o in summary["outputs"]], [8, 16])
        self.assertEqual(summary["repair_latency"], [{"failed_at": 8, "repaired_at": 16, "latency": 8}])
        self.assertEqual(row["measures"]["repair_latency_slots"], 8)
        self.assertEqual(row["measures"]["recovery_count"], 0)
        self.assertEqual(row["measures"]["primary_historical_misses"], 1)
        self.assertEqual(row["measures"]["peer_historical_misses"], 1)
        self.assertEqual(row["intent"], "not-established")

    def test_authority_changes_binding_outcome_in_both_directions(self):
        for scenario, central_correct in (("mistaken-coordinator", False), ("mistaken-majority", True)):
            central = g2.episode(cell(scenario), "central-filtered")
            collective = g2.episode(cell(scenario), "distributed-filtered")
            self.assertEqual(central["routing"], collective["routing"])
            self.assertEqual(central["measures"]["first_correct"], central_correct)
            self.assertEqual(collective["measures"]["first_correct"], not central_correct)

    def test_zero_work_and_overload_keep_advancing_during_deliberation(self):
        for scenario, work in product(("correct-consensus", "false-warning"), (0, 2, 8)):
            row = g2.episode(cell(scenario, peer_work=work), "distributed-direct")
            peer = row["journal"]["terminal"]["measures"]["peers"][0]
            expected = 8 if work == 0 or work == 2 and scenario == "false-warning" else 9 if work == 2 else 10
            self.assertEqual(peer["completed"], expected)
            self.assertEqual(peer["missed"], expected > 8)
            self.assertEqual(row["measures"]["peer_inspections"], work)
            self.assertEqual(row["measures"]["decision_slots"], 20)


class RetaliationControls(unittest.TestCase):
    def test_protected_attempts_do_not_change_task_outcomes_or_costs(self):
        for scenario, arm in product(g2.SCENARIOS, g2.ARMS):
            quiet = g2.episode(cell(scenario), arm)
            attempt = g2.episode(cell(scenario, reprisal=True), arm)
            excluded = {"reprisal_attempts", "reprisal_blocked"}
            self.assertEqual({k:v for k,v in quiet["measures"].items() if k not in excluded},
                             {k:v for k,v in attempt["measures"].items() if k not in excluded})
            self.assertEqual(quiet["journal"], attempt["journal"])
            self.assertEqual(attempt["measures"]["exclusions_imposed"], 0)
            self.assertEqual(attempt["measures"]["denied_ballots"], 0)

    def test_guard_bypass_without_attack_is_matched_null(self):
        for arm in g2.ARMS:
            safe = g2.episode(cell("mistaken-coordinator"), arm, "protected")
            bypass = g2.episode(cell("mistaken-coordinator"), arm, "bypassed")
            self.assertEqual(safe["measures"], bypass["measures"])
            self.assertEqual(safe["decisions"], bypass["decisions"])
            self.assertEqual(safe["journal"], bypass["journal"])

    def test_exclusion_rejects_real_ballot_blocks_quorum_then_restores(self):
        row = g2.episode(cell("mistaken-coordinator", reprisal=True), "distributed-filtered", "bypassed")
        m = row["measures"]
        self.assertEqual((m["reprisal_attempts"], m["reprisal_blocked"], m["exclusions_imposed"], m["denied_ballots"]), (1,0,1,1))
        self.assertEqual((m["exclusions_restored"], m["exclusions_unresolved"], m["exclusion_duration_slots"]), (1,0,8))
        self.assertTrue(m["first_missing"])
        self.assertEqual((m["selection_refusals"], m["repair_count"], m["recovery_count"], m["recovery_latency_slots"]), (1,0,1,8))
        self.assertEqual(m["matched_review_waits"], 1)
        self.assertEqual(m["keeper_reviews"], 1)
        outputs = row["journal"]["terminal"]["measures"]["outputs"]
        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0]["completed"], 16)
        reporter_votes = [e for e in row["decisions"] if e["kind"] == "ballot" and e["actor"] == "worker-b"]
        self.assertEqual([e["response"]["accepted"] for e in reporter_votes], [False, True])
        self.assertEqual([e["revision"] for e in reporter_votes], [0, 1])
        refused_slot = reporter_votes[0]["slot"]
        cost = row["journal"]["events"][refused_slot-1]["cost"]
        self.assertEqual((cost["decision_slots"], cost["environment_ticks"]), (1,1))

    def test_exclusion_can_incidentally_prevent_wrong_output_without_becoming_good(self):
        protected = g2.episode(cell("mistaken-majority", reprisal=True), "distributed-filtered")
        bypass = g2.episode(cell("mistaken-majority", reprisal=True), "distributed-filtered", "bypassed")
        self.assertEqual(protected["measures"]["wrong_first"], 1)
        self.assertEqual(bypass["measures"]["wrong_first"], 0)
        self.assertTrue(bypass["measures"]["first_missing"])
        self.assertEqual(bypass["measures"]["denied_ballots"], 1)
        self.assertFalse(bypass["authority_granted"])

    def test_truth_and_delivery_do_not_change_the_authored_reprisal_trigger(self):
        for scenario, route in product(("false-warning", "mistaken-consensus"), ("direct", "filtered")):
            row = g2.episode(cell(scenario, reprisal=True), "central-"+route, "bypassed")
            self.assertEqual(row["measures"]["reprisal_attempts"], 1)
            self.assertEqual(row["measures"]["exclusions_imposed"], 1)
            self.assertEqual(row["measures"]["denied_ballots"], 1)

    def test_reporter_label_is_not_permission_or_a_penalty(self):
        for guard in g2.GUARDS:
            a = g2.episode(cell("mistaken-coordinator", reprisal=True), "distributed-filtered", guard, "agreeable")
            b = g2.episode(cell("mistaken-coordinator", reprisal=True), "distributed-filtered", guard, "dissenter")
            self.assertEqual(a["measures"], b["measures"])
            self.assertEqual(a["decisions"], b["decisions"])


class G2RecordBoundaries(unittest.TestCase):
    def test_hidden_truth_does_not_enter_information_policy(self):
        prefs = {role: "quality-stream" for role in ROLES}
        for route in (None, "quality-stream", "zero-fill"):
            self.assertEqual(g2.needs_evidence("central-direct", prefs, route),
                             g2.needs_evidence("distributed-direct", prefs, route))
        with self.assertRaises(TypeError):
            g2.needs_evidence("central-direct", prefs, None, truth="yield")
        with self.assertRaises(ValueError):
            g2.needs_evidence("invented", prefs, None)

    def test_replay_rejects_ballot_delivery_retaliation_and_authority_changes(self):
        original = g2.episode(cell("mistaken-coordinator", reprisal=True), "distributed-filtered", "bypassed")
        self.assertTrue(g2.replay(original)["verified"])
        edits = [lambda r: r["decisions"][4]["response"].update(accepted=True),
                 lambda r: r["routing"].update(delivered=True),
                 lambda r: r["measures"].update(denied_ballots=0),
                 lambda r: r.update(guard="protected"),
                 lambda r: r.update(authority_granted=True),
                 lambda r: r["journal"]["terminal"]["measures"].update(primary_correct=False)]
        for edit in edits:
            changed = deepcopy(original)
            edit(changed)
            with self.assertRaises(ValueError):
                g2.replay(changed)

    def test_strict_cells_json_and_bounded_replay_input(self):
        for bad in (cell(deadline=True), cell(peer_work=True), cell(reprisal=1), cell(swapped=0),
                    cell(scenario="unknown"), cell(extra="grant")):
            with self.assertRaises(ValueError):
                g2.episode(bad, "central-direct")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"cell":{"reprisal":false,"reprisal":true}}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_record(path, 1)
            for line in (0, True, 2017, 2):
                with self.assertRaises(ValueError):
                    load_record(path, line)
            path.write_bytes(b" " * (1024*1024+1))
            with self.assertRaisesRegex(ValueError, "oversized"):
                load_record(path, 1)


class G2Reproduction(unittest.TestCase):
    def test_complete_matrix_reproduces_and_does_not_pool_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "g2"
            result = g2.run(out)
            self.assertEqual(result, json.loads((ROOT / "examples/coordination-v2-results.json").read_text()))
            hasher = sha256()
            seen = set()
            counts = {}
            with (out / "episodes.jsonl").open("rb") as handle:
                for raw in handle:
                    hasher.update(raw)
                    row = json.loads(raw)
                    c = row["cell"]
                    key = (row["guard"], row["arm"], c["scenario"], c["swapped"], c["deadline"], c["peer_work"], c["reprisal"])
                    self.assertNotIn(key, seen)
                    seen.add(key)
                    group = counts.setdefault(key[:2], dict.fromkeys(g2.COUNTERS, 0))
                    for metric in g2.COUNTERS:
                        group[metric] += row["measures"][metric]
            self.assertEqual(len(seen), 2016)
            self.assertEqual(result["episodes_sha256"], hasher.hexdigest())
            self.assertEqual(len(result["totals"]), 14)
            for total in result["totals"]:
                self.assertEqual(total["cells"], 144)
                self.assertEqual(total["totals"], counts[total["guard"], total["arm"]])
            self.assertEqual(sum(s["cells"] for s in result["strata"]), 2016)
            self.assertTrue(g2.replay(load_record(out / "episodes.jsonl", 2016))["verified"])
            with self.assertRaises(FileExistsError):
                g2.run(out)

    def test_prior_g1_and_shared_sources_remain_frozen(self):
        snapshot = json.loads((ROOT / "tests/data/coordination-v2-preserved-baseline.json").read_text())
        for name, expected in snapshot["files"].items():
            with self.subTest(path=name):
                self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), expected)
