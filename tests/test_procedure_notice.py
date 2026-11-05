"""Adversarial P1.1 notice, cross-petition, and reply regressions.

These cases assert externally observable authority and record-preservation
properties, rather than treating a valid packet hash as proof of notice.
"""

from copy import deepcopy
import json
import unittest

from commonwealth.procedure_v1.engine import ProceduralEpisode, replay
from commonwealth.study_v1.engine import DEFAULT_BUDGET, digest
from commonwealth.study_v1.fixtures import case


class ProcedureNoticeTests(unittest.TestCase):
    def episode(self, attempts=64, **kwargs):
        return ProceduralEpisode(case(deadline=3),
                                 budget={**DEFAULT_BUDGET, "attempts": attempts}, **kwargs)

    def send(self, e, action, actor="worker", **fields):
        return e.step(dict(action=action, actor=actor, **fields))["response"]

    def accepted(self, response):
        self.assertTrue(response["accepted"], response)
        return response

    def refused(self, response):
        self.assertFalse(response["accepted"], response)
        return response

    def motion(self, e):
        return self.send(e, "propose", method="quality-stream", grounds="Use the public order.",
                         relief="One bounded execution.", evidence=["initial"])

    def serve(self, e, revision=1):
        return self.send(e, "serve", "clerk", proposal=1, revision=revision)

    def respond(self, e, actor, revision=1, position="no-objection"):
        return self.send(e, "respond", actor, proposal=1, revision=revision,
                         position=position, account="I have considered this noticed motion.")

    def rule(self, e, decision="approve", revision=1, **changes):
        d = e.dockets[1][revision - 1]
        fields = dict(proposal=1, revision=revision, decision=decision,
                      findings="The identified record was considered.", rules=["P1-NOTICE", "P1-RECORD"],
                      reason="This disposition addresses the requested scope.",
                      packet=digest(e.packet(1, revision)),
                      addresses=[o["id"] for o in d["objections"]])
        fields.update(changes)
        return self.send(e, "rule", "keeper", **fields)

    def ready(self, e, decision="approve"):
        self.accepted(self.motion(e))
        self.accepted(self.serve(e))
        self.accepted(self.respond(e, "worker"))
        self.accepted(self.respond(e, "neighbor"))
        return self.accepted(self.rule(e, decision))["ruling"]

    def appeal(self, e, ruling, actor="worker", revision=1, **changes):
        fields = dict(proposal=1, revision=revision, ruling=ruling,
                      grounds=f"{actor}'s independent ground.",
                      relief=f"{actor}'s independent relief.", evidence=["initial"])
        fields.update(changes)
        return self.send(e, "appeal", actor, **fields)

    def serve_appeal(self, e, appeal, revision=1, actor="clerk"):
        return self.send(e, "serve-appeal", actor, proposal=1, revision=revision, appeal=appeal)

    def reply(self, e, appeal, actor, revision=1, position="no-objection", **changes):
        fields = dict(proposal=1, revision=revision, appeal=appeal, position=position,
                      grounds=f"{actor}'s answer to the appeal.",
                      relief="Dispose only after considering this answer.", evidence=["initial"])
        fields.update(changes)
        return self.send(e, "respond-appeal", actor, **fields)

    def appellate_docket(self, e, appeal, revision=1):
        return next(a for a in e.dockets[1][revision - 1]["appeals"] if a["id"] == appeal)

    def resolve(self, e, appeal, decision="affirm", revision=1, actor="reviewer", **changes):
        a = self.appellate_docket(e, appeal, revision)
        fields = dict(proposal=1, revision=revision, appeal=appeal, decision=decision,
                      findings="The petitions and answers remain in the record.", rules=["P1-APPEAL"],
                      reason="The identified grounds and requested relief were considered.",
                      packet=digest(e.packet(1, revision)),
                      addresses=[r["id"] for r in a["petitions"] + a["responses"]])
        fields.update(changes)
        return self.send(e, "resolve-appeal", actor, **fields)

    def change_record(self, e, kind):
        if kind == "record":
            response = self.send(e, "submit-record", "neighbor", kind="context", parent="initial",
                                 account="New context changes what the parties must consider.")
        elif kind == "correction":
            response = self.send(e, "correct-record", "clerk", event=1,
                                 correction="This is a subsequent annotation, not a rewrite.",
                                 reason="Preserve the original while adding context.")
        elif kind == "objection":
            response = self.send(e, "object", "neighbor", proposal=1, revision=1,
                                 grounds="The shared deadline has not been addressed.", evidence=["initial"])
        else:
            response = self.send(e, "request-evidence")
        return self.accepted(response)

    def assert_replay(self, e):
        e.finish()
        self.assertTrue(replay(json.loads(json.dumps(e.journal())))["verified"])

    def test_new_material_requires_notice_not_merely_a_new_packet(self):
        for kind in ("record", "correction", "objection", "observation"):
            with self.subTest(kind=kind):
                e = self.episode()
                self.accepted(self.motion(e))
                original_notice = self.accepted(self.serve(e))["notice"]
                self.accepted(self.respond(e, "worker"))
                self.accepted(self.respond(e, "neighbor", position="oppose"))
                responses = deepcopy(e.dockets[1][0]["responses"])
                self.change_record(e, kind)
                self.refused(self.rule(e))  # Fresh packet is not fresh service.
                self.refused(self.respond(e, "neighbor"))
                self.assertEqual(e.dockets[1][0]["responses"], responses)
                new_notice = self.accepted(self.serve(e))["notice"]
                self.assertNotEqual(original_notice["id"], new_notice["id"])
                self.refused(self.rule(e))  # Old responses cannot close this window.
                self.accepted(self.respond(e, "worker"))
                self.accepted(self.respond(e, "neighbor", position="oppose"))
                self.accepted(self.rule(e, "deny"))
                self.assertEqual(e.dockets[1][0]["responses"][:2], responses)
                self.assertEqual(e.dockets[1][0]["notices"], [original_notice, new_notice])
                self.assertIsNone(e.dockets[1][0]["grant"])
                self.assert_replay(e)

    def test_original_responses_are_bound_and_once_per_notice(self):
        e = self.episode()
        self.accepted(self.motion(e))
        notice = self.accepted(self.serve(e))["notice"]
        self.accepted(self.respond(e, "worker", position="oppose"))
        responses = deepcopy(e.dockets[1][0]["responses"])
        self.refused(self.respond(e, "worker", position="support"))
        self.assertEqual(e.dockets[1][0]["responses"], responses)
        self.assertEqual(responses[0]["notice"], notice["id"])
        self.change_record(e, "record")
        self.accepted(self.serve(e))
        self.accepted(self.respond(e, "worker", position="support"))
        both = e.dockets[1][0]["responses"]
        self.assertEqual(len({r["notice"] for r in both}), 2)
        self.assertEqual([r["position"] for r in both], ["oppose", "support"])

    def test_refused_redundant_service_does_not_reset_window_or_history(self):
        e = self.episode()
        self.accepted(self.motion(e))
        self.accepted(self.serve(e))
        self.accepted(self.respond(e, "neighbor", position="oppose"))
        before = deepcopy(e.dockets[1][0])
        self.refused(self.serve(e))
        self.assertEqual(e.dockets[1][0], before)
        self.accepted(self.rule(e, "deny"))
        self.assertEqual(e.dockets[1][0]["responses"][0]["position"], "oppose")

    def test_original_response_window_inclusive_and_silence_is_not_assent(self):
        e = self.episode()
        self.accepted(self.motion(e))
        notice = self.accepted(self.serve(e))["notice"]
        self.assertEqual(notice["respond_by"], notice["served_at"] + 2)
        self.refused(self.rule(e, "deny"))
        self.refused(self.rule(e, "deny"))
        self.assertEqual(e.tick, notice["respond_by"])
        self.accepted(self.rule(e, "deny"))
        self.assertEqual(e.dockets[1][0]["responses"], [])
        self.assertIsNone(e.dockets[1][0]["grant"])

    def test_each_party_can_petition_same_ruling_without_first_filer_monopoly(self):
        for first, second in (("worker", "neighbor"), ("neighbor", "worker")):
            with self.subTest(first=first):
                e = self.episode()
                ruling = self.ready(e)
                a = self.accepted(self.appeal(e, ruling, first))
                b = self.accepted(self.appeal(e, ruling, second))
                self.assertEqual(a["appeal"], b["appeal"])
                self.assertNotEqual(a["petition"], b["petition"])
                self.assertEqual(len(e.dockets[1][0]["appeals"]), 1)
                petitions = deepcopy(self.appellate_docket(e, a["appeal"])["petitions"])
                self.assertEqual([p["actor"] for p in petitions], [first, second])
                self.assertEqual([p["grounds"] for p in petitions],
                                 [f"{first}'s independent ground.", f"{second}'s independent ground."])
                self.refused(self.appeal(e, ruling, first, grounds="Replace the other record."))
                self.refused(self.appeal(e, ruling, second))
                self.assertEqual(self.appellate_docket(e, a["appeal"])["petitions"], petitions)
                self.assertFalse(a["automatic_stay"])
                self.assertFalse(b["automatic_stay"])
                self.assert_replay(e)

    def test_unserved_pending_appeal_allows_other_party_after_initial_deadline(self):
        e = self.episode()
        ruling = self.ready(e)
        first = self.accepted(self.appeal(e, ruling))
        for _ in range(4):
            self.accepted(self.send(e, "wait"))
        joined = self.accepted(self.appeal(e, ruling, "neighbor"))
        self.assertGreater(e.tick, e.dockets[1][0]["rulings"][0]["at"] + 4)
        self.assertEqual(joined["appeal"], first["appeal"])
        self.assertEqual(len(self.appellate_docket(e, first["appeal"])["petitions"]), 2)

    def test_initial_appeal_deadline_does_not_expand_without_existing_docket(self):
        for waits, expected in ((3, True), (4, False)):
            with self.subTest(waits=waits):
                e = self.episode()
                ruling = self.ready(e)
                for _ in range(waits):
                    self.accepted(self.send(e, "wait"))
                result = self.appeal(e, ruling)
                self.assertEqual(result["accepted"], expected)
                self.assertEqual(len(e.dockets[1][0]["appeals"]), int(expected))

    def test_cross_petition_deadline_includes_notice_boundary_but_not_next_slot(self):
        for extra_waits, expected in ((1, True), (2, False)):
            with self.subTest(extra_waits=extra_waits):
                e = self.episode()
                ruling = self.ready(e)
                appeal = self.accepted(self.appeal(e, ruling))["appeal"]
                self.accepted(self.send(e, "wait"))
                self.accepted(self.send(e, "wait"))
                notice = self.accepted(self.serve_appeal(e, appeal))["notice"]
                for _ in range(extra_waits):
                    self.accepted(self.send(e, "wait"))
                result = self.appeal(e, ruling, "neighbor")
                self.assertEqual(e.tick, notice["respond_by"] + int(not expected))
                self.assertEqual(result["accepted"], expected)

    def test_cross_petition_invalidates_service_and_retains_old_reply(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        old_notice = self.accepted(self.serve_appeal(e, appeal))["notice"]
        old_reply = self.accepted(self.reply(e, appeal, "worker", position="oppose"))["reply"]
        self.accepted(self.appeal(e, ruling, "neighbor"))
        self.refused(self.resolve(e, appeal))
        self.refused(self.reply(e, appeal, "neighbor"))
        new_notice = self.accepted(self.serve_appeal(e, appeal))["notice"]
        self.refused(self.resolve(e, appeal))
        self.accepted(self.reply(e, appeal, "worker", position="oppose"))
        self.accepted(self.reply(e, appeal, "neighbor", position="support"))
        a = self.appellate_docket(e, appeal)
        self.assertEqual([r["notice"] for r in a["responses"]],
                         [old_notice["id"], new_notice["id"], new_notice["id"]])
        self.refused(self.resolve(e, appeal, addresses=[p["id"] for p in a["petitions"]]
                                 + [r["id"] for r in a["responses"] if r["id"] != old_reply]))
        self.accepted(self.resolve(e, appeal))
        self.assertIn(old_reply, a["disposition"]["addresses"])
        self.assertEqual(a["responses"][0]["position"], "oppose")
        self.assertEqual(a["notices"], [old_notice, new_notice])
        self.assert_replay(e)

    def test_appeal_needs_service_even_when_filing_window_has_elapsed(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.refused(self.reply(e, appeal, "neighbor"))
        for _ in range(4):
            self.accepted(self.send(e, "wait"))
        self.refused(self.resolve(e, appeal, decision="vacate"))
        a = self.appellate_docket(e, appeal)
        self.assertEqual(a["status"], "pending")
        self.assertEqual(a["responses"], [])
        self.assertEqual(e.proposals[0]["status"], "approved")

    def test_appeal_window_is_not_truncated_and_silence_needs_explicit_disposition(self):
        e = self.episode(attempts=10)
        ruling = self.ready(e, "deny")
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        notice = self.accepted(self.serve_appeal(e, appeal))["notice"]
        self.assertEqual(notice["respond_by"], 9)
        self.refused(self.resolve(e, appeal))
        self.refused(self.resolve(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal)["status"], "pending")
        self.accepted(self.resolve(e, appeal))
        self.assertEqual(e.slots, 10)
        self.assertEqual(self.appellate_docket(e, appeal)["responses"], [])
        self.assertIsNone(e.dockets[1][0]["grant"])
        self.assertEqual(e.finish()["reason"], "attempt_budget")
        self.assert_replay(e)

    def test_appeal_replies_are_once_per_party_per_notice_and_no_assent_is_inferred(self):
        e = self.episode()
        ruling = self.ready(e, "deny")
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose",
                                 grounds="I oppose both the requested relief and its premise."))
        replies = deepcopy(self.appellate_docket(e, appeal)["responses"])
        self.refused(self.reply(e, appeal, "neighbor", position="support"))
        self.assertEqual(self.appellate_docket(e, appeal)["responses"], replies)
        self.accepted(self.reply(e, appeal, "worker", position="support"))
        self.accepted(self.resolve(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal)["responses"][0]["position"], "oppose")
        self.refused(self.send(e, "execute", proposal=1))

    def test_redundant_appeal_service_cannot_reset_window_or_erase_opposition(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        before = deepcopy(self.appellate_docket(e, appeal))
        self.refused(self.serve_appeal(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal), before)
        self.assertEqual(e.tick, before["notice"]["respond_by"])
        self.accepted(self.resolve(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal)["responses"], before["responses"])

    def test_new_appeal_material_invalidates_notice_and_old_responses(self):
        for kind in ("record", "correction", "observation"):
            with self.subTest(kind=kind):
                e = self.episode()
                ruling = self.ready(e)
                appeal = self.accepted(self.appeal(e, ruling))["appeal"]
                self.accepted(self.serve_appeal(e, appeal))
                self.accepted(self.reply(e, appeal, "worker"))
                self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
                old = deepcopy(self.appellate_docket(e, appeal)["responses"])
                self.change_record(e, kind)
                self.refused(self.resolve(e, appeal))
                self.refused(self.reply(e, appeal, "worker"))
                self.accepted(self.serve_appeal(e, appeal))
                self.refused(self.resolve(e, appeal))
                self.accepted(self.reply(e, appeal, "worker"))
                self.accepted(self.reply(e, appeal, "neighbor"))
                self.accepted(self.resolve(e, appeal))
                self.assertEqual(self.appellate_docket(e, appeal)["responses"][:2], old)
                self.assert_replay(e)

    def test_stale_packet_after_reply_is_not_cured_by_fresh_service(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        packet = digest(e.packet(1))
        self.accepted(self.reply(e, appeal, "worker"))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        self.refused(self.resolve(e, appeal, packet=packet))
        self.assertEqual(self.appellate_docket(e, appeal)["status"], "pending")
        self.accepted(self.resolve(e, appeal))

    def test_every_petition_and_reply_id_must_be_addressed_exactly_once(self):
        for mutation in ("missing-petition", "missing-reply", "unknown", "duplicate", "empty"):
            with self.subTest(mutation=mutation):
                e = self.episode()
                ruling = self.ready(e)
                appeal = self.accepted(self.appeal(e, ruling))["appeal"]
                self.accepted(self.appeal(e, ruling, "neighbor"))
                self.accepted(self.serve_appeal(e, appeal))
                self.accepted(self.reply(e, appeal, "worker"))
                self.accepted(self.reply(e, appeal, "neighbor"))
                a = self.appellate_docket(e, appeal)
                addresses = [r["id"] for r in a["petitions"] + a["responses"]]
                if mutation == "missing-petition":
                    addresses.pop(0)
                elif mutation == "missing-reply":
                    addresses.pop()
                elif mutation == "unknown":
                    addresses.append("petition-not-in-this-case")
                elif mutation == "duplicate":
                    addresses.append(addresses[0])
                else:
                    addresses = []
                before = deepcopy(a)
                self.refused(self.resolve(e, appeal, addresses=addresses))
                self.assertEqual(a, before)
                self.accepted(self.resolve(e, appeal))

    def test_reviewer_separation_and_availability_do_not_block_party_voice(self):
        e = self.episode(appeal_reviewer_at=100)
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.refused(self.serve_appeal(e, appeal, actor="reviewer"))
        self.accepted(self.serve_appeal(e, appeal))
        self.refused(self.reply(e, appeal, "clerk"))
        self.accepted(self.reply(e, appeal, "worker"))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        self.refused(self.resolve(e, appeal, actor="keeper"))
        self.refused(self.resolve(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal)["status"], "pending")
        self.assertEqual(len(self.appellate_docket(e, appeal)["responses"]), 2)

    def test_disposed_combined_appeal_cannot_be_reopened_or_receive_new_replies(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "worker"))
        self.accepted(self.reply(e, appeal, "neighbor"))
        self.accepted(self.resolve(e, appeal))
        before = deepcopy(self.appellate_docket(e, appeal))
        self.refused(self.appeal(e, ruling, "neighbor"))
        self.refused(self.serve_appeal(e, appeal))
        self.refused(self.reply(e, appeal, "neighbor"))
        self.refused(self.resolve(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal), before)
        self.assertEqual(len(e.dockets[1][0]["appeals"]), 1)

    def test_original_service_requires_three_full_remaining_attempts(self):
        for attempts, accepted in ((4, False), (5, True)):
            with self.subTest(attempts=attempts):
                e = self.episode(attempts=attempts)
                self.accepted(self.motion(e))
                result = self.serve(e)
                self.assertEqual(result["accepted"], accepted)
                if accepted:
                    self.assertEqual(result["notice"]["respond_by"], 4)
                    self.accepted(self.respond(e, "worker"))
                    self.accepted(self.respond(e, "neighbor"))
                    self.accepted(self.rule(e, "deny"))
                else:
                    self.assertIsNone(e.dockets[1][0]["notice"])
                    self.assertEqual(e.dockets[1][0]["notices"], [])
                    self.assertEqual(e.summary()["refusals"], 1)
                self.assert_replay(e)

    def test_appeal_service_budget_refusal_does_not_silence_other_petitioner(self):
        e = self.episode(attempts=8)
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.refused(self.serve_appeal(e, appeal))
        self.accepted(self.appeal(e, ruling, "neighbor"))
        a = self.appellate_docket(e, appeal)
        self.assertIsNone(a["notice"])
        self.assertEqual(len(a["petitions"]), 2)
        terminal = e.finish()
        self.assertEqual(terminal["reason"], "attempt_budget")
        self.assertEqual(terminal["measures"]["refusals"], 1)
        self.assertTrue(any(o["kind"] == "appeal" and o["id"] == appeal
                            for o in terminal["measures"]["outstanding"]))
        outstanding = next(o for o in terminal["measures"]["outstanding"] if o["kind"] == "appeal")
        self.assertTrue(outstanding["notice_required"])
        self.assertIsNone(outstanding["respond_by"])
        self.assertEqual(outstanding["remaining_attempts"], 0)
        self.assertEqual(outstanding["petitions"], [p["id"] for p in a["petitions"]])
        with self.assertRaises(ValueError):
            self.serve_appeal(e, appeal)
        self.assert_replay(e)

    def test_budget_refused_reservice_preserves_original_notice_and_responses(self):
        e = self.episode(attempts=9)
        self.accepted(self.motion(e))
        self.accepted(self.serve(e))
        self.accepted(self.respond(e, "worker"))
        self.accepted(self.respond(e, "neighbor", position="oppose"))
        self.change_record(e, "record")
        self.accepted(self.send(e, "wait"))
        before = deepcopy(e.dockets[1][0])
        self.refused(self.serve(e))
        self.assertEqual(e.dockets[1][0], before)
        self.refused(self.rule(e))
        self.accepted(self.send(e, "wait"))
        terminal = e.finish()
        self.assertEqual(terminal["reason"], "attempt_budget")
        self.assertTrue(any(o["kind"] == "procedural-review"
                            for o in terminal["measures"]["outstanding"]))
        outstanding = next(o for o in terminal["measures"]["outstanding"]
                           if o["kind"] == "procedural-review")
        self.assertFalse(outstanding["unserved"])
        self.assertTrue(outstanding["notice_required"])
        self.assertIsNone(e.dockets[1][0]["grant"])
        self.assert_replay(e)

    def test_budget_refused_appeal_reservice_preserves_complete_history(self):
        e = self.episode(attempts=13)
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "worker"))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        self.change_record(e, "record")
        before = deepcopy(self.appellate_docket(e, appeal))
        self.refused(self.serve_appeal(e, appeal))
        self.assertEqual(self.appellate_docket(e, appeal), before)
        self.refused(self.resolve(e, appeal))
        self.accepted(self.send(e, "wait"))
        self.assertEqual(self.appellate_docket(e, appeal)["status"], "pending")
        self.assertTrue(any(o["kind"] == "appeal" for o in e.finish()["measures"]["outstanding"]))
        outstanding = next(o for o in e.finish()["measures"]["outstanding"] if o["kind"] == "appeal")
        self.assertTrue(outstanding["notice_required"])
        self.assertEqual(outstanding["remaining_attempts"], 0)
        self.assert_replay(e)

    def test_fresh_appeal_notice_at_exhaustion_never_resolves_itself(self):
        e = self.episode(attempts=10)
        ruling = self.ready(e, "deny")
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        notice = self.accepted(self.serve_appeal(e, appeal))["notice"]
        for _ in range(3):
            self.accepted(self.send(e, "wait"))
        terminal = e.finish()
        self.assertEqual(terminal["reason"], "attempt_budget")
        self.assertEqual(self.appellate_docket(e, appeal)["status"], "pending")
        self.assertIsNone(e.dockets[1][0]["grant"])
        outstanding = next(o for o in terminal["measures"]["outstanding"] if o["kind"] == "appeal")
        self.assertFalse(outstanding["notice_required"])
        self.assertEqual(outstanding["respond_by"], notice["respond_by"])
        self.assertEqual(outstanding["remaining_attempts"], 0)
        self.assert_replay(e)

    def test_all_dispositions_of_denial_leave_no_execution_grant(self):
        for disposition in ("affirm", "vacate", "remand"):
            with self.subTest(disposition=disposition):
                e = self.episode()
                ruling = self.ready(e, "deny")
                appeal = self.accepted(self.appeal(e, ruling))["appeal"]
                self.accepted(self.serve_appeal(e, appeal))
                self.accepted(self.reply(e, appeal, "worker", position="support"))
                self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
                result = self.accepted(self.resolve(e, appeal, disposition))
                self.assertFalse(result["new_execution_authority"])
                self.assertIsNone(e.dockets[1][0]["grant"])
                self.refused(self.send(e, "execute", proposal=1))
                self.assertEqual(e.outputs, [])

    def test_historical_appeal_notice_and_disposition_leave_new_grant_unchanged(self):
        for disposition in ("affirm", "vacate", "remand"):
            with self.subTest(disposition=disposition):
                e = self.episode()
                ruling = self.ready(e)
                self.accepted(self.send(e, "amend", proposal=1, revision=1, method="quality-stream",
                                        grounds="A revised bounded request.", relief="Review revision two.",
                                        evidence=["initial"]))
                appeal = self.accepted(self.appeal(e, ruling, revision=1))["appeal"]
                self.accepted(self.serve(e, revision=2))
                self.accepted(self.respond(e, "worker", revision=2))
                self.accepted(self.respond(e, "neighbor", revision=2))
                self.accepted(self.rule(e, revision=2))
                current = deepcopy(e.dockets[1][1])
                proposal = deepcopy(e.proposals[0])
                self.refused(self.serve_appeal(e, appeal, revision=2))
                self.refused(self.reply(e, appeal, "neighbor", revision=2))
                self.accepted(self.serve_appeal(e, appeal, revision=1))
                self.accepted(self.reply(e, appeal, "worker", revision=1))
                self.accepted(self.reply(e, appeal, "neighbor", revision=1, position="oppose"))
                self.accepted(self.resolve(e, appeal, disposition, revision=1))
                self.assertEqual(e.dockets[1][1], current)
                self.assertEqual(e.proposals[0], proposal)
                self.assertFalse(e.dockets[1][1]["requires_amendment"])
                self.accepted(self.send(e, "execute", proposal=1))
                self.assert_replay(e)

    def test_alias_and_unknown_identifiers_are_refusals_not_authority(self):
        e = self.episode(attempts=128)
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        before = deepcopy(e.dockets)
        for key in ("proposal", "revision"):
            for bad in (True, False, 1.0, "1", 0, -1, 99, None, [], {}):
                with self.subTest(key=key, bad=bad):
                    fields = dict(proposal=1, revision=1, appeal=appeal)
                    fields[key] = bad
                    self.refused(self.send(e, "serve-appeal", "clerk", **fields))
        for bad in (True, 1, "appeal-unknown", ruling, None, [], {}):
            with self.subTest(appeal=bad):
                self.refused(self.serve_appeal(e, bad))
                self.refused(self.reply(e, bad, "neighbor"))
        for bad in (True, 1, "ruling-unknown", appeal, None, [], {}):
            with self.subTest(ruling=bad):
                self.refused(self.appeal(e, bad, "neighbor"))
        self.assertEqual(e.dockets, before)
        self.assertEqual(e.summary()["refusals"], 41)
        self.assertEqual(e.tick, e.slots)
        self.assertTrue(all(event["cost"]["decision_slots"] == 1 for event in e.events))
        self.assert_replay(e)

    def test_refused_malformed_reply_does_not_consume_party_response_right(self):
        mutations = ({"grounds": ""}, {"relief": " "}, {"evidence": ["unknown"]},
                     {"evidence": ["initial", "initial"]}, {"position": "approve"},
                     {"grounds": " " * 4000 + "x"})
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                e = self.episode()
                ruling = self.ready(e)
                appeal = self.accepted(self.appeal(e, ruling))["appeal"]
                self.accepted(self.serve_appeal(e, appeal))
                self.refused(self.reply(e, appeal, "neighbor", **mutation))
                self.assertEqual(self.appellate_docket(e, appeal)["responses"], [])
                self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
                self.assertEqual(len(self.appellate_docket(e, appeal)["responses"]), 1)

    def test_text_limit_counts_raw_characters_not_stripped_characters(self):
        for length, expected in ((4000, True), (4001, False)):
            with self.subTest(length=length):
                e = self.episode()
                result = self.send(e, "propose", method="quality-stream", grounds=" " * (length - 1) + "x",
                                   relief="A bounded request.", evidence=["initial"])
                self.assertEqual(result["accepted"], expected)
                self.assertEqual(len(e.proposals), int(expected))

    def test_public_view_cannot_edit_notices_petitions_or_replies(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        before = deepcopy(e.dockets)
        exposed = e.view()["procedure"]["dockets"]["1"]["packet"]["revision"]["appeals"][0]
        exposed["notice"]["respond_by"] = 0
        exposed["petitions"][0]["grounds"] = "Rewritten"
        exposed["responses"][0]["position"] = "support"
        self.assertEqual(e.dockets, before)

    def test_replay_detects_notice_petition_reply_and_address_tampering(self):
        e = self.episode()
        ruling = self.ready(e)
        appeal = self.accepted(self.appeal(e, ruling))["appeal"]
        self.accepted(self.appeal(e, ruling, "neighbor"))
        self.accepted(self.serve_appeal(e, appeal))
        self.accepted(self.reply(e, appeal, "worker"))
        self.accepted(self.reply(e, appeal, "neighbor", position="oppose"))
        self.accepted(self.resolve(e, appeal))
        self.assert_replay(e)
        for target in ("notice", "petition", "reply", "addresses"):
            with self.subTest(target=target):
                journal = e.journal()
                a = journal["terminal"]["measures"]["procedure"]["dockets"]["1"][0]["appeals"][0]
                if target == "notice":
                    a["notice"]["respond_by"] -= 1
                elif target == "petition":
                    a["petitions"][1]["grounds"] = "Invented grounds."
                elif target == "reply":
                    a["responses"][1]["position"] = "support"
                else:
                    a["disposition"]["addresses"].pop()
                with self.assertRaises(ValueError):
                    replay(journal)


if __name__ == "__main__":
    unittest.main()
