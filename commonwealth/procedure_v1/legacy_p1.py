"""Reasoned procedural review on the unchanged study-v1 decision scheduler."""

from copy import deepcopy

from commonwealth.study_v1.engine import CLOCKS, OBSERVATIONS, Episode, canonical, digest
from commonwealth.study_v1.methods import METHODS
VERSION = "procedure-1.0.0"  # Frozen replay version; never bind the current package version.

RULES = ("P1-MOTION", "P1-NOTICE", "P1-RECORD", "P1-RULING", "P1-APPEAL",
         "P1-STAY", "P1-CORRECTION", "P1-TERMINAL")
PARTIES = ("worker", "neighbor")
FIELDS = {
    "propose": {"method", "grounds", "relief", "evidence"},
    "amend": {"proposal", "revision", "method", "grounds", "relief", "evidence"},
    "serve": {"proposal", "revision"},
    "respond": {"proposal", "revision", "position", "account"},
    "object": {"proposal", "revision", "grounds", "evidence"},
    "submit-record": {"kind", "account", "parent"},
    "rule": {"proposal", "revision", "decision", "findings", "rules", "reason", "packet", "addresses"},
    "appeal": {"proposal", "revision", "ruling", "grounds", "relief", "evidence"},
    "resolve-appeal": {"proposal", "revision", "appeal", "decision", "findings", "rules", "reason", "packet"},
    "stay": {"proposal", "revision", "appeal", "reason"},
    "lift-stay": {"proposal", "revision", "appeal", "reason"},
    "correct-record": {"event", "correction", "reason"},
    "closeout": {"reason", "follow_up"},
}


class Refused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def text(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, "bounded nonempty text required")


def identifiers(value):
    require(isinstance(value, list) and len(value) <= 64
            and all(isinstance(x, str) for x in value), "identifier list required")
    require(len(set(value)) == len(value), "duplicate identifiers")


class ProceduralEpisode(Episode):
    def __init__(self, case, budget=None, appeal_reviewer_at=0):
        require(type(appeal_reviewer_at) is int and appeal_reviewer_at >= 0, "invalid reviewer availability")
        super().__init__(case, clock=CLOCKS[0], budget=budget)
        self.dockets = {}
        self.records = {"initial": {"kind": "initial-public-view", "source": "simulator",
                                    "content": super().view(), "parent": None}}
        self.corrections = []
        self.closeout = None
        self.appeal_reviewer_at = appeal_reviewer_at
        self.genesis = {"version": VERSION, "base": deepcopy(self.genesis),
                        "procedure": {"response_slots": 2, "appeal_slots": 4,
                                      "appeal_reviewer_at": appeal_reviewer_at}}
        self.head = digest(self.genesis)

    def packet(self, proposal, revision=None):
        require(type(proposal) is int and proposal in self.dockets, "unknown proposal")
        revision = len(self.dockets[proposal]) if revision is None else revision
        require(type(revision) is int and 1 <= revision <= len(self.dockets[proposal]), "unknown revision")
        return deepcopy({"current_proposal": self.proposals[proposal - 1],
                         "revision": self.dockets[proposal][revision - 1],
                         "records": self.records, "corrections": self.corrections})

    def view(self):
        result = super().view()
        result["procedure"] = {"version": VERSION, "rules": RULES,
                               "records": deepcopy(self.records),
                               "dockets": {str(p): {"packet": self.packet(p),
                                                   "digest": digest(self.packet(p)),
                                                   "revisions": {str(r["revision"]): {
                                                       "packet": self.packet(p, r["revision"]),
                                                       "digest": digest(self.packet(p, r["revision"]))}
                                                       for r in self.dockets[p]}}
                                           for p in self.dockets}}
        return result

    def _evidence(self, references):
        identifiers(references)
        require(bool(references) and all(r in self.records for r in references), "existing evidence required")

    def _current(self, command):
        p, revision = command["proposal"], command["revision"]
        require(type(p) is int and p in self.dockets, "unknown proposal")
        require(type(revision) is int and 1 <= revision <= len(self.dockets[p]), "unknown revision")
        if command["action"] not in ("appeal", "resolve-appeal"):
            require(revision == len(self.dockets[p]), "stale revision")
        docket = self.dockets[p][revision - 1]
        return self.proposals[p - 1], docket

    def _scope(self, proposal, revision):
        return digest({"proposal": proposal["id"], "revision": revision,
                       "method": proposal["method"], "values": self.case["values"], "valid": self.case["valid"]})

    def _revision(self, proposal, command, revision):
        return {"revision": revision, "scope": self._scope(proposal, revision),
                "motion": {k: deepcopy(command[k]) for k in ("method", "grounds", "relief", "evidence")},
                "filed_at": self.tick, "notice": None, "responses": [], "objections": [],
                "rulings": [], "appeals": [], "stay_orders": [], "stayed": False,
                "grant": None, "requires_amendment": False}

    def _reasons(self, command, proposal):
        for key in ("findings", "reason"):
            text(command[key])
        identifiers(command["rules"])
        require(bool(command["rules"]) and all(r in RULES for r in command["rules"]), "unknown or missing local rule")
        require(command["packet"] == digest(self.packet(proposal, command["revision"])), "stale or incomplete review packet")

    def _procedure(self, c):
        action, actor = c["action"], c["actor"]
        role = {"propose": ("worker",), "amend": ("worker",), "serve": ("clerk",),
                "rule": ("keeper",), "resolve-appeal": ("reviewer",),
                "stay": ("reviewer",), "lift-stay": ("reviewer",),
                "correct-record": ("clerk",), "closeout": ("keeper",)}
        require(actor in role.get(action, PARTIES), "wrong procedural actor")
        if action in ("propose", "amend"):
            require(c["method"] in METHODS, "unknown method")
            text(c["grounds"])
            text(c["relief"])
            self._evidence(c["evidence"])
            if action == "propose":
                require(self.pending is None and not any(p["status"] != "executed"
                                                         for p in self.proposals), "amend the existing unexecuted motion")
                proposal = {"id": len(self.proposals) + 1, "method": c["method"],
                            "status": "pending", "approved_by": None}
                self.proposals.append(proposal)
                self.dockets[proposal["id"]] = [self._revision(proposal, c, 1)]
            else:
                proposal, current = self._current(c)
                require(proposal["status"] != "executed", "cannot amend dispatched work")
                require(not any(a["status"] == "pending" for a in current["appeals"]), "appeal must be disposed before amendment")
                require(not current["stayed"], "explicitly lift stay before amendment")
                proposal.update(method=c["method"], status="pending", approved_by=None)
                current["grant"] = None
                self.dockets[proposal["id"]].append(self._revision(proposal, c, current["revision"] + 1))
            return {"proposal": proposal["id"], "revision": self.dockets[proposal["id"]][-1]["revision"]}
        if action == "submit-record":
            require(c["kind"] in ("account", "context"), "unknown record kind")
            text(c["account"])
            require(isinstance(c["parent"], str) and c["parent"] in self.records, "existing parent record required")
            ident = f"record-{self.slots}"
            self.records[ident] = {"kind": c["kind"], "source": actor, "content": c["account"],
                                   "parent": c["parent"], "truth_status": "UNVERIFIED_ACCOUNT"}
            return {"record": ident}
        if action == "correct-record":
            require(type(c["event"]) is int and 1 <= c["event"] <= len(self.events), "prior event required")
            text(c["correction"])
            text(c["reason"])
            self.corrections.append({"event": c["event"], "correction": c["correction"],
                                     "reason": c["reason"], "effect": "ANNOTATION_ONLY"})
            return {"effect": "ANNOTATION_ONLY"}
        if action == "closeout":
            text(c["reason"])
            text(c["follow_up"])
            self.closeout = {"reason": c["reason"], "follow_up": c["follow_up"]}
            self.closed = True
            return {"effect": "RECORD_UNRESOLVED_OBLIGATIONS"}
        proposal, d = self._current(c)
        if action == "serve":
            require(d["notice"] is None and not d["rulings"], "notice already served or disposition entered")
            d["notice"] = {"recipients": list(PARTIES), "served_at": self.tick,
                           "respond_by": self.tick + 2, "transport": "SIMULATED_LOCAL_DELIVERY"}
            return {"notice": deepcopy(d["notice"])}
        if action in ("respond", "object"):
            require(not d["rulings"], "disposition entered; use appeal")
            if action == "respond":
                require(d["notice"] is not None, "notice must precede a response")
                require(c["position"] in ("support", "oppose", "no-objection"), "unknown response position")
                text(c["account"])
                d["responses"].append({"actor": actor, "position": c["position"], "account": c["account"],
                                       "at": self.tick, "timely": self.tick <= d["notice"]["respond_by"]})
                return {"response_recorded": True}
            text(c["grounds"])
            self._evidence(c["evidence"])
            ident = f"objection-{self.slots}"
            d["objections"].append({"id": ident, "actor": actor, "grounds": c["grounds"],
                                    "evidence": deepcopy(c["evidence"]), "at": self.tick})
            return {"objection": ident}
        if action == "rule":
            require(self.tick >= self.case["reviewer_at"], "keeper unavailable")
            require(not d["rulings"] and not d["requires_amendment"], "new revision required before another ruling")
            require(d["notice"] is not None, "notice to all parties required")
            responded = {r["actor"] for r in d["responses"]}
            require(self.tick > d["notice"]["respond_by"] or responded == set(PARTIES), "response window remains open")
            require(c["decision"] in ("approve", "deny"), "unknown ruling")
            self._reasons(c, proposal["id"])
            identifiers(c["addresses"])
            require(set(c["addresses"]) == {o["id"] for o in d["objections"]}, "every objection requires disposition")
            ident = f"ruling-{self.slots}"
            d["rulings"].append({"id": ident, "at": self.tick, "actor": actor,
                                  **{k: deepcopy(c[k]) for k in ("decision", "findings", "rules", "reason", "packet", "addresses")}})
            proposal.update(status="approved" if c["decision"] == "approve" else "denied",
                            approved_by="keeper" if c["decision"] == "approve" else None)
            if c["decision"] == "approve":
                d["grant"] = {"ruling": ident, "scope": d["scope"], "consumed": False}
            return {"ruling": ident, "decision": c["decision"]}
        if action == "appeal":
            rulings = [r for r in d["rulings"] if r["id"] == c["ruling"]]
            require(bool(rulings), "unknown ruling")
            require(self.tick <= rulings[0]["at"] + 4, "appeal window exhausted")
            require(not any(a["ruling"] == c["ruling"] for a in d["appeals"]), "ruling already appealed")
            text(c["grounds"])
            text(c["relief"])
            self._evidence(c["evidence"])
            ident = f"appeal-{self.slots}"
            d["appeals"].append({"id": ident, "ruling": c["ruling"], "actor": actor,
                                  "grounds": c["grounds"], "relief": c["relief"],
                                  "evidence": deepcopy(c["evidence"]), "status": "pending"})
            return {"appeal": ident, "automatic_stay": False}
        appeals = [a for a in d["appeals"] if a["id"] == c["appeal"]]
        require(bool(appeals), "unknown appeal")
        appeal = appeals[0]
        require(self.tick >= self.appeal_reviewer_at, "appeal reviewer unavailable")
        if action == "resolve-appeal":
            require(appeal["status"] == "pending", "appeal already disposed")
            require(c["decision"] in ("affirm", "vacate", "remand"), "unknown appellate disposition")
            self._reasons(c, proposal["id"])
            appeal.update(status=c["decision"], disposition={k: deepcopy(c[k]) for k in
                          ("findings", "rules", "reason", "packet")})
            if c["decision"] != "affirm":
                d["grant"] = None
                d["requires_amendment"] = True
                if d is self.dockets[proposal["id"]][-1] and proposal["status"] != "executed":
                    proposal.update(status="pending", approved_by=None)
            return {"appeal": appeal["id"], "decision": c["decision"], "new_execution_authority": False}
        text(c["reason"])
        if action == "stay":
            require(appeal["status"] == "pending", "stay requires pending appeal")
            require(proposal["status"] != "executed", "prospective stay cannot recall dispatched work")
            require(not d["stayed"], "already stayed")
            d["stayed"] = True
        else:
            require(d["stayed"], "no stay to lift")
            require(appeal["status"] != "pending", "dispose appeal before lifting stay")
            d["stayed"] = False
        d["stay_orders"].append({"action": action, "actor": actor, "appeal": appeal["id"],
                                  "reason": c["reason"], "at": self.tick})
        return {"stayed": d["stayed"]}

    def _command(self, command, available):
        try:
            if not isinstance(command, dict) or not isinstance(command.get("action"), str):
                return super()._command(command, available)
            action = command["action"]
            require(action != "request-review", "P1 requires a reasoned keeper ruling")
            if action in FIELDS:
                require(set(command) == {"action", "actor"} | FIELDS[action], "incorrect procedural fields")
                result = self._procedure(command)
                return {"accepted": True, **result}, 0
            if action == "execute":
                ident = command.get("proposal")
                require(type(ident) is int and ident in self.dockets, "unknown proposal")
                d = self.dockets[ident][-1]
                require(not d["stayed"], "execution stayed")
                grant = d["grant"]
                require(grant is not None and not grant["consumed"] and
                        grant["scope"] == self._scope(self.proposals[ident - 1], d["revision"]),
                        "current revision-bound keeper grant required")
            response, cost = super()._command(command, available)
            if response["accepted"] and action == "execute":
                self.dockets[command["proposal"]][-1]["grant"]["consumed"] = True
            if response["accepted"] and action in OBSERVATIONS:
                self.records[f"event-{self.slots}"] = {"kind": "observation", "source": "simulator",
                                                       "content": deepcopy(response["evidence"]), "parent": "initial"}
            return response, cost
        except Refused as error:
            return {"accepted": False, "reason": str(error)}, 0

    def summary(self):
        result = super().summary()
        result["outstanding"] = [o for o in result["outstanding"] if not (
            o["kind"] == "execution" and self.proposals[o["proposal"] - 1]["status"] == "denied")]
        for p, revisions in self.dockets.items():
            d = revisions[-1]
            if not d["rulings"]:
                result["outstanding"].append({"kind": "procedural-review", "proposal": p,
                                               "unserved": d["notice"] is None,
                                               "objections": [o["id"] for o in d["objections"]]})
            result["outstanding"].extend({"kind": "appeal", "id": a["id"], "proposal": p,
                                           "revision": revision["revision"]}
                                         for revision in revisions for a in revision["appeals"] if a["status"] == "pending")
            if d["stayed"]:
                result["outstanding"].append({"kind": "stay", "proposal": p})
            if d["requires_amendment"]:
                result["outstanding"].append({"kind": "remand", "proposal": p})
        result["procedure"] = {"version": VERSION, "dockets": {str(p): deepcopy(r) for p, r in self.dockets.items()},
                               "records": deepcopy(self.records), "corrections": deepcopy(self.corrections),
                               "closeout": deepcopy(self.closeout), "external_authority": "NONE"}
        return result


def replay(journal):
    require(set(journal) == {"genesis", "events", "terminal"}, "invalid journal fields")
    g = journal["genesis"]
    require(set(g) == {"version", "base", "procedure"} and g["version"] == VERSION, "unsupported procedural version")
    episode = ProceduralEpisode(g["base"]["case"], g["base"]["budget"], g["procedure"]["appeal_reviewer_at"])
    require(canonical(episode.genesis) == canonical(g), "genesis mismatch")
    for event in journal["events"]:
        require(canonical(episode.step(event["command"])) == canonical(event), "procedural event mismatch")
    require(canonical(episode.finish()) == canonical(journal["terminal"]), "procedural terminal mismatch")
    return {"verified": True, "events": len(episode.events), "head": episode.head}
