import uuid

from core.models import Job
from core.timeutil import utcnow


def backoff_seconds(attempt: int) -> int:
    return min(300, 2 ** max(attempt, 0))


class JobBook:
    def __init__(self, session=None):
        self.session = session
        self.jobs: dict[str, dict] = {}

    def begin(self, idempotency_key: str, kind: str, payload: dict | None = None) -> tuple[dict, bool]:
        if idempotency_key in self.jobs:
            return self.jobs[idempotency_key], False
        if self.session is not None:
            existing = self.session.query(Job).filter_by(idempotency_key=idempotency_key).one_or_none()
            if existing is not None:
                row = _from_model(existing)
                self.jobs[idempotency_key] = row
                return row, False
        row = {
            "run_id": uuid.uuid4().hex,
            "idempotency_key": idempotency_key,
            "kind": kind,
            "status": "pending",
            "attempts": 0,
            "payload": payload or {},
            "last_error": "",
            "result": None,
            "updated_at": utcnow().isoformat(),
        }
        self.jobs[idempotency_key] = row
        if self.session is not None:
            self.session.add(
                Job(
                    run_id=row["run_id"],
                    idempotency_key=idempotency_key,
                    kind=kind,
                    status="pending",
                    attempts=0,
                    payload=payload or {},
                    last_error="",
                    updated_at=row["updated_at"],
                )
            )
            self.session.commit()
        return row, True

    def succeed(self, idempotency_key: str, result) -> dict:
        row = self.jobs[idempotency_key]
        row["status"] = "succeeded"
        row["result"] = result
        row["updated_at"] = utcnow().isoformat()
        self._sync(row)
        return row

    def fail(self, idempotency_key: str, error: str, max_attempts: int = 3) -> dict:
        row = self.jobs[idempotency_key]
        row["attempts"] += 1
        row["last_error"] = error
        row["status"] = "dead_letter" if row["attempts"] >= max_attempts else "retry"
        row["retry_in"] = None if row["status"] == "dead_letter" else backoff_seconds(row["attempts"])
        row["updated_at"] = utcnow().isoformat()
        self._sync(row)
        return row

    def _sync(self, row: dict) -> None:
        if self.session is None:
            return
        stored = self.session.query(Job).filter_by(idempotency_key=row["idempotency_key"]).one()
        stored.status = row["status"]
        stored.attempts = row["attempts"]
        stored.last_error = row["last_error"]
        stored.updated_at = row["updated_at"]
        self.session.commit()


def _from_model(job: Job) -> dict:
    return {
        "run_id": job.run_id,
        "idempotency_key": job.idempotency_key,
        "kind": job.kind,
        "status": job.status,
        "attempts": job.attempts,
        "payload": job.payload,
        "last_error": job.last_error,
        "result": None,
        "updated_at": job.updated_at,
    }


class ExceptionQueue:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, kind: str, message: str) -> dict:
        item = {"id": len(self.items) + 1, "kind": kind, "message": message, "resolved": False}
        self.items.append(item)
        return item

    def open_items(self) -> list[dict]:
        return [item for item in self.items if not item["resolved"]]

    def resolve(self, item_id: int) -> None:
        for item in self.items:
            if item["id"] == item_id:
                item["resolved"] = True
