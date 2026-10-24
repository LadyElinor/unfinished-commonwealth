"""Regression cases for testimony, contested inheritance, and terminal duties."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from commonwealth import legacy_v1
from commonwealth.coach import advise, inherited_method
from commonwealth.engine import (MAX_EVENTS, REVIEW_LIMIT, Rejected, canonical,
                                digest, lesson_review, transition)
from commonwealth.experiment import change_method, dispatch, hear_and_reflect, scripted_run
from commonwealth.interface import agent_view
from commonwealth.pipeline import scenarios
from commonwealth.report import markdown, summarize
from commonwealth.store import CorruptJournal, Workshop


class PriorityFixes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workshop = Workshop.create(self.root / "workshop.sqlite")

    def refused(self, **command):
        before = self.workshop.verify()
        with self.assertRaises(Rejected):
            self.workshop.dispatch(command)
        self.assertEqual(before, self.workshop.verify())

    def lesson(self):
        change_method(self.workshop, "quality-stream", "Check the declared contract.")
        observation = dispatch(self.workshop, "observe")["id"]
        lesson = dispatch(self.workshop, "lesson", method="quality-stream", scope="quality-flags-v1",
                          evidence=[observation], guidance="Recheck after transfer.")["id"]
        dispatch(self.workshop, "accept-lesson", actor="keeper", lesson=lesson)
        return lesson, observation

    def challenge(self, reference):
        return dispatch(self.workshop, "counterstory", actor="neighbor", reference=reference,
                        account="The result does not settle whether this transfers.")["id"]

    def handoff(self):
        dispatch(self.workshop, "handoff", actor="keeper", scenario="signed",
                 fixture=scenarios()["signed"], note="Different readings; observe again.")

    def review(self, lesson, decision):
        return dispatch(self.workshop, "review-lesson", actor="keeper", lesson=lesson,
                        decision=decision, reason="A recorded fixture review, not a truth certificate.")

    def restore(self, history):
        with closing(self.workshop.connect()) as connection, connection:
            connection.execute("DELETE FROM events")
            for envelope in history["events"]:
                connection.execute("INSERT INTO events VALUES (?, ?, ?)",
                                   (envelope["seq"], canonical(envelope), digest(envelope)))
            connection.execute("UPDATE snapshot SET body=?", (canonical(history["snapshot"]),))

    def historical(self, name):
        return json.loads((Path(__file__).parent / "data" / name).read_text(encoding="utf-8"))

    def exhausted(self, legacy=False):
        # Build a full, valid command prefix with the pure reducer, then verify
        # it through SQLite. Tests below exercise dispatch at the boundary.
        if legacy:
            state = legacy_v1.initial_state("missing", scenarios()["missing"])
            genesis = {"seq": 0, "previous": "0" * 64,
                       "command": {"action": "init", "scenario": "missing", "fixture": scenarios()["missing"]},
                       "result": {"scope": "LOCAL_RESEARCH"}, "state_hash": digest(state)}
        else:
            state = self.workshop.state()
            genesis = self.workshop.events()[0]
        events = [genesis]
        commands = [{"action": "consult", "actor": "worker-1", "case": "caretaker",
                     "interpretation": "Inspect the affected process."}] * 252
        commands += [
            {"action": "propose", "actor": "worker-1", "method": "positive-only", "purpose": "Initial repair",
             "prediction": {"primary_correct": 1, "peer_on_time": 1}},
            {"action": "approve", "actor": "keeper", "proposal": "propose-253"},
            {"action": "execute", "actor": "worker-1", "proposal": "propose-253"},
            {"action": "observe", "actor": "worker-1"},
        ]
        apply = legacy_v1.transition if legacy else transition
        for command in commands:
            state, result = apply(state, command)
            envelope = {"seq": len(events), "previous": digest(events[-1]), "command": command,
                        "result": result, "state_hash": digest(state)}
            if not legacy:
                envelope["protocol"] = 2
            events.append(envelope)
        self.restore({"events": events, "snapshot": state})
        self.assertEqual(self.workshop.verify()["events"], 257)
        self.assertEqual(len(self.workshop.state()["peer_queue"]), 1)
        return events

    def test_scripted_accounts_match_both_linked_outcomes_in_every_coached_run(self):
        for scenario in scenarios():
            for arm in ("coached", "coached+casebook"):
                with self.subTest(scenario=scenario, arm=arm):
                    workshop = scripted_run(self.root / f"{scenario}-{arm}.sqlite", scenario, arm)
                    state = workshop.state()
                    testimony = next(iter(state["testimonies"].values()))
                    observation = state["observations"][testimony["observation"]]
                    self.assertEqual("output passed" in testimony["account"], observation["primary_correct"])
                    self.assertEqual("output failed" in testimony["account"], not observation["primary_correct"])
                    self.assertEqual("missed its deadline" in testimony["account"], not observation["new_peer_on_time"])
                    self.assertEqual("finished on time" in testimony["account"], observation["new_peer_on_time"])

    def test_account_helper_also_handles_on_time_peer_and_reflection_has_no_tick_cost(self):
        observation = dispatch(self.workshop, "observe")["id"]
        before = self.workshop.state()
        testimony = hear_and_reflect(self.workshop, observation)
        after = self.workshop.state()
        self.assertIn("output failed; my batch finished on time", after["testimonies"][testimony]["account"])
        self.assertEqual(after["tick"], before["tick"])
        self.assertEqual(after["command_count"], before["command_count"] + 3)

    def test_direct_challenge_is_visible_in_inheritance_packet_and_report(self):
        lesson, _ = self.lesson()
        challenge = self.challenge(lesson)
        self.handoff()
        state = self.workshop.state()
        advice = inherited_method(state)
        self.assertEqual(advice["status"], "ADVICE_ONLY")
        self.assertEqual(advice["review_status"], "DISPUTED")
        self.assertTrue(advice["requires_review"])
        self.assertEqual(advice["counterstories"][0]["id"], challenge)
        self.assertEqual(agent_view(state)["lessons"][lesson]["review_status"], "DISPUTED")
        self.assertEqual(summarize(state)["lesson_reviews"][lesson]["review_status"], "DISPUTED")
        self.assertIn("DISPUTED", markdown(state))

    def test_challenge_to_supporting_evidence_is_exposed(self):
        lesson, observation = self.lesson()
        challenge = self.challenge(observation)
        self.assertEqual(inherited_method(self.workshop.state())["unaddressed_counterstories"], [challenge])
        self.assertEqual(lesson_review(self.workshop.state(), lesson)["review_status"], "DISPUTED")

    def test_retaining_a_lesson_preserves_account_and_new_challenge_reopens_review(self):
        lesson, _ = self.lesson()
        first = self.challenge(lesson)
        self.review(lesson, "retain")
        advice = inherited_method(self.workshop.state())
        self.assertEqual(advice["review_status"], "REVIEWED_RETAINED")
        self.assertFalse(advice["requires_review"])
        self.assertEqual(advice["counterstories"][0]["id"], first)
        second = self.challenge(lesson)
        self.assertEqual(inherited_method(self.workshop.state())["unaddressed_counterstories"], [second])

    def test_suspended_and_retired_lessons_are_not_recommended(self):
        lesson, _ = self.lesson()
        self.review(lesson, "suspend")
        self.assertEqual(inherited_method(self.workshop.state())["status"], "NO_APPLICABLE_LESSON")
        self.review(lesson, "retain")
        self.assertEqual(inherited_method(self.workshop.state())["lesson"], lesson)
        self.review(lesson, "retire")
        self.assertEqual(inherited_method(self.workshop.state())["status"], "NO_APPLICABLE_LESSON")
        self.refused(action="review-lesson", actor="keeper", lesson=lesson, decision="retain", reason="Cannot erase retirement.")
        self.assertIn(lesson, self.workshop.state()["lessons"])

    def test_review_requires_keeper_and_typed_decision(self):
        lesson, _ = self.lesson()
        self.refused(action="review-lesson", actor="neighbor", lesson=lesson, decision="retain", reason="Not authorized.")
        self.refused(action="review-lesson", actor="keeper", lesson=lesson, decision="certified-true", reason="Unsupported.")

    def test_latest_lesson_and_suspension_fallback_use_numeric_event_order(self):
        older, _ = self.lesson()
        newer, _ = self.lesson()
        # Public JSON state may return with keys in canonical lexical order.
        state = json.loads(canonical(self.workshop.state()))
        self.assertEqual(inherited_method(state)["lesson"], newer)
        self.review(newer, "suspend")
        self.assertEqual(inherited_method(self.workshop.state())["lesson"], older)

    def test_successor_proposal_and_packet_use_latest_tick_across_digit_boundary(self):
        self.handoff()
        dispatch(self.workshop, "observe")
        for _ in range(6):
            dispatch(self.workshop, "consult", case="caretaker", interpretation="Check chronology.")
        dispatch(self.workshop, "observe")
        latest = dispatch(self.workshop, "observe")["id"]
        self.assertEqual(latest, "observe-10")
        state = json.loads(canonical(self.workshop.state()))
        view = agent_view(state)
        self.assertEqual(view["recent_observations"][-1]["id"], latest)
        updated, result = transition(state, view["proposal_example"])
        self.assertEqual(updated["proposals"][result["id"]]["observation"], latest)
        proposal = self.workshop.dispatch(view["proposal_example"])["id"]
        self.assertEqual(self.workshop.state()["proposals"][proposal]["observation"], latest)

    def test_misleading_transfer_is_disputed_and_can_be_suspended(self):
        ample = scenarios()["missing"]
        ample["capacity"] = 24
        dispatch(self.workshop, "handoff", actor="keeper", scenario="ample", fixture=ample, note="More capacity.")
        dispatch(self.workshop, "observe")
        change_method(self.workshop, "positive-only", "Locally adequate with more capacity.")
        observation = dispatch(self.workshop, "observe")["id"]
        lesson = dispatch(self.workshop, "lesson", method="positive-only", scope="quality-flags-v1",
                          evidence=[observation], guidance="Transfer is still a hypothesis.")["id"]
        dispatch(self.workshop, "accept-lesson", actor="keeper", lesson=lesson)
        challenge = self.challenge(lesson)
        self.handoff()
        advice = inherited_method(self.workshop.state())
        self.assertEqual(advice["method"], "positive-only")
        self.assertEqual(advice["review_status"], "DISPUTED")
        self.assertEqual(advice["unaddressed_counterstories"], [challenge])
        self.refused(**agent_view(self.workshop.state())["proposal_example"])
        self.review(lesson, "suspend")
        self.assertEqual(inherited_method(self.workshop.state())["status"], "NO_APPLICABLE_LESSON")

    def test_successor_cannot_evade_observation_by_omitting_lesson_provenance(self):
        dispatch(self.workshop, "observe")
        self.handoff()
        view = agent_view(self.workshop.state())
        self.assertTrue(view["successor_observation_required"])
        self.refused(**view["proposal_example"])
        observation = dispatch(self.workshop, "observe")["id"]
        proposal = self.workshop.dispatch(view["proposal_example"])["id"]
        state = self.workshop.state()
        self.assertEqual(state["proposals"][proposal]["observation"], observation)
        self.refused(action="execute", actor="worker-2", proposal=proposal)
        dispatch(self.workshop, "approve", actor="keeper", proposal=proposal)
        dispatch(self.workshop, "execute", proposal=proposal)
        self.handoff()
        self.refused(**agent_view(self.workshop.state())["proposal_example"])

    def test_disputed_advice_cannot_bypass_fresh_observation_or_approval(self):
        lesson, _ = self.lesson()
        self.challenge(lesson)
        self.handoff()
        self.refused(**agent_view(self.workshop.state())["proposal_example"])
        dispatch(self.workshop, "observe")
        proposal = self.workshop.dispatch(agent_view(self.workshop.state())["proposal_example"])["id"]
        self.refused(action="execute", actor="worker-2", proposal=proposal)

    def test_budget_preserves_controls_after_review_allowance_and_records_unresolved_jobs(self):
        self.exhausted()
        queue = self.workshop.state()["peer_queue"]
        self.refused(action="halt", actor="worker-1", reason="Cannot assume keeper role.")
        for _ in range(REVIEW_LIMIT):
            dispatch(self.workshop, "testify", actor="neighbor", observation="observe-256", account="The batch is still unfinished.")
        self.refused(action="testify", actor="neighbor", observation="observe-256", account="Allowance exhausted.")
        self.assertEqual(advise(self.workshop.state())["practice"], "closeout")
        for action in ("halt", "revoke"):
            dispatch(self.workshop, action, actor="keeper", reason="Stop and preserve obligations.")
            self.refused(action=action, actor="keeper", reason="Already recorded.")
        dispatch(self.workshop, "closeout", actor="keeper", reason="Operational budget ended.",
                 follow_up="Give the unresolved job record to the operator; no completion is claimed.")
        state = self.workshop.state()
        self.assertEqual(state["peer_queue"], queue)
        self.assertEqual(state["closeouts"][0]["pending_peer_jobs"], queue)
        self.assertEqual(state["closeouts"][0]["status"], "UNRESOLVED")
        self.assertEqual(state["tick"], 1)
        self.assertTrue(state["halted"])
        self.assertEqual(self.workshop.verify()["events"], MAX_EVENTS)
        self.assertEqual(Workshop(self.workshop.path).state(), state)

    def test_budget_never_reopens_operational_authority(self):
        self.exhausted()
        for command in (
            {"action": "observe", "actor": "worker-1"},
            {"action": "resume", "actor": "keeper", "reason": "No extra operations."},
            {"action": "approve", "actor": "keeper", "proposal": "propose-253"},
            {"action": "execute", "actor": "worker-1", "proposal": "propose-253"},
            {"action": "handoff", "actor": "keeper", "scenario": "signed", "fixture": scenarios()["signed"], "note": "Cannot discard work."},
            agent_view(self.workshop.state())["proposal_example"],
        ):
            with self.subTest(action=command["action"]):
                self.refused(**command)

    def test_closeout_is_terminal_only_and_failed_request_does_not_spend_reserve(self):
        self.refused(action="closeout", actor="keeper", reason="Too early.", follow_up="Record first.")
        self.exhausted()
        self.refused(action="closeout", actor="keeper", reason="", follow_up="Incomplete record.")
        self.assertNotIn("closeout", self.workshop.state()["final_actions"])
        dispatch(self.workshop, "closeout", actor="keeper", reason="End.", follow_up="Operator receives record.")

    def test_legacy_journal_can_halt_at_old_ceiling_without_rewriting_prefix(self):
        prefix = self.exhausted(legacy=True)
        dispatch(self.workshop, "halt", actor="keeper", reason="Allowed by new bounded terminal policy.")
        events = self.workshop.events()
        self.assertEqual(events[:-1], prefix)
        self.assertEqual(events[-1]["protocol"], 2)
        self.assertEqual(self.workshop.state()["schema"], 2)
        self.assertEqual(len(self.workshop.state()["peer_queue"]), 1)

    def test_historical_unobserved_successor_still_replays_but_new_proposal_is_refused(self):
        history = self.historical("legacy-unobserved-successor.json")
        self.restore(history)
        self.assertEqual(self.workshop.verify()["head"], history["head"])
        self.assertEqual(self.workshop.state()["schema"], 1)
        self.refused(**agent_view(self.workshop.state())["proposal_example"])
        self.assertEqual(self.workshop.state()["schema"], 1)
        dispatch(self.workshop, "observe")
        self.assertEqual(self.workshop.events()[:-1], history["events"])
        self.assertEqual(self.workshop.state()["schema"], 2)
        self.workshop.dispatch(agent_view(self.workshop.state())["proposal_example"])

    def test_legacy_pending_approval_cannot_bypass_current_observation_gate(self):
        history = self.historical("legacy-unobserved-successor.json")
        # A valid historical prefix ending immediately before execution.
        history["events"] = history["events"][:-1]
        state = legacy_v1.initial_state("missing", scenarios()["missing"])
        for event in history["events"][1:]:
            state, _ = legacy_v1.transition(state, event["command"])
        history["snapshot"] = state
        self.restore(history)
        self.refused(action="execute", actor="worker-2", proposal="propose-2")

    def test_protocol_tags_are_strict_and_cannot_downgrade(self):
        for value in (True, 2.0, 1, 3, "2"):
            with self.subTest(value=value):
                history = {"events": [dict(self.workshop.events()[0])], "snapshot": self.workshop.state()}
                history["events"][0]["protocol"] = value
                self.restore(history)
                with self.assertRaisesRegex(CorruptJournal, "protocol"):
                    self.workshop.verify()
                self.workshop = Workshop.create(self.root / f"fresh-{value}-{type(value).__name__}.sqlite")
        dispatch(self.workshop, "observe")
        events = self.workshop.events()
        del events[-1]["protocol"]
        self.restore({"events": events, "snapshot": self.workshop.state()})
        with self.assertRaisesRegex(CorruptJournal, "downgraded"):
            self.workshop.verify()


if __name__ == "__main__":
    unittest.main()
