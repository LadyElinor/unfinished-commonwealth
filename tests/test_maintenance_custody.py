"""Exercise the custodian's CLI entirely with public, constructed records."""
import copy
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import analyze_maintenance_pairs as study
from scripts import maintenance_custody as custody


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "examples/maintenance_pairs"
SEED = bytes(range(32)).hex()


def raw_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, packet):
    path.write_bytes((json.dumps(packet, indent=2) + "\n").encode())
    return raw_digest(path)


class CustodyHandoff(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.freeze, self.roster, self.manifest, self.outcomes, self.mapping, self.grades = (
            root / name for name in ("freeze", "roster", "manifest", "outcomes", "map", "grades"))
        public = json.loads((PUBLIC / "manifest.json").read_bytes())
        self.freeze_data = {"schema": "maintenance-custody-freeze-v1", "kind": "public-rehearsal",
                            **custody.code_pins(), "custody_plan_sha256": "a" * 64, "grading_procedure_sha256": "b" * 64,
                            "pins": {key: public["pins"][key] for key in custody.PRE_INTAKE_PINS}}
        self.freeze_hash = save(self.freeze, self.freeze_data)
        self.roster_data = {"schema": "maintenance-custody-roster-v1", "freeze_sha256": self.freeze_hash,
                            "rubric_sha256": public["pins"]["rubric"],
                            "tasks": [{k: t[k] for k in ("id", "lineage", "packet_sha256")} for t in public["tasks"]]}
        self.roster_hash = save(self.roster, self.roster_data)
        self.common = [str(self.freeze), str(self.roster), str(self.manifest),
                       "--freeze-sha256", self.freeze_hash, "--roster-sha256", self.roster_hash, "--seed", SEED]

    def cli(self, command, *args, valid=True):
        result = subprocess.run([sys.executable, "-m", "scripts.maintenance_custody", command, *map(str, args)],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if valid else 2, result.stderr)
        if not valid:
            self.assertEqual(result.stdout, "")
        return result.stdout.strip() if valid else result.stderr

    def lock_public_example(self, *, with_observer=False):
        if with_observer:
            self.freeze_data["schema"] = custody.FREEZE_V2
            self.common[4] = save(self.freeze, self.freeze_data)
            self.roster_data["freeze_sha256"] = self.common[4]
            self.common[6] = save(self.roster, self.roster_data)
        self.manifest_hash = self.cli("assign", *self.common)
        self.assertEqual(self.manifest_hash, raw_digest(self.manifest))
        tasks = {t["id"]: t for t in json.loads(self.manifest.read_bytes())["tasks"]}
        self.outcome_data = json.loads((PUBLIC / "outcomes.json").read_bytes())
        self.outcome_data["manifest_sha256"] = self.manifest_hash
        self.map_data = {"schema": "maintenance-blinding-map-v1", "manifest_sha256": self.manifest_hash, "entries": []}
        self.grade_data = {"schema": "maintenance-blinded-grades-v1", "entries": []}
        for run in self.outcome_data["runs"]:
            # New, constructed sessions for this rehearsal. Historical fixture files stay intact.
            run["order"] = 1 if run["arm"] == tasks[run["task"]]["first_arm"] else 2
            run["receipt_sha256"] = sha256(("handoff rehearsal " + run["receipt_sha256"]).encode()).hexdigest()
            for n, candidate in enumerate(run["candidates"], 1):
                blind = sha256(f'public test ID {len(self.map_data["entries"])}'.encode()).hexdigest()
                common = dict(blind_id=blind, patch_sha256=candidate["sha256"])
                self.map_data["entries"].append(dict(common, task=run["task"], arm=run["arm"], submission=n))
                self.grade_data["entries"].append(dict(common, grade=candidate["grade"]))
        self.grade_data["entries"].reverse()
        extra = []
        if with_observer:
            self.observer = self.roster.parent / "observer"
            self.observer_data = json.loads((PUBLIC / "observer.json").read_bytes())
            self.observer_data["manifest_sha256"] = self.manifest_hash
            extra = ["--observer-ledger", self.observer, "--observer-sha256", save(self.observer, self.observer_data)]
        return [*self.common, self.outcomes, self.mapping, self.grades, *extra, "--manifest-sha256", self.manifest_hash,
                "--map-sha256", save(self.mapping, self.map_data), "--grades-sha256", save(self.grades, self.grade_data),
                "--outcomes-sha256", save(self.outcomes, self.outcome_data)]

    def test_end_to_end_and_independent_final_lock(self):
        args = self.lock_public_example()
        report = json.loads(self.cli("recount", *args))
        self.assertEqual(report["difference_bounds"], [0, .25])
        self.assertEqual(report["blind_grade_replay"]["matched_submissions"], 10)
        self.assertEqual(report["outcome_checkpoint"], "matched")
        self.assertEqual(report["observer_replay"], {"status": "not_supplied"})
        self.assertEqual(report["assignment_replay"]["custody_authentication"], "external_review_required")
        self.assertEqual(self.cli("assign", *self.common), self.manifest_hash)
        self.outcome_data["runs"][0]["candidates"][0]["grade"] = "correct"
        revised_hash = save(self.outcomes, self.outcome_data)
        self.assertIn("final outcome checkpoint", self.cli("recount", *args, valid=False))
        # Even a fresh checkpoint on an incorrectly joined export cannot change a locked grade.
        args[-1] = revised_hash
        self.assertIn("locked blind grade", self.cli("recount", *args, valid=False))

    def test_balanced_substitution_and_roster_changes(self):
        args = self.lock_public_example()
        plan = json.loads(self.manifest.read_bytes())
        for task in plan["tasks"]:
            task["first_arm"] = "plain" if task["first_arm"] == "governed" else "governed"
        study.validate_manifest(plan)
        save(self.manifest, plan)
        self.assertIn("already exists", self.cli("assign", *self.common, valid=False))
        self.assertIn("replayed assignment", self.cli("recount", *args, valid=False))
        self.roster_data["tasks"].reverse()
        save(self.roster, self.roster_data)
        self.assertIn("roster checkpoint", self.cli("assign", *self.common, valid=False))

    def test_freeze_precedes_intake_and_binds_actual_tool(self):
        self.freeze_data["analyzer_sha256"] = "0"*64
        changed = save(self.freeze, self.freeze_data)
        self.assertIn("freeze checkpoint", self.cli("assign", *self.common, valid=False))
        args = list(self.common)
        args[4] = changed
        self.assertIn("frozen file mismatch", self.cli("assign", *args, valid=False))
        self.freeze_data.update(custody.code_pins(), grading_procedure_sha256="e"*64)
        args[4] = save(self.freeze, self.freeze_data)
        self.assertIn("different freeze", self.cli("assign", *args, valid=False))
        self.assertFalse(self.manifest.exists())

    def test_exact_blind_join_and_no_workflow_fields_in_grades(self):
        self.lock_public_example()
        for variant in ("missing", "extra", "reused blind", "reused slot", "other bytes", "workflow label"):
            with self.subTest(variant=variant):
                mapping, grades = copy.deepcopy(self.map_data), copy.deepcopy(self.grade_data)
                if variant == "missing":
                    grades["entries"].pop()
                elif variant == "extra":
                    grades["entries"].append(dict(grades["entries"][0], blind_id="e"*64))
                elif variant == "reused blind":
                    mapping["entries"][1]["blind_id"] = mapping["entries"][0]["blind_id"]
                elif variant == "reused slot":
                    keys = ("task", "arm", "submission")
                    mapping["entries"][1].update({k: mapping["entries"][0][k] for k in keys})
                elif variant == "other bytes":
                    grades["entries"][0]["patch_sha256"] = "c"*64
                else:
                    grades["entries"][0]["arm"] = "plain"
                with self.assertRaises(ValueError):
                    custody.check_blind_grades(mapping, grades, self.manifest_hash, self.outcome_data)

    def test_identity_is_per_submission_including_identical_patches(self):
        self.lock_public_example()
        same_patch = self.outcome_data["runs"][0]["candidates"][0]["sha256"]
        self.outcome_data["runs"][1]["candidates"][0]["sha256"] = same_patch
        entry = self.map_data["entries"][1]
        entry["patch_sha256"] = same_patch
        next(g for g in self.grade_data["entries"] if g["blind_id"] == entry["blind_id"])["patch_sha256"] = same_patch
        custody.check_blind_grades(self.map_data, self.grade_data, self.manifest_hash, self.outcome_data)

    def test_v2_requires_the_observer_checkpoint_and_matches_complete_roster(self):
        args = self.lock_public_example(with_observer=True)
        report = json.loads(self.cli("recount", *args))
        self.assertEqual(report["difference_bounds"], [0, .25])
        observed = report["observer_replay"]
        self.assertEqual((observed["status"], observed["sessions"], observed["billing_allocations"]), ("matched", 8, 14))
        self.assertEqual(observed["ledger_sha256"], raw_digest(self.observer))
        self.assertEqual(observed["billing_line_coverage"]["governed"],
                         {"known_lines": 5, "unknown_lines": 1, "sessions_with_incomplete_billing": 0, "observed_net_micro_usd": 370})
        self.assertEqual(report["arms"]["governed"]["usage"]["cost_micro_usd"], {"known_sum": 300, "known": 3, "unknown": 1})
        offset = args.index("--observer-ledger")
        self.assertIn("v2 freeze requires", self.cli("recount", *args[:offset], *args[offset+4:], valid=False))
        self.assertIn("supply both", self.cli("recount", *args[:offset], *args[offset+2:], valid=False))
        self.observer.write_bytes(self.observer.read_bytes() + b" ")
        self.assertIn("observer ledger checkpoint", self.cli("recount", *args, valid=False))

    def test_rehashed_export_rejects_each_meter_charge_and_submission_time_change(self):
        args = self.lock_public_example(with_observer=True)
        for run in self.outcome_data["runs"]:
            changes = [(run["usage"], key) for key in study.METERS]
            changes.extend((candidate, "elapsed_ms") for candidate in run["candidates"])
            for values, key in changes:
                with self.subTest(task=run["task"], arm=run["arm"], key=key):
                    original = values[key]
                    values[key] = 0 if original is None else original + 1
                    args[-1] = save(self.outcomes, self.outcome_data)
                    self.assertIn("observer", self.cli("recount", *args, valid=False))
                    values[key] = original
        self.outcome_data["runs"][0]["usage"]["cost_micro_usd"] += 1
        self.outcome_data["runs"][2]["usage"]["cost_micro_usd"] -= 1
        args[-1] = save(self.outcomes, self.outcome_data)
        self.assertIn("observer disagrees with cost", self.cli("recount", *args, valid=False))

    def test_deadline_crossing_rejected_under_locked_grades_and_session_time(self):
        args = self.lock_public_example(with_observer=True)
        run = self.outcome_data["runs"][1]
        session = self.observer_data["sessions"][1]
        run["candidates"][-1]["elapsed_ms"] = session["submissions"][-1]["elapsed_ms"] = study.DEADLINE
        run["usage"]["elapsed_ms"] = session["meters"]["elapsed_ms"] = study.DEADLINE + 1
        args[args.index("--observer-sha256") + 1] = save(self.observer, self.observer_data)
        args[-1] = save(self.outcomes, self.outcome_data)
        self.assertEqual(json.loads(self.cli("recount", *args))["difference_bounds"], [0, .25])
        run["candidates"][-1]["elapsed_ms"] += 1
        args[-1] = save(self.outcomes, self.outcome_data)
        self.assertIn("submission differs from observer", self.cli("recount", *args, valid=False))

    def test_observer_rejects_missing_repeated_and_mismatched_evidence(self):
        self.lock_public_example(with_observer=True)
        for variant in ("manifest", "missing", "duplicate", "extra", "reused allocation", "reordered",
                        "bool meter", "bool time", "partial subtotal"):
            ledger = copy.deepcopy(self.observer_data)
            sessions = ledger["sessions"]
            with self.subTest(variant=variant):
                if variant == "manifest":
                    ledger["manifest_sha256"] = "a" * 64
                elif variant == "missing":
                    sessions.pop()
                elif variant == "duplicate":
                    sessions.append(sessions[0])
                elif variant == "extra":
                    sessions[0]["task"] = "unassigned"
                elif variant == "reused allocation":
                    sessions[-1]["charges"]["lines"][0]["id"] = sessions[0]["charges"]["lines"][0]["id"]
                elif variant == "reordered":
                    sessions[1]["submissions"].reverse()
                elif variant == "bool meter":
                    sessions[0]["meters"]["public_checks"] = True
                elif variant == "bool time":
                    sessions[0]["submissions"][0]["elapsed_ms"] = True
                else:
                    sessions[5]["charges"]["lines"].pop()
                with self.assertRaises(ValueError):
                    custody.check_observer_ledger(ledger, self.manifest_hash, self.outcome_data)

    def test_nonstarts_missing_ledgers_and_confirmed_zero_stay_distinct(self):
        args = self.lock_public_example(with_observer=True)
        for run in self.outcome_data["runs"]:
            run.update(closure="not_started", disposition="unresolved", candidates=[])
            run["usage"] = dict.fromkeys(study.METERS)
            if run["arm"] == "plain":
                run["usage"]["cost_micro_usd"] = 0
        for session in self.observer_data["sessions"]:
            session.update(meters=dict.fromkeys(custody.OBSERVER_METERS), submissions=[])
            session["charges"] = {"complete": session["arm"] == "plain", "lines": []}
        self.map_data["entries"] = []
        self.grade_data["entries"] = []
        for flag, path, data in (("--map-sha256", self.mapping, self.map_data),
                                 ("--grades-sha256", self.grades, self.grade_data),
                                 ("--observer-sha256", self.observer, self.observer_data),
                                 ("--outcomes-sha256", self.outcomes, self.outcome_data)):
            args[args.index(flag) + 1] = save(path, data)
        report = json.loads(self.cli("recount", *args))
        self.assertEqual(report["pair_counts"]["neither_correct"], 4)
        self.assertEqual(report["arms"]["plain"]["usage"]["cost_micro_usd"], {"known_sum": 0, "known": 4, "unknown": 0})
        self.assertEqual(report["arms"]["governed"]["usage"]["cost_micro_usd"], {"known_sum": None, "known": 0, "unknown": 4})
        coverage = report["observer_replay"]["billing_line_coverage"]
        self.assertEqual(coverage["plain"]["sessions_with_incomplete_billing"], 0)
        self.assertEqual(coverage["governed"]["sessions_with_incomplete_billing"], 4)
        self.assertIsNone(coverage["governed"]["observed_net_micro_usd"])

    def test_charge_arithmetic_missing_zero_credits_and_invalid_amounts(self):
        def charge(*amounts, complete=True):
            lines = [{"id": str(i), "micro_usd": value} for i, value in enumerate(amounts)]
            return custody.session_charge({"complete": complete, "lines": lines}, set(), Counter())
        self.assertEqual(charge(), 0)
        self.assertIsNone(charge(complete=False))
        self.assertIsNone(charge(0, None))
        self.assertEqual(charge(8, -8), 0)
        for amounts in ((-1,), (True,), (1.5,), (None, "0")):
            with self.subTest(amounts=amounts), self.assertRaises(ValueError):
                charge(*amounts)
        with self.assertRaises(ValueError):
            charge(complete=1)

    def test_partial_billing_keeps_known_lines_without_asserting_a_session_net(self):
        args = self.lock_public_example(with_observer=True)
        charges = self.observer_data["sessions"][5]["charges"]
        charges["lines"].pop()  # Only the observed charge for 70 is available.
        charges["complete"] = False
        args[args.index("--observer-sha256") + 1] = save(self.observer, self.observer_data)
        report = json.loads(self.cli("recount", *args))
        coverage = report["observer_replay"]["billing_line_coverage"]["governed"]
        self.assertEqual(coverage, {"known_lines": 5, "unknown_lines": 0, "sessions_with_incomplete_billing": 1,
                                    "observed_net_micro_usd": 370})
        self.assertEqual(report["arms"]["governed"]["usage"]["cost_micro_usd"], {"known_sum": 300, "known": 3, "unknown": 1})

    def test_independent_assignment_vectors_and_concurrent_publication(self):
        # Independently computed using Node's crypto.createHash and uint32 BE encoding.
        self.assertEqual(custody.plain_first_positions(4, SEED, "11"*32), {1, 3})
        self.assertEqual(custody.plain_first_positions(24, SEED, "11"*32), {3, 5, 6, 9, 12, 13, 14, 15, 17, 18, 20, 23})
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: custody.publish_manifest(self.manifest, b"first"), range(8)))
        with self.assertRaisesRegex(ValueError, "different manifest"):
            custody.publish_manifest(self.manifest, b"second")
        self.assertEqual(self.manifest.read_bytes(), b"first")
