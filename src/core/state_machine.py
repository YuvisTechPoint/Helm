"""Explicit finite-state machines with auditable transitions."""

from __future__ import annotations

from dataclasses import dataclass

from core.errors import InvalidTransition


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    actor: str = "system"
    reason: str = ""


class StateMachine:
    def __init__(self, name: str, transitions: dict[str, set[str]], terminal: set[str] | None = None):
        self.name = name
        self.transitions = transitions
        self.terminal = terminal or set()

    def can_transition(self, current: str | None, target: str) -> bool:
        current = current or "unknown"
        if current == target:
            return True
        if current in self.terminal:
            return False
        allowed = self.transitions.get(current, set())
        return target in allowed

    def transition(self, current: str | None, target: str, *, actor: str = "system", reason: str = "") -> Transition:
        current = current or "unknown"
        if not self.can_transition(current, target):
            raise InvalidTransition(f"{self.name}: cannot move {current} → {target}")
        return Transition(from_state=current, to_state=target, actor=actor, reason=reason)
