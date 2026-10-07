from core.errors import BudgetExceeded
from core.models import Budget


class BudgetGuard:
    """YouTube production pauses at 90%. Acquisition hard-stops at 100%."""

    def __init__(self, session=None):
        self.session = session
        self.rows: dict[tuple[str, str], dict] = {}

    def _stored(self, tenant_id: str, provider: str):
        if self.session is None:
            return None
        return (
            self.session.query(Budget)
            .filter_by(tenant_id=tenant_id, provider=provider)
            .order_by(Budget.id.desc())
            .first()
        )

    def configure(self, tenant_id: str, provider: str, cap_cents: int) -> None:
        """Idempotent across process restarts: keeps spend already recorded for this tenant/provider."""
        stored = self._stored(tenant_id, provider)
        spent = stored.spent_cents if stored is not None else 0
        self.rows[(tenant_id, provider)] = {
            "cap_cents": cap_cents,
            "spent_cents": spent,
            "paused": spent >= cap_cents,
        }
        if self.session is not None:
            if stored is None:
                self.session.add(Budget(tenant_id=tenant_id, provider=provider, cap_cents=cap_cents, spent_cents=0, paused=0))
            else:
                stored.cap_cents = cap_cents
                stored.paused = int(spent >= cap_cents)
            self.session.commit()

    def ensure(self, tenant_id: str, provider: str, cap_cents: int) -> None:
        if (tenant_id, provider) not in self.rows:
            self.configure(tenant_id, provider, cap_cents)

    def _row(self, tenant_id: str, provider: str) -> dict:
        key = (tenant_id, provider)
        if key not in self.rows:
            raise BudgetExceeded(f"no budget configured for {tenant_id}/{provider}")
        return self.rows[key]

    def can_spend(self, tenant_id: str, provider: str, cents: int) -> bool:
        row = self._row(tenant_id, provider)
        return row["spent_cents"] + cents <= row["cap_cents"]

    def charge(self, tenant_id: str, provider: str, cents: int, *, pause_at: float = 1.0) -> dict:
        row = self._row(tenant_id, provider)
        if row["spent_cents"] + cents > row["cap_cents"]:
            raise BudgetExceeded("budget cap reached")
        row["spent_cents"] += cents
        if row["spent_cents"] >= pause_at * row["cap_cents"]:
            row["paused"] = True
        stored = self._stored(tenant_id, provider)
        if stored is not None:
            stored.spent_cents = row["spent_cents"]
            stored.paused = int(row["paused"])
            self.session.commit()
        return row

    def production_allowed(self, tenant_id: str, provider: str) -> bool:
        return not self._row(tenant_id, provider)["paused"]
