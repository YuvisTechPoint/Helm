from youtube.models import MetricSnapshot, OptimizationChange, PublishedVideo


class DbVideoStore:
    def __init__(self, session):
        self.session = session

    def get_by_key(self, key: str) -> dict | None:
        row = self.session.query(PublishedVideo).filter_by(idempotency_key=key).one_or_none()
        if row is None:
            return None
        return {
            "idempotency_key": row.idempotency_key,
            "youtube_id": row.youtube_id,
            "privacy_status": row.privacy_status,
            "title": row.title,
            "metadata": row.payload,
        }

    def save(self, row: dict) -> dict:
        existing = self.session.query(PublishedVideo).filter_by(idempotency_key=row["idempotency_key"]).one_or_none()
        if existing is None:
            existing = PublishedVideo(
                idempotency_key=row["idempotency_key"],
                youtube_id=row["youtube_id"],
                privacy_status=row["privacy_status"],
                title=row["title"],
                contains_synthetic_media=1,
                made_for_kids=0,
                payload=row.get("metadata", {}),
            )
            self.session.add(existing)
        else:
            existing.youtube_id = row["youtube_id"]
            existing.privacy_status = row["privacy_status"]
            existing.payload = row.get("metadata", {})
        self.session.commit()
        return row

    def list_all(self) -> list[dict]:
        return [
            {
                "idempotency_key": row.idempotency_key,
                "youtube_id": row.youtube_id,
                "privacy_status": row.privacy_status,
                "title": row.title,
            }
            for row in self.session.query(PublishedVideo).all()
        ]


class DbMetricStore:
    def __init__(self, session):
        self.session = session

    def save(self, video_id: str, label: str, metrics: dict, captured_at: str) -> dict:
        row = self.session.query(MetricSnapshot).filter_by(video_id=video_id, label=label).one_or_none()
        if row is None:
            row = MetricSnapshot(video_id=video_id, label=label, metrics=metrics, captured_at=captured_at)
            self.session.add(row)
        else:
            row.metrics = metrics
            row.captured_at = captured_at
        self.session.commit()
        return {"video_id": video_id, "label": label, "metrics": metrics, "captured_at": captured_at}


class DbOptimizerStore:
    def __init__(self, session):
        self.session = session

    def record_change(self, video_id: str, lever: str, status: str, baseline: str, payload: dict) -> dict:
        row = OptimizationChange(video_id=video_id, lever=lever, status=status, baseline=baseline, payload=payload)
        self.session.add(row)
        self.session.commit()
        return {"id": row.id, "video_id": video_id, "lever": lever, "status": status}
