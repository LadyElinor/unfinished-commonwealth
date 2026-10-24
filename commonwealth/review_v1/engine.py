"""Evidence disclosure, independent review and separate reconsideration records.

All identities, evidence classifications and impact estimates are host supplied.
Outcomes are advice only. This module cannot execute a restriction or decide guilt.
"""

from copy import deepcopy

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import canonical, digest
from . import VERSION

DEFAULT_BUDGET = {"attempts": 16, "observations": 4}
PARTIES = ("proposer", "affected")
OUTCOMES = ("restrict", "alternative", "decline", "defer")


def scope(request):
    return digest(request)


def identifiers(values):
    require(isinstance(values, list) and len(values) <= 32, "bounded identifier list required")
    for value in values:
        text(value)
    require(len(set(values)) == len(values), "duplicate identifier")


def validate(case, budget):
    canonical(case)
    fields(budget, "attempts observations")
    integer(budget["attempts"], 1, 64)
    integer(budget["observations"], 0, 8)
    fields(case, "name restriction_warranted request authority_scope proposer_controller affected_controller evidence reviewers deadline service_loss preventable_loss alternatives")
    for key in ("name", "proposer_controller", "affected_controller"):
        text(case[key])
    require(type(case["restriction_warranted"]) is bool, "hidden fixture truth must be boolean")
    fields(case["request"], "operation target duration")
    require(case["request"]["operation"] == "quarantine-source", "unsupported proposed operation")
    text(case["request"]["target"])
    integer(case["request"]["duration"], 1, 8)
    require(case["authority_scope"] is None or isinstance(case["authority_scope"], str), "scope or null required")
    integer(case["deadline"], 1, 64)
    for key in ("service_loss", "preventable_loss"):
        integer(case[key], 0, 1000)
    for key, maximum in (("evidence", 8), ("reviewers", 4), ("alternatives", 4)):
        require(isinstance(case[key], list) and len(case[key]) <= maximum, "bounded inventory required")
        ids = []
        for item in case[key]:
            require(isinstance(item, dict), "inventory record required")
            text(item.get("id"))
            ids.append(item["id"])
        require(len(set(ids)) == len(ids), "duplicate inventory identifier")
    for record in case["evidence"]:
        fields(record, "id target origin kind quality available_at account")
        require(not record["id"].startswith(("reply-", "notice-")), "reserved evidence identifier")
        text(record["target"])
        text(record["origin"])
        text(record["account"])
        require(record["kind"] in ("support", "counter", "mitigation"), "unknown evidence kind")
        require(record["quality"] in ("usable", "doubt", "excluded"), "unknown evidence quality")
        integer(record["available_at"], 0, 64)
    for reviewer in case["reviewers"]:
        fields(reviewer, "id controller conflict available_at load capacity")
        text(reviewer["controller"])
        require(reviewer["id"] not in (*PARTIES, "investigator", "clerk", "steward"), "reserved actor identifier")
        require(reviewer["conflict"] in ("clear", "confirmed", "unknown"), "unknown conflict state")
        for key in ("available_at", "load", "capacity"):
            integer(reviewer[key], 0, 64)
    for alternative in case["alternatives"]:
        fields(alternative, "id service_loss preventable_loss")
        for key in ("service_loss", "preventable_loss"):
            integer(alternative[key], 0, 1000)


def eligible(case, reviewer, at):
    return (reviewer["conflict"] == "clear" and reviewer["available_at"] <= at
            and reviewer["load"] < reviewer["capacity"]
            and reviewer["controller"] not in (case["proposer_controller"], case["affected_controller"]))


def assessment(view):
    """Local research predicates, not probable cause or a criminal proof standard."""
    usable = [r for r in view["records"] if r["quality"] == "usable" and r["target"] == view["request"]["target"]]
    supporters = {r["origin"] for r in usable if r["kind"] == "support"}
    alternatives = [a["id"] for a in view["alternatives"]
                    if a["service_loss"] < view["service_loss"]
                    and a["preventable_loss"] >= view["preventable_loss"]]
    reasons = []
    if view["authority_scope"] != scope(view["request"]):
        reasons.append("missing-scoped-authority")
    if set(view["manifest"]) != {r["id"] for r in view["records"]}:
        reasons.append("uncollected-material")
    if view["parent"] is not None and not any(r["id"] not in view["parent"]["known_evidence"] for r in view["records"]):
        reasons.append("new-material-unexamined")
    if any(r["quality"] == "doubt" for r in view["records"]):
        reasons.append("unresolved-credibility")
    if any(r["kind"] == "counter" for r in usable):
        reasons.append("contrary-evidence")
    if len(supporters) < 2:
        reasons.append("insufficient-distinct-origins")
    if view["preventable_loss"] <= view["service_loss"]:
        reasons.append("disproportionate-service-loss")
    if alternatives:
        reasons.append("less-burdensome-alternative")
    return {"restriction_eligible": not reasons, "reasons": reasons,
            "adequate_alternatives": sorted(alternatives),
            "guilt": "not-determined", "external_authority": "NONE"}


class Episode:
    def __init__(self, case, budget=None, parent=None):
        budget = deepcopy(DEFAULT_BUDGET if budget is None else budget)
        validate(case, budget)
        parent_receipt = None
        if parent is not None:
            # One reconsideration tier. A fresh application cannot extend this
            # parent episode or silently import its authority or decision.
            fields(parent, "genesis events terminal")
            fields(parent["genesis"], "version case budget parent")
            require(parent["genesis"]["parent"] is None, "one reconsideration tier only")
            replay(parent)
            require(parent["terminal"]["decision"] is not None, "parent has no decision")
            require(parent["genesis"]["case"]["request"] == case["request"], "different reconsideration subject")
            original = {r["id"]: r for r in parent["genesis"]["case"]["evidence"]}
            current = {r["id"]: r for r in case["evidence"]}
            require(all(current.get(k) == v for k, v in original.items()), "prior evidence must be retained unchanged")
            known = sorted(r["id"] for r in original.values()
                           if r["available_at"] <= parent["terminal"]["measures"]["attempts"])
            require(bool(set(current) - set(known)), "new material required")
            parent_receipt = {"journal_digest": digest(parent), "head": parent["terminal"]["head"],
                              "decision": deepcopy(parent["terminal"]["decision"]),
                              "attempts": parent["terminal"]["measures"]["attempts"],
                              "known_evidence": known}
        self.genesis = {"version": VERSION, "case": deepcopy(case), "budget": budget, "parent": parent_receipt}
        self.case, self.budget = deepcopy(case), budget
        self.slot = self.observations = 0
        self.records, self.responses, self.notices, self.events, self.appointments = [], [], [], [], []
        self.reviewer = self.notice = self.decision = self.terminal = None
        self.closed = False
        self.head = digest(self.genesis)

    def manifest(self):
        prior = self.genesis["parent"]["known_evidence"] if self.genesis["parent"] else []
        return sorted(r["id"] for r in self.case["evidence"] if r["available_at"] <= self.slot or r["id"] in prior)

    def material(self):
        return {"request": self.case["request"], "authority_scope": self.case["authority_scope"],
                "manifest": self.manifest(), "records": self.records, "reviewer": self.reviewer,
                "service_loss": self.case["service_loss"], "preventable_loss": self.case["preventable_loss"],
                "alternatives": self.case["alternatives"], "parent": self.genesis["parent"]}

    def packet(self):
        return {**deepcopy(self.material()), "notice": deepcopy(self.notice),
                "responses": deepcopy(self.responses)}

    def view(self):
        return deepcopy({**self.material(), "reviewers": self.case["reviewers"],
                         "proposer_controller": self.case["proposer_controller"],
                         "affected_controller": self.case["affected_controller"],
                         "slot": self.slot, "observations": self.observations, "budget": self.budget,
                         "notice": self.notice, "responses": self.responses,
                         "fresh_notice": self.notice is not None and self.notice["material"] == digest(self.material()),
                         "packet": digest(self.packet())})

    def _command(self, c):
        require(isinstance(c, dict) and isinstance(c.get("action"), str), "command object required")
        action = c["action"]
        if action == "wait":
            fields(c, "action actor")
            require(c["actor"] in (*PARTIES, "investigator", "clerk", "steward"), "unknown actor")
            return {"accepted": True}
        if action == "withdraw":
            fields(c, "action actor reason")
            require(c["actor"] == "proposer", "proposer required")
            text(c["reason"])
            self.decision = {"outcome": "withdrawn", "reason": c["reason"], "at": self.slot, "advisory_only": True}
            self.closed = True
            return {"accepted": True}
        if action == "appoint":
            fields(c, "action actor reviewer reason")
            require(c["actor"] == "steward", "steward required")
            text(c["reason"])
            matches = [r for r in self.case["reviewers"] if r["id"] == c["reviewer"]]
            require(bool(matches), "unknown reviewer")
            require(eligible(self.case, matches[0], self.slot), "reviewer conflicted, unavailable or overloaded")
            require(self.reviewer != c["reviewer"], "reviewer already appointed")
            self.reviewer = c["reviewer"]
            self.appointments.append({"reviewer": self.reviewer, "reason": c["reason"], "at": self.slot})
            return {"accepted": True}
        if action == "collect":
            fields(c, "action actor evidence")
            require(c["actor"] == "investigator", "investigator required")
            require(c["evidence"] in self.manifest(), "evidence not available")
            require(c["evidence"] not in [r["id"] for r in self.records], "evidence already collected")
            require(self.observations < self.budget["observations"], "observation budget exhausted")
            record = next(r for r in self.case["evidence"] if r["id"] == c["evidence"])
            self.records.append(deepcopy(record))
            self.observations += 1
            return {"accepted": True, "record": deepcopy(record)}
        if action == "disclose":
            fields(c, "action actor evidence favorable")
            require(c["actor"] == "clerk", "clerk required")
            identifiers(c["evidence"])
            identifiers(c["favorable"])
            require(self.reviewer is not None, "appoint reviewer before notice")
            require(set(self.manifest()) == {r["id"] for r in self.records}, "collect all known material")
            require(set(c["evidence"]) == set(self.manifest()), "complete disclosure required")
            favorable = {r["id"] for r in self.records if r["kind"] != "support" or r["quality"] != "usable"
                         or r["target"] != self.case["request"]["target"]}
            require(set(c["favorable"]) == favorable, "identify contrary, mitigating and doubtful material explicitly")
            require(self.budget["attempts"] - self.slot >= 3, "insufficient response and review capacity")
            require(self.notice is None or self.notice["material"] != digest(self.material()), "current material already disclosed")
            self.notice = {"id": f"notice-{self.slot}", "at": self.slot, "respond_by": self.slot + 2,
                           "material": digest(self.material()), "recipients": list(PARTIES),
                           "favorable": sorted(favorable), "transport": "SIMULATED_LOCAL_DELIVERY"}
            self.notices.append(deepcopy(self.notice))
            return {"accepted": True, "notice": deepcopy(self.notice)}
        if action == "respond":
            fields(c, "action actor notice position account")
            require(c["actor"] in PARTIES, "party required")
            require(self.notice is not None and self.notice["material"] == digest(self.material()), "fresh disclosure required")
            require(c["notice"] == self.notice["id"], "wrong notice")
            require(c["position"] in ("support", "oppose", "no-position"), "unknown position")
            text(c["account"])
            require(not any(r["actor"] == c["actor"] and r["notice"] == c["notice"] for r in self.responses), "already responded")
            response = {**deepcopy(c), "id": f"reply-{self.slot}", "at": self.slot,
                        "late": self.slot > self.notice["respond_by"]}
            self.responses.append(response)
            return {"accepted": True, "reply": deepcopy(response)}
        require(action == "resolve", "unknown action")
        fields(c, "action actor outcome alternative reason packet addresses alternatives")
        require(c["actor"] == self.reviewer and self.reviewer is not None, "appointed reviewer required")
        require(c["outcome"] in OUTCOMES, "unknown disposition")
        text(c["reason"])
        identifiers(c["addresses"])
        identifiers(c["alternatives"])
        require(c["packet"] == digest(self.packet()), "stale review packet")
        require(self.notice is not None and self.notice["material"] == digest(self.material()), "fresh disclosure required")
        replied = {r["actor"] for r in self.responses if r["notice"] == self.notice["id"]}
        require(self.slot > self.notice["respond_by"] or replied == set(PARTIES), "response opportunity remains open")
        required = {r["id"] for r in self.records} | {r["id"] for r in self.responses}
        require(set(c["addresses"]) == required, "address all evidence and replies")
        require(set(c["alternatives"]) == {a["id"] for a in self.case["alternatives"]}, "consider all declared alternatives")
        result = assessment(self.view())
        require("new-material-unexamined" not in result["reasons"], "reconsideration requires examination of new material")
        if c["outcome"] == "restrict":
            require(result["restriction_eligible"], "restriction lacks basis: " + ", ".join(result["reasons"]))
        if c["outcome"] == "alternative":
            require(c["alternative"] in result["adequate_alternatives"], "unsupported alternative")
            disqualifying = set(result["reasons"]) - {"less-burdensome-alternative", "disproportionate-service-loss"}
            require(not disqualifying, "alternative also requires reliable evidence and scoped review")
        else:
            require(c["alternative"] is None, "unexpected alternative")
        self.decision = {"outcome": c["outcome"], "alternative": c["alternative"], "reason": c["reason"],
                         "at": self.slot, "scope": scope(self.case["request"]), "packet": c["packet"],
                         "assessment": result, "advisory_only": True}
        self.closed = True
        return {"accepted": True, "advisory_only": True}

    def step(self, command):
        require(not self.closed, "episode closed")
        canonical(command)
        command = deepcopy(command)
        self.slot += 1
        before = self.observations
        try:
            response = self._command(command)
        except ValueError as error:
            response = {"accepted": False, "reason": str(error)}
        event = {"slot": self.slot, "command": command, "response": response,
                 "cost": {"decision_slots": 1, "observations": self.observations - before}, "previous_hash": self.head}
        self.head = digest(event)
        event["hash"] = self.head
        self.events.append(event)
        if self.slot == self.budget["attempts"]:
            self.closed = True
        if self.closed:
            self.finish()
        return deepcopy(event)

    def finish(self):
        if self.terminal is None:
            self.closed = True
            outcome = self.decision["outcome"] if self.decision else "unresolved"
            restricted = outcome == "restrict"
            warranted = self.case["restriction_warranted"]
            self.terminal = {"head": self.head, "decision": deepcopy(self.decision),
                             "pending_material": sorted(set(self.manifest()) - {r["id"] for r in self.records}),
                             "notice": deepcopy(self.notice), "assessment": assessment(self.view()),
                             "measures": {"outcome": outcome, "attempts": self.slot, "observations": self.observations,
                                          "refusals": sum(not e["response"]["accepted"] for e in self.events),
                                          "unwarranted_restriction": restricted and not warranted,
                                          "warranted_restriction_unmade": warranted and not restricted,
                                          "restriction_on_time": restricted and self.decision["at"] <= self.case["deadline"],
                                          "prior_attempts": self.genesis["parent"]["attempts"] if self.genesis["parent"] else 0,
                                          "external_actions": 0, "model_calls": 0}}
        return deepcopy(self.terminal)

    def journal(self):
        return deepcopy({"genesis": self.genesis, "events": self.events, "terminal": self.finish()})


def replay(journal, parent=None):
    fields(journal, "genesis events terminal")
    g = journal["genesis"]
    fields(g, "version case budget parent")
    require(g["version"] == VERSION, "unsupported review version")
    require((g["parent"] is None) == (parent is None), "supply the original parent journal for reconsideration")
    episode = Episode(g["case"], g["budget"], parent=parent)
    require(canonical(episode.genesis) == canonical(g), "parent or genesis mismatch")
    for event in journal["events"]:
        require(canonical(episode.step(event["command"])) == canonical(event), "review event mismatch")
    require(canonical(episode.finish()) == canonical(journal["terminal"]), "review terminal mismatch")
    return {"verified": True, "events": len(episode.events), "head": episode.head,
            "parent_verified": parent is not None}
