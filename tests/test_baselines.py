"""Constant-policy control, honest accounting, and frozen prior histories."""

from collections import Counter
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from commonwealth.cli import main
from commonwealth.engine import Rejected, digest, initial_state, transition
from commonwealth.experiment import ARMS, change_method, demo, dispatch, evaluate, scripted_run
from commonwealth.pipeline import scenarios
from commonwealth.store import Workshop


# Captured from the four existing arms before adding the constant-policy arm.
# Each pair freezes both the hash-chain head and the entire canonical event list.
ORIGINAL_HISTORIES = {
    "missing": {
        "single": (
            "ada60f5313679b3dafe30d6a82367e3d0b708432bc6f34df16e3f5fd8eb14349",
            "992e71467916a09c4da5092c3fc60f67950bbca25683d7f62881b4287df6a551"),
        "team-primary-only": (
            "c83cacbff88a4456ac908eed2734c434e11c1fef92256d2344aad63b040013cf",
            "683aae78e633ce013e6e278552746dff243a8ad5c851234024d58ad0eea239f7"),
        "coached": (
            "9ea8f276cfd6d9a0aec66e2af5bdb41f8789f5194586b9145628b7dddd998a03",
            "e3dbb55578604b1c24d698ceec6bcaa91c70f41b460b948d44269eb367a3dc53"),
        "coached+casebook": (
            "5224cfa0c5b2b17bfa9481a2444a11c0f551e459688bb5fd824c232ab96fc5ad",
            "ca834ca8129f008aa907f6393867afa3dea5e03fe8badd7184f8f5ce42830fa9"),
    },
    "signed": {
        "single": (
            "cd18abece9394b5997a270a609c68f04401fc8ef5c0c92ad95f939fefaff1129",
            "4ca9acec215de8f0e1d0d7606be90f004ff3e193dc63862cc38ed73d0bc4d7c3"),
        "team-primary-only": (
            "cd18abece9394b5997a270a609c68f04401fc8ef5c0c92ad95f939fefaff1129",
            "4ca9acec215de8f0e1d0d7606be90f004ff3e193dc63862cc38ed73d0bc4d7c3"),
        "coached": (
            "b0d4f7fe1715a52c7717b5d65801de45f1ba5e9438928a1e4d987539dde3b525",
            "12de67c93c0e676a9a985b0d3d559605e067fe68cfad37be990295476487648e"),
        "coached+casebook": (
            "85f940fff091f5b85c70a7c302509794e1655d0b702b4a2de342b63b09e64b9f",
            "4ce3a568c7086caeb0f6f654adadccc66494c2a92c17393f3435b9c824b116e7"),
    },
    "flagged": {
        "single": (
            "d577e6ab249885227f01d5ff180f6cfad31f0f41c152fcc6c6bd85b6700466d0",
            "e6bbf47a14dcaf46a116b9f03b65dc153c6f5aa43c80e45d034d57c16d4555bd"),
        "team-primary-only": (
            "d577e6ab249885227f01d5ff180f6cfad31f0f41c152fcc6c6bd85b6700466d0",
            "e6bbf47a14dcaf46a116b9f03b65dc153c6f5aa43c80e45d034d57c16d4555bd"),
        "coached": (
            "f7f525c0ac4dbc5c79ebca7ef36f8005e4d614c0a48022dcc7aab76718855d96",
            "e1c7c96294c8cb154bf1635b930df4df5500e9ae7852a8a14364de680f7276e3"),
        "coached+casebook": (
            "82504697065a749ef3478210794c266a51ce5af460105da6898e26795dccc0ad",
            "2f7b8a5713b6998f23c2b248513355a86e70406db48d9bc4623042a763c2ebdc"),
    },
}


class EvaluationBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.output = cls.root / "comparison"
        cls.report = evaluate(cls.output)

    def workshop(self, scenario, arm):
        return Workshop(self.output / f"{scenario}-{arm}.sqlite")

    def test_all_fifteen_scenario_arm_pairs_and_saved_report(self):
        expected_arms = ("single", "team-primary-only", "coached", "coached+casebook",
                         "constant-quality-stream")
        self.assertEqual(ARMS, expected_arms)
        self.assertEqual(self.report["scenario_count"], 3)
        self.assertEqual(self.report["arm_count"], 5)
        self.assertEqual(len(self.report["runs"]), 15)
        self.assertEqual(
            [(run["scenario"], run["arm"]) for run in self.report["runs"]],
            [(scenario, arm) for scenario in scenarios() for arm in expected_arms])
        self.assertEqual(json.loads((self.output / "results.json").read_text()), self.report)
        self.assertTrue(all(run["replay"]["verified"] for run in self.report["runs"]))

    def test_constant_policy_is_chosen_and_authorized_before_observation(self):
        for scenario in scenarios():
            with self.subTest(scenario=scenario):
                workshop = self.workshop(scenario, "constant-quality-stream")
                events = workshop.events()
                self.assertEqual([event["command"]["action"] for event in events],
                                 ["init", "propose", "approve", "execute"] + ["observe"] * 4)
                proposal_id = events[1]["result"]["id"]
                self.assertEqual(events[1]["command"]["method"], "quality-stream")
                self.assertEqual(events[1]["command"]["prediction"],
                                 {"primary_correct": 1.0, "peer_on_time": 1.0})
                self.assertEqual(events[2]["command"],
                                 {"action": "approve", "actor": "keeper", "proposal": proposal_id})
                self.assertEqual(events[3]["command"],
                                 {"action": "execute", "actor": "worker-1", "proposal": proposal_id})
                state = workshop.state()
                proposal = state["proposals"][proposal_id]
                self.assertEqual(proposal["status"], "EXECUTED")
                self.assertEqual(proposal["approved_by"], "keeper")
                self.assertEqual(proposal["expires_before_tick"], 3)
                observations = list(state["observations"].values())
                self.assertEqual([o["tick"] for o in observations], [1, 2, 3, 4])
                self.assertTrue(all(o["method"] == "quality-stream" for o in observations))
                self.assertTrue(all(o["primary_correct"] and o["new_peer_on_time"] for o in observations))
                self.assertTrue(all(o["deadline_misses_this_tick"] == 0 for o in observations))
                self.assertEqual(state["peer_queue"], [])
                for field in ("testimonies", "listening", "reflections", "casebook_consultations", "lessons"):
                    self.assertFalse(state[field])
                self.assertEqual(state["command_count"], 7)
                self.assertEqual(workshop.verify()["events"], 8)

    def test_constant_policy_uses_existing_change_method_without_coaching(self):
        for scenario in scenarios():
            with self.subTest(scenario=scenario), \
                    patch("commonwealth.experiment.change_method", wraps=change_method) as change, \
                    patch("commonwealth.experiment.hear_and_reflect", side_effect=AssertionError("unexpected coaching")):
                workshop = scripted_run(self.root / f"helper-{scenario}.sqlite", scenario,
                                        "constant-quality-stream")
                change.assert_called_once()
                self.assertIs(change.call_args.args[0], workshop)
                self.assertEqual(change.call_args.args[1], "quality-stream")

    def test_constant_policy_cannot_execute_without_real_approval(self):
        def omit_approval(workshop, action, **fields):
            if action == "approve":
                return {"action": "approve"}  # A fabricated return must not grant authority.
            return dispatch(workshop, action, **fields)

        for scenario in scenarios():
            path = self.root / f"no-approval-{scenario}.sqlite"
            with self.subTest(scenario=scenario), \
                    patch("commonwealth.experiment.dispatch", side_effect=omit_approval):
                with self.assertRaisesRegex(Rejected, "exact proposal approval required"):
                    scripted_run(path, scenario, "constant-quality-stream")
            workshop = Workshop(path)
            self.assertEqual(workshop.verify()["events"], 2)
            self.assertEqual(workshop.state()["method"], "zero-fill")
            self.assertEqual(workshop.state()["tick"], 0)

    def test_constant_policy_requires_keeper_identity_for_approval(self):
        def wrong_approver(workshop, action, **fields):
            if action == "approve":
                fields["actor"] = "worker-1"
            return dispatch(workshop, action, **fields)

        path = self.root / "wrong-approver.sqlite"
        with patch("commonwealth.experiment.dispatch", side_effect=wrong_approver):
            with self.assertRaisesRegex(Rejected, "fixture maintainer must authorize"):
                scripted_run(path, "missing", "constant-quality-stream")
        self.assertEqual(Workshop(path).verify()["events"], 2)
        self.assertEqual(Workshop(path).state()["tick"], 0)

    def test_original_histories_are_unchanged_on_every_fixture(self):
        for scenario, arms in ORIGINAL_HISTORIES.items():
            for arm, (head, events_digest) in arms.items():
                with self.subTest(scenario=scenario, arm=arm):
                    workshop = self.workshop(scenario, arm)
                    self.assertEqual(workshop.verify()["head"], head)
                    self.assertEqual(digest(workshop.events()), events_digest)

    def test_demo_history_is_unchanged(self):
        workshop = demo(self.root / "demo.sqlite")
        replay = workshop.verify()
        self.assertEqual(replay["events"], 24)
        self.assertEqual(replay["head"],
                         "96baf584d179654e5abc836d127afdac80d916a08c05bcb482f732a01c0acb0a")
        self.assertEqual(digest(workshop.events()),
                         "fb4d923e6794d49563420384a5e1a1c545e4a12059ef03f301747b1214ad2c40")

    def test_action_counts_and_common_budgets_match_real_journals(self):
        for run in self.report["runs"]:
            with self.subTest(scenario=run["scenario"], arm=run["arm"]):
                events = self.workshop(run["scenario"], run["arm"]).events()
                counts = dict(Counter(event["command"]["action"] for event in events[1:]))
                self.assertEqual(run["command_action_counts"], counts)
                self.assertNotIn("init", counts)
                self.assertEqual(sum(counts.values()), run["measures"]["command_count"])
                self.assertEqual(counts["observe"], 4)
                self.assertEqual(run["measures"]["observed_ticks"], 4)
                self.assertEqual(run["measures"]["command_limit"], 256)
        self.assertEqual(self.report["design"]["common_observation_ticks"], 4)
        self.assertEqual(self.report["design"]["common_command_ceiling"], 256)
        self.assertGreater(len({run["measures"]["command_count"] for run in self.report["runs"]}), 1)

    def test_timing_metadata_matches_replayed_tick_and_command_changes(self):
        timing = self.report["design"]["timing_model"]
        self.assertEqual(timing["clock"], "OBSERVATION_TICKS")
        self.assertEqual(timing["tick_advancing_actions"], ["observe"])
        self.assertEqual(timing["ticks_per_observe"], 1)
        self.assertEqual(timing["ticks_per_other_command"], 0)
        self.assertEqual(timing["command_only_actions"], ["testify", "listen", "reflect", "consult"])
        self.assertIs(timing["command_only_actions_consume_command_budget"], True)
        seen_actions = set()
        for run in self.report["runs"]:
            events = self.workshop(run["scenario"], run["arm"]).events()
            genesis = events[0]["command"]
            state = initial_state(genesis["scenario"], genesis["fixture"])
            for event in events[1:]:
                action = event["command"]["action"]
                updated, _ = transition(state, event["command"])
                self.assertEqual(updated["tick"] - state["tick"], int(action == "observe"))
                self.assertEqual(updated["command_count"] - state["command_count"], 1)
                state = updated
                seen_actions.add(action)
        self.assertTrue(set(timing["command_only_actions"]).issubset(seen_actions))

    def test_resource_and_inference_limits_are_explicit_without_invented_costs(self):
        self.assertEqual(self.report["status"], "EXPOSED_SCRIPTED_DEMONSTRATION")
        self.assertEqual(self.report["model_calls"], 0)
        resource = self.report["design"]["resource_accounting"]
        self.assertEqual(resource["command_action_counts_source"],
                         "ACCEPTED_JOURNAL_COMMANDS_EXCLUDING_GENESIS")
        self.assertIs(resource["equal_command_ceiling_implies_equal_usage"], False)
        self.assertEqual(resource["record_inspections_are"], "SIMULATED_INSPECTION_CREDITS")
        self.assertEqual(resource["cost_measurement_status"],
                         {name: "NOT_MEASURED" for name in ("wall_time", "model_cost", "tokens", "energy")})
        self.assertTrue(any("fixed quality-stream policy suffices" in item
                            for item in self.report["conclusions_allowed"]))
        unsupported = " ".join(self.report["conclusions_not_supported"])
        for limitation in ("cause better model behavior", "sealed holdout", "adaptive learning",
                           "equal actual resource usage"):
            self.assertIn(limitation, unsupported)

    def test_cli_help_advertises_fifteen_runs(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit_status:
            main(["evaluate", "--help"])
        self.assertEqual(exit_status.exception.code, 0)
        self.assertIn("15 exposed scripted runs", output.getvalue())


if __name__ == "__main__":
    unittest.main()
