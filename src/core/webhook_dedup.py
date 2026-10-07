"""Idempotent webhook ingress — reject duplicate provider event IDs."""

from __future__ import annotations

import hashlib

from core.models import WebhookReceipt
from core.timeutil import utcnow


class WebhookDedup:
    def __init__(self, session=None):
        self.session = session
        self._seen: set[tuple[str, str]] = set()

    @staticmethod
    def payload_hash(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()

    def seen(self, provider: str, event_id: str) -> bool:
        key = (provider, event_id)
        if key in self._seen:
            return True
        if self.session is None:
            return False
        return (
            self.session.query(WebhookReceipt)
            .filter_by(provider=provider, event_id=event_id)
            .first()
            is not None
        )

    def record(self, provider: str, event_id: str, body: bytes) -> dict:
        key = (provider, event_id)
        if self.seen(provider, event_id):
            return {"duplicate": True, "provider": provider, "event_id": event_id}
        row = {
            "provider": provider,
            "event_id": event_id,
            "payload_hash": self.payload_hash(body),
            "processed_at": utcnow().isoformat(),
        }
        self._seen.add(key)
        if self.session is not None:
            self.session.add(WebhookReceipt(**row))
            self.session.commit()
        return {"duplicate": False, **row}
