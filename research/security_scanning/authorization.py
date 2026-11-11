"""Synthetic authorization gate: never connects to a network or hardware."""
from dataclasses import dataclass, field
from typing import FrozenSet
import hashlib
import json

@dataclass(frozen=True)
class Principal:
    identity: str
    teams: FrozenSet[str] = frozenset()

def argument_digest(arguments: dict) -> str:
    """Digest the JSON argument object as presented for review, with strict field types."""
    def validate(value):
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError("JSON object keys must be strings")
                validate(item)
        elif type(value) is list:
            for item in value:
                validate(item)
        elif value is not None and type(value) not in (str, int, float, bool):
            raise ValueError("unsupported JSON argument type")

    if type(arguments) is not dict:
        raise ValueError("arguments must be a JSON object")
    validate(arguments)
    wire = json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(("simulation-arguments-v1\n" + wire).encode()).hexdigest()


@dataclass(frozen=True)
class CommandApproval:
    identity: str
    team: str
    action: str
    arguments_sha256: str

    @classmethod
    def for_arguments(cls, identity: str, team: str, action: str, arguments: dict):
        return cls(identity, team, action, argument_digest(arguments))


@dataclass
class Gate:
    approvals: dict[str, tuple[str, str, str] | CommandApproval] = field(default_factory=dict)
    revoked: set[str] = field(default_factory=set)
    audit: list[dict] = field(default_factory=list)

    def check(self, principal: Principal | None, resource_team: str, action: str,
              token: str | None = None, *, robotic: bool = False, arguments: dict | None = None) -> bool:
        identity = principal.identity if principal else None
        authorized = principal is not None and resource_team in principal.teams
        # Action classification belongs to the gate. The legacy flag may only
        # request stricter handling, never relax a protected action.
        requires_approval = action != "read_private" or robotic or arguments is not None
        expected: tuple | CommandApproval = (identity, resource_team, action)
        argument_record = {}
        if arguments is not None:
            try:
                digest = argument_digest(arguments)
                expected = CommandApproval(identity, resource_team, action, digest)
                argument_record["arguments_sha256"] = digest
            except (ValueError, TypeError, RecursionError):
                authorized = False
                argument_record["argument_error"] = "invalid JSON arguments"
        if requires_approval:
            authorized = (authorized and token is not None and token not in self.revoked
                          and self.approvals.get(token) == expected)
        self.audit.append({"principal": identity, "team": resource_team,
                           "action": action, "robotic": requires_approval, "allowed": bool(authorized), **argument_record})
        return bool(authorized)

    def revoke(self, token: str) -> None:
        self.revoked.add(token)
        self.audit.append({"event": "revocation", "token": token})
