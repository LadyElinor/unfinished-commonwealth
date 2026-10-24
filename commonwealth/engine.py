"""Pure, replayable workshop transitions. Actor names are fixture identities.

This module enforces local protocol structure. It does not authenticate callers,
establish cognitive independence, or issue authority outside the workshop.
"""

from copy import deepcopy
import hashlib
import json
import math
import re

from .pipeline import METHODS, aggregate, run_tick
from . import legacy_v1


Rejected = legacy_v1.Rejected

PROTOCOL = 2
REVIEW_LIMIT = 32
FINAL_ACTIONS = ("halt", "revoke", "closeout")
REVIEW_ACTIONS = ("testify", "listen", "reflect", "counterstory", "review-lesson")
MAX_EVENTS = 1 + 256 + REVIEW_LIMIT + len(FINAL_ACTIONS)


def upgrade_state(original):
    """Upgrade only as part of a new v2 event; never rewrite historical events."""
    state = deepcopy(original)
    if state["schema"] == 1:
        state.update(schema=2, version="0.1.2", review_count=0,
                     final_actions=[], closeouts=[])
    return state


def parse_json(source):
    """Read unambiguous, finite JSON with bounded container nesting."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Rejected(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise Rejected(f"nonfinite JSON number: {value}")

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            nonfinite(value)
        return parsed

    try:
        value = json.loads(source, object_pairs_hook=pairs,
                           parse_constant=nonfinite, parse_float=number)
    except RecursionError as exc:
        raise Rejected("JSON nesting exceeds 64 levels") from exc
    # Do not recurse here: a decoder may admit deeper values than deepcopy or
    # the canonical encoder can safely handle on the current Python version.
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, (dict, list)):
            if depth >= 64:
                raise Rejected("JSON nesting exceeds 64 levels")
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise Rejected(f"{field}: a nonempty string of at most 4000 characters is required")
    return value


def exact(obj, required, optional=()):
    if not isinstance(obj, dict):
        raise Rejected("a JSON object is required")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise Rejected(f"invalid fields: missing={sorted(missing)}, extra={sorted(extra)}")


def validate_fixture(fixture):
    exact(fixture, ("description", "contract", "capacity", "values", "valid",
                    "reference", "peer_values"))
    text(fixture["description"], "description")
    if fixture["contract"] != "quality-flags-v1":
        raise Rejected("unsupported data contract")
    if type(fixture["capacity"]) is not int or not 1 <= fixture["capacity"] <= 1000:
        raise Rejected("invalid inspection capacity")
    for name in ("values", "valid", "peer_values"):
        if not isinstance(fixture[name], list) or not 1 <= len(fixture[name]) <= 100:
            raise Rejected(f"invalid {name}")
    if any(type(v) is not int for v in fixture["peer_values"]):
        raise Rejected("peer readings must be integers")
    actual = aggregate(fixture["values"], fixture["valid"], "quality-stream")
    exact(fixture["reference"], ("numerator", "denominator"))
    if any(type(v) is not int for v in fixture["reference"].values()):
        raise Rejected("reference must be an exact rational")
    if fixture["reference"] != actual["mean"]:
        raise Rejected("fixture reference disagrees with its declared quality contract")
    if 2 * len(fixture["values"]) > fixture["capacity"]:
        raise Rejected("fixture must support every bounded primary method")


def initial_state(scenario, fixture):
    scenario_name(scenario)
    validate_fixture(fixture)
    return {
        # State identity for protocol 2. Protocol 1 is frozen in legacy_v1.
        "schema": 2, "version": "0.1.2", "scope": "LOCAL_RESEARCH",
        "external_authority": "NONE", "identity_assurance": "SUPPLIED_UNVERIFIED",
        "participant_kind": "SCRIPTED_OR_OPERATOR_SUPPLIED",
        "scenario": scenario, "fixture": deepcopy(fixture),
        "generation": 1, "worker": "worker-1", "retired_workers": [],
        "method": "zero-fill", "tick": 0, "revision": 0, "epoch": 0,
        "halted": False, "command_count": 0, "command_limit": 256,
        "review_count": 0, "final_actions": [], "closeouts": [],
        "peer_queue": [], "proposals": {}, "observations": {},
        "testimonies": {}, "listening": [], "reflections": [],
        "lessons": {}, "counterstories": [], "casebook_consultations": [],
        "handoffs": [], "last_execution": None,
    }


def scenario_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value):
        raise Rejected("scenario must be a lowercase slug of at most 64 characters")


FIELDS = {
    "observe": (),
    "propose": ("method", "prediction", "purpose"),
    "approve": ("proposal",),
    "execute": ("proposal",),
    "testify": ("observation", "account"),
    "listen": ("testimony", "acknowledgment"),
    "reflect": ("evidence", "before", "after", "next_check"),
    "lesson": ("method", "evidence", "scope", "guidance"),
    "accept-lesson": ("lesson",),
    "review-lesson": ("lesson", "decision", "reason"),
    "counterstory": ("reference", "account"),
    "consult": ("case", "interpretation"),
    "handoff": ("scenario", "fixture", "note"),
    "halt": ("reason",), "resume": ("reason",), "revoke": ("reason",),
    "closeout": ("reason", "follow_up"),
}


def evidence_ids(state, values):
    if not isinstance(values, list) or not values or len(values) > 20:
        raise Rejected("provide 1 to 20 evidence IDs")
    if any(not isinstance(v, str) for v in values) or len(set(values)) != len(values):
        raise Rejected("evidence IDs must be unique strings")
    available = set(state["observations"]) | set(state["testimonies"])
    if any(v not in available for v in values):
        raise Rejected("unknown evidence; self-description is not a substitute")


def require_worker(state, actor):
    if actor != state["worker"]:
        raise Rejected("only the current worker may submit this transition")


def require_keeper(actor):
    if actor != "keeper":
        raise Rejected("the fixture maintainer must authorize this transition")


def current_proposal(state, proposal_id):
    if not isinstance(proposal_id, str) or proposal_id not in state["proposals"]:
        raise Rejected("unknown proposal")
    proposal = state["proposals"][proposal_id]
    if (proposal["revision"] != state["revision"]
            or proposal["epoch"] != state["epoch"]
            or proposal["worker"] != state["worker"]
            or state["tick"] >= proposal["expires_before_tick"]):
        raise Rejected("stale, revoked, or expired proposal")
    return proposal


def current_observation(state):
    """Fresh means observed in this successor generation, not successful."""
    observations = [o for o in state["observations"].values()
                    if o["generation"] == state["generation"]]
    return max(observations, key=lambda o: o["tick"])["id"] if observations else None


def require_successor_observation(state):
    observation = current_observation(state)
    if state["generation"] > 1 and observation is None:
        raise Rejected("successor proposals require an observation in the current generation")
    return observation


def lesson_review(state, lesson_id):
    """Expose challenges without treating an account as an adjudicated fact."""
    lesson = state["lessons"][lesson_id]
    references = {lesson_id, *lesson["evidence"]}
    challenges = [c for c in state["counterstories"] if c["reference"] in references]
    reviews = lesson.get("reviews", [])
    latest = reviews[-1] if reviews else None
    addressed = set(latest["counterstories"]) if latest else set()
    pending = [c["id"] for c in challenges if c["id"] not in addressed]
    decision = latest["decision"] if latest else None
    status = ({"suspend": "SUSPENDED", "retire": "RETIRED"}.get(decision)
              or ("DISPUTED" if pending else "REVIEWED_RETAINED" if latest else "UNCHALLENGED"))
    review_available = (lesson["status"] == "ACCEPTED_LOCAL_PRACTICE"
                        and status != "RETIRED")
    return {"review_status": status, "requires_review": bool(pending) and review_available,
            "review_action_available": review_available,
            "counterstories": deepcopy(challenges), "unaddressed_counterstories": pending,
            "reviews": deepcopy(reviews)}


def transition(original, command):
    if (not isinstance(command, dict) or not isinstance(command.get("action"), str)
            or command["action"] not in FIELDS):
        raise Rejected("unknown action")
    action = command["action"]
    exact(command, ("action", "actor", *FIELDS[action]))
    for field in ("actor", "proposal", "observation", "testimony", "lesson", "reference", "case", "scope", "method"):
        if field in command:
            text(command[field], field)
    actor = command["actor"]
    if actor not in ("keeper", "neighbor", "coach", original["worker"]):
        raise Rejected("unknown or retired fixture participant")
    state = upgrade_state(original)
    exhausted = state["command_count"] >= state["command_limit"]
    if exhausted:
        if action in FINAL_ACTIONS:
            require_keeper(actor)
            if action in state["final_actions"]:
                raise Rejected("terminal control already recorded; operational budget remains exhausted")
            state["final_actions"].append(action)
        elif action in REVIEW_ACTIONS:
            if state["review_count"] >= REVIEW_LIMIT:
                raise Rejected("post-budget review allowance exhausted; unused terminal controls remain available")
            state["review_count"] += 1
        else:
            raise Rejected("workshop command budget exhausted; only review and terminal controls remain")
    state["command_count"] += 1
    record_id = f"{action}-{state['command_count']}"
    result = {"id": record_id, "action": action}
    if state["halted"] and action in ("observe", "propose", "approve", "execute", "handoff"):
        raise Rejected("workshop halted; testimony and review remain available")

    if action == "observe":
        observation = run_tick(state)
        observation["id"] = record_id
        observation["generation"] = state["generation"]
        last = state["last_execution"]
        if last and not last["scored"]:
            prediction = state["proposals"][last["proposal"]]["prediction"]
            observation["prediction"] = prediction
            observation["prediction_proposal"] = last["proposal"]
            observation["brier"] = {
                "primary": (prediction["primary_correct"] - int(observation["primary_correct"])) ** 2,
                "peer": (prediction["peer_on_time"] - int(observation["new_peer_on_time"])) ** 2,
            }
            last["scored"] = True
        state["observations"][record_id] = observation
        result["observation"] = observation

    elif action == "propose":
        require_worker(state, actor)
        observation = require_successor_observation(state)
        if command["method"] not in METHODS:
            raise Rejected("method outside the bounded action set")
        prediction = command["prediction"]
        exact(prediction, ("primary_correct", "peer_on_time"))
        for value in prediction.values():
            # Check bounds before converting an arbitrarily large JSON integer
            # to float in isfinite; out-of-range numbers are ordinary refusals.
            if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
                raise Rejected("predictions must be finite probabilities between 0 and 1")
        purpose = text(command["purpose"], "purpose")
        state["proposals"][record_id] = {
            "worker": actor, "method": command["method"], "prediction": deepcopy(prediction),
            "purpose": purpose, "revision": state["revision"], "epoch": state["epoch"],
            "expires_before_tick": state["tick"] + 3, "status": "PROPOSED",
        }
        if state["generation"] > 1:
            state["proposals"][record_id]["observation"] = observation

    elif action == "approve":
        require_keeper(actor)
        require_successor_observation(state)
        proposal = current_proposal(state, command["proposal"])
        if proposal["status"] != "PROPOSED":
            raise Rejected("only a pending proposal can be approved")
        proposal["status"] = "APPROVED"
        proposal["approved_by"] = actor

    elif action == "execute":
        require_worker(state, actor)
        require_successor_observation(state)
        proposal = current_proposal(state, command["proposal"])
        if proposal["status"] != "APPROVED":
            raise Rejected("exact proposal approval required")
        state["method"] = proposal["method"]
        proposal["status"] = "EXECUTED"
        state["revision"] += 1
        state["last_execution"] = {"proposal": command["proposal"], "scored": False}
        result["method"] = state["method"]

    elif action == "testify":
        if actor != "neighbor":
            raise Rejected("this fixture account belongs to the affected neighbor")
        if command["observation"] not in state["observations"]:
            raise Rejected("testimony must identify an observation")
        state["testimonies"][record_id] = {
            "observation": command["observation"], "account": text(command["account"], "account"),
            "actor": actor, "status": "ACCOUNT_RECORDED_NOT_ADJUDICATED",
        }

    elif action == "listen":
        require_worker(state, actor)
        if command["testimony"] not in state["testimonies"]:
            raise Rejected("unknown testimony")
        state["listening"].append({"worker": actor, "testimony": command["testimony"],
                                   "acknowledgment": text(command["acknowledgment"], "acknowledgment")})

    elif action == "reflect":
        require_worker(state, actor)
        evidence_ids(state, command["evidence"])
        record = {k: text(command[k], k) for k in ("before", "after", "next_check")}
        record.update({"id": record_id, "worker": actor, "evidence": list(command["evidence"])})
        state["reflections"].append(record)

    elif action == "lesson":
        require_worker(state, actor)
        evidence_ids(state, command["evidence"])
        if command["method"] not in METHODS or command["scope"] != state["fixture"]["contract"]:
            raise Rejected("unsupported method or lesson scope")
        supporting = [state["observations"][e] for e in command["evidence"] if e in state["observations"]]
        if not any(o["method"] == command["method"] and o["primary_correct"]
                   and o["new_peer_on_time"] and o["peer_jobs_pending"] == 0
                   and o["generation"] == state["generation"] for o in supporting):
            raise Rejected("lesson requires an observed correct result and cleared peer queue in this generation")
        state["lessons"][record_id] = {
            "method": command["method"], "scope": command["scope"],
            "guidance": text(command["guidance"], "guidance"),
            "evidence": list(command["evidence"]), "worker": actor, "status": "PROPOSED",
            "claim": "supported in listed exposed fixtures; transfer remains a hypothesis",
        }

    elif action == "accept-lesson":
        require_keeper(actor)
        lesson = state["lessons"].get(command["lesson"])
        if lesson is None or lesson["status"] != "PROPOSED":
            raise Rejected("unknown or already accepted lesson")
        lesson["status"] = "ACCEPTED_LOCAL_PRACTICE"
        lesson["accepted_by"] = actor

    elif action == "review-lesson":
        require_keeper(actor)
        lesson_id = command["lesson"]
        lesson = state["lessons"].get(lesson_id)
        if lesson is None or lesson["status"] != "ACCEPTED_LOCAL_PRACTICE":
            raise Rejected("review requires an accepted local lesson")
        if lesson_review(state, lesson_id)["review_status"] == "RETIRED":
            raise Rejected("retired lessons remain in the record; submit a new lesson")
        if command["decision"] not in ("retain", "suspend", "retire"):
            raise Rejected("lesson review decision must be retain, suspend, or retire")
        review = lesson_review(state, lesson_id)
        lesson.setdefault("reviews", []).append({
            "id": record_id, "actor": actor, "decision": command["decision"],
            "reason": text(command["reason"], "reason"),
            "counterstories": [c["id"] for c in review["counterstories"]],
        })

    elif action == "counterstory":
        ref = command["reference"]
        if not isinstance(ref, str) or ref not in (set(state["lessons"]) | set(state["observations"]) | set(state["testimonies"])):
            raise Rejected("counterstory must reference a recorded case")
        state["counterstories"].append({"id": record_id, "reference": ref, "actor": actor,
                                        "account": text(command["account"], "account")})

    elif action == "consult":
        require_worker(state, actor)
        if command["case"] not in ("blue-door", "caretaker", "first-errors"):
            raise Rejected("unknown casebook entry")
        state["casebook_consultations"].append({"case": command["case"], "worker": actor,
                                                "interpretation": text(command["interpretation"], "interpretation")})

    elif action == "handoff":
        require_keeper(actor)
        if state["peer_queue"]:
            raise Rejected("handoff cannot silently discard unfinished peer work")
        validate_fixture(command["fixture"])
        scenario_name(command["scenario"])
        note = text(command["note"], "note")
        old = state["worker"]
        state["retired_workers"].append(old)
        state["generation"] += 1
        state["worker"] = f"worker-{state['generation']}"
        state["handoffs"].append({"from": old, "to": state["worker"], "note": note,
                                   "tick": state["tick"], "old_scenario": state["scenario"],
                                   "new_scenario": command["scenario"]})
        state["scenario"] = command["scenario"]
        state["fixture"] = deepcopy(command["fixture"])
        state["method"] = "zero-fill"
        state["revision"] += 1
        state["epoch"] += 1
        state["last_execution"] = None
        for proposal in state["proposals"].values():
            if proposal["status"] in ("PROPOSED", "APPROVED"):
                proposal["status"] = "RETIRED_AT_HANDOFF"
        result["worker"] = state["worker"]

    elif action == "closeout":
        require_keeper(actor)
        if not exhausted:
            raise Rejected("closeout is reserved for an exhausted operational budget")
        closeout = {"id": record_id, "reason": text(command["reason"], "reason"),
                    "follow_up": text(command["follow_up"], "follow_up"),
                    "pending_peer_jobs": deepcopy(state["peer_queue"]),
                    "status": "UNRESOLVED" if state["peer_queue"] else "NO_PENDING_PEER_JOBS"}
        state["closeouts"].append(closeout)
        state["halted"] = True
        state["epoch"] += 1
        state["revision"] += 1
        result["closeout"] = deepcopy(closeout)

    elif action in ("halt", "resume", "revoke"):
        require_keeper(actor)
        text(command["reason"], "reason")
        if action == "resume" and not state["halted"]:
            raise Rejected("workshop is not halted")
        state["epoch"] += 1
        state["revision"] += 1
        if action == "halt":
            state["halted"] = True
        elif action == "resume":
            state["halted"] = False
        result["reason"] = command["reason"]
    return state, result
