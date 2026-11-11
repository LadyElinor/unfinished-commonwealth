"""Offline demonstration of signed, one-use authorization.

HMAC is suitable only for a verifier and signer that share a secret outside the
agent's control. This in-memory replay ledger is not durable or distributed.
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Mapping
from .gates import authorize, Decision

def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def sign_approval(payload: Mapping, key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("key must be at least 32 bytes")
    return hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()

@dataclass
class Gateway:
    """Gate a synthetic action, atomically consuming a nonce in one process."""
    key: bytes
    used_nonces: set

    def __post_init__(self):
        if not isinstance(self.key, bytes) or len(self.key) < 32:
            raise ValueError("key must be at least 32 bytes")

    def decide(self, request: Mapping, policy: Mapping, approval: Mapping,
               signature: str, now: int | None = None) -> Decision:
        try:
            if not isinstance(approval, Mapping) or not isinstance(request, Mapping):
                return Decision(False, "invalid_input")
            if not isinstance(signature, str):
                return Decision(False, "invalid_signature")
            expected = sign_approval(approval, self.key)
            if not hmac.compare_digest(signature, expected):
                return Decision(False, "invalid_signature")
            nonce = approval.get("nonce")
            issued = approval.get("issued_at")
            expires = approval.get("expires_at")
            if not isinstance(nonce, str) or not nonce or type(issued) is not int or type(expires) is not int:
                return Decision(False, "invalid_approval_fields")
            clock = int(time.time()) if now is None else now
            if type(clock) is not int or issued > clock or expires < clock or expires <= issued:
                return Decision(False, "expired_or_future_approval")
            if nonce in self.used_nonces:
                return Decision(False, "replayed_approval")
            if any(approval.get(k) != request.get(k) for k in ("actor", "action", "resource")):
                return Decision(False, "approval_scope_mismatch")
            if approval.get("approved") is not True:
                return Decision(False, "approval_not_granted")
            # Require the base policy's resource grant without accepting its
            # legacy, unsigned approval list as the authority.
            base_request = dict(request)
            base_request.pop("approval", None)
            if request.get("action") in ("publish", "robot_command"):
                synthetic_policy = dict(policy)
                synthetic_policy["approvals"] = {"verified": {
                    "actor": request.get("actor"), "action": request.get("action"),
                    "resource": request.get("resource"), "approved": True
                }}
                base_request["approval"] = "verified"
                decision = authorize(base_request, synthetic_policy)
            else:
                decision = authorize(base_request, policy)
            if not decision.allowed:
                return decision
            self.used_nonces.add(nonce)
            return Decision(True, "signed_authorization")
        except (TypeError, ValueError, OverflowError):
            return Decision(False, "validation_error")
