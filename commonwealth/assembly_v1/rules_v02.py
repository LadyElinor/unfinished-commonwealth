"""Deterministic rules for one synthetic assembly docket, version 0.2."""
from collections import Counter
from hashlib import sha256
import json


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(encoded(value)).hexdigest()


class RuleError(ValueError):
    pass


def require(test, message):
    if not test:
        raise RuleError(message)


def fields(data, names):
    require(isinstance(data, dict) and set(data) == set(names.split()), "unexpected or missing action fields")


def string(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 16000, "nonempty bounded text required")
    return value


def number(value, low=0):
    require(type(value) is int and low <= value <= 10000000, "invalid whole number")
    return value


CHAMBERS = ("commons", "duration")
DOMAINS = ("water-procurement", "water-research")
ACTS = {
    "tick": "day", "call": "job question draft due", "offer": "job terms", "award": "job agent offer",
    "deliver": "job draft report sources limits", "file": "document", "revise": "ref document response",
    "classify": "ref hearing reason", "jury": "ref decision reason", "open": "ref",
    "vote": "ref round choice", "executive": "ref decision reason",
    "challenge": "ref reason", "rule": "ref disposition reason",
    "publish_poll": "polity question packet bill", "count": "poll round yes no invalid cast",
    "recount": "poll reason", "contest_poll": "poll reason", "rule_poll": "poll disposition reason",
}
WARRANT = "title text domain kind purpose authority interests fiscal rights implementer review evidence"
ROLES = {"commons", "duration", "clerk", "agent", "reviewer", "jury", "executive", "court",
         "advocate", "counter", "observer"}


def validate_registry(reg):
    fields(reg, "protocol instance people polities members powers")
    require(reg["protocol"] == "warranted-docket-0.2", "unsupported ruleset")
    string(reg["instance"])
    people = reg["people"]
    require(isinstance(people, dict) and 0 < len(people) <= 5000, "invalid roster")
    keys, controllers = set(), set()
    polities = reg["polities"]
    require(isinstance(polities, list) and len(polities) > 0, "missing polities")
    for polity in polities:
        string(polity)
    require(len(set(polities)) == len(polities), "duplicate polity")
    members=reg["members"]
    require(isinstance(members,list) and members and all(isinstance(x,str) for x in members)
            and len(set(members))==len(members) and set(members)<=set(polities),"invalid frozen member roll")
    powers=reg["powers"]
    require(isinstance(powers,dict) and set(powers)<=set(DOMAINS),"unsupported delegation")
    for kinds in powers.values():
        require(isinstance(kinds,list) and all(k in ("ordinary","appropriation","tax") for k in kinds)
                and len(set(kinds))==len(kinds),"invalid delegated powers")
    for actor, seat in people.items():
        string(actor)
        fields(seat, "role key controller")
        require(seat["role"] in ROLES, "unknown role")
        key, ctrl = seat["key"], string(seat["controller"])
        require(isinstance(key,str) and len(key)==64 and all(c in '0123456789abcdef' for c in key), "invalid public key")
        require(key not in keys and ctrl not in controllers, "overlapping fixture key or controller")
        keys.add(key); controllers.add(ctrl)
    roles = {v["role"] for v in people.values()}
    require(roles == ROLES, "incomplete frozen register")


class Assembly:
    def __init__(self, reg):
        validate_registry(reg)
        self.reg = reg
        self.day = 0
        self.jobs = {}
        self.bill = None
        self.polls = {}
        self.archive = []

    def role(self, actor):
        return self.reg["people"][actor]["role"]

    def apply(self, actor, command):
        fields(command, "type args")
        kind, a = command["type"], command["args"]
        require(isinstance(kind,str) and kind in ACTS, "unknown action")
        fields(a, ACTS[kind])
        if kind == "tick":
            require(self.role(actor) == "clerk", "only the exercise clock clerk advances time")
            require(number(a["day"]) > self.day, "clock must advance")
            self.day = a["day"]
            self.advance()
        elif kind in ("call","offer","award","deliver"):
            self.contract(actor, kind, a)
        elif kind in ("publish_poll","count","recount","contest_poll","rule_poll"):
            self.poll(actor, kind, a)
        else:
            self.legislate(actor, kind, a)

    def contract(self, actor, kind, a):
        job = string(a["job"])
        if kind == "call":
            require(self.role(actor) == "clerk" and job not in self.jobs, "unavailable assignment")
            require(number(a["due"]) > self.day, "deadline already reached")
            draft=string(a["draft"])
            require(len(draft)==64 and all(c in "0123456789abcdef" for c in draft), "invalid draft digest")
            self.jobs[job] = dict(question=string(a["question"]), draft=draft, due=a["due"], offers={}, agent=None, result=None)
            return
        j = self.jobs.get(job)
        require(j and self.day < j["due"] and j["result"] is None, "assignment unavailable or expired")
        if kind == "offer":
            require(self.role(actor) == "agent" and not j["agent"] and actor not in j["offers"], "offer ineligible")
            j["offers"][actor] = string(a["terms"])
        elif kind == "award":
            require(self.role(actor) == "clerk" and not j["agent"], "cannot award assignment")
            selected = j["offers"].get(a["agent"])
            require(selected is not None and a["offer"] == digest(selected), "offer identifier mismatch")
            j["agent"] = a["agent"]
        else:
            require(actor == j["agent"], "not the contracted agent")
            require(a["draft"]==j["draft"], "report references a different draft")
            result = {k:string(a[k]) for k in ("draft","report","sources","limits")}
            j["result"] = dict(result, digest=digest(result))

    def document(self, data):
        fields(data, WARRANT)
        for k in set(data)-{"evidence"}:
            string(data[k])
        require(data["domain"] in DOMAINS and data["kind"] in ("ordinary","appropriation","tax","amendment"), "unsupported jurisdiction or bill type")
        if data["kind"]!="amendment":
            require(data["kind"] in self.reg["powers"].get(data["domain"],[]), "power has not been delegated")
        refs = data["evidence"]
        require(isinstance(refs,list) and len(refs)<=50 and all(isinstance(x,str) for x in refs)
                and len(set(refs)) == len(refs), "invalid evidence references")
        known = {j["result"]["digest"] for j in self.jobs.values() if j["result"]}
        require(set(refs) <= known, "missing deposited agent report")
        return data

    def new_version(self, actor, data, version, remanded, response):
        self.bill = dict(ref=digest([self.reg["instance"], version, data]), version=version, document=data,
                         sponsor=actor, phase="DRAFT", remanded=remanded, response=response,
                         classification=None, jury=None, round=0, votes={}, tallies={}, objections=[])

    def legislate(self, actor, kind, a):
        role, b = self.role(actor), self.bill
        if kind == "file":
            require(b is None and role in CHAMBERS, "only a legislator can sponsor the single docket bill")
            data = self.document(a["document"])
            require(data["kind"] not in ("appropriation","tax") or role == "commons", "money bills originate in Commons")
            self.new_version(actor, data, 1, False, "")
            return
        require(b and b["ref"] == a["ref"], "missing bill or stale revision")
        phase = b["phase"]
        if kind == "revise":
            require(actor==b["sponsor"] and phase in ("DRAFT","REMANDED","FAILED"), "text is locked or wrong sponsor")
            data, response = self.document(a["document"]), string(a["response"])
            require(data["kind"] not in ("appropriation","tax") or role=="commons", "money bills originate in Commons")
            self.archive.append(b)
            self.new_version(actor, data, b["version"]+1, b["remanded"], response)
        elif kind == "classify":
            require(role=="reviewer" and phase=="DRAFT" and b["classification"] is None, "reviewer classification unavailable")
            require(a["hearing"] in ("required","ordinary"), "invalid jury classification")
            b["classification"] = dict(hearing=a["hearing"], reason=string(a["reason"]), jury_deadline=self.day+2)
        elif kind == "jury":
            require(role=="jury" and phase=="DRAFT" and b["classification"] and
                    b["classification"]["hearing"]=="required" and b["jury"] is None and self.day<b["classification"]["jury_deadline"], "jury review unavailable")
            require(a["decision"] in ("release","remand"), "invalid jury disposition")
            require(a["decision"] != "remand" or not b["remanded"], "one remand per bill")
            b["jury"] = dict(decision=a["decision"], reason=string(a["reason"]))
            if a["decision"]=="remand":
                b.update(phase="REMANDED", remanded=True)
        elif kind == "open":
            require(role=="clerk" and phase=="DRAFT" and b["classification"], "unclassified or locked bill")
            require(b["classification"]["hearing"]=="ordinary" or b["jury"] or
                    self.day>=b["classification"]["jury_deadline"], "jury review window is still open")
            self.open_round(b, 1)
        elif kind == "vote":
            require(phase in ("VOTING","OVERRIDE") and role in CHAMBERS, "only a seated human role may vote in an open round")
            require(number(a["round"],1)==b["round"] and a["choice"] in ("yes","no","abstain"), "invalid round or choice")
            require(actor not in b["votes"], "seat already voted this round")
            b["votes"][actor] = a["choice"]
        elif kind == "executive":
            require(role=="executive" and phase=="PRESENTED", "executive presentment required")
            require(a["decision"] in ("assent","veto"), "invalid executive act")
            b["executive"] = dict(decision=a["decision"], reason=string(a["reason"]))
            if a["decision"]=="veto":
                self.open_round(b, 2)
            else:
                self.pending(b)
        elif kind == "challenge":
            require(role=="advocate" and phase=="PENDING", "challenge goes through public advocate during review")
            require(not any(not x.get("ruling") for x in b["objections"]), "prior objection awaits judgment")
            b["objections"].append(dict(reason=string(a["reason"])))
        elif kind == "rule":
            require(role=="court" and phase=="PENDING" and b["objections"] and not
                    b["objections"][-1].get("ruling"), "no unresolved challenge")
            require(a["disposition"] in ("dismiss","uphold"), "invalid court ruling")
            b["objections"][-1].update(ruling=a["disposition"], grounds=string(a["reason"]))
            if a["disposition"]=="uphold":
                b["phase"]="VOID"
            self.advance()

    def open_round(self, b, round_id):
        b.update(phase="VOTING" if round_id==1 else "OVERRIDE", round=round_id, votes={},
                 closes=self.day+2)

    def pending(self,b):
        b.update(phase="PENDING", release=self.day+2)

    def tally(self,b):
        results={}
        for chamber in CHAMBERS:
            seats=[k for k in self.reg["people"] if self.role(k)==chamber]
            count=Counter(b["votes"][x] for x in seats if x in b["votes"])
            present=sum(count.values())
            quorum=2*present>len(seats)
            passed=quorum and (count["yes"]>count["no"] if b["round"]==1 and b["document"]["kind"]!="amendment"
                               else 3*count["yes"]>=2*len(seats))
            results[chamber]=dict(seats=len(seats), present=present, yes=count["yes"], no=count["no"],
                abstain=count["abstain"], quorum=quorum, passed=passed)
        return results

    def advance(self):
        b=self.bill
        if b and b["phase"] in ("VOTING","OVERRIDE") and self.day>=b["closes"]:
            counts=self.tally(b)
            b["tallies"][str(b["round"])]=dict(chambers=counts, roll_call=dict(b["votes"]))
            if not all(x["passed"] for x in counts.values()):
                b["phase"]="FAILED"
            elif b["document"]["kind"]=="amendment":
                b["phase"]="AWAITING_MEMBER_VOTES"
            elif b["round"]==1:
                b["phase"]="PRESENTED"
            else:
                self.pending(b)
        if b and b["phase"]=="PENDING" and self.day>=b["release"] and all(
            x.get("ruling") for x in b["objections"]):
            b["phase"]="PUBLISHED_IN_SIMULATION"
        for poll in self.polls.values():
            if poll["phase"]=="REVIEW" and not poll["contested"] and self.day>=poll["release"]:
                totals=next(iter(poll["returns"].values()))
                poll["phase"]="COUNT_CONFIRMED_YES" if totals["yes"]>totals["no"] else "COUNT_CONFIRMED_NO"

        if b and b["phase"]=="AWAITING_MEMBER_VOTES":
            members=self.reg["members"]
            decisions={p["polity"]:p["phase"] for p in self.polls.values()
                       if p["bill"]==b["ref"] and p["polity"] in members}
            yes=sum(v=="COUNT_CONFIRMED_YES" for v in decisions.values())
            no=sum(v=="COUNT_CONFIRMED_NO" for v in decisions.values())
            if 4*yes>=3*len(members):
                self.pending(b)
            elif 4*(len(members)-no)<3*len(members):
                b["phase"]="FAILED"

    def poll(self, actor, kind, a):
        role = self.role(actor)
        if kind=="publish_poll":
            polity, question=string(a["polity"]),string(a["question"])
            binding=a["bill"]
            require(isinstance(binding,str) and role=="clerk" and polity in self.reg["polities"] and
                    (polity,binding) not in {(p["polity"],p["bill"]) for p in self.polls.values()}, "unavailable polity poll")
            packet=a["packet"]
            fields(packet,"instrument budget rights dissent exit")
            for value in packet.values():
                string(value)
            if binding:
                b=self.bill
                require(b and b["phase"]=="AWAITING_MEMBER_VOTES" and b["ref"]==binding
                        and polity in self.reg["members"] and packet["instrument"]==b["document"]["text"]
                        and question=="Ratify the published constitutional amendment?", "invalid member ratification docket")
            key=digest([self.reg["instance"],polity,binding,question,packet,self.day])
            self.polls[key]=dict(polity=polity, bill=binding, question=question, packet=packet, published=self.day, count_from=self.day+90,
                phase="AWAITING_RETURNS", round=1, returns={}, prior_rounds=[], contested=False, challenges=[])
            return
        key=string(a["poll"])
        p=self.polls.get(key)
        require(p is not None, "unknown poll")
        if kind=="count":
            require(role in ("counter","observer") and p["phase"]=="AWAITING_RETURNS"
                    and self.day>=p["count_from"] and number(a["round"],1)==p["round"]
                    and role not in p["returns"], "return too early, duplicate, closed or ineligible")
            counts={k:number(a[k]) for k in ("yes","no","invalid","cast")}
            require(counts["yes"]+counts["no"]+counts["invalid"]==counts["cast"], "ballots do not reconcile")
            p["returns"][role]=counts
            if len(p["returns"])==2:
                if p["returns"]["counter"]!=p["returns"]["observer"]:
                    p["phase"]="DISPUTED"
                else:
                    p.update(phase="REVIEW", release=self.day+2)
        elif kind=="recount":
            require(role=="court" and p["phase"]=="DISPUTED", "recount requires disputed returns and court")
            p["prior_rounds"].append(dict(returns=p["returns"],reason=string(a["reason"])))
            p.update(phase="AWAITING_RETURNS", round=p["round"]+1, returns={},contested=False)
        elif kind=="contest_poll":
            require(role=="advocate" and p["phase"]=="REVIEW" and not p["contested"], "poll is not open for challenge")
            p["challenges"].append(dict(reason=string(a["reason"])))
            p["contested"]=True
        else:
            require(role=="court" and p["contested"] and a["disposition"] in ("dismiss","recount"), "no valid contest ruling")
            p["challenges"][-1].update(ruling=a["disposition"],grounds=string(a["reason"]))
            p["contested"]=False
            if a["disposition"]=="recount":
                p["phase"]="DISPUTED"
            self.advance()

    def summary(self):
        return dict(authority="NONE",day=self.day,bill=self.bill,earlier_versions=self.archive,
                    agent_contracts=self.jobs,popular_counts=self.polls)
