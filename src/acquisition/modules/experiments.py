"""M12 — weekly auto-experiments (FR-12.2) on angle, subject line, sequence length and send time."""

import copy
import hashlib

from acquisition.close import promote_experiment
from core.timeutil import utcnow

STATE_KEY = "experiments"
CHANGES_KEY = "experiment_changes"

DIMENSIONS: dict[str, list[str]] = {
    "angle": ["proof-first", "pain-first"],
    "subject": ["question", "observation"],
    "sequence_length": ["4-touch", "3-touch"],
    "send_time": ["morning", "afternoon"],
}

CHALLENGERS: dict[str, list[str]] = {
    "angle": ["insight-first", "question-first"],
    "subject": ["first-name", "company-name"],
    "sequence_length": ["4-touch", "3-touch"],
    "send_time": ["midday", "morning", "afternoon"],
}


def _variant(name: str, dimension: str, active: bool) -> dict:
    return {"name": name, "dimension": dimension, "sends": 0, "positive": 0, "active": active, "retired": False}


def default_state() -> dict:
    return {
        dimension: [_variant(name, dimension, index == 0) for index, name in enumerate(names)]
        for dimension, names in DIMENSIONS.items()
    }


class ExperimentStore:
    def __init__(self, repo=None, tenant_id: str = "local"):
        self.repo = repo
        self.tenant_id = tenant_id
        self._state = default_state()
        self._changes: list[dict] = []

    def _load(self, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or self.tenant_id
        if self.repo is None:
            return self._state
        state = self.repo.get_state(tenant_id, STATE_KEY)
        if not state:
            state = self.repo.set_state(tenant_id, STATE_KEY, default_state())
        return state

    def _save(self, state: dict, tenant_id: str | None = None) -> None:
        if self.repo is not None:
            self.repo.set_state(tenant_id or self.tenant_id, STATE_KEY, copy.deepcopy(state))
        else:
            self._state = state

    @property
    def variants(self) -> list[dict]:
        return self._load()["angle"]

    def assign(self, email: str, tenant_id: str | None = None) -> dict[str, str]:
        state = self._load(tenant_id)
        chosen = {}
        for dimension, variants in state.items():
            live = [variant for variant in variants if not variant.get("retired")]
            digest = int(hashlib.sha256(f"{email.lower()}:{dimension}".encode()).hexdigest(), 16)
            chosen[dimension] = live[digest % len(live)]["name"] if live else DIMENSIONS[dimension][0]
        return chosen

    def record_send(self, name: str, positive: bool = False, dimension: str = "angle", tenant_id: str | None = None) -> None:
        state = self._load(tenant_id)
        for variant in state.get(dimension, []):
            if variant["name"] == name:
                if positive:
                    variant["positive"] += 1
                else:
                    variant["sends"] += 1
        self._save(state, tenant_id)

    def record_assignment(self, assignment: dict[str, str], positive: bool = False, tenant_id: str | None = None) -> None:
        for dimension, name in assignment.items():
            self.record_send(name, positive=positive, dimension=dimension, tenant_id=tenant_id)

    def promote(self, min_sends: int = 20, tenant_id: str | None = None) -> dict | None:
        """Preview the angle winner without retiring anything."""
        candidates = copy.deepcopy(self._load(tenant_id)["angle"])
        return promote_experiment(candidates, min_sends=min_sends)

    def run_weekly(self, min_sends: int = 20, tenant_id: str | None = None) -> list[dict]:
        state = self._load(tenant_id)
        changes = []
        for dimension, variants in state.items():
            live = [variant for variant in variants if not variant.get("retired")]
            previous = next((variant["name"] for variant in live if variant.get("active")), None)
            winner = promote_experiment(live, min_sends=min_sends)
            if winner is None:
                continue
            retired = [variant["name"] for variant in live if variant.get("retired")]
            rate = winner["positive"] / winner["sends"] if winner["sends"] else 0.0
            known = {variant["name"] for variant in variants}
            challenger = next((name for name in CHALLENGERS[dimension] if name not in known), None)
            if challenger:
                variants.append(_variant(challenger, dimension, False))
            change = {
                "at": utcnow().isoformat(),
                "dimension": dimension,
                "winner": winner["name"],
                "previous": previous,
                "retired": retired,
                "challenger": challenger,
                "summary": f"{dimension} now uses '{winner['name']}'",
                "why": f"{rate:.0%} positive reply rate over {winner['sends']} sends, best among live variants",
            }
            changes.append(change)
        self._save(state, tenant_id)
        if changes:
            history = self.changes(tenant_id) + changes
            if self.repo is not None:
                self.repo.set_state(tenant_id or self.tenant_id, CHANGES_KEY, {"items": history[-200:]})
            else:
                self._changes = history
        return changes

    def changes(self, tenant_id: str | None = None) -> list[dict]:
        if self.repo is None:
            return list(self._changes)
        return list(self.repo.get_state(tenant_id or self.tenant_id, CHANGES_KEY, {"items": []}).get("items", []))

    def list(self, tenant_id: str | None = None) -> list[dict]:
        state = self._load(tenant_id)
        return [variant for variants in state.values() for variant in variants]

    def by_dimension(self, tenant_id: str | None = None) -> dict:
        return self._load(tenant_id)
