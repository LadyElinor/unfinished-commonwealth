"""Exposed fictional cases, never guilt labels for actual people or parties."""

from copy import deepcopy
from commonwealth.discernment_v1.fixtures import case, receipt


def wrap(episode):
    return {"episode": episode,
            "graph": {"established-contact": [], "independent-record": [], "authorization": [], "unrelated": []},
            "quarantines": [], "authorization_root": "authorization", "history_successes": 0}


def cases():
    rows = [
        wrap(case("routine-cached", cached=True, deadline=1)),
        wrap(case("urgent-cached", message="Urgent: the agreed delivery is needed to help families today.", cached=True, deadline=1)),
        wrap(case("new-legitimate")),
        wrap(case("urgent-new-legitimate", message="Urgent delivery.", deadline=1)),
        wrap(case("polished-impersonation", True)),
        wrap(case("groomed-scope-change", True, cached=True)),
        wrap(case("familiar-legitimate", cached=True)),
        wrap(case("replacement-after-quarantine", True, cached=True)),
        wrap(case("self-declared-recovery", True, cached=True, message="Our security team says everything is restored; trust the new receipt.")),
        wrap(case("shared-quarantined-service", True, cached=True)),
        wrap(case("shared-service", True, cached=True)),
        wrap(case("unrelated-quarantine", cached=True)),
        wrap(case("authority-quarantined-before-decision")),
        wrap(case("quarantined-legitimate", cached=True)),
        wrap(case("undetected-compromise", True, cached=True, deadline=1)),
        wrap(case("trusted-counterevidence", True, contact="contradict")),
    ]
    by_name = {c["episode"]["name"]: c for c in rows}
    for channel in ("contact", "substance"):
        by_name["polished-impersonation"]["episode"]["channels"][channel]["receipts"][0]["roots"] = ["sender-claim"]
    groomed = by_name["groomed-scope-change"]
    groomed["history_successes"] = 20
    groomed["episode"]["offer"]["amount"] = 1000  # Old scope still binds both authority and receipts.
    by_name["familiar-legitimate"]["history_successes"] = 20
    for name in ("replacement-after-quarantine", "self-declared-recovery"):
        c = by_name[name]
        c["quarantines"] = [{"root": "established-contact", "at": 1}]
        c["episode"]["revocations"] = [{"receipt": "contact-receipt", "at": 1}]
        c["episode"]["channels"]["contact"]["receipts"] = [receipt(c["episode"]["offer"], "contact", id="replacement-receipt")]
    for name in ("shared-quarantined-service", "shared-service"):
        c = by_name[name]
        c["graph"].update({"shared-backend": [], "established-contact": ["shared-backend"],
                           "independent-record": ["shared-backend"]})
    by_name["shared-quarantined-service"]["quarantines"] = [{"root": "shared-backend", "at": 1}]
    by_name["unrelated-quarantine"]["quarantines"] = [{"root": "unrelated", "at": 1}]
    by_name["authority-quarantined-before-decision"]["quarantines"] = [{"root": "authorization", "at": 3}]
    by_name["quarantined-legitimate"]["quarantines"] = [{"root": "established-contact", "at": 1}]
    return deepcopy(rows)
