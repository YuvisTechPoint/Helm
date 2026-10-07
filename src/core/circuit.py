"""Process-local circuit breaker so a down provider does not stall every tenant."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0
    state: str = "closed"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_after: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._state = CircuitState()

    @property
    def status(self) -> str:
        self._maybe_half_open()
        return self._state.state

    def _maybe_half_open(self) -> None:
        if self._state.state == "open" and monotonic() - self._state.opened_at >= self.reset_after:
            self._state.state = "half_open"

    def allow(self) -> bool:
        self._maybe_half_open()
        return self._state.state != "open"

    def record_success(self) -> None:
        self._state = CircuitState(state="closed")

    def record_failure(self) -> None:
        self._state.failures += 1
        if self._state.failures >= self.failure_threshold:
            self._state.state = "open"
            self._state.opened_at = monotonic()

    def call(self, fn, *args, fallback=None, **kwargs):
        if not self.allow():
            if fallback is not None:
                return fallback()
            from core.errors import ProviderUnavailable

            raise ProviderUnavailable(f"circuit open: {self.name}")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            if fallback is not None:
                return fallback()
            raise
        self.record_success()
        return result
