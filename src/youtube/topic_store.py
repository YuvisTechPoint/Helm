"""Persist YouTube topic lifecycle in the database."""

from __future__ import annotations

from youtube.models import TopicRow
from youtube.topic_state import TOPIC_MACHINE
from core.timeutil import utcnow


class TopicStore:
    def __init__(self, session=None):
        self.session = session
        self._memory: dict[str, dict] = {}

    def upsert(self, slug: str, title: str, cluster: str, kind: str, score: int = 0) -> dict:
        row = {
            "slug": slug,
            "title": title,
            "cluster": cluster,
            "kind": kind,
            "status": "backlog",
            "score": score,
            "planned_on": None,
        }
        if self.session is None:
            self._memory[slug] = row
            return row
        stored = self.session.query(TopicRow).filter_by(slug=slug).one_or_none()
        if stored is None:
            self.session.add(TopicRow(**row))
        else:
            row["status"] = stored.status
        self.session.commit()
        return row

    def get(self, slug: str) -> dict | None:
        if self.session is None:
            return self._memory.get(slug)
        stored = self.session.query(TopicRow).filter_by(slug=slug).one_or_none()
        if stored is None:
            return None
        return {
            "slug": stored.slug,
            "title": stored.title,
            "cluster": stored.cluster,
            "kind": stored.kind,
            "status": stored.status,
            "score": stored.score,
            "planned_on": stored.planned_on,
        }

    def transition(self, slug: str, target: str, *, actor: str = "pipeline", reason: str = "") -> dict:
        current = self.get(slug)
        if current is None:
            raise KeyError(f"unknown topic: {slug}")
        change = TOPIC_MACHINE.transition(current["status"], target, actor=actor, reason=reason)
        current["status"] = change.to_state
        if self.session is not None:
            stored = self.session.query(TopicRow).filter_by(slug=slug).one()
            stored.status = change.to_state
            from core.models import StateTransition

            self.session.add(
                StateTransition(
                    machine="youtube_topic",
                    aggregate_id=slug,
                    from_state=change.from_state,
                    to_state=change.to_state,
                    actor=actor,
                    reason=reason,
                    created_at=utcnow().isoformat(),
                )
            )
            self.session.commit()
        else:
            self._memory[slug] = current
        return current
