from core.models import KillSwitch
from core.timeutil import utcnow


class KillSwitchBoard:
    def __init__(self, session=None):
        self.session = session
        self.scopes: dict[str, dict] = {}

    def set(self, scope: str, active: bool, reason: str = "") -> None:
        row = {"scope": scope, "active": active, "reason": reason, "updated_at": utcnow().isoformat()}
        self.scopes[scope] = row
        if self.session is not None:
            existing = self.session.query(KillSwitch).filter_by(scope=scope).one_or_none()
            if existing is None:
                self.session.add(KillSwitch(scope=scope, active=int(active), reason=reason, updated_at=row["updated_at"]))
            else:
                existing.active = int(active)
                existing.reason = reason
                existing.updated_at = row["updated_at"]
            self.session.commit()

    def active(self, scope: str) -> bool:
        if self.scopes.get("global", {}).get("active"):
            return True
        if self.scopes.get(scope, {}).get("active"):
            return True
        if self.session is not None:
            rows = self.session.query(KillSwitch).filter(KillSwitch.scope.in_(["global", scope])).all()
            return any(row.active for row in rows)
        return False

    def reason(self, scope: str) -> str:
        if self.scopes.get("global", {}).get("active"):
            return self.scopes["global"].get("reason", "")
        return self.scopes.get(scope, {}).get("reason", "")
