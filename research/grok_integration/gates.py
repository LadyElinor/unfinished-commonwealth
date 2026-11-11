"""Fail-closed, pure authorization checks for synthetic agent actions.

This is an educational policy boundary, not a production security gateway.
An external executor must enforce its decision independently of the agent.
"""
from dataclasses import dataclass
from typing import Mapping

ALLOWED_ACTIONS = frozenset({"simulate", "read_public", "publish", "robot_command"})

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str

def authorize(request: Mapping[str, object], policy: Mapping[str, object]) -> Decision:
    """Deny on missing/malformed fields; do not infer privileges from identity."""
    try:
        if not isinstance(request, Mapping) or not isinstance(policy, Mapping):
            return Decision(False, "invalid_input")
        actor, action, resource = (request.get(k) for k in ("actor", "action", "resource"))
        if any(not isinstance(v, str) or not v.strip() for v in (actor, action, resource)):
            return Decision(False, "missing_identity_or_scope")
        if action not in ALLOWED_ACTIONS:
            return Decision(False, "unknown_action")
        grants = policy.get("grants")
        if not isinstance(grants, Mapping):
            return Decision(False, "missing_policy")
        permissions = grants.get(actor)
        if not isinstance(permissions, Mapping):
            return Decision(False, "no_actor_grants")
        resources = permissions.get(action)
        if not isinstance(resources, (tuple, list, frozenset, set)) or not all(isinstance(x, str) for x in resources):
            return Decision(False, "invalid_grant")
        if resource not in resources:
            return Decision(False, "scope_denied")
        if action in ("publish", "robot_command"):
            approval = request.get("approval")
            approvals = policy.get("approvals")
            if not isinstance(approval, str) or not approval or not isinstance(approvals, Mapping):
                return Decision(False, "approval_required")
            approved = approvals.get(approval)
            if not isinstance(approved, Mapping) or approved.get("actor") != actor or approved.get("action") != action or approved.get("resource") != resource or approved.get("approved") is not True:
                return Decision(False, "approval_mismatch")
        return Decision(True, "authorized")
    except (TypeError, ValueError):
        return Decision(False, "validation_error")
