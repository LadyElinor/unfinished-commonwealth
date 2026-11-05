"""Fixed controls, matched access, paired advice and reproducible outcomes."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.study_v1.contracts import SLOT_YIELD, VALID_MEAN
from commonwealth.study_v1.engine import CLOCKS, DEFAULT_BUDGET, Episode, replay
from commonwealth.study_v1.experiment import compact_summary, evaluate, matrix
from commonwealth.study_v1.fixtures import case, development_cases, discriminating_gate, inherited_record, LESSON_KINDS
from commonwealth.study_v1.policies import CONTROLS, arms, decide, usable_lesson

ROOT = Path(__file__).resolve().parents[1]


class DesignGates(unittest.TestCase):
    def test_development_suite_discriminates(self):
        self.assertEqual(discriminating_gate(development_cases())["universal_constant_methods"], [])

    def test_reject_coincident_and_single_family_suites(self):
        with self.assertRaisesRegex(ValueError, "coincident"):
            discriminating_gate([case(), case("coincident-yield", SLOT_YIELD, values=[1, 2], valid=[True, True])])
        with self.assertRaisesRegex(ValueError, "both contract"):
            discriminating_gate([case()])

    def test_reject_a_suite_solved_by_positive_only_despite_two_contracts(self):
        # mean([10, null, 20]) = 15; yield([1, 3]) = 2. Positive-only solves both.
        cases = [case(), case("yield", SLOT_YIELD, values=[1, 3], valid=[True, False])]
        with self.assertRaisesRegex(ValueError, "constant method"):
            discriminating_gate(cases)

    def test_uncertain_twins_have_identical_initial_views(self):
        first = Episode(case("mean", VALID_MEAN, declared=False))
        second = Episode(case("yield", SLOT_YIELD, declared=False))
        self.assertEqual(first.view(), second.view())
        for hidden in ("reference", "name", "expected", "primary_correct"):
            self.assertNotIn(hidden, first.view())
        for episode in (first, second):
            response = episode.step({"action": "request-evidence", "actor": "worker"})
            self.assertEqual(response["cost"]["observation_grants"], 1)
        self.assertNotEqual(first.view()["contract"], second.view()["contract"])

    def test_observation_access_is_equal_for_every_arm(self):
        for arm in arms():
            fixture = case(contract=SLOT_YIELD, declared=False)
            lesson = inherited_record(SLOT_YIELD, arm["inheritance"]) if arm["inheritance"] else None
            episode = Episode(fixture, lesson=lesson, coaching=arm["coaching"])
            response = episode.step({"action": "request-evidence", "actor": "worker"})
            self.assertEqual(response["response"]["evidence"],
                             {"source": "scheduled-task-order-v1", "contract": SLOT_YIELD})
            self.assertEqual(episode.budget, DEFAULT_BUDGET)

    def test_disputed_and_suspended_records_preserve_both_accounts_and_are_withheld(self):
        for kind in ("disputed", "suspended"):
            lesson = inherited_record(VALID_MEAN, kind)
            episode = Episode(case(), lesson=lesson)
            event = episode.step({"action": "listen", "actor": "worker", "source": "inheritance"})
            self.assertEqual(event["response"]["record"], lesson)
            self.assertIsNotNone(episode.view()["lesson"]["objection"])
            self.assertIsNone(usable_lesson(episode.view()["lesson"], VALID_MEAN))
        self.assertEqual(inherited_record(VALID_MEAN, "disputed")["keeper_decision"], "accept")

    def test_contract_switch_and_lesson_status_are_separate_factors(self):
        old = inherited_record(VALID_MEAN, "correct")
        self.assertEqual(usable_lesson(old, VALID_MEAN), "quality-stream")
        self.assertIsNone(usable_lesson(old, SLOT_YIELD))
        current = case(contract=SLOT_YIELD)
        before = deepcopy(current)
        for kind in LESSON_KINDS:
            Episode(current, lesson=inherited_record(SLOT_YIELD, kind))
        self.assertEqual(current, before)

    def test_current_evidence_overrides_stale_inherited_method(self):
        fixture = case(contract=SLOT_YIELD)
        episode = Episode(fixture, lesson=inherited_record(SLOT_YIELD, "stale"))
        while not episode.closed:
            episode.step(decide("participant", episode.view()))
        self.assertEqual(episode.proposals[0]["method"], "zero-fill")
        self.assertTrue(episode.summary()["primary_correct"])

    def test_completed_donor_practice_crosses_contract_without_its_authority(self):
        donor = Episode(case())
        while not donor.closed:
            donor.step(decide("participant", donor.view()))
        original = donor.journal()
        self.assertTrue(donor.summary()["primary_correct"])
        lesson = inherited_record(VALID_MEAN, "correct")
        lesson["source_run"] = {"head": donor.head, "output": donor.outputs[-1]}
        inherited = Episode(case("successor", SLOT_YIELD, deadline=3), lesson=lesson)
        no_memory = Episode(case("successor", SLOT_YIELD, deadline=3))
        self.assertEqual(inherited.proposals, [])
        self.assertEqual(inherited.budget, no_memory.budget)
        for episode in (inherited, no_memory):
            while not episode.closed:
                episode.step(decide("participant", episode.view()))
            self.assertTrue(episode.summary()["primary_correct"])
            self.assertEqual(episode.proposals[0]["method"], "zero-fill")
            self.assertTrue(any(e["response"].get("review", {}).get("actor") == "keeper" for e in episode.events))
        self.assertTrue(no_memory.summary()["primary_on_time"])
        self.assertFalse(inherited.summary()["primary_on_time"])
        self.assertEqual(inherited.view()["lesson"]["source_run"]["head"], donor.head)
        self.assertEqual(original, donor.journal())
        self.assertTrue(replay(inherited.journal())["verified"])


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.journals = matrix()

    def measures(self, case_name, arm, clock=CLOCKS[0]):
        return next(r["measures"] for r in self.report["runs"]
                    if (r["case"], r["arm"], r["clock"]) == (case_name, arm, clock))

    def test_complete_cross_product_all_controls_and_replays(self):
        expected = {(c["name"], a["name"], clock) for c in development_cases() for a in arms() for clock in CLOCKS}
        actual = {(r["case"], r["arm"], r["clock"]) for r in self.report["runs"]}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 432)
        self.assertTrue(all(r["replay"]["verified"] for r in self.report["runs"]))
        self.assertTrue(set(CONTROLS).issubset({a["name"] for a in arms()}))

    def test_budgets_equal_and_costs_reconcile_with_every_attempt(self):
        for row in self.report["runs"]:
            measures = row["measures"]
            journal = self.journals[row["id"]]
            self.assertEqual(row["budget"], DEFAULT_BUDGET)
            self.assertEqual(measures["attempts"], 8)
            self.assertEqual(measures["decision_slots"], 8)
            for field in ("decision_slots", "inspections", "observation_grants",
                          "observation_inspections", "primary_inspections", "peer_inspections"):
                self.assertEqual(measures[field], sum(e["cost"][field] for e in journal["events"]))
            self.assertEqual(measures["inspections"], sum(measures[field] for field in
                            ("observation_inspections", "primary_inspections", "peer_inspections")))
            self.assertLessEqual(measures["observation_grants"], 2)
            self.assertLessEqual(measures["inspections"], 48)
            if row["clock"] == CLOCKS[0]:
                self.assertEqual(measures["environment_ticks"], 8)

    def test_direct_selector_suffices_for_complete_information(self):
        for prefix in ("mean", "yield"):
            for suffix in ("clear", "urgent", "signed"):
                name = prefix + "-" + suffix
                self.assertTrue(self.measures(name, "contract-selector")["primary_correct"])
                self.assertEqual(self.measures(name, "contract-selector"),
                                 self.measures(name, "participant"))

    def test_simple_evidence_selector_resolves_ambiguity_without_memory(self):
        for prefix in ("mean", "yield"):
            name = prefix + "-uncertain"
            self.assertFalse(self.measures(name, "contract-selector")["primary_correct"])
            self.assertTrue(self.measures(name, "evidence-selector")["primary_correct"])
            self.assertEqual(self.measures(name, "evidence-selector"), self.measures(name, "participant"))

    def test_unnecessary_inspection_and_advice_lose_urgent_deadlines(self):
        for prefix in ("mean", "yield"):
            name = prefix + "-urgent"
            self.assertTrue(self.measures(name, "contract-selector")["primary_on_time"])
            for arm in ("always-inspect", "participant+coaching", "participant+inheritance-correct"):
                self.assertFalse(self.measures(name, arm)["primary_on_time"])
                self.assertTrue(self.measures(name, arm)["primary_correct"])

    def test_no_claimed_inheritance_or_coaching_correctness_advantage(self):
        for fixture in development_cases():
            baseline = self.measures(fixture["name"], "evidence-selector")
            for arm in arms():
                if arm["policy"] == "participant":
                    result = self.measures(fixture["name"], arm["name"])
                    self.assertLessEqual(result["primary_correct"], baseline["primary_correct"])
                    self.assertLessEqual(result["primary_on_time"], baseline["primary_on_time"])

    def test_capacity_failure_and_overload_are_retained(self):
        no_capacity = self.measures("yield-no-capacity", "evidence-selector")
        self.assertFalse(no_capacity["primary_correct"])
        self.assertEqual(no_capacity["inspections"], 0)
        self.assertTrue(no_capacity["outstanding"])
        overloaded = self.measures("yield-overload", "evidence-selector")
        self.assertTrue(overloaded["primary_correct"])
        self.assertGreater(overloaded["peer_historical_misses"], 0)

    def test_byte_deterministic_reports_and_journals(self):
        other, journals = matrix()
        self.assertEqual(other, self.report)
        self.assertEqual(journals, self.journals)

    def test_written_reports_and_all_journals_are_reproducible_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            self.assertEqual(evaluate(output), self.report)
            self.assertEqual(json.loads((output / "summary.json").read_text()), compact_summary(self.report))
            for ident, expected in self.journals.items():
                saved = json.loads((output / "journals" / f"{ident}.json").read_text())
                self.assertEqual(saved, expected)
                self.assertTrue(replay(saved)["verified"])
            with self.assertRaises(FileExistsError):
                evaluate(output)

    def test_exposed_status_no_model_calls_and_inference_limits(self):
        self.assertEqual(self.report["status"], "EXPOSED_DETERMINISTIC_DEVELOPMENT_ONLY")
        self.assertEqual(self.report["model_calls"], 0)
        self.assertEqual(len(self.report["unsupported_claims"]), 5)
        self.assertTrue(all(r["measures"]["actual_costs"] == "NOT_MEASURED" for r in self.report["runs"]))


class PreservationTests(unittest.TestCase):
    def test_frozen_workshop_files_and_recorded_failures_unchanged(self):
        manifest = json.loads((ROOT / "tests/data/study-preserved-v013.json").read_text())
        for name, expected in manifest["sha256"].items():
            with self.subTest(path=name):
                self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_committed_summary_matches_generated_result(self):
        report, _ = matrix()
        expected = json.loads((ROOT / "examples/study-v1-summary.json").read_text())
        self.assertEqual(compact_summary(report), expected)


if __name__ == "__main__":
    unittest.main()
