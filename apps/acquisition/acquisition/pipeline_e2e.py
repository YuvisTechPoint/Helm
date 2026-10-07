import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from acquisition.close import build_proposal, mark_paid as close_mark_paid, mark_signed
from acquisition.crm import crm_handoff
from acquisition.funnel import (
    _PHONE,
    assess_qualification,
    book_meeting,
    classify_reply,
    complete_handoff,
    draft_reply,
    enters_outreach,
    follow_up,
    in_business_hours,
    pre_call_brief,
    qualification_question,
    recontact_on,
    referral_lead,
    requested_channel,
    resolve_call_time,
    subject_line,
)
from acquisition.mailbox_limit import MailboxLimiter
from acquisition.mailbox_store import MailboxStore
from acquisition.modules.experiments import ExperimentStore
from acquisition.modules.icp import allocate_bandit, pick_cell
from acquisition.modules.learning import (
    build_monthly_report,
    plan_volume,
    retrain_score_weights,
    seed_from_client_list,
)
from acquisition.modules.llm_copy import LlmCopywriter, LlmCritic
from acquisition.modules.research_brief import build_research_brief
from acquisition.modules.scoring import compute_scores
from acquisition.modules.triggers import detect_triggers, outreach_reason
from acquisition.policy import AI_DISCLOSURE as AI_DISCLOSURE_PREFIX
from acquisition.policy import CONSENT_CHANNELS, PolicyGuard, critique
from acquisition.providers.email import email_verifier
from acquisition.providers.enrichment import enrich_lead
from acquisition.repository import AcquisitionRepository
from acquisition.runtime_ctx import acquisition_runtime
from acquisition.tenant_caps import TenantOutreachCap
from core.config import get_settings
from core.errors import PolicyDenied
from core.events import EventLog
from core.outbox import Outbox
from core.exception_store import ExceptionStore
from core.notify import NotifierHub

HOLDING_REPLY = "I'll confirm that and reply shortly."
SEQUENCE_OFFSETS = {"4-touch": (0, 3, 7, 13), "3-touch": (0, 4, 10)}
PROPOSAL_REMINDER_DAYS = 3
MAX_CLOSING_REMINDERS = 4
REPLIED_STAGES = {"replied", "positive", "qualified", "proposal_sent", "payment_pending", "converted", "nurture", "unsubscribed"}
AGENT_VERSION = "acq-agents-2"
SEND_COST_CENTS = 5
DEFAULT_TENANT_BUDGET_CENTS = 100_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _cents(price: float) -> int:
    return int(round(float(price) * 100))


def _hash(value: str) -> str:
    return hashlib.sha256(value.lower().encode()).hexdigest()[:16]


class LeadPipeline:
    def __init__(self, repo: AcquisitionRepository, guard: PolicyGuard | None = None):
        self.repo = repo
        runtime = acquisition_runtime()
        self.guard = guard or runtime.guard
        if self.guard.kill_switches is None:
            self.guard.kill_switches = runtime.kill
        self.kill = self.guard.kill_switches
        self.sender = runtime.sender
        self.channels = runtime.channels
        self.esign = runtime.esign
        self.payments = runtime.payments
        self.calendar = runtime.calendar
        self.verifier = email_verifier()
        self.events = EventLog(repo.session)
        self.outbox = Outbox(repo.session)
        self.exceptions = ExceptionStore(repo.session)
        self.notifier = NotifierHub()
        self.copywriter = LlmCopywriter(runtime.llm)
        self.critic = LlmCritic(runtime.llm)
        self.mailbox_limiter = MailboxLimiter()
        self.tenant_cap = TenantOutreachCap()
        self.mailboxes = MailboxStore(repo.session, repo)
        self.experiments = ExperimentStore(repo)
        self._critic_fails: dict[str, int] = {}

    # ------------------------------------------------------------------ helpers

    def _event(self, event_type: str, module: str, payload: dict, tenant_id: str) -> None:
        profile = self.repo.get_profile_meta(tenant_id) or {}
        prompt = self.repo.get_state(tenant_id, "prompt", {"name": "reply-v1"})
        body = {
            **payload,
            "profile_version": profile.get("version", 1),
            "channel": payload.get("channel", "email"),
            "agent_version": AGENT_VERSION,
            "prompt_version": prompt.get("name", "reply-v1"),
        }
        aggregate_id = payload.get("email") or payload.get("lead_id") or tenant_id
        self.outbox.publish(
            event_type=event_type,
            aggregate_type="lead",
            aggregate_id=str(aggregate_id),
            payload=body,
            tenant_id=tenant_id,
            actor=module,
        )

    def _lead(self, tenant_id: str, email: str) -> dict | None:
        email = email.lower()
        return next((row for row in self.repo.list_leads(tenant_id) if row["email"] == email), None)

    def _lead_by_phone(self, tenant_id: str, phone: str) -> dict | None:
        target = "".join(ch for ch in phone if ch.isdigit())[-10:]
        for row in self.repo.list_leads(tenant_id):
            digits = "".join(ch for ch in str(row.get("phone") or "") if ch.isdigit())
            if digits and digits[-10:] == target:
                return row
        return None

    def _brief_for(self, lead: dict, profile: dict) -> str:
        if lead.get("research_brief"):
            return lead["research_brief"]
        brief = build_research_brief(lead, profile, acquisition_runtime().llm)
        text = brief.as_text()
        self.repo.upsert_lead(lead["tenant_id"], lead["email"], {"research_brief": text, "brief_facts": brief.facts})
        return text

    def _weights(self, tenant_id: str) -> dict | None:
        weights = self.repo.get_state(tenant_id, "score_weights")
        return weights if weights.get("status") == "trained" else None

    def _converted_examples(self, tenant_id: str) -> list[dict]:
        converted = [lead for lead in self.repo.list_leads(tenant_id) if lead.get("stage") == "converted"]
        seeded = self.repo.get_state(tenant_id, "seed_clients", {"items": []}).get("items", [])
        return converted + seeded

    def _spend(self, tenant_id: str, category: str, cents: int) -> None:
        ledger = self.repo.get_state(tenant_id, "spend", {"by_category": {}, "total_cents": 0})
        ledger.setdefault("by_category", {})
        ledger["by_category"][category] = ledger["by_category"].get(category, 0) + cents
        ledger["total_cents"] = ledger.get("total_cents", 0) + cents
        self.repo.set_state(tenant_id, "spend", ledger)
        budget = acquisition_runtime().budget
        if budget:
            budget.ensure(tenant_id, "outreach", DEFAULT_TENANT_BUDGET_CENTS)
            budget.charge(tenant_id, "outreach", cents, pause_at=1.0)

    def _budget_allows(self, tenant_id: str, cents: int) -> bool:
        budget = acquisition_runtime().budget
        if not budget:
            return True
        budget.ensure(tenant_id, "outreach", DEFAULT_TENANT_BUDGET_CENTS)
        return budget.can_spend(tenant_id, "outreach", cents)

    def _sync_guard(self, lead: dict) -> None:
        """Guard sets are per-process; rebuild them from the durable lead record before any send."""
        email = lead["email"]
        if lead.get("automation_frozen") or lead.get("stage") == "converted":
            self.guard.frozen.add(email)
        if lead.get("stage") in REPLIED_STAGES:
            self.guard.replied.add(email)
        if self.repo.is_suppressed(email):
            self.guard.suppression.add(email, tenant_id=None)
        if lead.get("phone") and self.repo.is_suppressed(str(lead["phone"])):
            self.guard.suppression.add(str(lead["phone"]), tenant_id=None)

    def _reply_channel(self, lead: dict, inbound_channel: str) -> str:
        if inbound_channel in {"whatsapp", "sms"}:
            return inbound_channel
        return lead.get("active_channel") or "email"

    def _deliver(
        self,
        tenant_id: str,
        lead: dict,
        body: str,
        *,
        channel: str = "email",
        transactional: str | None = None,
        subject: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        """Single exit for every non-sequence message; always via PolicyGuard."""
        profile = self.repo.get_profile(tenant_id) or {}
        email = lead["email"]
        self._sync_guard(lead)
        if channel in {"whatsapp", "sms"} and "stop" not in body.lower():
            body = f"{body}\n\nReply STOP to opt out."
        request = {
            "tenant_id": tenant_id,
            "lead_id": email,
            "channel": channel,
            "email": email,
            "body": body,
            "subject": subject,
            "critic_passed": True,
            "verification": lead.get("verification", "valid"),
            "lawful_basis": lead.get("lawful_basis") or profile.get("lawful_basis", "legitimate_interest"),
            "transactional": transactional,
        }
        if channel in CONSENT_CHANNELS:
            request["phone"] = lead.get("phone")
            request["consent"] = self.repo.get_consent(tenant_id, email, channel)
            sender = self.channels[channel].send
        else:
            sender = self.sender.send
        message = {"direction": "outbound", "body": body, "channel": channel, **(meta or {})}
        try:
            result = self.guard.send(request, sender)
        except PolicyDenied as exc:
            self.repo.add_message(tenant_id, email, {**message, "blocked": str(exc)})
            self._event("send_blocked", "guard", {"email": email, "reason": str(exc), "channel": channel}, tenant_id)
            return {"sent": False, "reason": str(exc)}
        self.repo.add_message(tenant_id, email, message)
        return {"sent": True, "result": result}

    def _escalate(self, tenant_id: str, email: str, kind: str, detail: str, holding: bool = True, channel: str = "email") -> dict:
        item = self.exceptions.add(kind, f"{email}: {detail[:200]}", scope="acquisition")
        lead = self._lead(tenant_id, email)
        if holding and lead is not None:
            self._deliver(tenant_id, lead, HOLDING_REPLY, channel=self._reply_channel(lead, channel), meta={"holding": True})
        self.notifier.alert(f"Escalation for {email}: {kind}")
        self._event("escalated", "escalation", {"email": email, "kind": kind}, tenant_id)
        return {"status": "escalated", "exception_id": item["id"], "holding": HOLDING_REPLY}

    def _corpus(self, profile: dict, brief: str = "") -> str:
        return " ".join(
            profile.get("proof_points", [])
            + profile.get("services", [])
            + profile.get("faq", [])
            + [profile.get("business_name", ""), str(profile.get("price_floor", "")), str(profile.get("list_price", "")), brief]
        )

    # ------------------------------------------------------------------ sourcing

    def source_lead(self, tenant_id: str, lead: dict, icp_cell: dict | None = None) -> dict:
        email = lead["email"].lower()
        if self.repo.is_suppressed(email):
            return {"status": "suppressed", "email": email}
        profile = self.repo.get_profile(tenant_id) or {}
        domain = email.split("@")[-1]
        blocked_domains = {token.lower() for token in profile.get("competitor_domains", [])}
        if domain in blocked_domains:
            return {"status": "blocked", "reason": "competitor domain", "email": email}
        known = {row["email"] for row in self.repo.list_leads(tenant_id)}
        if email in known and lead.get("stage") != "sourced":
            return {"status": "duplicate", "email": email}
        if lead.get("company") and profile.get("existing_clients"):
            company = lead["company"].lower()
            if any(client.lower() in company for client in profile["existing_clients"]):
                return {"status": "duplicate", "reason": "existing client", "email": email}
        lead = enrich_lead(lead)
        triggers = detect_triggers(lead.get("reason", ""), profile)
        verification = lead.get("verification") or self.verifier.verify(lead["email"])
        if verification in {"invalid", "catch_all"} and lead.get("email", "").endswith("@role.example"):
            verification = "invalid"
        scores = compute_scores(
            lead,
            icp_cell or {},
            profile,
            verification,
            triggers,
            weights=self._weights(tenant_id),
            converted=self._converted_examples(tenant_id),
        )
        brief = build_research_brief({**lead, "email": email}, profile, acquisition_runtime().llm)
        reason = outreach_reason(lead, brief.facts)
        row = self.repo.upsert_lead(
            tenant_id,
            email,
            {
                **lead,
                "reason": reason,
                "verification": verification,
                "fit": scores["fit"],
                "intent": scores["intent"],
                "score": scores["score"],
                "lookalike": scores.get("lookalike", 0.0),
                "score_explain": scores.get("explain"),
                "triggers": triggers,
                "icp_cell": (icp_cell or {}).get("name"),
                "research_brief": brief.as_text(),
                "brief_facts": brief.facts,
                "stage": "sourced",
                "sourced_at": _now().isoformat(),
            },
        )
        self._event(
            "lead_sourced",
            "m3",
            {
                "email": email,
                "score": scores["score"],
                "icp_cell": (icp_cell or {}).get("name"),
                "triggers": [t.get("kind") or t.get("trigger") for t in triggers if isinstance(t, dict)],
            },
            tenant_id,
        )
        return {"status": "sourced", "lead": row, "score": scores["score"]}

    def source_inbound(self, tenant_id: str, lead: dict, message: str) -> dict:
        """M3.3 — inbound form/chat with consent already recorded."""
        email = lead["email"].lower()
        channel = lead.get("channel", "email")
        self.repo.record_consent(tenant_id, email, channel, lead.get("basis", "consent"), source="inbound_form", evidence=message[:500])
        sourced = self.source_lead(
            tenant_id,
            {**lead, "email": email, "stage": "sourced", "intent": 0.9, "source": "inbound", "lawful_basis": "consent"},
        )
        if sourced["status"] != "sourced":
            return sourced
        self.repo.update_stage(tenant_id, email, "replied")
        return self.handle_reply(tenant_id, email, message, channel=channel if channel in {"whatsapp", "sms"} else "email")

    def source_batch(self, tenant_id: str, limit: int | None = None) -> dict:
        from acquisition.modules.icp import generate_icp_hypotheses, sample_leads_for_cell

        profile = self.repo.get_profile(tenant_id)
        if profile is None:
            raise ValueError("service profile required")
        cells = self.repo.list_icp_cells(tenant_id)
        if not cells:
            cells = generate_icp_hypotheses(profile, acquisition_runtime().llm)
            for cell in cells:
                self.repo.save_icp_cell(tenant_id, cell["name"], cell, cell.get("successes", 0), cell.get("failures", 0))
        cell = pick_cell(cells)
        leads = sample_leads_for_cell(cell)
        if limit is not None:
            leads = leads[:limit]
        results = [self.source_lead(tenant_id, lead, cell) for lead in leads]
        return {"sourced": len(results), "icp_cell": cell["name"], "leads": results}

    def seed_clients(self, tenant_id: str, clients: list[dict]) -> dict:
        """FR-1.4 — past clients and won/lost deals seed ICP priors, dedupe and look-alikes."""
        profile = self.repo.get_profile(tenant_id)
        if profile is None:
            raise ValueError("service profile required")
        seeded = seed_from_client_list(profile, clients)
        existing = {cell["name"]: cell for cell in self.repo.list_icp_cells(tenant_id)}
        for cell in seeded["cells"]:
            prior = existing.get(cell["name"], {})
            self.repo.save_icp_cell(
                tenant_id,
                cell["name"],
                cell,
                prior.get("successes", 0) + cell["successes"],
                prior.get("failures", 0) + cell["failures"],
            )
        names = list(dict.fromkeys(profile.get("existing_clients", []) + seeded["existing_clients"]))
        if names != profile.get("existing_clients", []):
            self.repo.save_profile(tenant_id, {**profile, "existing_clients": names}, approved=self.repo.is_profile_approved(tenant_id))
        stored = self.repo.get_state(tenant_id, "seed_clients", {"items": []})
        stored["items"] = (stored.get("items", []) + seeded["converted_examples"])[-500:]
        self.repo.set_state(tenant_id, "seed_clients", stored)
        self._event("clients_seeded", "m1", {"clients": len(clients), "cells": len(seeded["cells"])}, tenant_id)
        return {"cells": seeded["cells"], "existing_clients": len(names), "lookalike_examples": len(stored["items"])}

    # ------------------------------------------------------------------ sequence

    def _pick_mailbox(self, tenant_id: str) -> dict | None:
        return self.mailboxes.pick(tenant_id)

    def _send_sequence_email(self, tenant_id: str, lead: dict, profile: dict, body: str, subject: str, touch: int) -> dict:
        email = lead["email"]
        if not self._budget_allows(tenant_id, SEND_COST_CENTS):
            return {"status": "blocked", "reason": "tenant budget hard stop reached"}
        mailbox = self._pick_mailbox(tenant_id)
        if mailbox is None:
            return {"status": "blocked", "reason": "no warmed, unpaused mailbox available"}
        self._sync_guard(lead)
        request = {
            "tenant_id": tenant_id,
            "lead_id": email,
            "channel": "email",
            "email": email,
            "subject": subject,
            "body": body + "\n\nReply STOP to opt out.",
            "critic_passed": True,
            "verification": lead.get("verification", "valid"),
            "lawful_basis": lead.get("lawful_basis") or profile.get("lawful_basis", "legitimate_interest"),
            "sequence_touch": True,
            "mailbox": mailbox["address"],
            "daily_cap": mailbox["daily_cap"],
        }
        result = self.guard.send(request, self.sender.send, mailbox_limiter=self.mailbox_limiter)
        self._spend(tenant_id, "sending", SEND_COST_CENTS)
        self.mailboxes.record_send(tenant_id, mailbox["address"])
        self.repo.add_message(
            tenant_id,
            email,
            {"direction": "outbound", "body": request["body"], "subject": subject, "touch": touch, "mailbox": mailbox["address"]},
        )
        return {"status": "sent", "send": result, "body": request["body"], "mailbox": mailbox["address"]}

    def outreach(self, tenant_id: str, email: str, *, force: bool = False) -> dict:
        profile = self.repo.get_profile(tenant_id)
        if profile is None:
            raise ValueError("service profile required")
        if not self.repo.is_profile_approved(tenant_id):
            return {"status": "blocked", "reason": "profile not approved"}
        if not force:
            if not self.tenant_cap.allow(tenant_id):
                return {"status": "blocked", "reason": "tenant daily outreach cap reached"}
            if profile.get("enforce_business_hours", True) and not in_business_hours(_now(), profile.get("timezone", "Asia/Kolkata")):
                return {"status": "blocked", "reason": "outside business hours"}
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        email = lead["email"]
        if not enters_outreach(lead.get("score", 0)):
            self.repo.update_stage(tenant_id, email, "nurture")
            return {"status": "nurture", "email": email}
        assignment = lead.get("variants") or self.experiments.assign(email, tenant_id)
        brief = self._brief_for({**lead, "tenant_id": tenant_id}, profile)
        lead_with_reason = {**lead, "reason": outreach_reason(lead, lead.get("brief_facts", []))}
        body = self.copywriter.first_touch(lead_with_reason, profile, angle=assignment["angle"])
        subject = subject_line(lead_with_reason, profile, assignment["subject"])
        verdict = self.critic.critique(body, self._corpus(profile, brief), first_touch=True)
        if not verdict["passed"]:
            fails = self._critic_fails.get(email, 0) + 1
            self._critic_fails[email] = fails
            if fails >= 2:
                item = self.exceptions.add("critic_failed_twice", "; ".join(verdict["reasons"]), scope="acquisition")
                return {"status": "escalated", "exception_id": item["id"]}
            return {"status": "blocked", "reasons": verdict["reasons"]}
        sent = self._send_sequence_email(tenant_id, lead, profile, body, subject, touch=0)
        if sent["status"] != "sent":
            return sent
        self.repo.upsert_lead(
            tenant_id,
            email,
            {"stage": "contacted", "variants": assignment, "contacted_at": _now().isoformat(), "touches": 1},
        )
        self.experiments.record_assignment(assignment, tenant_id=tenant_id)
        self._event(
            "email_sent",
            "m7",
            {"email": email, "variant": assignment["angle"], "variants": assignment, "icp_cell": lead.get("icp_cell"), "touch": 0},
            tenant_id,
        )
        return {"status": "contacted", "send": sent["send"], "body": sent["body"], "subject": subject, "variants": assignment}

    def sequence_plan(self, tenant_id: str, email: str) -> dict:
        lead = self._lead(tenant_id, email) or {}
        length = (lead.get("variants") or {}).get("sequence_length", "4-touch")
        offsets = SEQUENCE_OFFSETS.get(length, SEQUENCE_OFFSETS["4-touch"])
        send_time = (lead.get("variants") or {}).get("send_time", "morning")
        return {"offsets": list(offsets), "send_time": send_time}

    def follow_up(self, tenant_id: str, email: str, index: int) -> dict:
        """FR-6.3 — follow-ups add a new proof point; they stop on any reply or suppression."""
        profile = self.repo.get_profile(tenant_id)
        lead = self._lead(tenant_id, email)
        if profile is None or lead is None:
            return {"status": "stopped", "reason": "missing profile or lead"}
        if lead.get("stage") != "contacted":
            return {"status": "stopped", "reason": f"stage is {lead.get('stage')}"}
        if self.repo.is_suppressed(lead["email"]):
            return {"status": "stopped", "reason": "suppressed"}
        body = follow_up(lead, profile, index)
        verdict = self.critic.critique(body, self._corpus(profile, lead.get("research_brief", "")), first_touch=False)
        if not verdict["passed"]:
            return {"status": "skipped", "reasons": verdict["reasons"]}
        subject = "Re: " + subject_line(lead, profile, (lead.get("variants") or {}).get("subject", "question"))
        try:
            sent = self._send_sequence_email(tenant_id, lead, profile, body, subject, touch=index)
        except PolicyDenied as exc:
            return {"status": "stopped", "reason": str(exc)}
        if sent["status"] != "sent":
            return sent
        self.repo.upsert_lead(tenant_id, lead["email"], {"touches": int(lead.get("touches", 1)) + 1})
        self._event("email_sent", "m7", {"email": lead["email"], "touch": index, "variants": lead.get("variants")}, tenant_id)
        return {"status": "sent", "touch": index}

    def sequence_should_continue(self, tenant_id: str, email: str) -> dict:
        lead = self._lead(tenant_id, email)
        if lead is None:
            return {"continue": False, "reason": "unknown lead"}
        if self.repo.is_suppressed(lead["email"]):
            return {"continue": False, "reason": "suppressed"}
        if lead.get("stage") != "contacted":
            return {"continue": False, "reason": f"stage {lead.get('stage')}"}
        return {"continue": True}

    # ------------------------------------------------------------------ conversation

    def _unsubscribe(self, tenant_id: str, lead: dict) -> None:
        email = lead["email"]
        self.repo.suppress(email, tenant_id=None)
        self.guard.suppression.add(email, tenant_id=None)
        if lead.get("phone"):
            self.repo.suppress(str(lead["phone"]), tenant_id=None)
            self.guard.suppression.add(str(lead["phone"]), tenant_id=None)
        self.repo.withdraw_consent(tenant_id, email)
        self.repo.update_stage(tenant_id, email, "unsubscribed")
        self.repo.set_conversation_state(tenant_id, email, "closed")

    def handle_reply(self, tenant_id: str, email: str, text: str, channel: str = "email") -> dict:
        profile = self.repo.get_profile(tenant_id)
        if profile is None:
            raise ValueError("service profile required")
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        email = lead["email"]
        brief = self._brief_for({**lead, "tenant_id": tenant_id}, profile)
        label = classify_reply(text)
        if label == "question" and lead.get("pending_channel") and _PHONE.search(text):
            label = "channel_switch"
        self.repo.add_message(tenant_id, email, {"direction": "inbound", "body": text, "label": label, "channel": channel})
        self._event("reply_received", "m8", {"email": email, "label": label, "channel": channel, "icp_cell": lead.get("icp_cell")}, tenant_id)
        if label == "out_of_office":
            return {"status": "out_of_office", "label": label}
        self.guard.replied.add(email)
        if lead.get("stage") in {"sourced", "contacted"}:
            self.repo.update_stage(tenant_id, email, "replied")
        reply_channel = self._reply_channel(lead, channel)
        if label == "unsubscribe":
            self._unsubscribe(tenant_id, lead)
            self.repo.add_message(tenant_id, email, {"direction": "outbound", "body": "You're unsubscribed and will not be contacted again.", "channel": channel, "confirmation": True})
            self._event("unsubscribed", "m8", {"email": email, "channel": channel}, tenant_id)
            return {"status": "unsubscribed"}
        if label == "channel_switch":
            return self.switch_channel(tenant_id, email, text, inbound_channel=channel)
        if label == "referral":
            ref = referral_lead(text, email)
            if ref:
                self.source_lead(
                    tenant_id,
                    {
                        **ref,
                        "email": f"{ref['first_name'].lower()}-{uuid.uuid4().hex[:6]}@referral.example",
                        "company": lead.get("company", ""),
                        "reason": f"{lead.get('first_name', 'A colleague')} suggested we speak",
                    },
                )
        draft = draft_reply(label, text, profile, brief)
        if label == "not_now":
            when = recontact_on(text, _now())
            self.repo.schedule_recontact(tenant_id, email, when.isoformat())
            self._deliver(tenant_id, lead, draft["text"], channel=reply_channel)
            return {"status": "nurture", "recontact_at": when.isoformat()}
        if draft.get("escalate"):
            return self._escalate(tenant_id, email, draft["escalate"], text, channel=channel)
        if not draft["critic"]["passed"]:
            return self._escalate(tenant_id, email, "critic_failed", "; ".join(draft["critic"]["reasons"]), channel=channel)
        stage = "positive" if label == "interested" else "replied"
        if lead.get("stage") in {"sourced", "contacted", "replied"}:
            self.repo.update_stage(tenant_id, email, stage)
        if label == "interested":
            self.experiments.record_assignment(lead.get("variants") or {}, positive=True, tenant_id=tenant_id)
            if lead.get("icp_cell"):
                self.repo.update_icp_outcome(tenant_id, lead["icp_cell"], True)
        question = qualification_question(lead)
        reply_text = f"{draft['text']} {question}" if label == "interested" and question else draft["text"]
        delivered = self._deliver(tenant_id, lead, reply_text, channel=reply_channel)
        self._event("reply_handled", "m8", {"email": email, "label": label, "sent": delivered["sent"]}, tenant_id)
        return {"status": stage, "label": label, "reply": reply_text, "qualifying_question": question, "sent": delivered["sent"]}

    def switch_channel(self, tenant_id: str, email: str, text: str, inbound_channel: str = "email") -> dict:
        """FR-7.3/7.4 — the prospect's own request is the recorded consent that unlocks the channel."""
        profile = self.repo.get_profile(tenant_id) or {}
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        request = requested_channel(text) or {}
        channel = request.get("channel") or lead.get("pending_channel")
        phone = request.get("phone")
        if not phone:
            match = _PHONE.search(text)
            phone = "".join(ch for ch in match.group(0) if ch.isdigit() or ch == "+") if match else lead.get("phone")
        if channel is None:
            return {"status": "ignored"}
        if not phone:
            self.repo.upsert_lead(tenant_id, email, {"pending_channel": channel})
            reply = draft_reply("channel_switch", text, profile, "")["text"]
            self._deliver(tenant_id, lead, reply, channel=self._reply_channel(lead, inbound_channel))
            return {"status": "channel_pending", "channel": channel}
        basis = "express" if channel == "voice" else "consent"
        self.repo.record_consent(tenant_id, email, channel, basis, source=f"{inbound_channel}_reply", evidence=text[:500])
        updates = {"phone": phone, "pending_channel": None}
        if channel != "voice":
            updates["active_channel"] = channel
        lead = self.repo.upsert_lead(tenant_id, email, updates)
        self._event("consent_recorded", "m7", {"email": email, "channel": channel, "basis": basis}, tenant_id)
        if channel == "voice":
            call_at = resolve_call_time(request.get("when"), _now(), profile.get("timezone", "Asia/Kolkata"))
            self.repo.upsert_lead(tenant_id, email, {"call_at": call_at.isoformat(), "call_placed": False})
            confirm = f"Noted. An AI assistant for {profile.get('business_name', 'us')} will call {phone} at {call_at.strftime('%d %b %H:%M')}."
            self._deliver(tenant_id, lead, confirm, channel=self._reply_channel(lead, inbound_channel))
            return {"status": "call_scheduled", "channel": "voice", "call_at": call_at.isoformat()}
        welcome = (
            f"Hi {lead.get('first_name', '')}, continuing here as you asked — {profile.get('business_name', '')}. "
            "Reply STOP at any time to opt out."
        )
        delivered = self._deliver(tenant_id, lead, welcome, channel=channel)
        return {"status": "channel_switched", "channel": channel, "sent": delivered["sent"]}

    def place_call(self, tenant_id: str, email: str) -> dict:
        profile = self.repo.get_profile(tenant_id) or {}
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        body = f"{AI_DISCLOSURE_PREFIX} {profile.get('business_name', 'the business')}. You asked us to call about {', '.join(profile.get('services', [])[:1]) or 'your enquiry'}."
        self._sync_guard(lead)
        request = {
            "tenant_id": tenant_id,
            "lead_id": lead["email"],
            "email": lead["email"],
            "phone": lead.get("phone"),
            "channel": "voice",
            "direction": "outbound",
            "body": body,
            "critic_passed": True,
            "consent": self.repo.get_consent(tenant_id, lead["email"], "voice"),
        }
        try:
            result = self.guard.send(request, self.channels["voice"].send)
        except PolicyDenied as exc:
            self.repo.upsert_lead(tenant_id, lead["email"], {"call_placed": True, "call_blocked": str(exc)})
            return {"status": "blocked", "reason": str(exc)}
        self.repo.upsert_lead(tenant_id, lead["email"], {"call_placed": True, "call_id": result.get("call_id") or result.get("message_id")})
        self.repo.add_message(tenant_id, lead["email"], {"direction": "outbound", "body": body, "channel": "voice"})
        self._event("call_placed", "m7", {"email": lead["email"], "channel": "voice"}, tenant_id)
        return {"status": "called", "result": result}

    def handle_channel_message(self, tenant_id: str, channel: str, phone: str, text: str, name: str = "") -> dict:
        """Inbound WhatsApp/SMS: the prospect wrote first, which opens the service window for replies."""
        lead = self._lead_by_phone(tenant_id, phone)
        if lead is None:
            if classify_reply(text) == "unsubscribe":
                self.repo.suppress(phone, tenant_id=None)
                self.guard.suppression.add(phone, tenant_id=None)
                return {"status": "unsubscribed"}
            digits = "".join(ch for ch in phone if ch.isdigit())
            email = f"{channel}-{digits}@inbound.invalid"
            self.repo.record_consent(tenant_id, email, channel, "consent", source=f"inbound_{channel}", evidence=text[:500])
            sourced = self.source_lead(
                tenant_id,
                {
                    "email": email,
                    "first_name": name or "there",
                    "company": "",
                    "phone": phone,
                    "intent": 0.9,
                    "fit": 0.7,
                    "verification": "unverified",
                    "source": f"inbound_{channel}",
                    "active_channel": channel,
                    "lawful_basis": "consent",
                    "stage": "sourced",
                },
            )
            if sourced["status"] != "sourced":
                return sourced
            lead = sourced["lead"]
        elif not self.repo.get_consent(tenant_id, lead["email"], channel):
            self.repo.record_consent(tenant_id, lead["email"], channel, "consent", source=f"inbound_{channel}", evidence=text[:500])
        return self.handle_reply(tenant_id, lead["email"], text, channel=channel)

    def handle_call_report(self, tenant_id: str, phone: str, transcript: str, summary: str = "") -> dict:
        """Inbound or outbound call finished: log the transcript to the shared thread and route the outcome."""
        lead = self._lead_by_phone(tenant_id, phone)
        if lead is None:
            digits = "".join(ch for ch in phone if ch.isdigit())
            email = f"voice-{digits}@inbound.invalid"
            self.repo.record_consent(tenant_id, email, "voice", "consent", source="inbound_call", evidence=(summary or transcript)[:500])
            sourced = self.source_lead(
                tenant_id,
                {"email": email, "first_name": "there", "company": "", "phone": phone, "intent": 0.9, "fit": 0.7, "verification": "unverified", "source": "inbound_call", "stage": "sourced"},
            )
            if sourced["status"] != "sourced":
                return sourced
            lead = sourced["lead"]
        text = summary or transcript
        label = classify_reply(text)
        self.repo.add_message(tenant_id, lead["email"], {"direction": "inbound", "body": transcript[:4000], "summary": summary, "label": label, "channel": "voice"})
        self._event("call_logged", "m7", {"email": lead["email"], "label": label, "channel": "voice"}, tenant_id)
        if label == "unsubscribe":
            self._unsubscribe(tenant_id, lead)
            return {"status": "unsubscribed"}
        if label in {"legal", "hostile", "press", "custom_request"}:
            return self._escalate(tenant_id, lead["email"], label, text, holding=False)
        if label == "interested" and lead.get("stage") in {"sourced", "contacted", "replied"}:
            self.repo.update_stage(tenant_id, lead["email"], "positive")
            self.notifier.alert(f"Positive call with {phone}: {summary[:160]}")
            return {"status": "positive", "label": label}
        return {"status": "logged", "label": label}

    def answer_qualification(self, tenant_id: str, email: str, answer: str) -> dict:
        profile = self.repo.get_profile(tenant_id)
        lead = self._lead(tenant_id, email)
        if profile is None or lead is None:
            raise ValueError("profile and lead required")
        field = next((candidate for candidate in ("need", "authority", "budget", "timeline") if not lead.get(candidate)), None)
        if field is None:
            return {"status": "already_qualified"}
        self.repo.add_message(tenant_id, lead["email"], {"direction": "inbound", "body": answer, "label": f"bant:{field}"})
        updates = {field: answer}
        if field == "budget":
            digits = "".join(ch for ch in answer if ch.isdigit() or ch == ".")
            try:
                updates["budget_amount"] = float(digits)
            except ValueError:
                updates["budget_amount"] = None
        lead = self.repo.upsert_lead(tenant_id, lead["email"], updates)
        status = assess_qualification(lead, profile["price_floor"])
        channel = self._reply_channel(lead, "email")
        if status == "disqualified":
            close = "Thanks for the context. This may not be the right fit right now — I'll pause outreach."
            self.repo.upsert_lead(tenant_id, lead["email"], {"stage": "nurture", "nurture_reason": "disqualified"})
            self._deliver(tenant_id, lead, close, channel=channel)
            if lead.get("icp_cell"):
                self.repo.update_icp_outcome(tenant_id, lead["icp_cell"], False)
            return {"status": "disqualified", "message": close}
        if status == "qualified":
            self.repo.update_stage(tenant_id, lead["email"], "qualified")
            self._event("qualified", "m9", {"email": lead["email"], "icp_cell": lead.get("icp_cell")}, tenant_id)
            return {"status": "qualified"}
        question = qualification_question(lead)
        if question:
            self._deliver(tenant_id, lead, question, channel=channel)
        return {"status": "qualifying", "question": question}

    # ------------------------------------------------------------------ closing

    def qualify_and_convert(self, tenant_id: str, email: str, slot: str | None = None) -> dict:
        profile = self.repo.get_profile(tenant_id)
        lead = self._lead(tenant_id, email)
        if profile is None or lead is None:
            raise ValueError("profile and lead required")
        if lead.get("stage") == "converted":
            return {"status": "already_converted"}
        status = assess_qualification(lead, profile["price_floor"])
        if status == "qualifying":
            return {"status": "qualifying", "question": qualification_question(lead)}
        if status == "disqualified":
            return {"status": "disqualified"}
        if lead.get("stage") not in {"proposal_sent", "payment_pending"}:
            self.repo.update_stage(tenant_id, lead["email"], "qualified")
        conversion = profile.get("conversion_definition", "qualified_meeting")
        if conversion in {"signed_proposal", "paid"}:
            return self.send_proposal(tenant_id, lead["email"])
        if not slot:
            raise ValueError("a meeting slot is required for qualified_meeting conversion")
        return self.book_and_convert(tenant_id, lead["email"], slot)

    def book_and_convert(self, tenant_id: str, email: str, slot: str, event: dict | None = None) -> dict:
        """FR-10.1 — book, confirm with a pre-call agenda, schedule reminders, hand off."""
        profile = self.repo.get_profile(tenant_id) or {}
        lead = {**(self._lead(tenant_id, email) or {}), "stage": "qualified"}
        if event is None:
            event = book_meeting(lead, profile, self.calendar, slot)
        transcript = self.repo.get_transcript(tenant_id, lead["email"])
        brief = pre_call_brief(lead, profile, transcript)
        start = _parse(slot) or _now()
        reminders = [(start - timedelta(hours=24)).isoformat(), (start - timedelta(hours=1)).isoformat()]
        confirmation = f"Confirmed for {start.strftime('%a %d %b, %H:%M %Z').strip()}. {brief['prospect']}"
        return self._convert(
            tenant_id,
            lead["email"],
            deal_status="booked",
            deal_body={"slot": slot, "event_id": event.get("id"), "reminders_due": reminders, "reminders_sent": [], "pre_call_brief": brief["owner"]},
            price_cents=_cents(profile.get("price_floor", 0)),
            extra_lines=[f"Booked {slot}"],
            handover_suffix=confirmation,
            transactional="meeting_confirmation",
            result_extra={"event": event},
        )

    def send_proposal(self, tenant_id: str, email: str, discount: float = 0.0) -> dict:
        """FR-10.2 — proposal from approved pricing, sent for e-signature; conversion waits for the signature."""
        profile = self.repo.get_profile(tenant_id)
        lead = self._lead(tenant_id, email)
        if profile is None or lead is None:
            raise ValueError("profile and lead required")
        existing = self.repo.get_deal(tenant_id, lead["email"])
        if existing and existing.get("status") in {"proposal_sent", "signed", "payment_pending", "paid"}:
            return {"status": existing["status"], "deal": existing}
        proposal = build_proposal(profile, discount)
        envelope = self.esign.send(
            email=lead["email"],
            name=lead.get("first_name", ""),
            title=f"Proposal — {profile['business_name']}",
            proposal=proposal,
            metadata={"tenant_id": tenant_id, "email": lead["email"], "external_id": f"{tenant_id}:{lead['email']}"},
        )
        deal = self.repo.add_deal(
            tenant_id,
            lead["email"],
            _cents(proposal["price"]),
            "proposal_sent",
            {
                **proposal,
                "envelope_id": envelope["envelope_id"],
                "esign_provider": envelope["provider"],
                "esign_status": "sent",
                "sign_url": envelope.get("sign_url", ""),
                "proposal_sent_at": _now().isoformat(),
                "reminders": 0,
            },
        )
        self.repo.update_stage(tenant_id, lead["email"], "proposal_sent")
        message = (
            f"Here is the proposal for {', '.join(proposal['services'])} at {proposal['price']:,.0f}, "
            f"exactly the scope we discussed. You can review and sign here: {envelope.get('sign_url', '')}"
        )
        self._deliver(tenant_id, lead, message, channel=self._reply_channel(lead, "email"))
        self._event("proposal_sent", "m10", {"email": lead["email"], "price": proposal["price"], "envelope_id": envelope["envelope_id"]}, tenant_id)
        return {"status": "proposal_sent", "deal": deal, "sign_url": envelope.get("sign_url", "")}

    def _find_deal(self, tenant_id: str, *, email: str | None = None, key: str | None = None, value: str | None = None) -> dict | None:
        if email:
            return self.repo.get_deal(tenant_id, email)
        for deal in reversed(self.repo.list_deals(tenant_id)):
            if key and deal.get(key) == value:
                return deal
        return None

    def handle_esign_event(self, tenant_id: str, status: str, *, envelope_id: str | None = None, email: str | None = None) -> dict:
        profile = self.repo.get_profile(tenant_id)
        deal = self._find_deal(tenant_id, email=email) if email else self._find_deal(tenant_id, key="envelope_id", value=envelope_id)
        if profile is None or deal is None:
            raise ValueError("unknown proposal")
        lead_email = deal["lead_email"]
        status = status.lower()
        if status in {"completed", "signed", "document_completed"}:
            if deal.get("status") in {"signed", "payment_pending", "paid"}:
                return {"status": "already_signed", "deal": deal}
            signed = mark_signed({"price": deal.get("price", deal["price_cents"] / 100), "status": "sent"}, profile)
            deal = self.repo.update_deal(tenant_id, lead_email, "signed", {"esign_status": "completed", "signed_at": signed["converted_at"]})
            self._event("proposal_signed", "m10", {"email": lead_email}, tenant_id)
            if profile.get("conversion_definition") == "paid":
                return self.send_payment_link(tenant_id, lead_email)
            return self._convert(
                tenant_id,
                lead_email,
                deal_status="signed",
                deal_body={"converted_at": signed["converted_at"]},
                price_cents=deal["price_cents"],
                extra_lines=["Proposal signed"],
            )
        if status in {"declined", "rejected", "document_rejected"}:
            deal = self.repo.update_deal(tenant_id, lead_email, "declined", {"esign_status": "declined", "declined_at": _now().isoformat()})
            self.repo.upsert_lead(tenant_id, lead_email, {"stage": "nurture", "nurture_reason": "proposal_declined"})
            lead = self._lead(tenant_id, lead_email)
            if lead:
                self._deliver(tenant_id, lead, "Thanks for considering it. I'll close this out — if things change, just reply here.")
            self.notifier.alert(f"Proposal declined by {lead_email}")
            self._event("proposal_declined", "m10", {"email": lead_email}, tenant_id)
            return {"status": "declined", "deal": deal}
        deal = self.repo.update_deal(tenant_id, lead_email, deal["status"], {"esign_status": status})
        return {"status": deal["status"], "esign_status": status, "deal": deal}

    def send_payment_link(self, tenant_id: str, email: str) -> dict:
        """FR-10.3 — deposit link; conversion fires only on the payment webhook."""
        profile = self.repo.get_profile(tenant_id)
        deal = self.repo.get_deal(tenant_id, email)
        lead = self._lead(tenant_id, email)
        if profile is None or deal is None or lead is None:
            raise ValueError("signed deal required")
        if deal.get("status") == "paid":
            return {"status": "already_paid", "deal": deal}
        deposit_pct = float(profile.get("deposit_percent", 50))
        deposit_cents = int(round(deal["price_cents"] * deposit_pct / 100))
        link = self.payments.payment_link(
            amount_cents=deposit_cents,
            currency=get_settings().payment_currency,
            email=lead["email"],
            description=f"{profile['business_name']} — deposit for {', '.join(profile.get('services', [])[:2])}",
            metadata={"tenant_id": tenant_id, "email": lead["email"]},
        )
        deal = self.repo.update_deal(
            tenant_id,
            lead["email"],
            "payment_pending",
            {"deposit_cents": deposit_cents, "payment_link": link["url"], "payment_link_id": link["link_id"], "payment_provider": link["provider"], "payment_status": "pending", "payment_sent_at": _now().isoformat(), "reminders": 0},
        )
        self.repo.update_stage(tenant_id, lead["email"], "payment_pending")
        self._deliver(tenant_id, lead, f"Thanks for signing. The deposit to get started is here: {link['url']}", channel=self._reply_channel(lead, "email"))
        self._event("payment_link_sent", "m10", {"email": lead["email"], "deposit_cents": deposit_cents, "provider": link["provider"]}, tenant_id)
        return {"status": "payment_pending", "deal": deal, "payment_link": link["url"]}

    def mark_paid(self, tenant_id: str, email: str, amount_cents: int, reference: str = "") -> dict:
        profile = self.repo.get_profile(tenant_id)
        if profile is None:
            raise ValueError("service profile required")
        deal = self.repo.get_deal(tenant_id, email)
        if deal and deal.get("status") == "paid":
            return {"status": "already_paid", "deal": deal}
        if deal and deal.get("deposit_cents"):
            if amount_cents < deal["deposit_cents"]:
                self.repo.update_deal(tenant_id, email, deal["status"], {"partial_paid_cents": amount_cents, "payment_reference": reference})
                self._escalate(tenant_id, email, "partial_payment", f"received {amount_cents} of {deal['deposit_cents']}", holding=False)
                return {"status": "partial", "received_cents": amount_cents}
            price_cents = deal["price_cents"]
        else:
            close_mark_paid({"price": amount_cents / 100, "status": "signed"}, profile)
            price_cents = amount_cents
        self._event("payment_received", "m12", {"email": email, "amount_cents": amount_cents, "reference": reference}, tenant_id)
        result = self._convert(
            tenant_id,
            email,
            deal_status="paid",
            deal_body={"payment_status": "paid", "paid_cents": amount_cents, "payment_reference": reference, "paid_at": _now().isoformat()},
            price_cents=price_cents,
            extra_lines=[f"Deposit paid ({amount_cents / 100:,.2f})"],
        )
        return {**result, "status": "paid", "deal": self.repo.get_deal(tenant_id, email)}

    def _convert(
        self,
        tenant_id: str,
        email: str,
        *,
        deal_status: str,
        deal_body: dict,
        price_cents: int,
        extra_lines: list[str] | None = None,
        handover_suffix: str = "",
        transactional: str = "handover",
        result_extra: dict | None = None,
    ) -> dict:
        """FR-11 — CRM record with transcript, brief, scope, price; freeze automation; warm hand-over."""
        profile = self.repo.get_profile(tenant_id) or {}
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        if lead.get("stage") == "converted":
            deal = self.repo.get_deal(tenant_id, email)
            if deal and deal.get("status") != deal_status:
                deal = self.repo.update_deal(tenant_id, email, deal_status, deal_body)
            return {"status": "already_converted", "deal": deal}
        transcript = self.repo.get_transcript(tenant_id, lead["email"]) + (extra_lines or [])
        package = complete_handoff(self.guard, dict(lead), profile, transcript)
        brief = pre_call_brief(lead, profile, transcript)
        package["briefing"].update(
            {
                "research_brief": lead.get("research_brief", ""),
                "agreed_scope": profile.get("services", []),
                "price_cents": price_cents,
                "one_page": brief["owner"],
                "consents": self.repo.list_consents(tenant_id, lead["email"]),
            }
        )
        handover = f"{package['message']} {handover_suffix}".strip()
        self._deliver(tenant_id, {**lead, "automation_frozen": True}, handover, channel=self._reply_channel(lead, "email"), transactional=transactional, meta={"handover": True})
        package["crm"] = crm_handoff(package, tenant_id, self.notifier)
        self.repo.upsert_lead(tenant_id, lead["email"], {"stage": "converted", "automation_frozen": True, "converted_at": _now().isoformat()})
        self.repo.set_conversation_state(tenant_id, lead["email"], "handed_off")
        if self.repo.get_deal(tenant_id, lead["email"]):
            deal = self.repo.update_deal(tenant_id, lead["email"], deal_status, {**deal_body, "handoff": True})
        else:
            deal = self.repo.add_deal(tenant_id, lead["email"], price_cents, deal_status, {**deal_body, "handoff": True})
        if lead.get("icp_cell"):
            self.repo.update_icp_outcome(tenant_id, lead["icp_cell"], True)
        self.notifier.alert(f"Converted {lead['email']} for {profile.get('human_name', 'owner')}.\n{brief['owner']}")
        self._event(
            "converted",
            "m11",
            {"email": lead["email"], "conversion": profile.get("conversion_definition"), "deal_status": deal_status, "icp_cell": lead.get("icp_cell"), "variants": lead.get("variants")},
            tenant_id,
        )
        return {"status": "converted", "handoff": package, "deal": {**(deal or {}), "status": deal_status}, **(result_extra or {})}

    def handle_calendar_event(self, tenant_id: str, email: str, slot: str, kind: str = "BOOKING_CREATED", event_id: str = "") -> dict:
        profile = self.repo.get_profile(tenant_id) or {}
        lead = self._lead(tenant_id, email)
        if lead is None:
            raise ValueError("unknown lead")
        kind = kind.upper()
        deal = self.repo.get_deal(tenant_id, email)
        if kind in {"BOOKING_CANCELLED", "BOOKING_CANCELED"}:
            if deal:
                self.repo.update_deal(tenant_id, email, "cancelled", {"cancelled_at": _now().isoformat()})
            self.notifier.alert(f"{email} cancelled the meeting at {slot}")
            return {"status": "cancelled"}
        if kind == "BOOKING_RESCHEDULED" and deal:
            start = _parse(slot) or _now()
            self.repo.update_deal(
                tenant_id,
                email,
                "booked",
                {"slot": slot, "reminders_due": [(start - timedelta(hours=24)).isoformat(), (start - timedelta(hours=1)).isoformat()], "reminders_sent": []},
            )
            return {"status": "rescheduled", "slot": slot}
        if profile.get("conversion_definition", "qualified_meeting") != "qualified_meeting":
            self.repo.add_message(tenant_id, email, {"direction": "system", "body": f"Prospect booked a call for {slot}"})
            self.notifier.alert(f"{email} booked a call for {slot}")
            return {"status": "noted"}
        if lead.get("stage") == "converted":
            return {"status": "already_converted"}
        status = assess_qualification(lead, profile.get("price_floor", 0))
        if status != "qualified":
            return self.qualify_and_convert(tenant_id, email, slot)
        return self.book_and_convert(tenant_id, email, slot, event={"id": event_id or f"cal-{_hash(email + slot)}", "slot": slot, "provider": "calendar_webhook"})

    # ------------------------------------------------------------------ deliverability & data rights

    def record_email_event(self, tenant_id: str, kind: str, email: str, mailbox: str | None = None) -> dict:
        kind = kind.lower()
        mailbox = mailbox or (self.mailboxes.pick(tenant_id) or {}).get("address", "")
        health = self.mailboxes.record_event(tenant_id, mailbox, kind)
        lead = self._lead(tenant_id, email)
        if kind in {"bounce", "hard_bounce", "bounced"}:
            self.repo.suppress(email, tenant_id=tenant_id)
            if lead:
                self.repo.upsert_lead(tenant_id, email, {"verification": "invalid", "bounced": True})
        if kind in {"complaint", "spam", "spamreport"}:
            if lead:
                self._unsubscribe(tenant_id, lead)
            else:
                self.repo.suppress(email, tenant_id=None)
        if health.get("status") == "paused":
            self.notifier.alert(f"Mailbox {mailbox} paused (bounce {health['bounce_rate']:.1%}, complaints {health['complaint_rate']:.2%}); traffic rotated.")
            if self.mailboxes.pick(tenant_id) is None:
                self.exceptions.add("all_mailboxes_paused", f"{tenant_id}: every mailbox is paused", scope="acquisition")
        self._event("email_event", "m7", {"kind": kind, "mailbox": mailbox, "email_hash": _hash(email)}, tenant_id)
        return {"kind": kind, "mailbox": health}

    def export_lead(self, tenant_id: str, email: str) -> dict:
        data = self.repo.export_lead(tenant_id, email)
        self._event("data_exported", "rights", {"email_hash": _hash(email)}, tenant_id)
        return data

    def erase_lead(self, tenant_id: str, email: str) -> dict:
        lead = self._lead(tenant_id, email)
        if lead and lead.get("phone"):
            self.repo.suppress(str(lead["phone"]), tenant_id=None)
        result = self.repo.erase_lead(tenant_id, email)
        self.guard.suppression.add(email, tenant_id=None)
        self._event("data_erased", "rights", {"email_hash": _hash(email)}, tenant_id)
        return result

    # ------------------------------------------------------------------ learning & operations

    def plan_daily_volume(self, tenant_id: str) -> dict:
        settings = get_settings()
        target = int(self.repo.get_state(tenant_id, "volume", {}).get("weekly_qualified_target", settings.acquisition_weekly_qualified_target))
        mailbox_capacity = sum(box["daily_cap"] for box in self.mailboxes.list_mailboxes(tenant_id) if box.get("ready"))
        daily_cap = min(self.tenant_cap.daily_cap, mailbox_capacity)
        return plan_volume(self.repo.list_leads(tenant_id), target, daily_cap)

    def run_daily(self, tenant_id: str, max_batches: int = 10) -> dict:
        """Always-on sourcing sized to the weekly qualified-lead target; returns leads ready for sequences."""
        if self.kill.active("acquisition") or self.kill.active(f"acquisition:tenant:{tenant_id}"):
            return {"status": "paused", "reason": "kill switch active", "ready": []}
        if not self.repo.is_profile_approved(tenant_id):
            return {"status": "blocked", "reason": "profile not approved", "ready": []}
        plan = self.plan_daily_volume(tenant_id)
        ready: list[str] = []
        for _ in range(max_batches):
            if len(ready) >= plan["daily_contacts_planned"]:
                break
            batch = self.source_batch(tenant_id)
            for item in batch["leads"]:
                if item.get("status") == "sourced" and enters_outreach(item.get("score", 0)):
                    ready.append(item["lead"]["email"])
                elif item.get("status") == "sourced":
                    self.repo.update_stage(tenant_id, item["lead"]["email"], "nurture")
            if not batch["leads"]:
                break
        ready = ready[: plan["daily_contacts_planned"]]
        self._event("daily_plan", "m5", {"planned": plan["daily_contacts_planned"], "ready": len(ready)}, tenant_id)
        return {"status": "ok", "plan": plan, "ready": ready}

    def run_weekly_learning(self, tenant_id: str, min_sends: int = 20) -> dict:
        leads = self.repo.list_leads(tenant_id)
        weights = retrain_score_weights(leads, self.repo.get_state(tenant_id, "score_weights"))
        self.repo.set_state(tenant_id, "score_weights", weights)
        changes = self.experiments.run_weekly(min_sends=min_sends, tenant_id=tenant_id)
        cells = self.repo.list_icp_cells(tenant_id)
        allocation = []
        if cells:
            for cell in allocate_bandit(cells):
                body = {key: value for key, value in cell.items() if key not in {"body"}}
                self.repo.save_icp_cell(tenant_id, cell["name"], body, cell.get("successes", 0), cell.get("failures", 0))
                allocation.append({"name": cell["name"], "budget_share": cell.get("budget_share")})
        if weights.get("status") == "trained":
            changes = changes + [
                {
                    "at": weights["trained_at"],
                    "dimension": "score_weights",
                    "summary": f"score weights fit={weights['fit']} intent={weights['intent']}",
                    "why": f"retrained on {weights['samples']} contacted leads ({weights['positives']} positive)",
                }
            ]
        summary = {"weights": weights, "changes": changes, "allocation": allocation, "ran_at": _now().isoformat()}
        self.repo.set_state(tenant_id, "weekly_learning", summary)
        if changes:
            self.notifier.alert("This week the engine changed: " + "; ".join(change["summary"] for change in changes))
        self._event("weekly_learning", "m12", {"changes": len(changes), "weights_status": weights.get("status")}, tenant_id)
        return summary

    def money(self, tenant_id: str) -> dict:
        ledger = self.repo.get_state(tenant_id, "spend", {"by_category": {}, "total_cents": 0})
        deals = self.repo.list_deals(tenant_id)
        converted = self.repo.funnel_counts(tenant_id).get("converted", 0)
        spend = ledger.get("total_cents", 0)
        open_statuses = {"proposal_sent", "signed", "payment_pending", "booked"}
        return {
            "spend_cents": spend,
            "spend_by_category": ledger.get("by_category", {}),
            "converted": converted,
            "cpcc_cents": round(spend / converted, 2) if converted else None,
            "pipeline_value_cents": sum(
                deal.get("price_cents", 0) for deal in deals if deal.get("status") in open_statuses and not deal.get("handoff")
            ),
            "revenue_cents": sum(deal.get("paid_cents", deal.get("price_cents", 0)) for deal in deals if deal.get("status") in {"paid", "signed"} and deal.get("handoff")),
            "deals": len(deals),
        }

    def run_monthly_report(self, tenant_id: str, month: str | None = None) -> dict:
        month = month or _now().strftime("%Y-%m")
        changes = [change for change in self.experiments.changes(tenant_id) if str(change.get("at", "")).startswith(month)]
        weights = self.repo.get_state(tenant_id, "score_weights")
        report = build_monthly_report(
            month,
            self.repo.funnel_counts(tenant_id),
            self.repo.funnel_by_icp(tenant_id),
            self.money(tenant_id),
            changes,
            weights,
        )
        self.repo.set_state(tenant_id, f"report:{month}", report)
        index = self.repo.get_state(tenant_id, "reports", {"months": []})
        if month not in index["months"]:
            index["months"] = sorted(index["months"] + [month])
            self.repo.set_state(tenant_id, "reports", index)
        self.notifier.alert(report["text"])
        self._event("monthly_report", "m12", {"month": month}, tenant_id)
        return report

    def sweep(self, tenant_id: str, now: datetime | None = None) -> dict:
        """Durable timers in one pass: calls, re-contacts, meeting reminders, closing follow-ups, escalation SLA."""
        now = now or _now()
        profile = self.repo.get_profile(tenant_id) or {}
        done = {"calls": 0, "recontacts": 0, "reminders": 0, "closing_followups": 0, "sla_alerts": 0}
        for lead in self.repo.list_leads(tenant_id):
            call_at = _parse(lead.get("call_at"))
            if call_at and not lead.get("call_placed") and call_at <= now:
                self.place_call(tenant_id, lead["email"])
                done["calls"] += 1
            recontact = _parse(lead.get("recontact_at"))
            if lead.get("stage") == "nurture" and recontact and recontact <= now and not self.repo.is_suppressed(lead["email"]):
                body = (
                    f"{lead.get('first_name', '')}, you mentioned reconnecting around now. "
                    f"{(profile.get('faq') or [''])[0]} Is this a better time?"
                ).strip()
                if critique(body, self._corpus(profile), first_touch=False)["passed"]:
                    sent = self._deliver(tenant_id, lead, body, channel=self._reply_channel(lead, "email"))
                    if sent["sent"]:
                        self.repo.upsert_lead(tenant_id, lead["email"], {"stage": "replied", "recontact_at": None, "recontacted_at": now.isoformat()})
                        done["recontacts"] += 1
        for deal in self.repo.list_deals(tenant_id):
            email = deal["lead_email"]
            lead = self._lead(tenant_id, email)
            if lead is None:
                continue
            if deal.get("status") == "booked":
                sent = list(deal.get("reminders_sent", []))
                for due in deal.get("reminders_due", []):
                    due_at = _parse(due)
                    slot = _parse(deal.get("slot"))
                    if due in sent or due_at is None or due_at > now or (slot and slot <= now):
                        continue
                    text = f"Reminder: your call with {profile.get('human_name', 'us')} is at {slot.strftime('%a %d %b, %H:%M') if slot else deal.get('slot')}."
                    if self._deliver(tenant_id, lead, text, channel=self._reply_channel(lead, "email"), transactional="meeting_reminder")["sent"]:
                        sent.append(due)
                        done["reminders"] += 1
                if sent != deal.get("reminders_sent", []):
                    self.repo.update_deal(tenant_id, email, "booked", {"reminders_sent": sent})
            if deal.get("status") in {"proposal_sent", "payment_pending"}:
                started = _parse(deal.get("payment_sent_at") if deal["status"] == "payment_pending" else deal.get("proposal_sent_at"))
                reminders = int(deal.get("reminders", 0))
                if started is None or now < started + timedelta(days=PROPOSAL_REMINDER_DAYS * (reminders + 1)):
                    continue
                if reminders >= MAX_CLOSING_REMINDERS:
                    self.repo.update_deal(tenant_id, email, "stalled", {"stalled_at": now.isoformat()})
                    self._escalate(tenant_id, email, f"{deal['status']}_stalled", "no response after reminders", holding=False)
                    continue
                if deal["status"] == "proposal_sent":
                    try:
                        self.esign.remind(deal.get("envelope_id", ""))
                    except Exception:
                        pass
                    text = f"Following up on the proposal — happy to answer anything before you sign: {deal.get('sign_url', '')}"
                else:
                    text = f"A quick reminder that the deposit link is ready whenever you are: {deal.get('payment_link', '')}"
                if self._deliver(tenant_id, lead, text, channel=self._reply_channel(lead, "email"))["sent"]:
                    self.repo.update_deal(tenant_id, email, deal["status"], {"reminders": reminders + 1})
                    done["closing_followups"] += 1
        done["sla_alerts"] = self.check_escalation_sla(tenant_id, now)
        return done

    def check_escalation_sla(self, tenant_id: str, now: datetime | None = None) -> int:
        now = now or _now()
        hours = get_settings().acquisition_escalation_sla_hours
        notified = set(self.repo.get_state(tenant_id, "sla_notified", {"ids": []}).get("ids", []))
        breached = []
        for item in self.exceptions.list_open("acquisition"):
            created = _parse(item.get("created_at"))
            if created and now - created >= timedelta(hours=hours) and item["id"] not in notified:
                breached.append(item)
        for item in breached:
            self.notifier.alert(f"Escalation #{item['id']} ({item['kind']}) has waited over {hours}h: {item['message']}")
            notified.add(item["id"])
        if breached:
            self.repo.set_state(tenant_id, "sla_notified", {"ids": sorted(notified)})
        return len(breached)

    # ------------------------------------------------------------------ demo

    def run_demo(self, tenant_id: str, profile: dict, lead: dict, reply: str, slot: str) -> dict:
        lead = {**lead, "email": lead.get("email") or f"lead-{uuid.uuid4().hex[:8]}@buyer.example"}
        self.repo.save_profile(tenant_id, profile, approved=True)
        sourced = self.source_lead(tenant_id, lead)
        if sourced["status"] != "sourced":
            return sourced
        contacted = self.outreach(tenant_id, lead["email"], force=True)
        if contacted["status"] != "contacted":
            return contacted
        replied = self.handle_reply(tenant_id, lead["email"], reply)
        if replied["status"] not in {"replied", "positive"}:
            return replied
        self.repo.upsert_lead(
            tenant_id,
            lead["email"],
            {
                "need": "checkout friction",
                "authority": "yes",
                "budget": str(profile["price_floor"]),
                "budget_amount": profile["price_floor"],
                "timeline": "this month",
            },
        )
        result = self.qualify_and_convert(tenant_id, lead["email"], slot)
        if result["status"] == "proposal_sent" and getattr(self.esign, "name", "") == "memory":
            result = self.handle_esign_event(tenant_id, "completed", envelope_id=result["deal"]["envelope_id"])
        if result["status"] == "payment_pending" and getattr(self.payments, "name", "") == "memory":
            result = self.mark_paid(tenant_id, lead["email"], result["deal"]["deposit_cents"], reference="demo")
        return result
