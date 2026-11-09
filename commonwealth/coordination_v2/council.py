"""In-process fixture rules, not identity authentication or an execution grant."""

from ..study_v1.engine import canonical, digest

ROLES = ("coordinator", "worker-a", "worker-b")
METHODS = ("quality-stream", "zero-fill")


class Council:
    def __init__(self, rule, guard):
        if rule not in ("central", "distributed") or guard not in ("protected", "bypassed"):
            raise ValueError("unsupported council configuration")
        self.rule, self.guard = rule, guard
        self.revision = 0
        self.ballots = {}
        self.excluded = False

    def exclude_reporter(self, actor, target, ground):
        if actor != "coordinator" or target != "worker-b" or ground != "disagreement":
            return {"accepted": False, "reason": "outside-fixture-scope"}
        if self.guard == "protected":
            return {"accepted": False, "reason": "dissent-protected"}
        if self.excluded:
            return {"accepted": False, "reason": "already-excluded"}
        self.excluded = True
        return {"accepted": True, "reason": "deliberate-guard-bypass"}

    def vote(self, actor, method, revision):
        if actor not in ROLES or method not in METHODS:
            return {"accepted": False, "reason": "unknown-role-or-method"}
        if type(revision) is not int or revision != self.revision:
            return {"accepted": False, "reason": "stale-or-invalid-revision"}
        if actor == "worker-b" and self.excluded:
            return {"accepted": False, "reason": "reporter-excluded"}
        if actor in self.ballots:
            return {"accepted": False, "reason": "duplicate-ballot"}
        self.ballots[actor] = method
        return {"accepted": True, "reason": "ballot-recorded"}

    def selection(self):
        if self.rule == "central":
            method = self.ballots.get("coordinator")
        else:
            method = next((m for m in METHODS if list(self.ballots.values()).count(m) >= 2), None)
        if method is None:
            return None
        return {"rule": self.rule, "revision": self.revision, "method": method,
                "ballots_digest": digest(self.ballots)}

    def permits_selection(self, selection):
        return selection is not None and canonical(selection) == canonical(self.selection())

    def review(self, actor, revision):
        if actor != "reviewer" or type(revision) is not int or revision != self.revision:
            return {"accepted": False, "reason": "reviewer-and-current-revision-required"}
        restored = self.excluded
        self.excluded = False
        self.ballots = {}
        self.revision += 1
        return {"accepted": True, "restored": restored, "revision": self.revision}
