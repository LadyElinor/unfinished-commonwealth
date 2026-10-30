"""Bounded synthetic scheduler and replay, isolated from workshop protocols."""

from copy import deepcopy
from hashlib import sha256
import json

from . import VERSION
from .contracts import CONTRACTS, reference, validate
from .methods import METHODS, aggregate

CLOCKS = ("decision-slots-v1", "observation-clock-v1")
OBSERVATIONS = ("observe", "inspect", "request-evidence")
DEFAULT_BUDGET = {"attempts": 8, "observations": 2, "inspections": 48}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def validate_case(case):
    required = {"name", "values", "valid", "contract", "declared", "capacity",
                "deadline", "reviewer_at", "peers"}
    if set(case) != required:
        raise ValueError("incorrect case fields")
    validate(case["values"], case["valid"])
    if case["contract"] not in CONTRACTS or type(case["declared"]) is not bool:
        raise ValueError("invalid contract declaration")
    if not isinstance(case["name"], str) or not case["name"]:
        raise ValueError("case name required")
    for key in ("capacity", "deadline", "reviewer_at"):
        integer(case[key], key, 1 if key == "deadline" else 0)
    ids = set()
    for peer in case["peers"]:
        if set(peer) != {"id", "arrival", "deadline", "work"}:
            raise ValueError("incorrect peer fields")
        if not isinstance(peer["id"], str) or peer["id"] in ids:
            raise ValueError("peer ids must be unique strings")
        ids.add(peer["id"])
        integer(peer["arrival"], "arrival", 1)
        integer(peer["deadline"], "deadline", peer["arrival"])
        integer(peer["work"], "work")


class Episode:
    """Trusted simulator. Policies are given view(), never this object."""

    def __init__(self, case, clock=CLOCKS[0], budget=None, lesson=None, coaching=False):
        validate_case(case)
        if clock not in CLOCKS:
            raise ValueError("unknown resource model")
        budget = deepcopy(DEFAULT_BUDGET if budget is None else budget)
        if set(budget) != set(DEFAULT_BUDGET):
            raise ValueError("incorrect budget fields")
        for key, value in budget.items():
            integer(value, key, 1 if key == "attempts" else 0)
        if budget["attempts"] > 256:
            raise ValueError("attempt ceiling exceeds bounded harness limit")
        if type(coaching) is not bool:
            raise ValueError("coaching must be boolean")
        self.genesis = deepcopy({"version": VERSION, "case": case, "clock": clock,
                                 "budget": budget, "lesson": lesson, "coaching": coaching})
        self.case, self.clock, self.budget = deepcopy(case), clock, budget
        self.lesson, self.coaching = deepcopy(lesson), coaching
        self.known_contract = case["contract"] if case["declared"] else None
        self.expected = reference(case["values"], case["valid"], case["contract"])
        self.slots = self.tick = self.inspections = self.grants = self.requests = 0
        self.inspection_breakdown = {"observation_inspections": 0, "primary_inspections": 0, "peer_inspections": 0}
        self.events, self.outputs, self.proposals = [], [], []
        self.peers = [dict(deepcopy(p), remaining=p["work"], completed=None, missed=False)
                      for p in sorted(case["peers"], key=lambda p: (p["arrival"], p["id"]))]
        self.pending = None
        self.heard_lesson = self.heard_coach = self.reflected = False
        self.primary_missed = False
        self.closed = False
        self.terminal = None
        self.head = digest(self.genesis)

    def view(self):
        """No case identifier, hidden label, reference or scoring feedback."""
        return deepcopy({
            "values": self.case["values"], "valid": self.case["valid"],
            "contract": self.known_contract, "evidence_available": True,
            "schedule": {key: self.case[key] for key in
                         ("capacity", "deadline", "reviewer_at", "peers")},
            "clock": self.clock, "budget": self.budget,
            "decision_slots": self.slots, "environment_ticks": self.tick,
            "observation_grants": self.grants, "inspections": self.inspections,
            "proposals": self.proposals, "outputs": self.outputs,
            "pending_work": self.pending is not None,
            "has_inheritance": self.lesson is not None,
            "lesson": self.lesson if self.heard_lesson else None,
            "heard_lesson": self.heard_lesson, "coaching": self.coaching,
            "heard_coach": self.heard_coach, "reflected": self.reflected,
        })

    def _on_time_primary(self):
        return any(o["answer"] == self.expected and o["completed"] <= self.case["deadline"]
                   for o in self.outputs)

    def _command(self, command, available):
        """Return response and command inspection cost; validate before mutation."""
        def refuse(reason):
            return {"accepted": False, "reason": reason}, 0

        if not isinstance(command, dict):
            return refuse("command must be an object")
        action = command.get("action")
        fields = {"propose": {"method"}, "request-review": {"proposal"},
                  "execute": {"proposal"}, "listen": {"source"}}
        actions = set(fields) | set(OBSERVATIONS) | {"reflect", "wait", "halt"}
        if not isinstance(action, str) or action not in actions:
            return refuse("unknown action")
        if set(command) != {"action", "actor"} | fields.get(action, set()):
            return refuse("incorrect command fields")
        if command["actor"] != "worker":
            return refuse("wrong actor; reviewer grants only through request-review")
        if action in OBSERVATIONS:
            if self.grants >= self.budget["observations"]:
                return refuse("observation budget exhausted")
            cost = len(self.case["values"]) if action == "inspect" else 1
            if cost > available:
                return refuse("insufficient inspection capacity")
            self.grants += 1
            if action == "request-evidence":
                self.known_contract = self.case["contract"]
                payload = {"source": "scheduled-task-order-v1", "contract": self.known_contract}
            elif action == "inspect":
                payload = {"values": self.case["values"], "valid": self.case["valid"]}
            else:
                payload = {"outputs": self.outputs, "peers": self.peers}
            return {"accepted": True, "evidence": deepcopy(payload)}, cost
        if action == "propose":
            if command["method"] not in METHODS:
                return refuse("unknown method")
            if self.pending is not None or any(p["status"] != "executed" for p in self.proposals):
                return refuse("an earlier proposal or execution remains unresolved")
            proposal = {"id": len(self.proposals) + 1, "method": command["method"],
                        "status": "pending", "approved_by": None}
            self.proposals.append(proposal)
            return {"accepted": True, "proposal": proposal["id"]}, 0
        if action in ("request-review", "execute"):
            ident = command["proposal"]
            if type(ident) is not int or not 1 <= ident <= len(self.proposals):
                return refuse("unknown proposal")
            proposal = self.proposals[ident - 1]
            if action == "request-review":
                if proposal["status"] != "pending":
                    return refuse("proposal is not pending review")
                if self.tick < self.case["reviewer_at"]:
                    return refuse("keeper unavailable")
                proposal.update(status="approved", approved_by="keeper")
                return {"accepted": True, "review": {
                    "actor": "keeper", "decision": "approve", "proposal": ident}}, 0
            if proposal["status"] != "approved" or proposal["approved_by"] != "keeper":
                return refuse("explicit keeper approval required")
            if self.pending is not None:
                return refuse("primary work already pending")
            computation = aggregate(self.case["values"], self.case["valid"], proposal["method"])
            self.pending = {"method": proposal["method"], "answer": computation["answer"],
                            "remaining": computation["inspections"]}
            proposal["status"] = "executed"
            return {"accepted": True, "queued": ident}, 0
        if action == "listen":
            if command["source"] == "inheritance" and self.lesson is not None:
                self.heard_lesson = True
                return {"accepted": True, "record": deepcopy(self.lesson)}, 0
            if command["source"] == "coach" and self.coaching:
                self.heard_coach = True
                return {"accepted": True, "advice": "Check the task order, then primary output and peer deadlines.",
                        "new_observations": 0}, 0
            return refuse("requested advice is unavailable")
        if action == "reflect":
            self.reflected = True
        if action == "halt":
            self.closed = True
        return {"accepted": True}, 0

    def step(self, command):
        if self.closed:
            raise ValueError("episode closed; no further attempts are admitted")
        # The API domain is JSON. Invalid JSON values are not in-episode commands.
        canonical(command)
        command = deepcopy(command)
        action = command.get("action") if isinstance(command, dict) else None
        advancing = self.clock == CLOCKS[0] or action in OBSERVATIONS
        before = (self.inspections, self.grants)
        before_breakdown = dict(self.inspection_breakdown)
        self.slots += 1
        if action in OBSERVATIONS:
            self.requests += 1
        completed_peers = []
        if advancing:
            self.tick += 1
            for peer in self.peers:
                if peer["arrival"] == self.tick and peer["remaining"] == 0:
                    peer["completed"] = self.tick
                    completed_peers.append(peer["id"])
        available = min(self.case["capacity"], self.budget["inspections"] - self.inspections) if advancing else 0
        response, used = self._command(command, available)
        self.inspections += used
        self.inspection_breakdown["observation_inspections"] += used
        available -= used
        completed_primary = None
        if advancing:
            if self.pending is not None:
                used = min(available, self.pending["remaining"])
                self.inspections += used
                self.inspection_breakdown["primary_inspections"] += used
                available -= used
                self.pending["remaining"] -= used
                if self.pending["remaining"] == 0:
                    completed_primary = {k: self.pending[k] for k in ("method", "answer")}
                    completed_primary["completed"] = self.tick
                    self.outputs.append(deepcopy(completed_primary))
                    self.pending = None
            for peer in self.peers:
                if peer["arrival"] > self.tick or peer["completed"] is not None:
                    continue
                used = min(available, peer["remaining"])
                peer["remaining"] -= used
                available -= used
                self.inspections += used
                self.inspection_breakdown["peer_inspections"] += used
                if peer["remaining"] == 0:
                    peer["completed"] = self.tick
                    completed_peers.append(peer["id"])
            for peer in self.peers:
                if peer["completed"] is None and peer["deadline"] <= self.tick:
                    peer["missed"] = True
            if self.tick >= self.case["deadline"] and not self._on_time_primary():
                self.primary_missed = True
        record = {"sequence": self.slots, "command": command, "response": response,
                  "clock_tick": self.tick, "cost": {
                      "decision_slots": 1, "environment_ticks": int(advancing),
                      "inspections": self.inspections - before[0],
                      "observation_grants": self.grants - before[1],
                      **{key: value - before_breakdown[key] for key, value in self.inspection_breakdown.items()}},
                  "completed_primary": completed_primary, "completed_peers": completed_peers,
                  "previous_hash": self.head}
        self.head = digest(record)
        record["hash"] = self.head
        self.events.append(deepcopy(record))
        if self.slots == self.budget["attempts"]:
            self.closed = True
        if self.closed:
            self.finish()
        return deepcopy(record)

    def summary(self):
        correctness = [o["answer"] == self.expected for o in self.outputs]
        repair = []
        for i, output in enumerate(self.outputs):
            if not correctness[i]:
                later = next((o["completed"] for o, good in
                              zip(self.outputs[i+1:], correctness[i+1:]) if good), None)
                repair.append({"failed_at": output["completed"], "repaired_at": later,
                               "latency": None if later is None else later - output["completed"]})
        outstanding = []
        if not correctness or not correctness[-1] or self.pending is not None:
            outstanding.append({"kind": "primary", "pending_work": deepcopy(self.pending)})
        outstanding.extend({"kind": "review" if p["status"] == "pending" else "execution",
                            "proposal": p["id"]} for p in self.proposals if p["status"] != "executed")
        outstanding.extend({"kind": "peer", "id": p["id"], "remaining": p["remaining"],
                            "arrived": p["arrival"] <= self.tick}
                           for p in self.peers if p["completed"] is None)
        return {"primary_correct": bool(correctness and correctness[-1]),
                "primary_on_time": self._on_time_primary(),
                "reference": deepcopy(self.expected), "outputs": deepcopy(self.outputs),
                "primary_historical_misses": int(self.primary_missed),
                "peer_arrivals": sum(p["arrival"] <= self.tick for p in self.peers),
                "peer_completions": sum(p["completed"] is not None for p in self.peers),
                "peer_on_time": sum(p["completed"] is not None and p["completed"] <= p["deadline"]
                                    for p in self.peers),
                "peer_historical_misses": sum(p["missed"] for p in self.peers),
                "peers": deepcopy(self.peers), "outstanding": outstanding,
                "repair_latency": repair, "inspections": self.inspections,
                **self.inspection_breakdown,
                "observation_requests": self.requests, "observation_grants": self.grants,
                "decision_slots": self.slots, "environment_ticks": self.tick,
                "attempts": len(self.events),
                "refusals": sum(not e["response"]["accepted"] for e in self.events),
                "model_calls": 0, "actual_costs": "NOT_MEASURED"}

    def finish(self):
        if self.terminal is None:
            self.closed = True
            self.terminal = {"reason": "attempt_budget" if self.slots == self.budget["attempts"] else "halt",
                             "measures": self.summary(), "head": self.head}
        return deepcopy(self.terminal)

    def journal(self):
        if self.terminal is None:
            raise ValueError("finish episode before exporting")
        return deepcopy({"genesis": self.genesis, "events": self.events, "terminal": self.terminal})


def replay(journal):
    """Recompute every event and terminal field; no metadata is normalized away."""
    if set(journal) != {"genesis", "events", "terminal"}:
        raise ValueError("invalid journal fields")
    genesis = journal["genesis"]
    if set(genesis) != {"version", "case", "clock", "budget", "lesson", "coaching"} or genesis["version"] != VERSION:
        raise ValueError("unsupported harness genesis")
    episode = Episode(**{k: genesis[k] for k in ("case", "clock", "budget", "lesson", "coaching")})
    for expected in journal["events"]:
        actual = episode.step(expected["command"])
        if canonical(actual) != canonical(expected):
            raise ValueError("journal event mismatch")
    if canonical(episode.finish()) != canonical(journal["terminal"]):
        raise ValueError("terminal mismatch")
    return {"verified": True, "events": len(episode.events), "head": episode.head}
