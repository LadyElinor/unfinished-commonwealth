"""Conformance at the external-agent / C2 / B1.1 boundary."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/agent_profile_v1"
sys.path.insert(0, str(ROOT / "client_dist/src"))
sys.path.insert(0, str(EXAMPLES))

import adapter
from commonwealth.store import Workshop
from commonwealth.participant_v1.store import read_credential
from commonwealth.participant_v1.transport import Server
from commonwealth.participant_v1_1.store import Boundary
from commonwealth_client_v2.store import Outbox
from commonwealth_client_v2.transport import request
from commonwealth_client_v2.wire import canonical


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boundary = Boundary(Workshop.create(self.root / "workshop.db").path, clock=lambda: 1000)
        self.boundary.install()
        self.boundary.issue(self.root / "token", ttl=60)
        self.token = read_credential(self.root / "token")
        self.task = self.boundary.task(self.token)[1]
        self.packet = adapter.brief(self.task)
        self.decision = dict(profile=adapter.PROFILE, brief_id=self.packet["brief_id"], choice="propose",
                             **self.task["task"]["proposal_example"])

    def command(self, *args):
        import os
        env = {**os.environ, "PYTHONPATH": str(ROOT / "client_dist/src")}
        return subprocess.run([sys.executable, str(EXAMPLES / "adapter.py"), *map(str, args)],
                              cwd=self.root, env=env, text=True, capture_output=True)

    def server(self):
        server = Server(self.boundary)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        def stop():
            server.shutdown()
            thread.join()
            server.server_close()
        self.addCleanup(stop)
        return server

    def test_v11_wait_evidence_and_decline_are_local_and_version_bound(self):
        packet = adapter.brief(self.task, profile=adapter.PROFILE_1_1)
        t, r = self.root/"task.json", self.root/"decision.json"
        t.write_text(json.dumps(self.task))
        for choice, state in (("wait","WAITING_LOCALLY"), ("request-evidence","EVIDENCE_REQUESTED_LOCALLY"),
                              ("decline","DECLINED_LOCALLY")):
            reply = dict(profile=adapter.PROFILE_1_1, brief_id=packet["brief_id"], choice=choice, reason="Need the order.")
            r.write_text(json.dumps(reply))
            result = self.command("stage", t, r, self.root/"none.db", "http://127.0.0.1:1", self.root/"no-token",
                                  "--profile", adapter.PROFILE_1_1)
            self.assertEqual(json.loads(result.stdout)["state"], state)
            self.assertFalse((self.root/"none.db").exists())
            with self.assertRaises(ValueError):
                adapter.interpret(self.packet, reply)
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 0)

    def test_v11_allowlist_withholds_unlisted_nested_fields(self):
        t = copy.deepcopy(self.task)
        v = t["task"]
        v["data"]["reference"] = "PRIVATE"
        v["methods"]["keeper-only"] = "PRIVATE"
        v["recent_observations"] = [dict(tick=1,reference="PRIVATE",primary_correct=True)]
        v["testimony_data"] = {"t1":{"actor":"neighbor","account":"Public account","private":"PRIVATE"}}
        v["counterstory_data"] = [dict(account="Disputed",private="PRIVATE")]
        v["lessons"] = {"l1":dict(guidance="Inspect again",internal="PRIVATE")}
        packet = adapter.brief(t, profile=adapter.PROFILE_1_1)
        text = json.dumps(packet)
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("primary_correct", packet["work"]["recent_observations"][0])
        self.assertIn("Public account", text)
        self.assertIn("Disputed", text)

    def test_python_agent_lost_reply_recovers_and_stale_request_is_refused(self):
        server = self.server()
        packet = adapter.brief(self.task, profile=adapter.PROFILE_1_1)
        command = [sys.executable, "-I", str(EXAMPLES/"python_agent.py")]
        reply = json.loads(subprocess.check_output(command, input=json.dumps(packet), text=True))
        raw = canonical(adapter.interpret(packet, reply)).encode()
        path = self.root/"python.db"
        Outbox.stage(path, server.url, self.token, self.task, raw)
        self.assertEqual(request(server.url, self.token, "POST", "/proposals", raw)[0], 200)
        self.assertEqual(Outbox(path).operate(self.token, "resolve")["state"], "UNRESOLVED")
        self.assertEqual(Outbox(path).operate(self.token, "retry")["recorded"]["receipt"]["disposition"], "ACCEPTED")
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 1)
        stale = adapter.interpret(packet, {**reply, "purpose":"New decision on an old head"})
        self.assertEqual(request(server.url, self.token, "POST", "/proposals", canonical(stale).encode())[1]["disposition"], "STALE_VIEW")
        wrong = subprocess.run(command, input=json.dumps({**packet,"role":"legislative-seat"}),
                               text=True,capture_output=True)
        self.assertNotEqual(wrong.returncode, 0)

    def test_response_bound_to_context_and_offer(self):
        pin = {"head": "1"*64, "registry": "2"*64, "events": 38}
        review = {"schema": "unfinished-commonwealth.assembly-review.v1", "scope": "LOCAL_RESEARCH_ONLY",
                  "external_authority": "NONE", "authority_granted": False, "permits_execution": False,
                  "checkpoint": pin}
        packet = adapter.brief(self.task, review)
        self.assertNotEqual(packet["brief_id"], self.packet["brief_id"])
        with self.assertRaises(ValueError):
            adapter.interpret(packet, self.decision)
        with self.assertRaises(ValueError):
            adapter.brief(self.task, {**review, "authority_granted": True})
        self.assertEqual(packet["assembly_reference"]["kind"], "operator-supplied-checkpoint")
        for change in ({"actor": "keeper"}, {"choice": "vote"}, {"method": "execute"},
                       {"prediction": {"primary_correct": True, "peer_on_time": 1}},
                       {"profile": "v2"}, {"purpose": self.token}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                adapter.interpret(self.packet, {**self.decision, **change})

    def test_unavailable_work_can_be_declined_without_using_quota(self):
        for update in ({"halted": True}, {"successor_observation_required": True}):
            task = copy.deepcopy(self.task)
            task["task"].update(update)
            packet = adapter.brief(task)
            with self.assertRaises(ValueError):
                adapter.interpret(packet, {**self.decision, "brief_id": packet["brief_id"]})
            decline = dict(profile=adapter.PROFILE, brief_id=packet["brief_id"], choice="decline",
                           reason="A fresh observation or resume is needed.")
            self.assertIsNone(adapter.interpret(packet, decline))
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 0)

    def test_stale_head_is_recorded_as_refusal(self):
        server = self.server()
        old_request = adapter.interpret(self.packet, self.decision)
        body = {**old_request, "request_id": "other"}
        self.assertEqual(self.boundary.submit(self.token, canonical(body).encode())[0], 200)
        path = self.root / "stale.db"
        Outbox.stage(path, server.url, self.token, self.task, canonical(old_request).encode())
        result = Outbox(path).operate(self.token, "retry")
        self.assertEqual(result["recorded"]["receipt"]["disposition"], "STALE_VIEW")

    def test_decline_cli_does_not_stage_or_submit(self):
        task = self.root / "task.json"
        reply = self.root / "reply.json"
        outbox = self.root / "unused.db"
        task.write_text(json.dumps(self.task), encoding="utf-8")
        reply.write_text(json.dumps(dict(profile=adapter.PROFILE, brief_id=self.packet["brief_id"],
                                         choice="decline", reason="Insufficient evidence.")), encoding="utf-8")
        result = self.command("stage", task, reply, outbox, "http://127.0.0.1:1", self.root/"missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "DECLINED_LOCALLY")
        self.assertFalse(outbox.exists())

    def test_malformed_or_duplicate_json_refused_without_outbox(self):
        task = self.root / "task.json"
        reply = self.root / "reply.json"
        task.write_text(json.dumps(self.task), encoding="utf-8")
        reply.write_text('{"choice":"decline","choice":"propose"}', encoding="utf-8")
        result = self.command("stage", task, reply, self.root/"never.db", "http://127.0.0.1:1", self.root/"token")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root/"never.db").exists())

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable")
    def test_javascript_agent_real_host_loss_and_exact_retry(self):
        server = self.server()
        task_path = self.root / "task.json"
        response_path = self.root / "response.json"
        outbox = self.root / "intent.db"
        got = self.command("observe", server.url, self.root/"token")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertNotIn(self.token, got.stdout)
        task_path.write_text(got.stdout, encoding="utf-8")
        brief = self.command("brief", task_path)
        self.assertEqual(brief.returncode, 0, brief.stderr)
        answer = subprocess.run(["node", str(EXAMPLES/"javascript_agent.mjs")], input=brief.stdout,
                                cwd=self.root, text=True, capture_output=True, check=True).stdout
        response_path.write_text(answer, encoding="utf-8")
        stage = self.command("stage", task_path, response_path, outbox, server.url, self.root/"token")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        self.assertEqual(json.loads(stage.stdout)["state"], "UNRESOLVED")
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 0)
        # Deliver the same bytes through HTTP and discard its reply, modeling response loss.
        decision = adapter.interpret(self.packet, json.loads(answer))
        status, _ = request(server.url, self.token, "POST", "/proposals", canonical(decision).encode())
        self.assertEqual(status, 200)
        self.assertEqual(Outbox(outbox).operate(self.token, "resolve")["state"], "UNRESOLVED")
        saved = Outbox(outbox).operate(self.token, "retry")["recorded"]["receipt"]
        self.assertEqual(saved["disposition"], "ACCEPTED")
        self.assertIs(saved["permits_execution"], False)
        self.assertEqual(self.boundary.audit()["capabilities"][0]["used"], 1)
