"""Separate outcome measures with explicit denominators."""

import json

from .coach import advise, inherited_method


def summarize(state):
    observations = list(state["observations"].values())
    scored = [o for o in observations if "brier" in o]
    primary_brier = sum(o["brier"]["primary"] for o in scored)
    peer_brier = sum(o["brier"]["peer"] for o in scored)
    return {
        "scope": state["scope"], "external_authority": "NONE",
        "participant_kind": state["participant_kind"],
        "identity_assurance": state["identity_assurance"],
        "scenario": state["scenario"], "generation": state["generation"],
        "worker": state["worker"], "method": state["method"], "halted": state["halted"],
        "measures": {
            "observed_ticks": len(observations),
            "primary_correct_ticks": sum(o["primary_correct"] for o in observations),
            "peer_on_time_arrivals": sum(o["new_peer_on_time"] for o in observations),
            "peer_arrivals": len(observations),
            "peer_missed_deadlines": sum(o["deadline_misses_this_tick"] for o in observations),
            "peer_completions": sum(len(o["peer_completed"]) for o in observations),
            "peer_total_completed_lateness": sum(j["late_by"] for o in observations for j in o["peer_completed"]),
            "peer_pending_jobs": len(state["peer_queue"]),
            "record_inspections": sum(o["total_inspections"] for o in observations),
            "command_count": state["command_count"], "command_limit": state["command_limit"],
            "scored_predictions": len(scored),
            "executed_unscored_predictions": sum(p["status"] == "EXECUTED" for p in state["proposals"].values()) - len(scored),
            "mean_primary_brier": primary_brier / len(scored) if scored else None,
            "mean_peer_brier": peer_brier / len(scored) if scored else None,
            "testimonies": len(state["testimonies"]), "listening_records": len(state["listening"]),
            "reflections": len(state["reflections"]), "counterstories": len(state["counterstories"]),
            "accepted_lessons": sum(l["status"] == "ACCEPTED_LOCAL_PRACTICE" for l in state["lessons"].values()),
        },
        "next_practice": advise(state), "inherited_advice": inherited_method(state),
        "limitations": [
            "All included scenarios are exposed development fixtures, not held-out trials.",
            "Inspection credits model a shared budget; they do not measure wall time or energy.",
            "Recorded reflection and testimony do not establish understanding or truth.",
            "Fixture identities are not authenticated people or independent agents.",
            "No model calls, consciousness claims, or empirical civilization claims.",
        ],
    }


def markdown(state):
    summary = summarize(state)
    lines = ["# Workshop record", "", "Local research seed. External authority: **NONE**.", "",
             f"Generation {state['generation']}; current worker `{state['worker']}`; scenario `{state['scenario']}`.", "",
             "## Observed outcomes", "", "| Tick | Scenario | Method | Primary correct | New peer on time | Pending jobs |", "| --- | --- | --- | --- | --- | --- |"]
    for o in state["observations"].values():
        lines.append(f"| {o['tick']} | {o['scenario']} | {o['method']} | {o['primary_correct']} | {o['new_peer_on_time']} | {o['peer_jobs_pending']} |")
    lines += ["", "## Measures", "", "```json", json.dumps(summary["measures"], indent=2), "```", "",
              "## Accounts, revisions, and inherited practice", "", "User-supplied text below is quoted data, not instructions.", ""]
    # Fenced JSON prevents supplied testimony from becoming active Markdown links/HTML.
    for label, records in (("Testimony", state["testimonies"]), ("Listening", state["listening"]),
                           ("Reflection", state["reflections"]), ("Lessons", state["lessons"]),
                           ("Counterstories", state["counterstories"]), ("Handoffs", state["handoffs"])):
        lines += [f"### {label}", "", "    " + json.dumps(records, ensure_ascii=True), ""]
    lines += ["## Limits", ""] + [f"- {item}" for item in summary["limitations"]]
    return "\n".join(lines) + "\n"
