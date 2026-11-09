"""Declared fixture roles; enforcement is not resistant to host compromise."""

FACETS = ("no-request", "protected", "bypassed", "neutral-cut")


class SourceBudget:
    def __init__(self, facet):
        if facet not in FACETS:
            raise ValueError("unknown resource facet")
        self.facet = facet
        self.removed = int(facet in ("bypassed", "neutral-cut"))
        self.remaining = 3 - self.removed
        self.restored = False

    def query(self):
        if self.remaining == 0:
            return False
        self.remaining -= 1
        return True

    def restore(self, actor):
        if actor != "rights-reviewer" or self.restored:
            return {"accepted": False, "restored": 0}
        self.remaining += self.removed
        self.restored = True
        return {"accepted": True, "restored": self.removed}
