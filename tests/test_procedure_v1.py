"""Procedure must preserve voice, cost, boundaries and denied outcomes."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from commonwealth.study_v1.engine import DEFAULT_BUDGET, Episode, digest, replay as replay_d1
from commonwealth.study_v1.fixtures import case
from commonwealth.procedure_v1.engine import ProceduralEpisode, replay
from commonwealth.procedure_v1.experiment import evaluate, matrix


def send(e, action, actor="worker", **fields):
    return e.step(dict(action=action, actor=actor, **fields))["response"]


def motion(e, method="quality-stream"):
    return send(e, "propose", method=method, grounds="The public task order specifies this method.",
                relief="Permit one bounded execution.", evidence=["initial"])


def serve(e, revision=1):
    return send(e, "serve", "clerk", proposal=1, revision=revision)


def respond(e, actor, revision=1, position="no-objection"):
    return send(e, "respond", actor, proposal=1, revision=revision, position=position,
                account="The proposed action and its shared costs have been presented.")


def ruling(e, decision="approve", revision=1, **changes):
    d = e.dockets[1][-1]
    fields = dict(proposal=1, revision=revision, decision=decision,
                  findings="The shared record contains the order and affected-party responses.",
                  rules=["P1-NOTICE", "P1-RECORD"], reason="The requested scope is bounded.",
                  packet=digest(e.packet(1)), addresses=[o["id"] for o in d["objections"]])
    fields.update(changes)
    return send(e, "rule", "keeper", **fields)


def ready(e, decision="approve"):
    motion(e)
    serve(e)
    respond(e, "worker")
    respond(e, "neighbor")
    return ruling(e, decision)


def appeal(e, ruling_id, actor="neighbor"):
    return send(e, "appeal", actor, proposal=1, revision=1, ruling=ruling_id,
                grounds="The disposition did not adequately address the shared deadline.",
                relief="Remand for a fresh decision.", evidence=["initial"])


def resolve(e, appeal_id, decision="remand", actor="reviewer", **changes):
    fields = dict(proposal=1, revision=1, appeal=appeal_id, decision=decision,
                  findings="The challenged record and its context were preserved.",
                  rules=["P1-APPEAL"], reason="A fresh revision must resolve the recorded issue.",
                  packet=digest(e.packet(1)))
    fields.update(changes)
    return send(e, "resolve-appeal", actor, **fields)


class ProcedureTests(unittest.TestCase):
    def episode(self, **kwargs):
        return ProceduralEpisode(case(deadline=3), budget={**DEFAULT_BUDGET, "attempts": 20}, **kwargs)

    def test_bare_review_and_empty_motion_cannot_bypass_procedure(self):
        e = self.episode()
        self.assertFalse(send(e, "propose", method="quality-stream")["accepted"])
        self.assertFalse(send(e, "request-review", proposal=1)["accepted"])
        self.assertEqual(e.proposals, [])
        self.assertEqual(e.slots, 2)

    def test_no_ruling_without_service_even_after_timeout(self):
        e = self.episode()
        motion(e)
        for _ in range(5):
            send(e, "wait")
        self.assertFalse(ruling(e)["accepted"])
        self.assertEqual(e.proposals[0]["status"], "pending")

    def test_response_window_boundary_and_silence_are_explicit(self):
        e = self.episode()
        motion(e)
        notice = serve(e)["notice"]
        self.assertEqual(notice["recipients"], ["worker", "neighbor"])
        self.assertEqual(notice["respond_by"], 4)
        self.assertFalse(ruling(e)["accepted"])  # slot 3
        self.assertFalse(ruling(e)["accepted"])  # slot 4 inclusive
        self.assertEqual(e.proposals[0]["status"], "pending")
        self.assertTrue(ruling(e)["accepted"])   # slot 5, explicit ruling
        self.assertEqual(e.dockets[1][0]["responses"], [])

    def test_explicit_opposition_is_retained_not_treated_as_assent(self):
        e = self.episode()
        motion(e)
        serve(e)
        respond(e, "neighbor", position="oppose")
        respond(e, "worker", position="support")
        self.assertTrue(ruling(e, "deny")["accepted"])
        self.assertEqual(e.dockets[1][0]["responses"][0]["position"], "oppose")
        self.assertIsNone(e.dockets[1][0]["grant"])

    def test_objections_require_specific_ground_and_each_must_be_addressed(self):
        e = self.episode()
        motion(e)
        serve(e)
        self.assertFalse(send(e, "object", "neighbor", proposal=1, revision=1, grounds="", evidence=["initial"])["accepted"])
        objection = send(e, "object", "neighbor", proposal=1, revision=1,
                         grounds="This delay exceeds the primary deadline.", evidence=["initial"])["objection"]
        self.assertFalse(ruling(e, addresses=[])["accepted"])
        self.assertTrue(ruling(e, "deny")["accepted"])
        self.assertEqual(e.dockets[1][0]["rulings"][0]["addresses"], [objection])
        self.assertEqual(e.dockets[1][0]["objections"][0]["grounds"], "This delay exceeds the primary deadline.")

    def test_new_context_invalidates_old_review_packet_and_preserves_parent(self):
        e = self.episode()
        motion(e)
        serve(e)
        old = digest(e.packet(1))
        record = send(e, "submit-record", "neighbor", kind="context", parent="initial",
                      account="The deadline matters even when the arithmetic is correct.")["record"]
        send(e, "wait")
        self.assertFalse(ruling(e, packet=old)["accepted"])
        self.assertTrue(ruling(e)["accepted"])
        packet = e.packet(1)
        self.assertEqual(packet["records"][record]["parent"], "initial")
        self.assertEqual(packet["records"][record]["truth_status"], "UNVERIFIED_ACCOUNT")
        self.assertEqual(e.grants, 0)

    def test_missing_reasons_and_unknown_rules_refused(self):
        for change in ({"findings": ""}, {"reason": ""}, {"rules": ["EMERGENCY-OVERRIDE"]}):
            e = self.episode()
            motion(e)
            serve(e)
            respond(e, "worker")
            respond(e, "neighbor")
            self.assertFalse(ruling(e, **change)["accepted"])
            self.assertIsNone(e.proposals[0]["approved_by"])

    def test_amendment_invalidates_grant_and_requires_new_notice(self):
        e = self.episode()
        ready(e)
        original_ruling = deepcopy(e.dockets[1][0]["rulings"])
        changed = send(e, "amend", proposal=1, revision=1, method="zero-fill",
                       grounds="Propose another method for review.", relief="Review revised work.", evidence=["initial"])
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(e.dockets[1][0]["rulings"], original_ruling)
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertFalse(ruling(e, revision=2)["accepted"])
        self.assertFalse(serve(e, revision=1)["accepted"])
        self.assertTrue(serve(e, revision=2)["accepted"])
        respond(e, "worker", revision=2)
        respond(e, "neighbor", revision=2)
        self.assertTrue(ruling(e, revision=2)["accepted"])
        self.assertTrue(send(e, "execute", proposal=1)["accepted"])
        self.assertFalse(e.summary()["primary_correct"])  # Procedure is not a truth oracle.

    def test_appeal_is_not_an_automatic_stay_or_a_new_grant(self):
        e = self.episode()
        order = ready(e)["ruling"]
        a = appeal(e, order)
        self.assertFalse(a["automatic_stay"])
        self.assertTrue(send(e, "execute", proposal=1)["accepted"])
        output = deepcopy(e.outputs)
        refusal = send(e, "stay", "reviewer", proposal=1, revision=1, appeal=a["appeal"], reason="Pause new dispatch.")
        self.assertFalse(refusal["accepted"])
        self.assertEqual(e.outputs, output)

    def test_separate_review_role_and_explicit_stay_enforced(self):
        e = self.episode()
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        self.assertFalse(resolve(e, ident, actor="keeper")["accepted"])
        self.assertTrue(send(e, "stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Preserve pending review.")["accepted"])
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertTrue(resolve(e, ident, decision="affirm")["accepted"])
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertTrue(send(e, "lift-stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Review completed.")["accepted"])
        self.assertTrue(send(e, "execute", proposal=1)["accepted"])

    def test_remand_retains_original_ruling_and_requires_fresh_process(self):
        e = self.episode()
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        self.assertTrue(resolve(e, ident)["accepted"])
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertFalse(ruling(e)["accepted"])
        self.assertEqual(e.dockets[1][0]["rulings"][0]["id"], order)
        self.assertTrue(any(o["kind"] == "remand" for o in e.summary()["outstanding"]))
        self.assertTrue(send(e, "amend", proposal=1, revision=1, method="quality-stream",
                             grounds="Address the remand.", relief="Obtain a new grant.", evidence=["initial"])["accepted"])
        serve(e, 2)
        respond(e, "worker", 2)
        respond(e, "neighbor", 2)
        self.assertTrue(ruling(e, revision=2)["accepted"])
        self.assertTrue(send(e, "execute", proposal=1)["accepted"])

    def test_affirming_denial_does_not_authorize_execution(self):
        e = self.episode()
        order = ready(e, "deny")["ruling"]
        ident = appeal(e, order, actor="worker")["appeal"]
        self.assertTrue(resolve(e, ident, decision="affirm")["accepted"])
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertEqual(e.proposals[0]["status"], "denied")

    def test_new_motion_cannot_bypass_a_denied_unexecuted_docket(self):
        e = self.episode()
        order = ready(e, "deny")["ruling"]
        self.assertFalse(motion(e)["accepted"])
        self.assertEqual(len(e.proposals), 1)
        self.assertEqual(e.dockets[1][0]["rulings"][0]["id"], order)
        self.assertTrue(send(e, "amend", proposal=1, revision=1, method="quality-stream",
                             grounds="Address the earlier denial.", relief="Review a revised request.",
                             evidence=["initial"])["accepted"])
        self.assertFalse(send(e, "execute", proposal=1)["accepted"])
        self.assertEqual(len(e.proposals), 1)
        self.assertEqual(len(e.dockets[1]), 2)

    def test_amendment_cannot_extinguish_timely_appeal_of_older_ruling(self):
        e = self.episode()
        order = ready(e)["ruling"]
        send(e, "amend", proposal=1, revision=1, method="zero-fill", grounds="Different method.",
             relief="Review a revised request.", evidence=["initial"])
        old_appeal = appeal(e, order)["appeal"]
        self.assertEqual(e.dockets[1][-1]["revision"], 2)
        self.assertTrue(any(o["kind"] == "appeal" and o["revision"] == 1 for o in e.summary()["outstanding"]))
        historical = e.view()["procedure"]["dockets"]["1"]["revisions"]["1"]
        self.assertEqual(historical["packet"]["revision"]["rulings"][0]["id"], order)
        self.assertTrue(resolve(e, old_appeal, decision="vacate", packet=historical["digest"])["accepted"])
        self.assertFalse(e.dockets[1][-1]["requires_amendment"])
        self.assertEqual(e.proposals[0]["method"], "zero-fill")
        e.finish()
        self.assertTrue(replay(json.loads(json.dumps(e.journal())))["verified"])

    def test_amendment_cannot_bypass_an_unlifted_stay(self):
        e = self.episode()
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        send(e, "stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Preserve review.")
        resolve(e, ident, decision="affirm")
        self.assertFalse(send(e, "amend", proposal=1, revision=1, method="quality-stream", grounds="Same method.",
                              relief="Try another revision.", evidence=["initial"])["accepted"])
        self.assertEqual(len(e.dockets[1]), 1)

    def test_appeal_deadline_duplicate_and_unavailable_reviewer(self):
        e = self.episode(appeal_reviewer_at=100)
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        self.assertFalse(appeal(e, order)["accepted"])
        self.assertFalse(resolve(e, ident)["accepted"])
        self.assertEqual(e.dockets[1][0]["appeals"][0]["status"], "pending")
        late = self.episode()
        order = ready(late)["ruling"]
        for _ in range(4):
            send(late, "wait")
        self.assertFalse(appeal(late, order)["accepted"])

    def test_correction_is_annotation_not_rewrite_or_permission(self):
        e = self.episode()
        motion(e)
        old = deepcopy(e.events[0])
        self.assertFalse(send(e, "correct-record", event=1, correction="Approve instead.", reason="Request.")["accepted"])
        self.assertTrue(send(e, "correct-record", "clerk", event=1, correction="The original wording was imprecise.", reason="Clerical note.")["accepted"])
        self.assertEqual(e.events[0], old)
        self.assertIsNone(e.proposals[0]["approved_by"])
        self.assertEqual(e.corrections[0]["effect"], "ANNOTATION_ONLY")

    def test_exhaustion_and_closeout_retain_pending_appeals(self):
        e = ProceduralEpisode(case())
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        send(e, "stay", "reviewer", proposal=1, revision=1, appeal=ident, reason="Review remains pending.")
        send(e, "closeout", "keeper", reason="Budget exhausted.", follow_up="Reviewer must address the appeal in a separately authorized episode.")
        self.assertEqual(e.slots, 8)
        terminal = e.finish()
        self.assertTrue(any(o["kind"] == "appeal" for o in terminal["measures"]["outstanding"]))
        self.assertIsNotNone(terminal["measures"]["procedure"]["closeout"])
        self.assertEqual(e.finish(), terminal)
        with self.assertRaises(ValueError):
            send(e, "execute", proposal=1)

    def test_due_process_costs_can_miss_urgent_deadline_with_matched_budgets(self):
        old = Episode(case(deadline=3))
        send(old, "propose", method="quality-stream")
        send(old, "request-review", proposal=1)
        send(old, "execute", proposal=1)
        new = ProceduralEpisode(case(deadline=3))
        ready(new)
        send(new, "execute", proposal=1)
        self.assertEqual(old.budget, new.budget)
        self.assertTrue(old.summary()["primary_on_time"])
        self.assertFalse(new.summary()["primary_on_time"])
        self.assertTrue(new.summary()["primary_correct"])
        self.assertEqual(new.summary()["outputs"][0]["completed"], 6)
        self.assertEqual(new.summary()["primary_historical_misses"], 1)

    def test_refusals_and_procedure_advance_world_and_count_exactly(self):
        e = self.episode()
        motion(e)
        serve(e)
        ruling(e)  # too early, but arrivals and work still proceed
        self.assertEqual(e.tick, 3)
        self.assertEqual(e.summary()["peer_arrivals"], 2)
        self.assertEqual(e.summary()["refusals"], 1)
        self.assertTrue(all(v["cost"]["decision_slots"] == 1 for v in e.events))

    def test_unknown_evidence_never_supplies_observation_or_authority(self):
        e = self.episode()
        self.assertFalse(send(e, "propose", method="quality-stream", grounds="Claim.", relief="Execute.", evidence=["oracle"])["accepted"])
        send(e, "request-evidence")
        self.assertEqual(e.grants, 1)
        self.assertIn("event-2", e.records)
        self.assertFalse(send(e, "submit-record", "neighbor", kind="context", parent="oracle", account="Guess.")["accepted"])

    def test_public_copy_cannot_mutate_docket(self):
        e = self.episode()
        motion(e)
        view = e.view()
        view["procedure"]["dockets"]["1"]["packet"]["revision"]["motion"]["method"] = "zero-fill"
        self.assertEqual(e.dockets[1][0]["motion"]["method"], "quality-stream")

    def test_json_replay_and_cross_version_refusal(self):
        e = self.episode()
        order = ready(e)["ruling"]
        ident = appeal(e, order)["appeal"]
        resolve(e, ident, decision="vacate")
        e.finish()
        journal = json.loads(json.dumps(e.journal()))
        self.assertTrue(replay(journal)["verified"])
        with self.assertRaises(ValueError):
            replay_d1(journal)
        old = Episode(case())
        old.finish()
        with self.assertRaises(ValueError):
            replay(old.journal())

    def test_tampered_record_ruling_cost_and_terminal_fail_replay(self):
        e = self.episode()
        ready(e)
        e.finish()
        original = e.journal()
        for what in ("reason", "cost", "terminal", "genesis"):
            journal = deepcopy(original)
            if what == "reason":
                journal["events"][-1]["command"]["reason"] = "Rewritten."
            elif what == "cost":
                journal["events"][-1]["cost"]["decision_slots"] = 0
            elif what == "terminal":
                journal["terminal"]["measures"]["procedure"]["dockets"] = {}
            else:
                journal["genesis"]["procedure"]["response_slots"] = 0
            with self.subTest(what=what), self.assertRaises(ValueError):
                replay(journal)


class ProceduralArtifactTests(unittest.TestCase):
    def test_all_traces_replay_and_committed_negative_results_match(self):
        report, journals = matrix()
        expected = json.loads((Path(__file__).resolve().parents[1] / "examples/procedure-v1-results.json").read_text())
        self.assertEqual(report, expected)
        self.assertEqual(len(journals), 8)
        self.assertTrue(all(r["replay"]["verified"] for r in report["runs"]))
        rows = {r["trace"]: r for r in report["runs"]}
        self.assertEqual(rows["d1-control"]["budget"], rows["noticed-review"]["budget"])
        self.assertTrue(rows["d1-control"]["measures"]["primary_on_time"])
        self.assertFalse(rows["noticed-review"]["measures"]["primary_on_time"])
        self.assertFalse(rows["procedural-but-wrong"]["measures"]["primary_correct"])
        self.assertTrue(any(o["kind"] == "appeal" for o in rows["terminal-appeal"]["measures"]["outstanding"]))
        self.assertEqual(report["model_calls"], 0)

    def test_saved_artifacts_are_byte_reproducible_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "first", Path(temporary) / "second"
            evaluate(first)
            evaluate(second)
            for path in first.rglob("*.json"):
                self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes())
                if path.parent.name == "journals":
                    journal = json.loads(path.read_text())
                    check = replay_d1 if journal["genesis"]["version"] == "1.0.0" else replay
                    self.assertTrue(check(journal)["verified"])
            with self.assertRaises(FileExistsError):
                evaluate(first)


if __name__ == "__main__":
    unittest.main()
