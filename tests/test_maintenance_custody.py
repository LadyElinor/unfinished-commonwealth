"""Exercise the custodian's CLI entirely with public, constructed records."""
import copy
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

    def lock_public_example(self):
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
        return [*self.common, self.outcomes, self.mapping, self.grades, "--manifest-sha256", self.manifest_hash,
                "--map-sha256", save(self.mapping, self.map_data), "--grades-sha256", save(self.grades, self.grade_data),
                "--outcomes-sha256", save(self.outcomes, self.outcome_data)]

    def test_end_to_end_and_independent_final_lock(self):
        args = self.lock_public_example()
        report = json.loads(self.cli("recount", *args))
        self.assertEqual(report["difference_bounds"], [0, .25])
        self.assertEqual(report["blind_grade_replay"]["matched_submissions"], 10)
        self.assertEqual(report["outcome_checkpoint"], "matched")
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

    def test_independent_assignment_vectors_and_concurrent_publication(self):
        # Independently computed using Node's crypto.createHash and uint32 BE encoding.
        self.assertEqual(custody.plain_first_positions(4, SEED, "11"*32), {1, 3})
        self.assertEqual(custody.plain_first_positions(24, SEED, "11"*32), {3, 5, 6, 9, 12, 13, 14, 15, 17, 18, 20, 23})
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: custody.publish_manifest(self.manifest, b"first"), range(8)))
        with self.assertRaisesRegex(ValueError, "different manifest"):
            custody.publish_manifest(self.manifest, b"second")
        self.assertEqual(self.manifest.read_bytes(), b"first")
