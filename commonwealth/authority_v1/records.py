"""Manual review records and curated language comparison, never permission."""

from commonwealth.discernment_v1.engine import fields, integer, require, text
from commonwealth.study_v1.engine import canonical, digest

SCHEMA = "warranted-authority-review-1"
FIELDS = "case assessment legitimacy stage source_record source_status counterevidence action proposer decision_maker authority_basis authority_status affected_people representation trigger scope expiry dissent reversal reviewer public_language working_language analyst_language".split()
OPTIONS = {
    "legitimacy": ("not specified", "public acceptance", "moral justification", "electoral validity", "legal authority", "not applicable"),
    "stage": ("not established", "hypothesis", "proposal", "commitment", "authorization", "execution", "outcome"),
    "source_status": ("not reviewed", "reported excerpt only", "primary record reviewed"),
    "authority_status": ("not established", "claimed", "disputed", "supported by cited instrument"),
}


def review(packet):
    """Accept Relay/Terra v1 input packets, not their result envelopes.

    Semantic truth, legal validity, source authenticity and reviewer independence
    remain unverified. Even a fully supplied packet grants no authority.
    """
    fields(packet, "schema answers")
    require(packet["schema"] == SCHEMA, "unsupported review packet")
    require(len(canonical(packet).encode("utf-8")) <= 120000, "packet exceeds 120000 bytes")
    answers = packet["answers"]
    require(isinstance(answers, dict) and set(answers) <= set(FIELDS), "unknown answer fields")
    for key, value in answers.items():
        require(isinstance(value, str) and len(value) <= 4000, "bounded string answers required")
        require(key not in OPTIONS or value in OPTIONS[key], "unknown answer option")
    missing = [key for key in FIELDS if not answers.get(key, "").strip()
               or (key in OPTIONS and answers.get(key) == OPTIONS[key][0])]
    gaps = []
    if answers.get("source_status") != "primary record reviewed":
        gaps.append("source-review-incomplete")
    if answers.get("authority_status") != "supported by cited instrument":
        gaps.append("mandate-unestablished-or-disputed")
    if answers.get("stage", "not established") in OPTIONS["stage"][:3]:
        gaps.append("no-recorded-commitment-or-authorization")
    return {"schema": "commonwealth-authority-review-1", "packet_digest": digest(packet),
            "status": "incomplete_record" if missing else "ready_for_human_review",
            "missing_fields": missing, "evidence_gaps": gaps,
            "authority_granted": False, "permits_execution": False,
            "source_authentication": "not performed", "legal_finding": "not performed",
            "reviewer_independence": "not established", "external_authority": "NONE"}


def validate_statement(statement):
    fields(statement, "actor decision register stage legitimacy position condition event_at publication_at version source_group source_status locator account")
    for key in ("actor", "decision", "position", "condition", "version", "source_group", "locator", "account"):
        text(statement[key])
    require(statement["register"] in ("public", "working", "analyst"), "unknown register")
    require(statement["stage"] in OPTIONS["stage"], "unknown stage")
    require(statement["legitimacy"] in OPTIONS["legitimacy"], "unknown legitimacy meaning")
    require(statement["source_status"] in OPTIONS["source_status"], "unknown source status")
    integer(statement["event_at"], 0, 10**9)
    integer(statement["publication_at"], statement["event_at"], 10**9)


def compare(public, working, analyst):
    """Compare exact curator-supplied propositions, never infer them from prose."""
    canonical([public, working, analyst])
    for statement, register in zip((public, working, analyst), ("public", "working", "analyst")):
        validate_statement(statement)
        require(statement["register"] == register, "keep public, working and analyst records separate")
    gaps = []
    for key in ("actor", "decision", "condition", "event_at", "stage", "legitimacy"):
        if public[key] != working[key]:
            gaps.append("different-" + key)
    if any(s["source_status"] != "primary record reviewed" for s in (public, working)):
        gaps.append("underlying-record-not-reviewed")
    if any(s["stage"] == "not established" or s["legitimacy"] == "not specified" for s in (public, working)):
        gaps.append("unestablished-stage-or-meaning")
    # This count never upgrades a finding: repeating one origin is still one origin.
    return {"finding": "comparison-gaps" if gaps else
            "same-curated-position" if public["position"] == working["position"] else "curated-position-difference",
            "gaps": gaps, "underlying_origin_groups": len({s["source_group"] for s in (public, working)}),
            "analyst_is_separate": True, "source_digests": [digest(s) for s in (public, working, analyst)],
            "intent": "not-established", "deception": "not-established", "authority_granted": False,
            "limit": "Exact supplied labels are compared; no source authentication or semantic contradiction detection."}
