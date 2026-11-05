"""E1 necessary-condition gates, hand schedules and adverse controls."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.uncertainty_v1 import experiment as e1
from commonwealth.uncertainty_v1.fixtures import PATTERNS, specification, EPISODES
from commonwealth.uncertainty_v1.policies import choose, wants_source
from commonwealth.uncertainty_v1.resources import SourceBudget
from commonwealth.uncertainty_v1.__main__ import load_record

ROOT = Path(__file__).resolve().parents[1]


def cell(pattern="agreement", **changes):
    return {"pattern": pattern, "swapped": False, "peer_work": 4, "review": "accurate"} | changes


class EvidencePolicies(unittest.TestCase):
    def test_same_observations_opposite_truth_cannot_both_be_initially_correct(self):
        a, b = cell("ambiguous-M", review="unavailable"), cell("ambiguous-Y", review="unavailable")
        self.assertEqual(specification(a)[1], specification(b)[1])
        for policy in e1.POLICIES:
            ra, rb = e1.episode(a, policy), e1.episode(b, policy)
            self.assertEqual(ra["events"], rb["events"])
            self.assertLessEqual(ra["measures"]["first_correct"] + rb["measures"]["first_correct"], 1)

    def test_origin_deduplication_does_not_authenticate_independence(self):
        disclosed = specification(cell("disclosed-copy"))[1]
        concealed = specification(cell("concealed-copy"))[1]
        self.assertEqual(choose("source-majority", disclosed), "Y")
        self.assertIsNone(choose("origin-majority", disclosed))
        self.assertEqual(choose("origin-majority", concealed), "Y")
        self.assertFalse(wants_source("corroborate-or-abstain", concealed[:2], 2))
        self.assertEqual(choose("corroborate-or-abstain", concealed[:2]), "Y")
        self.assertTrue(wants_source("corroborate-or-abstain", disclosed[:2], 2))
        conflict = [{"source":"s1","origin":"a","claim":"M"}, {"source":"s2","origin":"a","claim":"Y"}]
        self.assertIsNone(choose("origin-majority", conflict))

    def test_sparse_and_missing_evidence_are_not_consensus(self):
        packets = specification(cell("sparse"))[1]
        self.assertEqual(choose("source-majority", packets), "M")
        self.assertIsNone(choose("corroborate-or-abstain", packets))
        for policy in e1.POLICIES[2:]:
            self.assertIsNone(choose(policy, specification(cell("silent"))[1]))

    def test_policy_input_cannot_carry_truth_future_or_duplicate_source(self):
        packet = specification(cell())[1][0]
        for packets in ([dict(packet, truth="M")], [packet, packet], [dict(packet, claim=True)]):
            with self.assertRaises(ValueError):
                choose("source-majority", packets)
        with self.assertRaises(TypeError):
            choose("source-majority", [], truth="M")

    def test_no_policy_or_reviewer_uses_definitive_query(self):
        original = e1.Episode.step
        def guarded(sim, command):
            self.assertNotEqual(command["action"], "request-evidence")
            return original(sim, command)
        with patch.object(e1.Episode, "step", guarded):
            for policy, review in product(e1.POLICIES, ("accurate", "delayed", "wrong", "unavailable")):
                row = e1.episode(cell("concealed-copy", review=review), policy)
                self.assertFalse(row["journal"]["genesis"]["case"]["declared"])


class EvidenceClock(unittest.TestCase):
    def test_exact_arithmetic_and_first_execution_times(self):
        for swapped, expected in ((False, 15), (True, 10)):
            for policy, slot in (("constant-" + ("Y" if swapped else "M"), 4),
                                 ("source-majority", 7), ("corroborate-or-abstain", 6)):
                row = e1.episode(cell(swapped=swapped), policy)
                output = row["journal"]["terminal"]["measures"]["outputs"][0]
                self.assertEqual(output["completed"], slot)
                self.assertEqual(output["answer"]["value"], {"numerator":expected,"denominator":1})
                self.assertEqual(row["measures"]["primary_on_time"], slot <= 6)

    def test_zero_work_and_overload_peers_advance_through_consultation(self):
        for work, finish in ((0, 4), (4, 5), (8, 6)):
            row = e1.episode(cell(peer_work=work), "source-majority")
            peer = row["journal"]["terminal"]["measures"]["peers"][0]
            self.assertEqual(peer["completed"], finish)
            self.assertEqual(row["measures"]["peer_historical_misses"], int(work != 0))
            self.assertEqual(row["measures"]["decision_slots"], 20)

    def test_late_review_increases_repair_time_without_erasing_miss(self):
        for review, repair, time in (("accurate", 5, 12), ("delayed", 11, 18)):
            row = e1.episode(cell("disclosed-copy", review=review), "source-majority")
            self.assertEqual(row["measures"]["repair_latency_slots"], repair)
            self.assertEqual(row["first_correct_at"], time)
            self.assertEqual(row["measures"]["primary_historical_misses"], 1)
            self.assertEqual(row["measures"]["review_requests"], 1 + int(review == "delayed"))

    def test_wrong_review_can_corrupt_a_previously_correct_output(self):
        row = e1.episode(cell(review="wrong"), "constant-M")
        m = row["measures"]
        self.assertEqual((m["first_correct"], m["final_wrong"], m["review_regressions"], m["unresolved_errors"]), (1,1,1,1))
        self.assertEqual(m["primary_on_time"], 1)
        self.assertEqual(row["first_correct_at"], 4)
        self.assertEqual(m["outstanding_obligations"], 1)

    def test_unavailable_review_retains_unresolved_error_and_censoring(self):
        row = e1.episode(cell(review="unavailable"), "constant-Y")
        m = row["measures"]
        self.assertEqual((m["final_wrong"], m["unresolved_errors"], m["never_correct"], m["censored_late_slots"]), (1,1,1,14))
        self.assertEqual(m["first_correct_late_slots"], 0)
        self.assertEqual(m["review_grants"], 0)
        self.assertEqual(m["rights_reviews"], 0)

    def test_abstention_is_missing_output_and_recovery_not_error_repair(self):
        row = e1.episode(cell("silent"), "source-majority")
        m = row["measures"]
        self.assertEqual((m["first_absent"], m["recoveries_after_abstention"], m["repaired_errors"]), (1,1,0))
        self.assertEqual(m["recovery_latency_slots"], 5)
        self.assertEqual(m["matched_execution_waits"], 3)
        self.assertEqual(m["keeper_reviews"], 1)
        self.assertEqual(m["source_missing"], 3)


class ResourceDenial(unittest.TestCase):
    def test_guard_and_neutral_cut_matched_controls(self):
        non_retaliation = set(e1.COUNTERS) - set(e1.METRIC_GROUPS["retaliation"])
        for pattern, policy in product(PATTERNS, e1.POLICIES):
            rows = {facet:e1.episode(cell(pattern),policy,facet) for facet in e1.FACETS}
            for a,b in (("no-request","protected"),("bypassed","neutral-cut")):
                self.assertEqual({k:rows[a]["measures"][k] for k in non_retaliation},
                                 {k:rows[b]["measures"][k] for k in non_retaliation})
                self.assertEqual(rows[a]["journal"],rows[b]["journal"])
                self.assertEqual(rows[a]["events"][1:],rows[b]["events"][1:])
            self.assertEqual(rows["neutral-cut"]["measures"]["reprisal_imposed"],0)

    def test_real_query_denial_is_paid_and_restoration_retains_history(self):
        row=e1.episode(cell("lone-error"),"source-majority","bypassed")
        m=row["measures"]
        self.assertEqual((m["source_grants"],m["source_denials"],m["credits_removed"],m["credits_restored"]),(2,1,1,1))
        self.assertEqual(m["deprivation_slots"],8)
        denied=next(e for e in row["events"] if e["kind"]=="source" and not e["granted"])
        event=row["journal"]["events"][denied["slot"]-1]
        self.assertEqual(event["cost"]["decision_slots"],1)
        self.assertEqual(event["cost"]["observation_inspections"],0)
        self.assertIsNone(denied["packet"])
        self.assertEqual(m["reprisal_denied_queries"],1)
        self.assertEqual(m["observation_inspections"],3) # two sources + separate review reserve

    def test_unavailable_review_leaves_resource_loss_unresolved(self):
        m=e1.episode(cell(review="unavailable"),"source-majority","bypassed")["measures"]
        self.assertEqual((m["credits_unrestored"],m["reprisal_unrestored"],m["deprivation_slots"]),(1,1,19))

    def test_wrong_task_review_still_restores_procedural_right(self):
        m=e1.episode(cell(review="wrong"),"source-majority","bypassed")["measures"]
        self.assertEqual((m["final_wrong"],m["credits_restored"],m["reprisal_denied_queries"]),(1,1,1))

    def test_removed_credit_is_distinct_from_a_denied_query(self):
        m=e1.episode(cell(),"constant-M","bypassed")["measures"]
        self.assertEqual((m["credits_removed"],m["source_denials"],m["reprisal_imposed"]),(1,0,1))

    def test_only_declared_rights_reviewer_restores_once(self):
        budget=SourceBudget("bypassed")
        self.assertTrue(budget.query()); self.assertTrue(budget.query()); self.assertFalse(budget.query())
        self.assertFalse(budget.restore("coordinator")["accepted"])
        self.assertFalse(budget.query())
        self.assertEqual(budget.restore("rights-reviewer")["restored"],1)
        self.assertFalse(budget.restore("rights-reviewer")["accepted"])
        self.assertTrue(budget.query()); self.assertFalse(budget.query())


class EvidenceRecords(unittest.TestCase):
    def test_replay_rejects_changed_policy_evidence_costs_and_authority(self):
        row=e1.episode(cell("lone-error"),"source-majority","bypassed")
        self.assertTrue(e1.replay(row)["verified"])
        for mutate in (lambda r:r["measures"].update(source_denials=0),
                       lambda r:r["evaluation"]["packets"][0].update(claim="M"),
                       lambda r:r["events"][1].update(granted=False),
                       lambda r:r.update(authority_granted=True),
                       lambda r:r["journal"]["events"][0]["cost"].update(decision_slots=0)):
            changed=deepcopy(row); mutate(changed)
            with self.assertRaises(ValueError): e1.replay(changed)

    def test_strict_cells_and_bounded_duplicate_free_json(self):
        for bad in (cell(extra=1),cell(swapped=1),cell(peer_work=True),cell(review=[]),cell(pattern="unknown")):
            with self.assertRaises(ValueError): e1.episode(bad,"constant-M")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"row.jsonl"
            path.write_text('{"cell":{"swapped":true,"swapped":false}}\n')
            with self.assertRaises(ValueError): load_record(path,1)
            for line in (0,True,EPISODES+1,2):
                with self.assertRaises(ValueError): load_record(path,line)
            path.write_bytes(b" "*(1024*1024+1))
            with self.assertRaisesRegex(ValueError,"oversized"): load_record(path,1)

    def test_previous_experiments_are_frozen(self):
        baseline=json.loads((ROOT/"tests/data/uncertainty-preserved-baseline.json").read_text())
        for path,expected in baseline["files"].items():
            with self.subTest(path=path): self.assertEqual(sha256((ROOT/path).read_bytes()).hexdigest(),expected)


class EvidenceReproduction(unittest.TestCase):
    def test_full_matrix_replay_digest_summary_and_independent_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"e1"
            result=e1.run(out)
            self.assertEqual(result,json.loads((ROOT/"examples/uncertainty-v1-results.json").read_text()))
            self.assertEqual(result["episode_count"],3840)
            self.assertEqual([len(result[k]) for k in ("totals","by_review","by_pattern")],[20,80,160])
            self.assertEqual(sha256((out/"episodes.jsonl").read_bytes()).hexdigest(),result["episodes_sha256"])
            self.assertTrue(e1.replay(load_record(out/"episodes.jsonl",3840))["verified"])
            with self.assertRaises(FileExistsError): e1.run(out)
            if shutil.which("node"):
                run=subprocess.run(["node",str(ROOT/"scripts/audit_uncertainty.mjs"),str(out/"episodes.jsonl"),str(out/"results.json")],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(json.loads(run.stdout)["episodes"],3840)
            else:
                self.skipTest("full Python reproduction passed; Node unavailable for independent audit")

    @unittest.skipUnless(shutil.which("node"),"Node required for independent audit tamper check")
    def test_independent_checker_rejects_changed_arithmetic_schedule_and_denial(self):
        row=e1.episode(cell(),"constant-M","bypassed")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"row.jsonl"
            for mutate in (lambda r:r["measures"].update(reprisal_imposed=0),
                           lambda r:r["journal"]["terminal"]["measures"]["outputs"][0]["answer"]["value"].update(numerator=99),
                           lambda r:r["journal"]["events"][0]["cost"].update(environment_ticks=0)):
                changed=deepcopy(row); mutate(changed); path.write_text(json.dumps(changed)+"\n")
                run=subprocess.run(["node",str(ROOT/"scripts/audit_uncertainty.mjs"),str(path),"--partial"],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
