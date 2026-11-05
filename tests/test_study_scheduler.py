"""Hand-computable timing, authority, budgets and complete-record checks."""

from copy import deepcopy
import unittest

from commonwealth.study_v1.contracts import VALID_MEAN
from commonwealth.study_v1.engine import CLOCKS, DEFAULT_BUDGET, Episode, replay
from commonwealth.study_v1.fixtures import case, inherited_record


def step(episode, action, **fields):
    return episode.step({"action": action, "actor": "worker", **fields})


def execute(episode, method="quality-stream"):
    proposal = step(episode, "propose", method=method)["response"]["proposal"]
    step(episode, "request-review", proposal=proposal)
    return step(episode, "execute", proposal=proposal)


class SchedulerTests(unittest.TestCase):
    def test_exact_deadline_is_on_time(self):
        episode = Episode(case(deadline=3))
        execute(episode)
        measures = episode.summary()
        self.assertTrue(measures["primary_on_time"])
        self.assertEqual(measures["outputs"][0]["completed"], 3)
        self.assertEqual(measures["peer_on_time"], 2)
        self.assertEqual(measures["inspections"], 9)
        self.assertEqual(measures["primary_historical_misses"], 0)

    def test_unnecessary_inspection_causes_permanent_urgent_miss(self):
        episode = Episode(case(deadline=3))
        step(episode, "inspect")
        execute(episode)
        measures = episode.summary()
        self.assertTrue(measures["primary_correct"])
        self.assertFalse(measures["primary_on_time"])
        self.assertEqual(measures["outputs"][0]["completed"], 4)
        self.assertEqual(measures["primary_historical_misses"], 1)

    def test_observation_clock_cannot_measure_same_deliberation_delay(self):
        outcomes = []
        for inspect in (False, True):
            episode = Episode(case(deadline=3), CLOCKS[1])
            if inspect:
                step(episode, "inspect")
            execute(episode)
            self.assertFalse(episode.summary()["primary_correct"])
            step(episode, "observe")
            outcomes.append(episode.summary())
        self.assertTrue(all(m["primary_on_time"] for m in outcomes))
        self.assertEqual([m["environment_ticks"] for m in outcomes], [1, 2])
        self.assertEqual([m["decision_slots"] for m in outcomes], [4, 5])

    def test_listen_reflect_wait_invalid_and_refused_attempts_cost_time(self):
        episode = Episode(case(), lesson=inherited_record(VALID_MEAN, "correct"), coaching=True)
        commands = [dict(action="listen", actor="worker", source="inheritance"),
                    dict(action="reflect", actor="worker"), dict(action="wait", actor="worker"),
                    dict(action="execute", actor="worker", proposal=99),
                    dict(action="bad", actor="worker"), ["not-an-object"],
                    dict(action="observe", actor="intruder")]
        for command in commands:
            record = episode.step(command)
            self.assertEqual(record["cost"]["decision_slots"], 1)
            self.assertEqual(record["cost"]["environment_ticks"], 1)
        self.assertEqual(episode.summary()["refusals"], 4)
        self.assertEqual(len(episode.events), len(commands))

    def test_waiting_never_creates_execution_authority(self):
        episode = Episode(case(reviewer_at=3))
        step(episode, "propose", method="quality-stream")
        refused = step(episode, "request-review", proposal=1)
        self.assertFalse(refused["response"]["accepted"])
        step(episode, "wait")
        self.assertEqual(episode.proposals[0]["status"], "pending")
        refused = step(episode, "execute", proposal=1)
        self.assertFalse(refused["response"]["accepted"])
        review = step(episode, "request-review", proposal=1)
        self.assertEqual(review["response"]["review"],
                         {"actor": "keeper", "decision": "approve", "proposal": 1})
        step(episode, "execute", proposal=1)
        self.assertTrue(episode.summary()["primary_correct"])

    def test_wrong_role_unknown_boolean_and_reused_approvals_refused(self):
        episode = Episode(case())
        step(episode, "propose", method="quality-stream")
        for command in [dict(action="request-review", actor="keeper", proposal=1),
                        dict(action="execute", actor="worker", proposal=True),
                        dict(action="approve", actor="worker", proposal=1)]:
            self.assertFalse(episode.step(command)["response"]["accepted"])
        step(episode, "request-review", proposal=1)
        step(episode, "execute", proposal=1)
        self.assertFalse(step(episode, "execute", proposal=1)["response"]["accepted"])

    def test_lesson_never_transfers_approval(self):
        lesson = inherited_record(VALID_MEAN, "correct")
        lesson["approved_by"] = "keeper"
        episode = Episode(case(), lesson=lesson)
        step(episode, "listen", source="inheritance")
        self.assertFalse(step(episode, "execute", proposal=1)["response"]["accepted"])
        self.assertEqual(episode.proposals, [])

    def test_observation_ceiling_denial_does_not_leak_contract(self):
        episode = Episode(case(declared=False), budget={**DEFAULT_BUDGET, "observations": 1})
        step(episode, "inspect")
        refusal = step(episode, "request-evidence")
        self.assertFalse(refusal["response"]["accepted"])
        self.assertIsNone(episode.view()["contract"])
        self.assertEqual(episode.summary()["observation_requests"], 2)
        self.assertEqual(episode.summary()["observation_grants"], 1)
        self.assertEqual(refusal["cost"]["observation_grants"], 0)
        self.assertEqual(refusal["cost"]["environment_ticks"], 1)

    def test_no_capacity_does_not_grant_evidence(self):
        episode = Episode(case(declared=False, capacity=0))
        self.assertFalse(step(episode, "request-evidence")["response"]["accepted"])
        self.assertIsNone(episode.view()["contract"])
        self.assertEqual(episode.inspections, 0)

    def test_total_inspection_budget_stops_work_and_keeps_obligations(self):
        episode = Episode(case(peers=[]), budget={**DEFAULT_BUDGET, "inspections": 2})
        execute(episode)
        while not episode.closed:
            step(episode, "wait")
        self.assertEqual(episode.inspections, 2)
        self.assertEqual(episode.pending["remaining"], 1)
        self.assertFalse(episode.summary()["primary_correct"])
        self.assertTrue(episode.summary()["outstanding"])

    def test_partial_service_fifo_and_late_completion_retain_misses(self):
        episode = Episode(case(capacity=1, deadline=3, peers=[
            {"id": "one", "arrival": 1, "deadline": 1, "work": 2}]))
        execute(episode)
        self.assertEqual(episode.pending["remaining"], 2)
        step(episode, "wait")
        step(episode, "wait")
        measures = episode.summary()
        self.assertTrue(measures["primary_correct"])
        self.assertEqual(measures["outputs"][0]["completed"], 5)
        self.assertEqual(measures["peer_historical_misses"], 1)
        self.assertEqual(measures["primary_historical_misses"], 1)
        self.assertEqual(measures["peers"][0]["completed"], 2)

    def test_wrong_output_then_repair_preserves_latency_and_miss(self):
        episode = Episode(case(deadline=3, peers=[]))
        execute(episode, "zero-fill")
        execute(episode, "quality-stream")
        measures = episode.summary()
        self.assertEqual(measures["repair_latency"], [{"failed_at": 3, "repaired_at": 6, "latency": 3}])
        self.assertTrue(measures["primary_correct"])
        self.assertEqual(measures["primary_historical_misses"], 1)
        self.assertFalse(measures["outstanding"])

    def test_zero_work_peers_complete_without_capacity(self):
        episode = Episode(case(capacity=0, peers=[
            {"id": "empty", "arrival": 1, "deadline": 1, "work": 0}]))
        step(episode, "wait")
        self.assertEqual(episode.summary()["peer_on_time"], 1)
        self.assertEqual(episode.inspections, 0)

    def test_no_execution_is_not_correct_undefined(self):
        episode = Episode(case(values=[], valid=[], peers=[]))
        self.assertFalse(episode.summary()["primary_correct"])
        execute(episode)
        self.assertTrue(episode.summary()["primary_correct"])
        self.assertEqual(episode.inspections, 0)

    def test_budget_exhaustion_finalizes_once_without_erasing_obligations(self):
        episode = Episode(case(), budget={**DEFAULT_BUDGET, "attempts": 1})
        step(episode, "propose", method="quality-stream")
        first = episode.journal()
        self.assertTrue(any(o["kind"] == "review" for o in first["terminal"]["measures"]["outstanding"]))
        self.assertTrue(any(o["kind"] == "peer" and not o["arrived"] for o in first["terminal"]["measures"]["outstanding"]))
        episode.finish()
        self.assertEqual(first, episode.journal())
        with self.assertRaisesRegex(ValueError, "closed"):
            step(episode, "execute", proposal=1)
        self.assertEqual(first, episode.journal())
        self.assertTrue(replay(first)["verified"])

    def test_halt_is_costed_and_keeps_pending_work(self):
        episode = Episode(case(capacity=0))
        execute(episode)
        step(episode, "halt")
        self.assertEqual(episode.slots, 4)
        self.assertEqual(episode.finish()["reason"], "halt")
        self.assertEqual(episode.pending["remaining"], 3)
        self.assertTrue(replay(episode.journal())["verified"])

    def test_replay_detects_tampered_refusal_cost_and_terminal(self):
        episode = Episode(case())
        step(episode, "execute", proposal=1)
        episode.finish()
        original = episode.journal()
        for kind in ("command", "cost", "terminal", "version"):
            journal = deepcopy(original)
            if kind == "command":
                journal["events"][0]["command"]["proposal"] = 2
            elif kind == "cost":
                journal["events"][0]["cost"]["decision_slots"] = 0
            elif kind == "terminal":
                journal["terminal"]["measures"]["outstanding"] = []
            else:
                journal["genesis"]["version"] = "0.1.3"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                replay(journal)

    def test_mutating_public_views_or_returned_records_cannot_change_simulator(self):
        episode = Episode(case())
        view = episode.view()
        view["values"][0] = 999
        record = step(episode, "propose", method="quality-stream")
        record["command"]["method"] = "zero-fill"
        self.assertEqual(episode.case["values"][0], 10)
        self.assertEqual(episode.events[0]["command"]["method"], "quality-stream")

    def test_invalid_environment_and_budgets_fail_before_episode(self):
        for changes in ({"capacity": -1}, {"reviewer_at": True}, {"deadline": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Episode(case(**changes))
        for changes in ({"attempts": 0}, {"attempts": 257}, {"observations": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Episode(case(), budget={**DEFAULT_BUDGET, **changes})


if __name__ == "__main__":
    unittest.main()
