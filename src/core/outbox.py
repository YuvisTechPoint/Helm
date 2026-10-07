"""Transactional outbox — events commit atomically with domain state."""

from __future__ import annotations

import hashlib
import uuid

from core.models import Event, OutboxMessage, StateTransition
from core.timeutil import utcnow


class Outbox:
    def __init__(self, session=None):
        self.session = session
        self._memory: list[dict] = []

    def publish(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
        tenant_id: str | None = None,
        actor: str = "system",
        event_id: str | None = None,
    ) -> dict:
        event_id = event_id or uuid.uuid4().hex
        now = utcnow().isoformat()
        row = {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": payload,
            "status": "pending",
            "attempts": 0,
            "created_at": now,
            "published_at": None,
        }
        if self.session is None:
            self._memory.append(row)
            return row
        self.session.add(
            Event(tenant_id=tenant_id, type=event_type, actor=actor, payload=payload, created_at=now)
        )
        self.session.add(
            OutboxMessage(
                event_id=event_id,
                tenant_id=tenant_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
                status="pending",
                created_at=now,
            )
        )
        self.session.commit()
        return row

    def record_transition(
        self,
        *,
        machine: str,
        aggregate_id: str,
        from_state: str,
        to_state: str,
        tenant_id: str | None = None,
        actor: str = "system",
        reason: str = "",
    ) -> None:
        if self.session is None:
            return
        self.session.add(
            StateTransition(
                machine=machine,
                aggregate_id=aggregate_id,
                tenant_id=tenant_id,
                from_state=from_state,
                to_state=to_state,
                actor=actor,
                reason=reason,
                created_at=utcnow().isoformat(),
            )
        )

    def drain(self, limit: int = 50) -> dict:
        """Mark pending outbox rows published (CRM webhook, notifications)."""
        if self.session is None:
            pending = [row for row in self._memory if row["status"] == "pending"][:limit]
            for row in pending:
                row["status"] = "published"
                row["published_at"] = utcnow().isoformat()
            return {"published": len(pending)}

        from core.config import get_settings

        settings = get_settings()
        rows = (
            self.session.query(OutboxMessage)
            .filter_by(status="pending")
            .order_by(OutboxMessage.id.asc())
            .limit(limit)
            .all()
        )
        published = 0
        for row in rows:
            try:
                if settings.crm_webhook_url:
                    import httpx

                    httpx.post(settings.crm_webhook_url, json={"event_type": row.event_type, "payload": row.payload}, timeout=10)
                row.status = "published"
                row.published_at = utcnow().isoformat()
                published += 1
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)
                if row.attempts >= 5:
                    row.status = "dead_letter"
        if rows:
            self.session.commit()
        return {"published": published, "pending": self.session.query(OutboxMessage).filter_by(status="pending").count()}
