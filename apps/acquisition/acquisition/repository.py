from acquisition.models import (
    AcqStateRow,
    ConsentRow,
    ConversationRow,
    DealRow,
    ICPCellRow,
    LeadRow,
    ServiceProfileRow,
    SuppressionRow,
)
from core.timeutil import utcnow


class AcquisitionRepository:
    def __init__(self, session=None):
        self.session = session
        self._profiles: dict[str, dict] = {}
        self._leads: list[dict] = []
        self._conversations: list[dict] = []
        self._deals: list[dict] = []
        self._suppressions: list[str] = []
        self._consents: list[dict] = []
        self._state: dict[tuple[str, str], dict] = {}
        self._icp_cells: dict[tuple[str, str], dict] = {}

    def save_profile(self, tenant_id: str, body: dict, *, approved: bool = False) -> dict:
        version = int(body.get("version", 1))
        row = {"tenant_id": tenant_id, "version": version, "body": body, "approved": approved}
        self._profiles[tenant_id] = row
        if self.session is not None:
            self.session.add(ServiceProfileRow(tenant_id=tenant_id, version=version, body=body, approved=int(approved)))
            self.session.commit()
        return row

    def approve_profile(self, tenant_id: str) -> dict | None:
        if tenant_id in self._profiles:
            self._profiles[tenant_id]["approved"] = True
            return self._profiles[tenant_id]
        if self.session is not None:
            item = (
                self.session.query(ServiceProfileRow)
                .filter_by(tenant_id=tenant_id)
                .order_by(ServiceProfileRow.version.desc())
                .first()
            )
            if item is None:
                return None
            item.approved = 1
            self.session.commit()
            return {"tenant_id": tenant_id, "version": item.version, "body": item.body, "approved": True}
        return None

    def is_profile_approved(self, tenant_id: str) -> bool:
        if tenant_id in self._profiles:
            return bool(self._profiles[tenant_id].get("approved"))
        if self.session is not None:
            item = (
                self.session.query(ServiceProfileRow)
                .filter_by(tenant_id=tenant_id)
                .order_by(ServiceProfileRow.version.desc())
                .first()
            )
            return bool(item and item.approved)
        return False

    def get_profile(self, tenant_id: str) -> dict | None:
        if tenant_id in self._profiles:
            return self._profiles[tenant_id]["body"]
        if self.session is not None:
            item = (
                self.session.query(ServiceProfileRow)
                .filter_by(tenant_id=tenant_id)
                .order_by(ServiceProfileRow.version.desc())
                .first()
            )
            if item:
                return item.body
        return None

    def get_profile_meta(self, tenant_id: str) -> dict | None:
        if tenant_id in self._profiles:
            row = self._profiles[tenant_id]
            return {**row["body"], "approved": row["approved"], "version": row["version"]}
        if self.session is not None:
            item = (
                self.session.query(ServiceProfileRow)
                .filter_by(tenant_id=tenant_id)
                .order_by(ServiceProfileRow.version.desc())
                .first()
            )
            if item:
                return {**item.body, "approved": bool(item.approved), "version": item.version}
        return None

    def record_consent(
        self,
        tenant_id: str,
        email: str,
        channel: str,
        basis: str,
        source: str = "",
        evidence: str = "",
    ) -> dict:
        row = {
            "tenant_id": tenant_id,
            "lead_email": email.lower(),
            "channel": channel,
            "basis": basis,
            "source": source,
            "evidence": evidence,
            "recorded_at": utcnow().isoformat(),
            "withdrawn": False,
        }
        if self.session is not None:
            self.session.add(
                ConsentRow(
                    tenant_id=tenant_id,
                    lead_email=row["lead_email"],
                    channel=channel,
                    basis=basis,
                    withdrawn=0,
                    source=source,
                    evidence=evidence,
                    recorded_at=row["recorded_at"],
                )
            )
            self.session.commit()
        else:
            self._consents.append(row)
        return row

    @staticmethod
    def _consent_row(item: ConsentRow) -> dict:
        return {
            "tenant_id": item.tenant_id,
            "lead_email": item.lead_email,
            "channel": item.channel,
            "basis": item.basis,
            "source": item.source or "",
            "evidence": item.evidence or "",
            "recorded_at": item.recorded_at,
            "withdrawn": bool(item.withdrawn),
            "withdrawn_at": item.withdrawn_at,
        }

    def get_consent(self, tenant_id: str, email: str, channel: str) -> dict | None:
        rows = [row for row in self.list_consents(tenant_id, email) if row["channel"] == channel]
        if not rows or rows[-1]["withdrawn"]:
            return None
        return rows[-1]

    def withdraw_consent(self, tenant_id: str, email: str, channel: str | None = None) -> int:
        email = email.lower()
        now = utcnow().isoformat()
        count = 0
        if self.session is not None:
            query = self.session.query(ConsentRow).filter_by(tenant_id=tenant_id, lead_email=email)
            if channel is not None:
                query = query.filter_by(channel=channel)
            for stored in query.all():
                if not stored.withdrawn:
                    stored.withdrawn = 1
                    stored.withdrawn_at = now
                    count += 1
            self.session.commit()
            return count
        for row in self._consents:
            if row["tenant_id"] == tenant_id and row["lead_email"] == email and (channel is None or row["channel"] == channel):
                if not row["withdrawn"]:
                    row["withdrawn"] = True
                    row["withdrawn_at"] = now
                    count += 1
        return count

    def list_consents(self, tenant_id: str, email: str) -> list[dict]:
        email = email.lower()
        if self.session is not None:
            return [
                self._consent_row(item)
                for item in self.session.query(ConsentRow).filter_by(tenant_id=tenant_id, lead_email=email).order_by(ConsentRow.id).all()
            ]
        return [dict(row) for row in self._consents if row["tenant_id"] == tenant_id and row["lead_email"] == email]

    def get_state(self, tenant_id: str, key: str, default: dict | None = None) -> dict:
        import copy

        if self.session is not None:
            stored = self.session.query(AcqStateRow).filter_by(tenant_id=tenant_id, key=key).one_or_none()
            return copy.deepcopy(stored.body) if stored is not None else copy.deepcopy(default or {})
        cached = self._state.get((tenant_id, key))
        return copy.deepcopy(cached) if cached is not None else copy.deepcopy(default or {})

    def set_state(self, tenant_id: str, key: str, body: dict) -> dict:
        import copy

        body = copy.deepcopy(body)
        if self.session is not None:
            stored = self.session.query(AcqStateRow).filter_by(tenant_id=tenant_id, key=key).one_or_none()
            if stored is None:
                self.session.add(AcqStateRow(tenant_id=tenant_id, key=key, body=body))
            else:
                stored.body = body
            self.session.commit()
        else:
            self._state[(tenant_id, key)] = body
        return copy.deepcopy(body)

    def save_icp_cell(self, tenant_id: str, name: str, body: dict, successes: int = 0, failures: int = 0) -> dict:
        self._icp_cells[(tenant_id, name)] = {
            "name": name,
            "body": body,
            "successes": successes,
            "failures": failures,
            **body,
        }
        if self.session is not None:
            existing = self.session.query(ICPCellRow).filter_by(tenant_id=tenant_id, name=name).one_or_none()
            if existing is None:
                self.session.add(
                    ICPCellRow(tenant_id=tenant_id, name=name, body=body, successes=successes, failures=failures)
                )
            else:
                existing.body = body
                existing.successes = successes
                existing.failures = failures
            self.session.commit()
        return {"tenant_id": tenant_id, "name": name, "body": body, "successes": successes, "failures": failures}

    def list_icp_cells(self, tenant_id: str) -> list[dict]:
        if self.session is not None:
            return [
                {
                    "name": row.name,
                    "body": row.body,
                    "successes": row.successes,
                    "failures": row.failures,
                    **row.body,
                }
                for row in self.session.query(ICPCellRow).filter_by(tenant_id=tenant_id).all()
            ]
        return [dict(row) for (tenant, _), row in self._icp_cells.items() if tenant == tenant_id]

    def update_icp_outcome(self, tenant_id: str, name: str, positive: bool) -> None:
        cached = self._icp_cells.get((tenant_id, name))
        if cached is not None:
            cached["successes" if positive else "failures"] += 1
        if self.session is not None:
            row = self.session.query(ICPCellRow).filter_by(tenant_id=tenant_id, name=name).one_or_none()
            if row is None:
                return
            if positive:
                row.successes += 1
            else:
                row.failures += 1
            self.session.commit()

    def get_transcript(self, tenant_id: str, email: str) -> list[str]:
        for row in self.list_conversations(tenant_id):
            if row["lead_email"].lower() == email.lower():
                return [f"{msg['direction']}: {msg['body']}" for msg in row.get("messages", [])]
        return []

    def schedule_recontact(self, tenant_id: str, email: str, when: str) -> dict:
        return self.upsert_lead(tenant_id, email, {"recontact_at": when, "stage": "nurture"})

    def upsert_lead(self, tenant_id: str, email: str, body: dict) -> dict:
        email = email.lower()
        existing_body: dict = {}
        for lead in self._leads:
            if lead["tenant_id"] == tenant_id and lead["email"] == email:
                existing_body = dict(lead)
                break
        if self.session is not None:
            stored = self.session.query(LeadRow).filter_by(tenant_id=tenant_id, email=email).one_or_none()
            if stored is not None:
                existing_body = {**dict(stored.body or {}), **existing_body}
        row = {
            **existing_body,
            "tenant_id": tenant_id,
            "email": email,
            "stage": body.get("stage", existing_body.get("stage", "sourced")),
            **body,
        }
        replaced = False
        for index, lead in enumerate(self._leads):
            if lead["tenant_id"] == tenant_id and lead["email"] == email:
                self._leads[index] = row
                replaced = True
                break
        if not replaced:
            self._leads.append(row)
        if self.session is not None:
            stored = self.session.query(LeadRow).filter_by(tenant_id=tenant_id, email=email).one_or_none()
            if stored is None:
                self.session.add(LeadRow(tenant_id=tenant_id, email=email, stage=row["stage"], body=row))
            else:
                stored.stage = row["stage"]
                stored.body = row
            self.session.commit()
        return row

    def list_leads(self, tenant_id: str) -> list[dict]:
        if self.session is not None:
            return [
                {"tenant_id": row.tenant_id, "email": row.email, "stage": row.stage, **row.body}
                for row in self.session.query(LeadRow).filter_by(tenant_id=tenant_id).all()
            ]
        return [lead for lead in self._leads if lead["tenant_id"] == tenant_id]

    def update_stage(self, tenant_id: str, email: str, stage: str) -> dict:
        lead = self.upsert_lead(tenant_id, email, {"stage": stage})
        if self.session is not None:
            stored = self.session.query(LeadRow).filter_by(tenant_id=tenant_id, email=email.lower()).one_or_none()
            if stored:
                stored.stage = stage
                stored.body = {**stored.body, "stage": stage}
                self.session.commit()
        return lead

    def add_message(self, tenant_id: str, email: str, message: dict) -> dict:
        email = email.lower()
        message = {"at": utcnow().isoformat(), "channel": "email", **message}
        row = next(
            (item for item in self._conversations if item["tenant_id"] == tenant_id and item["lead_email"] == email),
            None,
        )
        if row is None:
            row = {"tenant_id": tenant_id, "lead_email": email, "messages": [], "state": "open"}
            self._conversations.append(row)
        row["messages"].append(message)
        if self.session is not None:
            stored = self.session.query(ConversationRow).filter_by(tenant_id=tenant_id, lead_email=email).one_or_none()
            if stored is None:
                self.session.add(
                    ConversationRow(tenant_id=tenant_id, lead_email=email, messages={"messages": list(row["messages"])}, state="open")
                )
            else:
                stored.messages = {"messages": [*stored.messages.get("messages", []), message]}
            self.session.commit()
        return row

    def set_conversation_state(self, tenant_id: str, email: str, state: str) -> None:
        email = email.lower()
        for row in self._conversations:
            if row["tenant_id"] == tenant_id and row["lead_email"] == email:
                row["state"] = state
        if self.session is not None:
            stored = self.session.query(ConversationRow).filter_by(tenant_id=tenant_id, lead_email=email).one_or_none()
            if stored is not None:
                stored.state = state
                self.session.commit()

    def list_conversations(self, tenant_id: str) -> list[dict]:
        if self.session is not None:
            return [
                {
                    "tenant_id": row.tenant_id,
                    "lead_email": row.lead_email,
                    "messages": row.messages.get("messages", []),
                    "state": row.state,
                }
                for row in self.session.query(ConversationRow).filter_by(tenant_id=tenant_id).all()
            ]
        return [row for row in self._conversations if row["tenant_id"] == tenant_id]

    def add_deal(self, tenant_id: str, email: str, price_cents: int, status: str, body: dict) -> dict:
        email = email.lower()
        row = {"tenant_id": tenant_id, "lead_email": email, "price_cents": price_cents, "status": status, **body}
        self._deals.append(row)
        if self.session is not None:
            self.session.add(DealRow(tenant_id=tenant_id, lead_email=email, price_cents=price_cents, status=status, body=row))
            self.session.commit()
        return row

    def list_deals(self, tenant_id: str) -> list[dict]:
        if self.session is not None:
            return [
                {**(item.body or {}), "tenant_id": item.tenant_id, "lead_email": item.lead_email, "price_cents": item.price_cents, "status": item.status}
                for item in self.session.query(DealRow).filter_by(tenant_id=tenant_id).all()
            ]
        return [row for row in self._deals if row["tenant_id"] == tenant_id]

    def get_deal(self, tenant_id: str, email: str) -> dict | None:
        rows = [row for row in self.list_deals(tenant_id) if row["lead_email"].lower() == email.lower()]
        return rows[-1] if rows else None

    def update_deal(self, tenant_id: str, email: str, status: str, updates: dict | None = None) -> dict | None:
        email = email.lower()
        updates = updates or {}
        target = None
        for row in reversed(self._deals):
            if row["tenant_id"] == tenant_id and row["lead_email"].lower() == email:
                row.update(updates)
                row["status"] = status
                target = row
                break
        if self.session is not None:
            stored = (
                self.session.query(DealRow)
                .filter_by(tenant_id=tenant_id, lead_email=email)
                .order_by(DealRow.id.desc())
                .first()
            )
            if stored is not None:
                stored.status = status
                stored.body = {**(stored.body or {}), **updates, "status": status}
                self.session.commit()
                target = {**stored.body, "tenant_id": tenant_id, "lead_email": email, "price_cents": stored.price_cents}
        return target

    def export_lead(self, tenant_id: str, email: str) -> dict:
        email = email.lower()
        lead = next((row for row in self.list_leads(tenant_id) if row["email"] == email), None)
        thread = next((row for row in self.list_conversations(tenant_id) if row["lead_email"] == email), None)
        return {
            "email": email,
            "lead": lead,
            "conversation": thread,
            "consents": self.list_consents(tenant_id, email),
            "deals": [row for row in self.list_deals(tenant_id) if row["lead_email"].lower() == email],
            "suppressed": self.is_suppressed(email),
            "exported_at": utcnow().isoformat(),
        }

    def erase_lead(self, tenant_id: str, email: str) -> dict:
        """Delete personal data; keep only a do-not-contact suppression entry."""
        email = email.lower()
        self._leads = [row for row in self._leads if not (row["tenant_id"] == tenant_id and row["email"] == email)]
        self._conversations = [
            row for row in self._conversations if not (row["tenant_id"] == tenant_id and row["lead_email"] == email)
        ]
        self._consents = [row for row in self._consents if not (row["tenant_id"] == tenant_id and row["lead_email"] == email)]
        removed = {"leads": 0, "conversations": 0, "consents": 0}
        if self.session is not None:
            removed["leads"] = self.session.query(LeadRow).filter_by(tenant_id=tenant_id, email=email).delete()
            removed["conversations"] = self.session.query(ConversationRow).filter_by(tenant_id=tenant_id, lead_email=email).delete()
            removed["consents"] = self.session.query(ConsentRow).filter_by(tenant_id=tenant_id, lead_email=email).delete()
            self.session.commit()
        if not self.is_suppressed(email):
            self.suppress(email, tenant_id=None)
        return {"erased": email, "removed": removed, "suppressed": True, "erased_at": utcnow().isoformat()}

    def suppress(self, value: str, tenant_id: str | None = None) -> None:
        value = value.lower()
        if value not in self._suppressions:
            self._suppressions.append(value)
        if self.session is not None:
            self.session.add(SuppressionRow(tenant_id=tenant_id, value=value, kind="email"))
            self.session.commit()

    def is_suppressed(self, value: str) -> bool:
        value = value.lower()
        if value in self._suppressions:
            return True
        if self.session is not None:
            return self.session.query(SuppressionRow).filter_by(value=value).first() is not None
        return False

    def funnel_counts(self, tenant_id: str) -> dict[str, int]:
        stages = ["sourced", "contacted", "replied", "positive", "qualified", "converted", "nurture", "unsubscribed"]
        leads = self.list_leads(tenant_id)
        return {stage: sum(1 for lead in leads if lead.get("stage") == stage) for stage in stages}

    def funnel_by_icp(self, tenant_id: str) -> dict[str, dict[str, int]]:
        stages = ["sourced", "contacted", "replied", "positive", "qualified", "converted"]
        grouped: dict[str, dict[str, int]] = {}
        for lead in self.list_leads(tenant_id):
            cell = lead.get("icp_cell") or "unassigned"
            bucket = grouped.setdefault(cell, {stage: 0 for stage in stages})
            stage = lead.get("stage", "sourced")
            if stage in bucket:
                bucket[stage] += 1
        return grouped
