from core.models import ExceptionItem
from core.timeutil import utcnow


class ExceptionStore:
    def __init__(self, session=None):
        self.session = session
        self.memory: list[dict] = []

    def add(self, kind: str, message: str, scope: str = "youtube") -> dict:
        row = {
            "id": len(self.memory) + 1,
            "kind": kind,
            "message": message,
            "scope": scope,
            "resolved": False,
            "created_at": utcnow().isoformat(),
        }
        self.memory.append(row)
        if self.session is not None:
            item = ExceptionItem(kind=f"{scope}:{kind}", message=message, resolved=0, created_at=row["created_at"])
            self.session.add(item)
            self.session.commit()
            row["id"] = item.id
        return row

    def list_open(self, scope: str | None = None) -> list[dict]:
        rows = [row for row in self.memory if not row["resolved"]]
        if scope:
            rows = [row for row in rows if row.get("scope") == scope]
        if self.session is not None:
            query = self.session.query(ExceptionItem).filter_by(resolved=0)
            db_rows = []
            for item in query.all():
                if scope and not item.kind.startswith(f"{scope}:"):
                    continue
                db_rows.append(
                    {
                        "id": item.id,
                        "kind": item.kind.split(":", 1)[-1],
                        "message": item.message,
                        "scope": item.kind.split(":", 1)[0] if ":" in item.kind else "youtube",
                        "resolved": False,
                        "created_at": item.created_at,
                    }
                )
            if db_rows:
                return db_rows
        return rows

    def resolve(self, item_id: int) -> bool:
        for row in self.memory:
            if row["id"] == item_id:
                row["resolved"] = True
                return True
        if self.session is not None:
            item = self.session.query(ExceptionItem).filter_by(id=item_id).one_or_none()
            if item is None:
                return False
            item.resolved = 1
            self.session.commit()
            return True
        return False
