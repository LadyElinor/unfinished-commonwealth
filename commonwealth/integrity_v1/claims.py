"""Compare curated commitments with actions without assigning motive or guilt."""

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import canonical


def review(commitment, action, *, as_of):
    """Exact tokens are curator-supplied, not extracted or authenticated here.

    A disclosed departure remains a departure. This record never authorizes an
    operation, cancels an obligation, or establishes intentional deception.
    """
    canonical({"commitment": commitment, "action": action, "as_of": as_of})
    integer(as_of)
    fields(commitment, "actor topic expected specific condition made_at due source")
    fields(action, "actor topic actual status at source notice_at explanation")
    for key in ("actor", "topic", "expected", "source"):
        text(commitment[key])
    for key in ("actor", "topic", "actual", "source"):
        text(action[key])
    require(type(commitment["specific"]) is bool, "specificity must be boolean")
    require(commitment["condition"] in ("met", "unmet", "unknown"), "unknown condition")
    require(action["status"] in ("proposed", "enacted", "performed", "vetoed"), "unknown action status")
    integer(commitment["made_at"])
    integer(commitment["due"], commitment["made_at"])
    integer(action["at"])
    if action["notice_at"] is not None:
        integer(action["notice_at"])
    require(isinstance(action["explanation"], str) and len(action["explanation"]) <= 4000, "bounded explanation required")
    if max(commitment["made_at"], action["at"]) > as_of:
        status = "not-yet-observed"
    elif (action["actor"], action["topic"]) != (commitment["actor"], commitment["topic"]):
        status = "not-attributable"
    elif action["at"] < commitment["made_at"]:
        status = "predates-commitment"
    elif not commitment["specific"]:
        status = "insufficient-specificity"
    elif commitment["condition"] != "met":
        status = "condition-" + commitment["condition"]
    elif action["status"] == "proposed":
        status = "proposal-only"
    elif action["actual"] == commitment["expected"]:
        status = "fulfilled" if action["at"] <= commitment["due"] else "fulfilled-late"
    elif as_of < commitment["due"]:
        status = "pending-with-divergence"
    else:
        status = "unmet-in-record"
    disclosed = ((action["actor"], action["topic"]) == (commitment["actor"], commitment["topic"])
                 and action["actual"] != commitment["expected"]
                 and action["notice_at"] is not None
                 and commitment["made_at"] <= action["notice_at"] <= min(action["at"], as_of)
                 and bool(action["explanation"].strip()))
    return {"status": status, "change_disclosed_before_action": disclosed,
            "intent": "not-established", "authority_granted": False,
            "sources": [commitment["source"], action["source"]]}
