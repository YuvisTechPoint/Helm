from datetime import date, datetime, timedelta, timezone

from acquisition.funnel import observe_mailbox
from acquisition.models import MailboxRow

WARMUP_DAYS = 14
MIN_SENDS_FOR_RATES = 20
META_KEY = "mailbox_meta"

DEFAULT_MAILBOX = {
    "tenant_id": "local",
    "address": "ava@outreach.example",
    "domain": "outreach.example",
    "daily_cap": 30,
    "paused": False,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MailboxStore:
    """Sending mailboxes on secondary domains: warm-up, rotation, per-box caps and auto-pause."""

    def __init__(self, session=None, repo=None):
        self.session = session
        self.repo = repo
        self._memory: list[dict] = []
        self._meta: dict[str, dict] = {}

    def _load_meta(self, tenant_id: str) -> dict:
        if self.repo is not None:
            return self.repo.get_state(tenant_id, META_KEY, {})
        return self._meta.setdefault(tenant_id, {})

    def _save_meta(self, tenant_id: str, meta: dict) -> None:
        if self.repo is not None:
            self.repo.set_state(tenant_id, META_KEY, meta)
        else:
            self._meta[tenant_id] = meta

    def _rows(self, tenant_id: str) -> list[dict]:
        if self.session is not None:
            rows = self.session.query(MailboxRow).filter_by(tenant_id=tenant_id).all()
            return [
                {"tenant_id": row.tenant_id, "address": row.address, "domain": row.domain, "daily_cap": row.daily_cap, "paused": bool(row.paused)}
                for row in rows
            ]
        return [dict(box) for box in self._memory if box["tenant_id"] == tenant_id]

    def _decorate(self, box: dict, meta: dict) -> dict:
        info = meta.get(box["address"], {})
        today = date.today().isoformat()
        sent = info.get("sent", 0)
        warmup_started = info.get("warmup_started")
        warmed = warmup_started is None or _now() - datetime.fromisoformat(warmup_started) >= timedelta(days=WARMUP_DAYS)
        paused = bool(box.get("paused") or info.get("paused"))
        return {
            **box,
            "paused": paused,
            "sent_today": info.get("sent_today", 0) if info.get("day") == today else 0,
            "sent_total": sent,
            "bounce_rate": round(info.get("bounces", 0) / sent, 4) if sent else 0.0,
            "complaint_rate": round(info.get("complaints", 0) / sent, 4) if sent else 0.0,
            "inbox_rate": info.get("inbox_rate", 0.95),
            "warmup_started": warmup_started,
            "warmed": warmed,
            "ready": warmed and not paused,
        }

    def list_mailboxes(self, tenant_id: str) -> list[dict]:
        rows = self._rows(tenant_id)
        if not rows:
            rows = [self.ensure_default(tenant_id)]
        meta = self._load_meta(tenant_id)
        return [self._decorate(box, meta) for box in rows]

    def ensure_default(self, tenant_id: str) -> dict:
        rows = self._rows(tenant_id)
        if rows:
            return rows[0]
        box = {**DEFAULT_MAILBOX, "tenant_id": tenant_id}
        if tenant_id != DEFAULT_MAILBOX["tenant_id"]:
            box["address"] = f"ava+{tenant_id}@outreach.example"
        if self.session is not None:
            exists = self.session.query(MailboxRow).filter_by(address=box["address"]).one_or_none()
            if exists is None:
                self.session.add(MailboxRow(tenant_id=tenant_id, address=box["address"], domain=box["domain"], daily_cap=box["daily_cap"], paused=0))
                self.session.commit()
        else:
            self._memory.append(box)
        return box

    def add_mailbox(self, tenant_id: str, address: str, domain: str, daily_cap: int = 30, warmed: bool = False) -> dict:
        address = address.lower()
        if self.session is not None:
            row = self.session.query(MailboxRow).filter_by(address=address).one_or_none()
            if row is not None and row.tenant_id != tenant_id:
                raise ValueError("mailbox belongs to another tenant")
            if row is None:
                self.session.add(MailboxRow(tenant_id=tenant_id, address=address, domain=domain, daily_cap=daily_cap, paused=0))
            else:
                row.daily_cap = daily_cap
            self.session.commit()
        elif not any(box["address"] == address for box in self._memory):
            self._memory.append({"tenant_id": tenant_id, "address": address, "domain": domain, "daily_cap": daily_cap, "paused": False})
        meta = self._load_meta(tenant_id)
        meta.setdefault(address, {})["warmup_started"] = None if warmed else _now().isoformat()
        self._save_meta(tenant_id, meta)
        return next(box for box in self.list_mailboxes(tenant_id) if box["address"] == address)

    def pick(self, tenant_id: str) -> dict | None:
        """Rotate to the ready mailbox with the most remaining headroom today."""
        ready = [box for box in self.list_mailboxes(tenant_id) if box["ready"] and box["sent_today"] < box["daily_cap"]]
        if not ready:
            return None
        return min(ready, key=lambda box: box["sent_today"] / max(box["daily_cap"], 1))

    def record_send(self, tenant_id: str, address: str) -> dict:
        meta = self._load_meta(tenant_id)
        info = meta.setdefault(address, {})
        today = date.today().isoformat()
        if info.get("day") != today:
            info["day"] = today
            info["sent_today"] = 0
        info["sent_today"] = info.get("sent_today", 0) + 1
        info["sent"] = info.get("sent", 0) + 1
        self._save_meta(tenant_id, meta)
        return info

    def set_paused(self, tenant_id: str, address: str, paused: bool) -> None:
        meta = self._load_meta(tenant_id)
        meta.setdefault(address, {})["paused"] = paused
        self._save_meta(tenant_id, meta)
        if self.session is not None:
            row = self.session.query(MailboxRow).filter_by(tenant_id=tenant_id, address=address).one_or_none()
            if row:
                row.paused = int(paused)
                self.session.commit()
        for box in self._memory:
            if box["tenant_id"] == tenant_id and box["address"] == address:
                box["paused"] = paused

    def record_event(self, tenant_id: str, address: str, kind: str) -> dict:
        meta = self._load_meta(tenant_id)
        info = meta.setdefault(address, {})
        if kind in {"bounce", "hard_bounce", "bounced"}:
            info["bounces"] = info.get("bounces", 0) + 1
        elif kind in {"complaint", "spam", "spamreport"}:
            info["complaints"] = info.get("complaints", 0) + 1
        elif kind == "delivered":
            info["delivered"] = info.get("delivered", 0) + 1
        self._save_meta(tenant_id, meta)
        sent = max(info.get("sent", 0), info.get("delivered", 0))
        bounce_rate = info.get("bounces", 0) / sent if sent else 0.0
        complaint_rate = info.get("complaints", 0) / sent if sent else 0.0
        status = "ok"
        if sent >= MIN_SENDS_FOR_RATES or info.get("complaints", 0) >= 3:
            box = {"paused": False}
            status = observe_mailbox(box, bounce_rate, complaint_rate, info.get("inbox_rate", 0.95))
            if box["paused"]:
                self.set_paused(tenant_id, address, True)
        return {"address": address, "status": status, "bounce_rate": bounce_rate, "complaint_rate": complaint_rate, "sent": sent}

    def observe(self, tenant_id: str, bounce_rate: float, complaint_rate: float, inbox_rate: float, address: str | None = None) -> str:
        box = next((item for item in self.list_mailboxes(tenant_id) if address is None or item["address"] == address), None)
        if box is None:
            return "unknown"
        state = {"paused": False}
        status = observe_mailbox(state, bounce_rate, complaint_rate, inbox_rate)
        meta = self._load_meta(tenant_id)
        meta.setdefault(box["address"], {})["inbox_rate"] = inbox_rate
        self._save_meta(tenant_id, meta)
        if state["paused"]:
            self.set_paused(tenant_id, box["address"], True)
        return status
