from core.models import Event
from core.timeutil import utcnow


class EventLog:
    """Append-only log. Updates are rejected."""

    def __init__(self, session=None):
        self.session = session
        self.memory: list[dict] = []

    def append(self, type_: str, actor: str, payload: dict | None = None, tenant_id: str | None = None) -> dict:
        row = {
            "tenant_id": tenant_id,
            "type": type_,
            "actor": actor,
            "payload": payload or {},
            "created_at": utcnow().isoformat(),
        }
        self.memory.append(row)
        if self.session is not None:
            self.session.add(
                Event(
                    tenant_id=tenant_id,
                    type=type_,
                    actor=actor,
                    payload=payload or {},
                    created_at=row["created_at"],
                )
            )
            self.session.commit()
        return row

    def update(self, *_args, **_kwargs):
        raise RuntimeError("events are append-only")

    def delete(self, *_args, **_kwargs):
        raise RuntimeError("events are append-only")
