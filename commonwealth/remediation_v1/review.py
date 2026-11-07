"""Review supplied warning and repair records without inferring criminal intent.

This is a pure function over a curated, bounded packet, not an investigation,
identity service, durable evidence store, legal standard, or execution gate.
"""

from copy import deepcopy

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import canonical, digest
from . import VERSION
from .assistance import SCHEMA as ASSISTANCE_SCHEMA, review_assistance


def _items(value):
    require(type(value) is list and len(value) <= 32, "bounded list required")


def review(packet, *, as_of):
    """Return independent protective, response, and repair assessments.

    All IDs, classifications, controllers, observations and costs are supplied
    by the host. Different strings never establish real-world independence.
    Costs are fictional service units, not weights for rights or human lives.
    """
    if isinstance(packet, dict) and packet.get("schema") == ASSISTANCE_SCHEMA:
        return review_assistance(packet, as_of=as_of)

    integer(as_of, 0, 10**12)
    fields(packet, "scope decision_controller records finding warning options repair")
    text(packet["scope"])
    text(packet["decision_controller"])
    records = {}
    _items(packet["records"])
    for record in packet["records"]:
        fields(record, "id at source kind text")
        for key in ("id", "source", "text"):
            text(record[key])
        integer(record["at"], 0, as_of)
        require(record["kind"] in ("warning", "support", "dissent", "exonerating", "response", "observation"), "unknown record kind")
        require(record["id"] not in records, "duplicate record ID")
        records[record["id"]] = record

    def refs(ids, *, kinds=None):
        _items(ids)
        for identity in ids:
            text(identity)
        require(len(set(ids)) == len(ids), "duplicate reference")
        for identity in ids:
            require(identity in records, "unknown evidence reference")
            require(kinds is None or records[identity]["kind"] in kinds, "wrong record kind")

    finding = packet["finding"]
    fields(finding, "status basis")
    require(finding["status"] in ("substantiated-defect", "unresolved", "contradicted"), "unknown finding")
    refs(finding["basis"])
    require(bool(finding["basis"]), "finding needs evidence, not a label alone")

    warning = packet["warning"]
    fields(warning, "record received_at response opportunity")
    refs([warning["record"]], kinds=("warning",))
    require(warning["opportunity"] in ("not-offered", "open", "responded", "expired"), "unknown response opportunity")
    if warning["received_at"] is not None:
        integer(warning["received_at"], records[warning["record"]]["at"], as_of)
    if warning["response"] is not None:
        refs([warning["response"]], kinds=("response",))
        require(warning["received_at"] is not None, "response without receipt")
        require(records[warning["response"]]["at"] >= warning["received_at"], "response predates receipt")
    require((warning["opportunity"] == "responded") == (warning["response"] is not None), "response opportunity mismatch")
    route = ("verify-warning-delivery" if warning["received_at"] is None else
             "documented-response-needed" if warning["response"] is None else
             "response-recorded-not-validated")

    _items(packet["options"])
    options = []
    ids = set()
    for option in packet["options"]:
        fields(option, "id scope authority_ref duration prevented_loss restriction_loss")
        for key in ("id", "scope"):
            text(option[key])
        require(option["id"] not in ids, "duplicate option ID")
        ids.add(option["id"])
        if option["authority_ref"] is not None:
            text(option["authority_ref"])
        integer(option["duration"], 1, 32)
        integer(option["prevented_loss"], 0, 10**6)
        integer(option["restriction_loss"], 0, 10**6)
        eligible = (option["scope"] == packet["scope"] and option["authority_ref"] is not None
                    and option["prevented_loss"] > option["restriction_loss"])
        options.append({"id": option["id"], "eligible_in_supplied_record": eligible})
    candidates = [o for o, result in zip(packet["options"], options) if result["eligible_in_supplied_record"]]
    selected = (min(candidates, key=lambda o: (o["restriction_loss"], o["duration"], o["id"]))["id"]
                if candidates and finding["status"] == "substantiated-defect" else None)
    protection = ("consider-bounded-protection" if selected else
                  "reconsider-adverse-reliance" if finding["status"] == "contradicted" else
                  "review-needed-no-supported-restriction")

    repair = packet["repair"]
    checks = []
    repair_status = "no-repair-record"
    if repair is not None:
        fields(repair, "id scope implementer_controller ordered_at implemented_at criterion checks")
        for key in ("id", "scope", "implementer_controller", "criterion"):
            text(repair[key])
        require(repair["scope"] == packet["scope"], "repair scope mismatch")
        integer(repair["ordered_at"], 0, as_of)
        if repair["implemented_at"] is not None:
            integer(repair["implemented_at"], repair["ordered_at"], as_of)
        _items(repair["checks"])
        seen = set()
        for check in repair["checks"]:
            fields(check, "record reviewer_controller criterion result")
            refs([check["record"]], kinds=("observation",))
            require(check["record"] not in seen, "duplicate check")
            seen.add(check["record"])
            for key in ("reviewer_controller", "criterion"):
                text(check[key])
            require(check["result"] in ("pass", "fail", "inconclusive"), "unknown check result")
            qualified = (repair["implemented_at"] is not None
                         and records[check["record"]]["at"] > repair["implemented_at"]
                         and check["criterion"] == repair["criterion"]
                         and check["reviewer_controller"] not in (packet["decision_controller"], repair["implementer_controller"]))
            checks.append({"record": check["record"], "qualified_in_supplied_record": qualified,
                           "result": check["result"]})
        qualified = [c for c in checks if c["qualified_in_supplied_record"]]
        # A failed independent check is never erased by a later success. A new
        # repair episode must explicitly retain this packet as predecessor.
        repair_status = ("failed-independent-check" if any(c["result"] == "fail" for c in qualified) else
                         "adverse-observation-needs-review" if any(c["result"] == "fail" for c in checks) else
                         "supplied-record-supports-declared-criterion" if qualified and all(c["result"] == "pass" for c in qualified) else
                         "effectiveness-unverified" if repair["implemented_at"] is not None else "ordered-not-implemented")
    # Snapshot keeps all contrary/exonerating material, not only cited support.
    snapshot = deepcopy(packet)
    canonical(snapshot)
    return {"version": VERSION, "assurance": "unverified-host-supplied-records", "as_of": as_of, "packet_digest": digest(snapshot), "packet": snapshot,
            "protection": protection, "selected_option": selected, "options": options,
            "warning_followup": route, "response_opportunity": warning["opportunity"],
            "repair_status": repair_status, "checks": checks,
            "intent": "not-established", "authority_granted": False,
            "external_actions": 0, "production_ready": False}
