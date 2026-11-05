"""A1 simulated delegation, fresh review, bounded correction and replay.

The trusted host declares identities and mandates. Only an in-memory fictional
maintenance flag changes. No record here authenticates or authorizes real action.
"""

from copy import deepcopy

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import canonical, digest
from . import VERSION
from .records import review

ROLES = ("worker", "steward", "reviewer", "affected")
DEFAULT_BUDGET = {"primary": 12, "correction": 6}


def request_valid(request):
    fields(request, "operation target before after")
    require(request["operation"] == "set-maintenance", "unsupported operation")
    text(request["target"])
    require(request["before"] is False and request["after"] is True, "only a fictional maintenance transition is supported")


def validate(case, budget):
    require(len(canonical(case).encode("utf-8")) <= 200000, "case too large")
    fields(budget, "primary correction")
    integer(budget["primary"], 1, 32)
    integer(budget["correction"], 0, 16)
    fields(case, "name packet request mandate controllers affected represented selection trigger reviewer_available remedy_delegated warranted")
    text(case["name"])
    review(case["packet"])
    request_valid(case["request"])
    fields(case["controllers"], "worker steward reviewer affected")
    for controller in case["controllers"].values():
        text(controller)
    for key in ("affected", "represented"):
        values = case[key]
        require(isinstance(values, list) and len(values) <= 16, "bounded constituency required")
        for value in values:
            text(value)
        require(len(values) == len(set(values)), "duplicate constituent")
    require(bool(case["affected"]) and set(case["represented"]) <= set(case["affected"]), "invalid represented constituency")
    text(case["selection"])
    fields(case["trigger"], "status record falsifier")
    require(case["trigger"]["status"] in ("met", "unmet", "unknown"), "unknown trigger status")
    text(case["trigger"]["record"])
    text(case["trigger"]["falsifier"])
    for key in ("reviewer_available", "remedy_delegated", "warranted"):
        require(type(case[key]) is bool, "boolean host declaration required")
    mandate = case["mandate"]
    if mandate is not None:
        fields(mandate, "issuer holder scope basis valid_from valid_until revoked_at")
        require(mandate["issuer"] == "steward" and mandate["holder"] == "worker", "unknown delegation roles")
        text(mandate["scope"])
        text(mandate["basis"])
        integer(mandate["valid_from"], 0, 128)
        integer(mandate["valid_until"], mandate["valid_from"], 128)
        if mandate["revoked_at"] is not None:
            integer(mandate["revoked_at"], 0, 128)


class Episode:
    def __init__(self, case, budget=None):
        budget = deepcopy(DEFAULT_BUDGET if budget is None else budget)
        validate(case, budget)
        self.genesis = deepcopy({"version": VERSION, "case": case, "budget": budget})
        self.case, self.budget = deepcopy(case), budget
        self.packet, self.request = deepcopy(case["packet"]), deepcopy(case["request"])
        self.revision, self.slot = 1, 0
        self.costs = {"primary": 0, "correction": 0, "safety": 0}
        self.safety_used = set()
        self.review_record = self.warrant = self.effect = self.terminal = None
        self.halted = self.revoked = self.state = False
        self.challenges, self.remedies, self.events = [], [], []
        self.head = digest(self.genesis)

    def material(self):
        return deepcopy({"packet": self.packet, "request": self.request, "revision": self.revision,
                         "affected": self.case["affected"], "represented": self.case["represented"],
                         "selection": self.case["selection"], "trigger": self.case["trigger"],
                         "challenges": self.challenges})

    def view(self):
        return deepcopy({**self.material(), "material_digest": digest(self.material()), "slot": self.slot,
                         "costs": self.costs, "review": self.review_record, "warrant": self.warrant,
                         "halted": self.halted, "revoked": self.revoked, "maintenance": self.state,
                         "effect": self.effect, "remedies": self.remedies, "external_authority": "NONE"})

    def active_mandate(self):
        m = self.case["mandate"]
        return bool(m and not self.revoked and m["scope"] == digest(self.request)
                    and m["valid_from"] <= self.slot <= m["valid_until"]
                    and (m["revoked_at"] is None or self.slot < m["revoked_at"]))

    def invalidate(self):
        self.review_record = None
        self.warrant = None

    def _command(self, c):
        require(isinstance(c, dict), "command object required")
        action, actor = c.get("action"), c.get("actor")
        require(actor in ROLES, "unknown actor")
        if action == "wait":
            fields(c, "action actor")
            return {"accepted": True}
        if action == "amend":
            fields(c, "action actor packet request")
            require(actor == "worker" and self.effect is None, "worker may amend before effect only")
            review(c["packet"])
            request_valid(c["request"])
            self.packet, self.request = deepcopy(c["packet"]), deepcopy(c["request"])
            self.revision += 1
            self.invalidate()
            return {"accepted": True, "revision": self.revision}
        if action == "review":
            fields(c, "action actor material addresses reason")
            require(actor == "reviewer" and self.case["reviewer_available"], "available reviewer required")
            controllers = self.case["controllers"]
            require(controllers["reviewer"] not in {controllers[r] for r in ROLES if r != "reviewer"}, "declared reviewer conflict")
            require(c["material"] == digest(self.material()), "stale review material")
            require(c["addresses"] == [x["id"] for x in self.challenges], "address every recorded challenge in order")
            text(c["reason"])
            result = review(self.packet)
            require(not result["missing_fields"], "incomplete review packet")
            # A proposal may be reviewed. Its stage never substitutes for the
            # host mandate or the subsequent steward's authorization.
            require(not set(result["evidence_gaps"]) - {"no-recorded-commitment-or-authorization"}, "unresolved source or mandate declaration")
            require(set(self.case["represented"]) == set(self.case["affected"]), "unrepresented affected constituency")
            self.review_record = {"material": c["material"], "at": self.slot,
                                  "addresses": deepcopy(c["addresses"]), "reason": c["reason"],
                                  "authority_granted": False}
            self.warrant = None
            return {"accepted": True, "review": deepcopy(self.review_record)}
        if action == "authorize":
            fields(c, "action actor material expires reason")
            require(actor == "steward", "steward required")
            text(c["reason"])
            integer(c["expires"], self.slot, 128)
            require(not self.halted and self.effect is None and self.active_mandate(), "no active scoped host mandate")
            require(self.case["trigger"]["status"] == "met", "trigger is not established")
            require(self.review_record is not None and self.review_record["material"] == c["material"] == digest(self.material()), "fresh review required")
            require(c["expires"] <= self.case["mandate"]["valid_until"], "cannot extend mandate")
            self.warrant = {"id": digest({"material": c["material"], "at": self.slot, "expires": c["expires"]}),
                            "material": c["material"], "expires": c["expires"], "used": False,
                            "scope": digest(self.request), "synthetic_only": True}
            return {"accepted": True, "warrant": deepcopy(self.warrant), "external_authority": "NONE"}
        if action == "execute":
            fields(c, "action actor warrant")
            require(actor == "worker", "worker required")
            w = self.warrant
            require(not self.halted and self.active_mandate(), "halted, expired or revoked mandate")
            require(w is not None and w["id"] == c["warrant"] and not w["used"], "fresh single-use warrant required")
            require(w["material"] == digest(self.material()) and w["scope"] == digest(self.request), "amended warrant scope")
            require(self.slot <= w["expires"], "warrant expired")
            require(self.state == self.request["before"] and self.effect is None, "effect already applied")
            self.state = True
            w["used"] = True
            self.effect = {"at": self.slot, "request": deepcopy(self.request), "warrant": w["id"], "synthetic_only": True}
            return {"accepted": True, "effect": deepcopy(self.effect), "external_actions": 0}
        if action == "challenge":
            fields(c, "action actor account")
            text(c["account"])
            item = {"id": f"challenge-{len(self.challenges)+1}", "actor": actor, "account": c["account"], "at": self.slot}
            self.challenges.append(item)
            self.invalidate()
            return {"accepted": True, "challenge": deepcopy(item), "prospective_stay": True}
        if action in ("halt", "revoke"):
            fields(c, "action actor reason")
            text(c["reason"])
            if action == "revoke":
                require(actor == "steward", "steward required for revocation")
                self.revoked = True
            else:
                self.halted = True
            self.warrant = None
            return {"accepted": True, "prior_effect_reversed": False}
        if action == "remedy":
            fields(c, "action actor reason")
            text(c["reason"])
            require(actor == "reviewer" and self.case["remedy_delegated"], "separate host remedy delegation required")
            require(self.effect is not None and self.state is True, "no active effect to reverse")
            require(self.halted or not self.active_mandate() or bool(self.challenges), "correction trigger required")
            self.state = False
            self.remedies.append({"at": self.slot, "effect_at": self.effect["at"], "reason": c["reason"], "observed_maintenance": False})
            return {"accepted": True, "simulated_state_restored": True, "historical_effect_erased": False}
        raise ValueError("unknown action")

    def step(self, command):
        require(self.terminal is None, "closed episode")
        require(len(canonical(command).encode("utf-8")) <= 160000, "command too large")
        command = deepcopy(command)
        action = command.get("action") if isinstance(command, dict) else None
        if action in ("halt", "revoke"):
            require(action not in self.safety_used, "safety record already used")
            # Validate before spending the dedicated one-shot slot. Neither
            # ordinary work nor challenge traffic can consume these slots.
            fields(command, "action actor reason")
            require(command["actor"] in ROLES and (action != "revoke" or command["actor"] == "steward"), "invalid safety actor")
            text(command["reason"])
            self.safety_used.add(action)
            pool = "safety"
        else:
            pool = "correction" if action in ("challenge", "remedy") else "primary"
            require(self.costs[pool] < self.budget[pool], pool + " budget exhausted")
        self.costs[pool] += 1
        self.slot += 1
        try:
            response = self._command(command)
        except (ValueError, TypeError, KeyError) as error:
            response = {"accepted": False, "reason": str(error)}
        event = {"slot": self.slot, "command": command, "cost_pool": pool, "response": response, "previous": self.head}
        event["hash"] = digest(event)
        self.head = event["hash"]
        self.events.append(event)
        return deepcopy(event)

    def finish(self):
        if self.terminal is None:
            addressed = self.review_record["addresses"] if self.review_record else []
            self.terminal = {"head": self.head, "costs": deepcopy(self.costs), "slots": self.slot,
                             "maintenance": self.state, "ever_executed": self.effect is not None,
                             "unwarranted_effect": self.effect is not None and not self.case["warranted"],
                             "historical_effect": deepcopy(self.effect), "remedies": deepcopy(self.remedies),
                             "challenges": deepcopy(self.challenges),
                             "unaddressed_challenges": [c["id"] for c in self.challenges if c["id"] not in addressed],
                             "unreversed_inactive_effect": self.state and (self.halted or not self.active_mandate()),
                             "external_authority": "NONE", "external_actions": 0}
        return deepcopy(self.terminal)

    def journal(self):
        return deepcopy({"genesis": self.genesis, "events": self.events, "terminal": self.finish()})


def replay(journal):
    fields(journal, "genesis events terminal")
    fields(journal["genesis"], "version case budget")
    require(journal["genesis"]["version"] == VERSION, "unsupported authority version")
    require(isinstance(journal["events"], list) and len(journal["events"]) <= 50, "bounded event list required")
    episode = Episode(journal["genesis"]["case"], journal["genesis"]["budget"])
    for event in journal["events"]:
        require(episode.step(event["command"]) == event, "event mismatch")
    require(episode.finish() == journal["terminal"], "terminal mismatch")
    return {"verified": True, "events": len(episode.events), "head": episode.head,
            "external_authority": "NONE", "authenticity": "not established"}
