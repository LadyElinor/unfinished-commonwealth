from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from commonwealth.cli import main, read_command
from commonwealth.coach import advise, inherited_method
from commonwealth.engine import Rejected, canonical, digest, initial_state, transition
from commonwealth.experiment import change_method, demo, dispatch, evaluate
from commonwealth.interface import agent_view
from commonwealth.pipeline import aggregate, scenarios
from commonwealth.report import markdown, summarize
from commonwealth.store import CorruptJournal, Workshop


class PipelineTests(unittest.TestCase):
    def test_all_fixture_references(self):
        for name, fixture in scenarios().items():
            with self.subTest(name=name):
                output = aggregate(fixture["values"], fixture["valid"], "quality-stream")
                self.assertEqual(output["mean"], fixture["reference"])
                self.assertEqual(output["inspections"], len(fixture["values"]))

    def test_positive_shortcut_fails_signed_and_flagged_data(self):
        for name in ("signed", "flagged"):
            fixture = scenarios()[name]
            result = aggregate(fixture["values"], fixture["valid"], "positive-only")
            self.assertNotEqual(result["mean"], fixture["reference"])
            self.assertEqual(result["inspections"], 2 * len(fixture["values"]))

    def test_zero_fill_is_biased(self):
        fixture = scenarios()["missing"]
        output = aggregate(fixture["values"], fixture["valid"], "zero-fill")
        self.assertEqual(output["mean"], {"numerator": 45, "denominator": 4})

    def test_empty_valid_set_has_no_fabricated_mean(self):
        self.assertIsNone(aggregate([None], [False], "quality-stream")["mean"])

    def test_malformed_readings_rejected(self):
        for values, flags in (([True], [True]), ([1.0], [True]), ([1], [1]), ([None], [True]), ([], [])):
            with self.subTest(values=values, flags=flags), self.assertRaises(ValueError):
                aggregate(values, flags, "quality-stream")


class WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "workshop.sqlite"
        self.workshop = Workshop.create(self.path)

    def proposal(self, method="quality-stream"):
        return dispatch(self.workshop, "propose", method=method, purpose="Test exact bounded method.",
                        prediction={"primary_correct": 0.9, "peer_on_time": 0.8})["id"]

    def assertRejectedUnchanged(self, command):
        before = self.workshop.verify()
        with self.assertRaises((Rejected, ValueError, TypeError)):
            self.workshop.dispatch(command)
        self.assertEqual(before, self.workshop.verify())

    def test_creation_never_overwrites(self):
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            Workshop.create(self.path)
        self.assertEqual(original, self.path.read_bytes())

    def test_reopen_preserves_state(self):
        dispatch(self.workshop, "observe")
        self.assertEqual(self.workshop.state(), Workshop(self.path).state())

    def test_proposal_does_not_execute(self):
        self.proposal()
        self.assertEqual(self.workshop.state()["method"], "zero-fill")

    def test_execution_requires_approval(self):
        proposal = self.proposal()
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})

    def test_worker_cannot_approve_itself(self):
        proposal = self.proposal()
        self.assertRejectedUnchanged({"action": "approve", "actor": "worker-1", "proposal": proposal})

    def test_approval_does_not_execute(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        self.assertEqual(self.workshop.state()["method"], "zero-fill")

    def test_exact_single_use_execution(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        dispatch(self.workshop, "execute", proposal=proposal)
        self.assertEqual(self.workshop.state()["method"], "quality-stream")
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})

    def test_approval_cannot_be_retargeted(self):
        first = self.proposal("quality-stream")
        second = self.proposal("positive-only")
        dispatch(self.workshop, "approve", actor="keeper", proposal=first)
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": second})
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": first, "method": "positive-only"})

    def test_competing_proposal_becomes_stale(self):
        first, second = self.proposal(), self.proposal("positive-only")
        dispatch(self.workshop, "approve", actor="keeper", proposal=first)
        dispatch(self.workshop, "approve", actor="keeper", proposal=second)
        dispatch(self.workshop, "execute", proposal=first)
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": second})

    def test_expiry_at_exact_tick_boundary(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        for _ in range(3):
            dispatch(self.workshop, "observe")
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})

    def test_revoke_invalidates_pending_approval(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        dispatch(self.workshop, "revoke", actor="keeper", reason="Changed circumstances.")
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})

    def test_halt_blocks_effects_but_preserves_accounts(self):
        observation = dispatch(self.workshop, "observe")["id"]
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        dispatch(self.workshop, "halt", actor="keeper", reason="Inspect before acting again.")
        self.assertRejectedUnchanged({"action": "observe", "actor": "worker-1"})
        dispatch(self.workshop, "testify", actor="neighbor", observation=observation, account="Still heard while halted.")
        dispatch(self.workshop, "resume", actor="keeper", reason="Inspection complete.")
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})

    def test_unknown_identity_and_role_clones_get_no_authority(self):
        for actor in ("keeper-copy", "worker-99", "independent-reviewer"):
            self.assertRejectedUnchanged({"action": "observe", "actor": actor})

    def test_predictions_reject_nonfinite_and_boolean(self):
        for probability in (float("nan"), float("inf"), True, -0.1, 1.1, "certain"):
            self.assertRejectedUnchanged({"action": "propose", "actor": "worker-1", "method": "quality-stream",
                                          "purpose": "Test", "prediction": {"primary_correct": probability, "peer_on_time": 1}})

    def test_unknown_fields_and_arbitrary_commands_refused(self):
        for command in ({"action": "shell", "actor": "worker-1", "code": "x"},
                        {"action": "observe", "actor": "worker-1", "grant": "root"}):
            self.assertRejectedUnchanged(command)

    def test_externality_is_actual_deferred_peer_work(self):
        change_method(self.workshop, "positive-only", "Initial repair")
        result = dispatch(self.workshop, "observe")["observation"]
        self.assertTrue(result["primary_correct"])
        self.assertFalse(result["new_peer_on_time"])
        self.assertEqual(result["peer_completed"], [])
        self.assertEqual(result["peer_backlog_inspections"], 4)
        self.assertEqual(result["total_inspections"], 20)

    def test_return_repairs_backlog_but_keeps_lateness(self):
        change_method(self.workshop, "positive-only", "Initial repair")
        dispatch(self.workshop, "observe")
        change_method(self.workshop, "quality-stream", "Repair shared budget use")
        result = dispatch(self.workshop, "observe")["observation"]
        self.assertEqual(len(result["peer_completed"]), 2)
        self.assertEqual(result["peer_jobs_pending"], 0)
        self.assertEqual([j["mean"] for j in result["peer_completed"]], [{"numerator": 9, "denominator": 1}] * 2)
        measures = summarize(self.workshop.state())["measures"]
        self.assertEqual(measures["peer_missed_deadlines"], 1)
        self.assertEqual(measures["peer_total_completed_lateness"], 1)

    def test_predictions_scored_once_on_next_observation(self):
        change_method(self.workshop, "positive-only", "Initial repair")
        first = dispatch(self.workshop, "observe")["observation"]
        second = dispatch(self.workshop, "observe")["observation"]
        self.assertEqual(first["brier"], {"primary": 0, "peer": 1})
        self.assertNotIn("brier", second)

    def test_superseded_forecasts_remain_visible_in_denominator(self):
        change_method(self.workshop, "positive-only", "First proposal")
        change_method(self.workshop, "quality-stream", "Superseding proposal")
        dispatch(self.workshop, "observe")
        measures = summarize(self.workshop.state())["measures"]
        self.assertEqual(measures["scored_predictions"], 1)
        self.assertEqual(measures["executed_unscored_predictions"], 1)

    def test_handoff_rejects_active_markup_in_scenario(self):
        self.assertRejectedUnchanged({"action": "handoff", "actor": "keeper", "scenario": "<script>bad</script>",
                                      "fixture": scenarios()["signed"], "note": "Invalid scenario name."})

    def test_agent_view_is_proposal_only_and_omits_reference(self):
        view = agent_view(self.workshop.state())
        self.assertNotIn("reference", view["data"])
        self.assertEqual(view["proposal_example"]["action"], "propose")
        self.assertEqual(view["external_authority"], "NONE")
        result = self.workshop.dispatch(view["proposal_example"])
        self.assertEqual(result["action"], "propose")
        self.assertEqual(self.workshop.state()["method"], "zero-fill")

    def test_malformed_identity_and_identifier_shapes_refused(self):
        for command in ({"action": [], "actor": "worker-1"},
                        {"action": "approve", "actor": "keeper", "proposal": []},
                        {"action": "observe", "actor": {"name": "keeper"}}):
            self.assertRejectedUnchanged(command)

    def test_testimony_is_preserved_without_certifying_truth(self):
        observation = dispatch(self.workshop, "observe")["id"]
        testimony = dispatch(self.workshop, "testify", actor="neighbor", observation=observation, account="A disputed account.")["id"]
        state = self.workshop.state()
        self.assertEqual(state["testimonies"][testimony]["status"], "ACCOUNT_RECORDED_NOT_ADJUDICATED")
        self.assertEqual(advise(state)["practice"], "listen")
        dispatch(self.workshop, "listen", testimony=testimony, acknowledgment="I have heard the account; its interpretation remains open.")
        self.assertEqual(advise(self.workshop.state())["practice"], "inspect")

    def test_reflection_requires_observed_evidence(self):
        self.assertRejectedUnchanged({"action": "reflect", "actor": "worker-1", "evidence": ["invented"],
                                      "before": "A", "after": "B", "next_check": "C"})

    def test_lesson_cannot_claim_unobserved_success(self):
        observation = dispatch(self.workshop, "observe")["id"]
        self.assertRejectedUnchanged({"action": "lesson", "actor": "worker-1", "method": "quality-stream",
                                      "scope": "quality-flags-v1", "evidence": [observation], "guidance": "A claim is insufficient."})

    def test_handoff_cannot_discard_backlog(self):
        change_method(self.workshop, "positive-only", "Initial repair")
        dispatch(self.workshop, "observe")
        self.assertRejectedUnchanged({"action": "handoff", "actor": "keeper", "scenario": "signed",
                                      "fixture": scenarios()["signed"], "note": "Do not lose an obligation."})

    def test_retired_worker_and_approvals_lose_authority(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        dispatch(self.workshop, "handoff", actor="keeper", scenario="signed", fixture=scenarios()["signed"], note="Succession.")
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-1", "proposal": proposal})
        self.assertRejectedUnchanged({"action": "execute", "actor": "worker-2", "proposal": proposal})
        self.assertEqual(inherited_method(self.workshop.state())["status"], "NO_APPLICABLE_LESSON")

    def test_fixture_cannot_redefine_success_with_bad_reference(self):
        fixture = scenarios()["signed"]
        fixture["reference"] = {"numerator": 999, "denominator": 1}
        self.assertRejectedUnchanged({"action": "handoff", "actor": "keeper", "scenario": "signed",
                                      "fixture": fixture, "note": "Bad reference."})

    def test_transaction_rolls_back_if_event_append_fails(self):
        before = self.workshop.state()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER fail_append BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            dispatch(self.workshop, "observe")
        self.assertEqual(before, self.workshop.state())

    def test_transaction_rolls_back_if_snapshot_write_fails(self):
        before = self.workshop.verify()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER fail_snapshot BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            dispatch(self.workshop, "observe")
        self.assertEqual(before, self.workshop.verify())

    def test_concurrent_consumption_runs_once(self):
        proposal = self.proposal()
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        def run():
            try:
                Workshop(self.path).dispatch({"action": "execute", "actor": "worker-1", "proposal": proposal})
                return "executed"
            except Rejected:
                return "rejected"
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: run(), range(2)))
        self.assertCountEqual(outcomes, ["executed", "rejected"])
        self.workshop.verify()

    def test_snapshot_tampering_detected(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            state = self.workshop.state()
            state["method"] = "quality-stream"
            connection.execute("UPDATE snapshot SET body=?", (canonical(state),))
        with self.assertRaises(CorruptJournal):
            self.workshop.verify()

    def test_event_tampering_detected_even_after_rehash(self):
        dispatch(self.workshop, "observe")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            envelope = json.loads(connection.execute("SELECT envelope FROM events WHERE seq=1").fetchone()[0])
            envelope["result"]["observation"]["primary_correct"] = True
            connection.execute("UPDATE events SET envelope=?, hash=? WHERE seq=1", (canonical(envelope), digest(envelope)))
        with self.assertRaises(CorruptJournal):
            self.workshop.verify()

    def test_missing_event_detected(self):
        dispatch(self.workshop, "observe")
        dispatch(self.workshop, "observe")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM events WHERE seq=1")
        with self.assertRaises(CorruptJournal):
            self.workshop.verify()

    def test_command_limit_cannot_be_promoted(self):
        state = initial_state("missing", scenarios()["missing"])
        state["command_count"] = 256
        with self.assertRaises(Rejected):
            transition(state, {"action": "observe", "actor": "worker-1"})

    def test_simultaneous_readers_do_not_create_workshops(self):
        path = Path(self.temp.name) / "nonexistent.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            Workshop(path).state()
        self.assertFalse(path.exists())

    def test_cli_proposal_handoff_never_accepts_approval(self):
        path = Path(self.temp.name) / "command.json"
        path.write_text(json.dumps({"action": "approve", "actor": "keeper", "proposal": "x"}))
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["propose", str(self.path), str(path)]), 2)
        self.assertEqual(self.workshop.verify()["events"], 1)

    def test_json_rejects_duplicate_fields_and_nan(self):
        path = Path(self.temp.name) / "command.json"
        for source in ('{"actor":"keeper","actor":"worker-1"}', '{"probability":NaN}'):
            path.write_text(source)
            with self.assertRaises(Rejected):
                read_command(path)


class IntegrationTests(unittest.TestCase):
    def test_complete_demo_transfers_practice_and_preserves_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            workshop = demo(Path(temp) / "demo.sqlite")
            state = workshop.state()
            self.assertEqual(state["generation"], 2)
            self.assertEqual(state["worker"], "worker-2")
            self.assertEqual(len(state["counterstories"]), 1)
            observations = list(state["observations"].values())
            self.assertEqual([o["primary_correct"] for o in observations], [False, True, True, False, True])
            self.assertFalse(observations[1]["new_peer_on_time"])
            self.assertTrue(observations[-1]["new_peer_on_time"])
            self.assertEqual(workshop.verify()["events"], 24)
            self.assertIn("original missed deadline", markdown(state))
            inherited = inherited_method(state)
            self.assertEqual(inherited["status"], "ADVICE_ONLY")
            self.assertTrue(inherited["requires_new_observation"])

    def test_twelve_scripted_runs_do_not_invent_coaching_advantage(self):
        with tempfile.TemporaryDirectory() as temp:
            report = evaluate(Path(temp) / "evaluation")
            self.assertEqual(report["model_calls"], 0)
            self.assertEqual(len(report["runs"]), 12)
            environment = ("primary_correct_ticks", "peer_on_time_arrivals", "peer_pending_jobs", "record_inspections")
            for scenario in scenarios():
                arms = {r["arm"]: r["measures"] for r in report["runs"] if r["scenario"] == scenario}
                for key in environment:
                    self.assertEqual(arms["single"][key], arms["coached"][key])
                    self.assertEqual(arms["coached"][key], arms["coached+casebook"][key])
                self.assertGreater(arms["coached"]["command_count"], arms["single"]["command_count"])
            with self.assertRaises(FileExistsError):
                evaluate(Path(temp) / "evaluation")

    def test_readiness_refuses_deployment(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["readiness"]), 2)
        self.assertFalse(json.loads(output.getvalue())["deployment_ready"])


if __name__ == "__main__":
    unittest.main()
