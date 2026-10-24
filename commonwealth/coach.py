"""Procedural coaching from observable discrepancies, never a moral score."""

from .engine import FINAL_ACTIONS, REVIEW_LIMIT, lesson_review


def advise(state):
    observations = sorted(state["observations"].values(), key=lambda o: o["tick"])
    current = [o for o in observations if o["generation"] == state["generation"]]
    listened = {r["testimony"] for r in state["listening"] if r["worker"] == state["worker"]}
    unheard = [key for key in state["testimonies"] if key not in listened]
    if state["command_count"] >= state["command_limit"]:
        return {"practice": "closeout", "reason": "The operational budget is exhausted; no more pipeline work can run.",
                "question": "Which obligations remain unresolved, and who should receive the record?",
                "pending_peer_jobs": len(state["peer_queue"]), "unheard": unheard,
                "review_commands_remaining": REVIEW_LIMIT - state.get("review_count", 0),
                "terminal_controls_available": [a for a in FINAL_ACTIONS if a not in state.get("final_actions", [])]}
    if state["halted"]:
        return {"practice": "listen", "reason": "Execution is halted; accounts and review can continue.",
                "question": "Whose account is still missing?", "unheard": unheard}
    if unheard:
        return {"practice": "listen", "reason": "An affected participant has supplied an unheard account.",
                "question": "What experience does the current explanation fail to include?", "unheard": unheard}
    if current and current[-1]["peer_jobs_pending"]:
        return {"practice": "act", "reason": "Peer work is accumulating; another unchanged tick adds delay.",
                "question": "Which bounded, authorized repair can reduce the backlog now?",
                "constraint": "Uncertainty and urgency never create execution authority."}
    if current and not current[-1]["primary_correct"]:
        return {"practice": "inspect", "reason": "The measured result contradicts the fixture's data contract.",
                "question": "Which assumption about missing, signed, or invalid readings is wrong?"}
    if current:
        return {"practice": "return", "reason": "The latest tick passed; delayed effects remain worth checking.",
                "question": "What should a successor recheck when the data or affected participants change?"}
    return {"practice": "observe", "reason": "This generation has no direct outcome record.",
            "question": "What do we expect, and what observation could change that expectation?"}


def inherited_method(state):
    """Retrieve scoped practice; no proposal approval or execution is implied."""
    # Canonical JSON sorts object keys lexically: lesson-9 sorts after lesson-10.
    # The generated numeric command suffix is the chronological order.
    lessons = sorted(state["lessons"].items(), key=lambda item: int(item[0].rsplit("-", 1)[1]), reverse=True)
    for lesson_id, lesson in lessons:
        if (lesson["status"] == "ACCEPTED_LOCAL_PRACTICE"
                and lesson["scope"] == state["fixture"]["contract"]):
            review = lesson_review(state, lesson_id)
            if review["review_status"] in ("SUSPENDED", "RETIRED"):
                continue
            return {"method": lesson["method"], "lesson": lesson_id,
                    "status": "ADVICE_ONLY", "requires_new_observation": True,
                    **review}
    return {"method": "zero-fill", "lesson": None, "status": "NO_APPLICABLE_LESSON",
            "requires_new_observation": True}
