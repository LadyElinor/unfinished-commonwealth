"""Synthetic authorization gate: never connects to a network or hardware."""
from dataclasses import dataclass, field
from typing import FrozenSet

@dataclass(frozen=True)
class Principal:
    identity: str
    teams: FrozenSet[str] = frozenset()

@dataclass
class Gate:
    approvals: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    revoked: set[str] = field(default_factory=set)
    audit: list[dict] = field(default_factory=list)

    def check(self, principal: Principal | None, resource_team: str, action: str,
              token: str | None = None, *, robotic: bool = False) -> bool:
        identity = principal.identity if principal else None
        authorized = principal is not None and resource_team in principal.teams
        # Action classification belongs to the gate. The legacy flag may only
        # request stricter handling, never relax a protected action.
        requires_approval = action == "move_simulated" or robotic
        authorized = authorized and action in {"read_private", "move_simulated"}
        if requires_approval:
            authorized = (authorized and token is not None and token not in self.revoked
                          and self.approvals.get(token) == (identity, resource_team, action))
        self.audit.append({"principal": identity, "team": resource_team,
                           "action": action, "robotic": requires_approval, "allowed": bool(authorized)})
        return bool(authorized)

    def revoke(self, token: str) -> None:
        self.revoked.add(token)
        self.audit.append({"event": "revocation", "token": token})
