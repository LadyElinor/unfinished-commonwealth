"""Controls for the exposed reviewer-screening and payment-clock rehearsal."""
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from commonwealth.remediation_v1 import role_history as r


BASE = Path(__file__).resolve().parents[1] / "examples/owed-assistance.json"


class RoleHistoryTests(unittest.TestCase):
    def setUp(self):
        self.base = r.load_packet(BASE)

    def run_world(self, name, arm="history", reserve=True, budget=5):
        return r.simulate(self.base, r.hearing(name, reserve), arm, budget)

    def test_decision_can_be_controlled_without_a_vote(self):
        office = self.run_world("nonvoting-selector", "office")
        history = self.run_world("nonvoting-selector")
        for trace, selector, files in ((office, "P1", ["A"]), (history, "R1", ["A", "B"])):
            actions = {e["action"]: e for e in trace["events"]}
            self.assertEqual(actions["select"]["actor"], selector)
            self.assertEqual(list(actions["select"]["files"]), files)
            self.assertNotEqual(actions["vote"]["actor"], selector)
        self.assertEqual(office["timeline"][-1]["inquiry"]["status"], "declared-inventory-reviewed")
        self.assertEqual(history["timeline"][-1]["inquiry"]["other_cases_owed_correction"], ["B"])
        self.assertEqual(history["initial_screen"]["selector"]["matched_conflict_records"], ["decision-17"])
        self.assertEqual(office["history"], history["history"])
        self.assertEqual(office["planned"], history["planned"])

    def test_stable_person_survives_move_but_not_name_collision(self):
        for name in ("direct-approver", "moved-approver"):
            trace = self.run_world(name)
            self.assertEqual(trace["authorized"]["voter"], "R1")
            self.assertEqual(trace["initial_screen"]["voter"]["matched_conflict_records"], ["decision-17"])
        for name in ("mistaken-identity", "former-colleague", "minor-connection", "disputed-allegation"):
            trace = self.run_world(name)
            self.assertEqual(trace["authorized"]["voter"], "P1")
            self.assertFalse(trace["misconduct_findings"])
        self.assertEqual(self.run_world("material-witness")["authorized"]["briefer"], "R1")
        self.assertEqual(self.run_world("financial-dependence")["authorized"]["voter"], "R1")

    def test_unanswered_challenge_wrong_case_and_wrong_source(self):
        h = r.hearing("disputed-allegation", True)
        h.response = None
        h.records += (r.Record("other-case", "P1", "material-witness", "witness-register", "another-case"),
                      r.Record("accusation", "P1", "signed-denial", "challenge"))
        trace = r.simulate(self.base, h, "history", 5)
        check = trace["initial_screen"]["voter"]
        self.assertFalse(check["excluded"])
        self.assertIsNone(trace["response"])
        self.assertEqual(trace["challenge"], h.challenge)
        self.assertNotIn("other-case", check["records_considered"])
        self.assertIn("accusation", check["records_considered"])
        self.assertTrue(check["would_change_with"])
        self.assertEqual(trace["misconduct_findings"], [])

    def test_first_available_conflict_free_reserve_and_no_original_fallback(self):
        h = r.hearing("nonvoting-selector", True)
        h.reserve = (replace(r.ALTERNATE, id="R0"), *h.reserve)
        h.available = frozenset({"R0", "R1"})
        h.records += (r.Record("reserve-role", "R0", "material-witness", "witness-register"),)
        trace = r.simulate(self.base, h, "history", 5)
        self.assertEqual(trace["authorized"]["selector"], "R1")
        self.assertEqual([s["excluded"] for s in trace["reserve_checks"]], [True, False])
        h.available = frozenset({"R0"})
        blocked = r.simulate(self.base, h, "history", 5)
        self.assertEqual(blocked["terminal"], "no-eligible-reserve")
        self.assertEqual(blocked["authorized"], {})
        self.assertEqual([e["action"] for e in blocked["events"]], ["screen", "replace"])
        self.assertEqual(blocked["timeline"][-1]["inquiry"]["next_owner"], "assistance-service")

    def test_budget_stops_vote_without_converting_brief_to_finding(self):
        trace = self.run_world("material-witness", budget=4)
        self.assertEqual([e["action"] for e in trace["events"]], ["screen", "replace", "select", "brief"])
        last = trace["timeline"][-1]
        self.assertEqual(last["inquiry"]["pending_files"], ["A", "B"])
        self.assertEqual(last["inquiry"]["findings"], {})
        self.assertEqual(trace["terminal"], "budget-exhausted")
        self.assertIsNone(r.score(trace, {"P1"})["review_elapsed"])

    def test_credit_and_claimant_burden_follow_source_records(self):
        self.base["transfers"][0]["at"] = 6
        self.base["work"].append(dict(record="condition", at=4, activity="Retell the denial", obligation="rule-inquiry",
                                      required=True, units=0, bearer="affected-person"))
        trace = self.run_world("moved-approver", reserve=False)
        outcome = r.score(trace, {"P1"})
        self.assertEqual((outcome["payment_tick"], outcome["lateness"]), (6, 1))
        self.assertEqual((outcome["claimant_demands"], outcome["claimant_work"]), (1, 0))
        self.assertEqual(trace["timeline"][-1]["participation"]["choices"]["further-contact"], "declined")
        self.base["transfers"].clear()
        outcome = r.score(self.run_world("minor-connection"), set())
        self.assertIsNone(outcome["payment_tick"])
        self.assertIsNone(outcome["lateness"])

    def test_all_pairs_are_matched_and_frozen(self):
        rows = list(r.matrix(self.base))
        keys = {(e["world"], e["reserve_available"], e["trace"]["budget"], e["trace"]["arm"]) for e in rows}
        self.assertEqual(len(keys), 72)
        self.assertEqual(len(rows), 72)
        for office, history in zip(rows[::2], rows[1::2]):
            for key in ["planned", "history", "case", "challenge", "response", "reserve_order", "budget"]:
                self.assertEqual(office["trace"][key], history["trace"][key])
            for row in (office, history):
                score = row["score"]
                self.assertEqual([score[k] for k in ("payment_tick", "lateness", "claimant_demands")], [5, 0, 0])
                self.assertEqual(score["unsupported_misconduct"], 0)
                for snap in row["trace"]["timeline"]:
                    credit = 100 if snap["tick"] >= 5 else 0
                    self.assertEqual(snap["payment"]["supported_credit_units"], credit)
        self.base["institution"] = "amended"
        with self.assertRaisesRegex(ValueError, "frozen"):
            list(r.matrix(self.base))

    def test_public_cli_replays_archived_receipts(self):
        root = BASE.parents[1]
        run = subprocess.run([sys.executable, "-m", "commonwealth.remediation_v1.role_history", str(BASE)],
                             cwd=root, text=True, capture_output=True, check=True)
        with gzip.open(root / "examples/role-history-traces.jsonl.gz", "rb") as f:
            archive = f.read()
        self.assertEqual(run.stdout.encode("utf-8"), archive)
        self.assertEqual(hashlib.sha256(archive).hexdigest(),
                         "1375ad918433daa0570b6323ec75b658306075c25e4b1c197434694d6a039511")

    @unittest.skipUnless(shutil.which("node"), "Node is required for the independent recount")
    def test_independent_recount_and_counterexamples(self):
        root = BASE.parents[1]
        archive = root / "examples/role-history-traces.jsonl.gz"
        cmd = ["node", str(root / "scripts/recount_role_history.mjs")]
        result = subprocess.run(cmd + [str(archive)], capture_output=True, text=True, check=True)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["episodes"], 72)
        for key, expected in (("history/true/5", (9, 0, 0, 41)), ("office/true/5", (9, 4, 1, 37)),
                              ("history/true/4", (4, 0, 5, 36)), ("history/false/5", (4, 0, 5, 26))):
            group = summary["groups"][key]
            self.assertEqual(tuple(group[k] for k in ("voted", "conflicts_retained", "missed", "slots")), expected)
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            lines = f.read().splitlines()
        def rejects(lines):
            proc = subprocess.run(cmd, input="\n".join(lines), text=True, capture_output=True)
            self.assertNotEqual(proc.returncode, 0)
        rejects(lines[:-1])
        rejects([lines[0], *lines[:-1]])
        first = json.loads(lines[0])
        first["score"]["claimant_demands"] = 1
        rejects([json.dumps(first), *lines[1:]])
        first = json.loads(lines[0])
        first["trace"]["events"][-1]["actor"] = "P1"
        rejects([json.dumps(first), *lines[1:]])
