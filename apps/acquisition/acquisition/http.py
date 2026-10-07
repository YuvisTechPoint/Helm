from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from acquisition.close import build_proposal, quote_price
from acquisition.defaults import ensure_ready_profile
from acquisition.funnel import activate_prompt, evaluate_classifier, first_touch, score_lead
from acquisition.pipeline_e2e import LeadPipeline
from acquisition.policy import PolicyGuard, critique
from acquisition.repository import AcquisitionRepository
from acquisition.tenancy import TenantDirectory
from core.config import Settings
from core.errors import BudgetExceeded, IsolationError, PolicyDenied
from core.http_platform import paginate

CHANNELS = ("email", "whatsapp", "sms", "voice")


class ProfileIn(BaseModel):
    business_name: str
    services: list[str]
    proof_points: list[str]
    price_floor: float
    list_price: float
    discount_limit: float
    conversion_definition: str = "qualified_meeting"
    human_name: str
    faq: list[str] = []
    faq_terms: list[str] = []
    objections: dict[str, str] = {}
    ideal_clients: list[str] = Field(default_factory=list)
    anti_ideal_clients: list[str] = Field(default_factory=list)
    existing_clients: list[str] = Field(default_factory=list)
    competitor_domains: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=lambda: ["india"])
    languages: list[str] = Field(default_factory=lambda: ["en"])
    guarantees: list[str] = Field(default_factory=list)
    testimonials: list[str] = Field(default_factory=list)
    case_studies: list[dict] = Field(default_factory=list)
    calendar_link: str = ""
    website: str = ""
    deposit_percent: float = Field(default=50, ge=1, le=100)
    timezone: str = "Asia/Kolkata"
    lawful_basis: str = "legitimate_interest"
    notify: str = "email"
    enforce_business_hours: bool = True
    version: int = 1
    submit_for_review: bool = False


class TenantIn(BaseModel):
    tenant_id: str
    region: str


class DomainIn(BaseModel):
    tenant_id: str
    domain: str


class SpendIn(BaseModel):
    tenant_id: str
    amount: int
    category: str = "data"


class ScoreIn(BaseModel):
    email: str = "sample@buyer.example"
    first_name: str = "Ada"
    company: str = "Example Co"
    reason: str = ""
    fit: float = 0.7
    intent: float = 0.6
    industry: str = ""
    title: str = ""
    geo: str = ""
    size: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    verification: str = "valid"


class LeadIn(BaseModel):
    email: str
    first_name: str
    company: str
    reason: str = ""
    fit: float = 0.7
    intent: float = 0.6
    industry: str = ""
    title: str = ""
    phone: str = ""
    language: str = ""
    geo: str = ""
    size: str = ""
    tech_stack: list[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def email_has_at(cls, value: str) -> str:
        if "@" not in value or " " in value.strip():
            raise ValueError("email must be a single address")
        return value.strip().lower()


class ReplyIn(BaseModel):
    email: str
    text: str
    channel: str = "email"


class ConvertIn(BaseModel):
    email: str
    slot: str = ""


class QualifyIn(BaseModel):
    email: str
    answer: str


class InboundFormIn(BaseModel):
    email: str
    first_name: str
    company: str
    message: str
    channel: str = "email"
    basis: str = "consent"
    phone: str = ""


class ConsentIn(BaseModel):
    email: str
    channel: str
    basis: str = "consent"
    source: str = "owner"
    evidence: str = ""


class WithdrawIn(BaseModel):
    email: str
    channel: str | None = None


class ProposalIn(BaseModel):
    email: str
    discount: float = 0.0


class KillIn(BaseModel):
    scope: str = Field(pattern="^(global|acquisition|tenant|channel)$")
    active: bool
    reason: str = ""
    channel: str | None = None


class MailboxIn(BaseModel):
    address: str
    domain: str
    daily_cap: int = Field(default=30, ge=1, le=200)
    warmed: bool = False


class ObserveIn(BaseModel):
    bounce_rate: float
    complaint_rate: float
    inbox_rate: float
    address: str | None = None


class ClientsIn(BaseModel):
    clients: list[dict]


class VolumeIn(BaseModel):
    weekly_qualified_target: int = Field(ge=1, le=1000)


class AcquisitionState:
    def __init__(self, settings: Settings | None = None, session=None):
        self.settings = settings or Settings()
        self.session = session
        self.repo = AcquisitionRepository(session)
        self.guard = PolicyGuard()
        self.tenants = TenantDirectory()
        self.tenants.create(self.settings.acquisition_tenant_id, self.settings.acquisition_region)
        self.tenants.set_budget(self.settings.acquisition_tenant_id, 10_000)
        self.pipeline = LeadPipeline(self.repo, self.guard)
        self.exceptions = self.pipeline.exceptions
        self.prompt = {"name": "reply-v1", "active": False}

    @property
    def spend_cents(self) -> int:
        return self.pipeline.money(self.settings.acquisition_tenant_id)["spend_cents"]


def _kill_scope(body: KillIn, tenant_id: str) -> str:
    if body.scope == "global":
        return "global"
    if body.scope == "acquisition":
        return "acquisition"
    if body.scope == "tenant":
        return f"acquisition:tenant:{tenant_id}"
    if body.channel not in CHANNELS:
        raise HTTPException(400, f"channel must be one of {', '.join(CHANNELS)}")
    return f"acquisition:channel:{body.channel}"


def router(state: AcquisitionState) -> APIRouter:
    api = APIRouter(prefix="/acquisition", tags=["acquisition"])
    tenant = state.settings.acquisition_tenant_id
    pipeline = state.pipeline

    def guarded(call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except (ValueError, PolicyDenied) as exc:
            raise HTTPException(409, str(exc)) from exc

    def scoped(requested: str) -> str:
        if requested != tenant:
            try:
                state.tenants.leads_for(tenant, requested)
            except IsolationError as exc:
                raise HTTPException(403, str(exc)) from exc
            except KeyError as exc:
                raise HTTPException(403, "unknown tenant") from exc
        return requested

    # ------------------------------------------------------------------ dashboard views

    @api.get("/ops")
    def ops(tenant_id: str = tenant):
        tenant_id = scoped(tenant_id)
        profile = state.repo.get_profile_meta(tenant_id)
        money = pipeline.money(tenant_id)
        volume = pipeline.plan_daily_volume(tenant_id)
        return {
            "tenant_id": tenant_id,
            "profile_approved": bool(profile and profile.get("approved")),
            "kill": {
                "global": pipeline.kill.active("global"),
                "acquisition": pipeline.kill.active("acquisition"),
                "tenant": pipeline.kill.active(f"acquisition:tenant:{tenant_id}"),
            },
            "funnel": state.repo.funnel_counts(tenant_id),
            "money": money,
            "volume": volume,
            "mailboxes_ready": sum(1 for box in pipeline.mailboxes.list_mailboxes(tenant_id) if box.get("ready")),
            "open_escalations": len(state.exceptions.list_open("acquisition")),
        }

    @api.post("/score")
    def score_preview(body: ScoreIn, tenant_id: str = tenant):
        from acquisition.modules.scoring import compute_scores
        from acquisition.modules.triggers import detect_triggers

        tenant_id = scoped(tenant_id)
        profile = state.repo.get_profile(tenant_id) or {}
        lead = body.model_dump()
        cells = state.repo.list_icp_cells(tenant_id)
        icp = cells[0] if cells else {}
        triggers = detect_triggers(body.reason, profile)
        return compute_scores(lead, icp, profile, body.verification, triggers, weights=pipeline._weights(tenant_id), converted=pipeline._converted_examples(tenant_id))

    @api.get("/funnel")
    def funnel(tenant_id: str = tenant):
        tenant_id = scoped(tenant_id)
        return {
            "tenant_id": tenant_id,
            "counts": state.repo.funnel_counts(tenant_id),
            "by_icp": state.repo.funnel_by_icp(tenant_id),
        }

    @api.get("/money")
    def money(tenant_id: str = tenant):
        return pipeline.money(scoped(tenant_id))

    @api.get("/deals")
    def deals(tenant_id: str = tenant, limit: int = 50, offset: int = 0):
        page = paginate(state.repo.list_deals(scoped(tenant_id)), limit, offset)
        return {"deals": page["items"], **page}

    @api.get("/leads")
    def list_leads(tenant_id: str = tenant, stage: str | None = None, limit: int = 50, offset: int = 0):
        tenant_id = scoped(tenant_id)
        leads = state.repo.list_leads(tenant_id)
        if stage:
            leads = [lead for lead in leads if lead.get("stage") == stage]
        keep = ("email", "first_name", "company", "stage", "score", "fit", "intent", "icp_cell", "active_channel", "variants", "phone", "lookalike")
        slim = [{key: lead.get(key) for key in keep} for lead in leads]
        page = paginate(slim, limit, offset)
        return {"leads": page["items"], **page}

    @api.get("/leads/{email}")
    def get_lead(email: str, tenant_id: str = tenant):
        tenant_id = scoped(tenant_id)
        lead = next((row for row in state.repo.list_leads(tenant_id) if row["email"] == email.lower()), None)
        if lead is None:
            raise HTTPException(404, "lead not found")
        thread = next((row for row in state.repo.list_conversations(tenant_id) if row["lead_email"] == email.lower()), None)
        return {"lead": lead, "deal": state.repo.get_deal(tenant_id, email), "conversation": thread}

    @api.get("/experiments")
    def experiments(tenant_id: str = tenant):
        tenant_id = scoped(tenant_id)
        store = pipeline.experiments
        return {
            "experiments": store.list(tenant_id),
            "by_dimension": store.by_dimension(tenant_id),
            "winner": store.promote(min_sends=20, tenant_id=tenant_id),
            "changes": store.changes(tenant_id)[-20:],
        }

    @api.get("/mailboxes")
    def mailboxes(tenant_id: str = tenant):
        return {"mailboxes": pipeline.mailboxes.list_mailboxes(tenant_id)}

    @api.post("/mailboxes")
    def add_mailbox(body: MailboxIn, tenant_id: str = tenant):
        profile = state.repo.get_profile(tenant_id) or {}
        primary = (profile.get("website") or "").lower().replace("https://", "").replace("http://", "").split("/")[0].removeprefix("www.")
        if primary and body.domain.lower() == primary:
            raise HTTPException(400, "never send cold email from the primary business domain; use a secondary domain")
        try:
            state.tenants.assign_domain(tenant_id, body.domain.lower())
        except IsolationError as exc:
            raise HTTPException(409, str(exc)) from exc
        except KeyError:
            pass
        return guarded(pipeline.mailboxes.add_mailbox, tenant_id, body.address, body.domain.lower(), body.daily_cap, body.warmed)

    @api.post("/mailboxes/{address}/pause")
    def pause_mailbox(address: str, tenant_id: str = tenant):
        pipeline.mailboxes.set_paused(tenant_id, address.lower(), True)
        return {"address": address, "paused": True}

    @api.post("/mailboxes/{address}/resume")
    def resume_mailbox(address: str, tenant_id: str = tenant):
        pipeline.mailboxes.set_paused(tenant_id, address.lower(), False)
        return {"address": address, "paused": False}

    @api.post("/mailboxes/observe")
    def observe_mailbox(body: ObserveIn, tenant_id: str = tenant):
        status = pipeline.mailboxes.observe(tenant_id, body.bounce_rate, body.complaint_rate, body.inbox_rate, body.address)
        if status == "paused":
            pipeline.notifier.alert(f"Mailbox {body.address or 'default'} paused on deliverability signals")
        return {"status": status}

    @api.get("/channels")
    def channels():
        from acquisition.providers.messaging import channel_status

        status = channel_status(state.settings)
        for name in CHANNELS:
            status.setdefault(name, {})["killed"] = pipeline.kill.active(f"acquisition:channel:{name}")
        return {"channels": status}

    @api.get("/icp")
    def list_icp(tenant_id: str = tenant):
        return {"cells": state.repo.list_icp_cells(tenant_id)}

    @api.get("/conversations")
    def conversations(tenant_id: str = tenant, q: str | None = None, limit: int = 50, offset: int = 0):
        rows = state.repo.list_conversations(scoped(tenant_id))
        if q:
            needle = q.lower()
            rows = [
                row
                for row in rows
                if needle in row["lead_email"].lower() or any(needle in str(message.get("body", "")).lower() for message in row.get("messages", []))
            ]
        page = paginate(rows, limit, offset)
        return {"conversations": page["items"], **page}

    @api.get("/escalations")
    def escalations():
        return {"escalations": state.exceptions.list_open("acquisition"), "sla_hours": state.settings.acquisition_escalation_sla_hours}

    @api.post("/escalations/{item_id}/resolve")
    def resolve_escalation(item_id: int, body: dict | None = None):
        if not state.exceptions.resolve(item_id):
            raise HTTPException(404, "escalation not found")
        if body and body.get("profile_addition"):
            profile = state.repo.get_profile(tenant)
            if profile:
                addition = body["profile_addition"]
                profile.setdefault("faq", []).append(addition)
                terms = [word.lower() for word in addition.split() if len(word) > 4][:5]
                profile["faq_terms"] = list(dict.fromkeys(profile.get("faq_terms", []) + terms))
                state.repo.save_profile(tenant, profile, approved=True)
        return {"resolved": item_id}

    # ------------------------------------------------------------------ profile & ICP

    @api.get("/profile")
    def get_profile(tenant_id: str = tenant):
        profile = state.repo.get_profile_meta(tenant_id)
        if profile is None:
            raise HTTPException(404, "profile not found")
        return profile

    @api.post("/profile")
    def save_profile(body: ProfileIn, tenant_id: str = tenant):
        payload = body.model_dump()
        payload.pop("submit_for_review", None)
        row = state.repo.save_profile(tenant_id, payload, approved=not body.submit_for_review)
        return {"version": row["version"], "approved": row["approved"]}

    @api.post("/profile/draft")
    def draft_profile(url: str, tenant_id: str = tenant):
        from acquisition.modules.profile_draft import draft_profile_from_url
        from acquisition.runtime_ctx import acquisition_runtime

        return draft_profile_from_url(url, acquisition_runtime().llm)

    @api.post("/profile/approve")
    def approve_profile(tenant_id: str = tenant):
        row = state.repo.approve_profile(tenant_id)
        if row is None:
            raise HTTPException(404, "profile not found")
        return {"approved": True, "version": row.get("version", 1)}

    @api.post("/icp/generate")
    def generate_icp(tenant_id: str = tenant):
        from acquisition.modules.icp import allocate_bandit, generate_icp_hypotheses
        from acquisition.runtime_ctx import acquisition_runtime

        profile = ensure_ready_profile(state.repo, tenant_id)
        cells = generate_icp_hypotheses(profile, acquisition_runtime().llm)
        allocated = allocate_bandit(cells)
        for cell in allocated:
            state.repo.save_icp_cell(tenant_id, cell["name"], cell, cell.get("successes", 0), cell.get("failures", 0))
        return {"cells": allocated}

    @api.post("/clients/seed")
    def seed_clients(body: ClientsIn, tenant_id: str = tenant):
        return guarded(pipeline.seed_clients, tenant_id, body.clients)

    # ------------------------------------------------------------------ consent & data rights

    @api.post("/consent")
    def record_consent(
        body: ConsentIn | None = None,
        email: str | None = None,
        channel: str | None = None,
        basis: str | None = None,
        tenant_id: str = tenant,
    ):
        if body is None:
            if not (email and channel and basis):
                raise HTTPException(400, "email, channel and basis are required")
            body = ConsentIn(email=email, channel=channel, basis=basis)
        if body.channel not in CHANNELS:
            raise HTTPException(400, f"channel must be one of {', '.join(CHANNELS)}")
        return state.repo.record_consent(tenant_id, body.email, body.channel, body.basis, source=body.source, evidence=body.evidence)

    @api.get("/consent/{email}")
    def list_consent(email: str, tenant_id: str = tenant):
        return {"consents": state.repo.list_consents(tenant_id, email)}

    @api.post("/consent/withdraw")
    def withdraw_consent(body: WithdrawIn, tenant_id: str = tenant):
        return {"withdrawn": state.repo.withdraw_consent(tenant_id, body.email, body.channel)}

    @api.get("/leads/{email}/export")
    def export_lead(email: str, tenant_id: str = tenant):
        return pipeline.export_lead(tenant_id, email)

    @api.delete("/leads/{email}")
    def erase_lead(email: str, tenant_id: str = tenant):
        return pipeline.erase_lead(tenant_id, email)

    # ------------------------------------------------------------------ sourcing & outreach

    @api.post("/leads")
    def create_lead(body: LeadIn, tenant_id: str = tenant):
        return pipeline.source_lead(tenant_id, {key: value for key, value in body.model_dump().items() if value not in ("", [])})

    @api.post("/leads/source-batch")
    def source_batch(tenant_id: str = tenant):
        ensure_ready_profile(state.repo, tenant_id)
        try:
            return pipeline.source_batch(tenant_id)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/leads/{email}/workflow")
    def start_lead_workflow(email: str, tenant_id: str = tenant):
        from acquisition.orchestrator import start_workflow

        lead = next((row for row in state.repo.list_leads(tenant_id) if row["email"] == email.lower()), None)
        if state.repo.get_profile(tenant_id) is None or lead is None:
            raise HTTPException(404, "profile or lead not found")
        return start_workflow("LeadSequenceWorkflow", {"tenant_id": tenant_id, "email": lead["email"]}, workflow_id=f"lead-seq-{tenant_id}-{lead['email']}")

    @api.post("/leads/outreach")
    def outreach_lead(body: LeadIn, tenant_id: str = tenant):
        pipeline.source_lead(tenant_id, {key: value for key, value in body.model_dump().items() if value not in ("", [])})
        try:
            return pipeline.outreach(tenant_id, body.email)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.get("/volume")
    def volume(tenant_id: str = tenant):
        return pipeline.plan_daily_volume(tenant_id)

    @api.post("/volume")
    def set_volume(body: VolumeIn, tenant_id: str = tenant):
        state.repo.set_state(tenant_id, "volume", {"weekly_qualified_target": body.weekly_qualified_target})
        return pipeline.plan_daily_volume(tenant_id)

    @api.post("/daily/run")
    def run_daily(tenant_id: str = tenant):
        from acquisition.orchestrator import start_workflow

        ensure_ready_profile(state.repo, tenant_id)
        return start_workflow("AcquisitionDailyWorkflow", {"tenant_id": tenant_id})

    @api.post("/sweep")
    def sweep(tenant_id: str = tenant):
        return pipeline.sweep(tenant_id)

    # ------------------------------------------------------------------ conversation

    @api.post("/inbound/email")
    def inbound_email(body: ReplyIn, tenant_id: str = tenant):
        try:
            return pipeline.handle_reply(tenant_id, body.email, body.text, channel=body.channel)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/inbound/form")
    def inbound_form(body: InboundFormIn, tenant_id: str = tenant):
        lead = {
            "email": body.email,
            "first_name": body.first_name,
            "company": body.company,
            "channel": body.channel,
            "basis": body.basis,
        }
        if body.phone:
            lead["phone"] = body.phone
        try:
            return pipeline.source_inbound(tenant_id, lead, body.message)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/channels/switch")
    def switch_channel(body: ReplyIn, tenant_id: str = tenant):
        return guarded(pipeline.switch_channel, tenant_id, body.email, body.text, body.channel)

    @api.post("/calls/{email}")
    def place_call(email: str, tenant_id: str = tenant):
        return guarded(pipeline.place_call, tenant_id, email)

    @api.post("/qualify")
    def qualify(body: QualifyIn, tenant_id: str = tenant):
        try:
            return pipeline.answer_qualification(tenant_id, body.email, body.answer)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    # ------------------------------------------------------------------ closing

    @api.post("/convert")
    def convert(body: ConvertIn, tenant_id: str = tenant):
        try:
            return pipeline.qualify_and_convert(tenant_id, body.email, body.slot or None)
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/proposals")
    def send_proposal(body: ProposalIn, tenant_id: str = tenant):
        return guarded(pipeline.send_proposal, tenant_id, body.email, body.discount)

    @api.post("/proposals/{email}/payment-link")
    def payment_link(email: str, tenant_id: str = tenant):
        return guarded(pipeline.send_payment_link, tenant_id, email)

    @api.post("/demo")
    def run_demo(body: ReplyIn | None = None, tenant_id: str = tenant):
        import uuid

        profile = ensure_ready_profile(state.repo, tenant_id)
        lead = {
            "email": f"lead-{uuid.uuid4().hex[:8]}@buyer.example",
            "first_name": "Ada",
            "company": "Example Co",
            "reason": "checkout hides shipping rates until account creation",
            "fit": 0.8,
            "intent": 0.7,
        }
        reply = body.text if body else "Interested — let's talk next week."
        try:
            return pipeline.run_demo(tenant_id, profile, lead, reply, "2026-10-15T10:00:00+05:30")
        except PolicyDenied as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/quote")
    def quote(discount: float = 0, tenant_id: str = tenant):
        profile = ensure_ready_profile(state.repo, tenant_id)
        try:
            price = quote_price(profile["list_price"], discount, profile["price_floor"], profile["discount_limit"])
        except PolicyDenied as exc:
            raise HTTPException(409, str(exc)) from exc
        return build_proposal({**profile, "list_price": profile["list_price"]}, discount) | {"price": price}

    # ------------------------------------------------------------------ controls

    @api.get("/controls")
    def controls(tenant_id: str = tenant):
        kill = pipeline.kill
        return {
            "global": kill.active("global"),
            "acquisition": kill.active("acquisition"),
            "tenant": kill.active(f"acquisition:tenant:{tenant_id}"),
            "channels": {name: kill.active(f"acquisition:channel:{name}") for name in CHANNELS},
            "reason": kill.reason("acquisition") or kill.reason(f"acquisition:tenant:{tenant_id}"),
        }

    @api.post("/controls/kill")
    def set_kill(body: KillIn, tenant_id: str = tenant):
        scope = _kill_scope(body, tenant_id)
        pipeline.kill.set(scope, body.active, body.reason)
        pipeline._event("kill_switch", "controls", {"scope": scope, "active": body.active, "reason": body.reason}, tenant_id)
        return {"scope": scope, "active": body.active}

    @api.post("/tenants")
    def create_tenant(body: TenantIn):
        try:
            return state.tenants.create(body.tenant_id, body.region)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @api.post("/domains")
    def assign_domain(body: DomainIn):
        try:
            state.tenants.assign_domain(body.tenant_id, body.domain)
        except IsolationError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"domain": body.domain, "tenant_id": body.tenant_id}

    @api.post("/spend")
    def spend(body: SpendIn):
        try:
            state.tenants.spend(body.tenant_id, body.amount)
        except BudgetExceeded as exc:
            raise HTTPException(409, str(exc)) from exc
        ledger = state.repo.get_state(body.tenant_id, "spend", {"by_category": {}, "total_cents": 0})
        ledger.setdefault("by_category", {})
        ledger["by_category"][body.category] = ledger["by_category"].get(body.category, 0) + body.amount
        ledger["total_cents"] = ledger.get("total_cents", 0) + body.amount
        state.repo.set_state(body.tenant_id, "spend", ledger)
        return state.tenants.tenants[body.tenant_id]

    # ------------------------------------------------------------------ learning & evaluation

    @api.get("/learning")
    def learning(tenant_id: str = tenant):
        ensure_ready_profile(state.repo, tenant_id)
        return {
            "weights": state.repo.get_state(tenant_id, "score_weights"),
            "last_run": state.repo.get_state(tenant_id, "weekly_learning"),
            "prompt": state.repo.get_state(tenant_id, "prompt"),
            "volume": pipeline.plan_daily_volume(tenant_id),
        }

    @api.post("/learning/run")
    def run_learning(tenant_id: str = tenant, min_sends: int = 20):
        return pipeline.run_weekly_learning(tenant_id, min_sends)

    @api.get("/reports")
    def reports(tenant_id: str = tenant):
        months = state.repo.get_state(tenant_id, "reports", {"months": []})["months"]
        return {"reports": [state.repo.get_state(tenant_id, f"report:{month}") for month in reversed(months)]}

    @api.post("/reports/monthly")
    def monthly_report(tenant_id: str = tenant, month: str | None = None):
        return pipeline.run_monthly_report(tenant_id, month)

    @api.get("/eval")
    def eval_classifier():
        return evaluate_classifier()

    @api.post("/prompts/activate")
    def activate(tenant_id: str = tenant):
        current = state.repo.get_state(tenant_id, "prompt", {})
        try:
            activate_prompt(state.prompt, baseline_accuracy=current.get("eval", {}).get("accuracy"))
        except PolicyDenied as exc:
            raise HTTPException(409, str(exc)) from exc
        state.repo.set_state(tenant_id, "prompt", state.prompt)
        return state.prompt

    @api.post("/schedules/bootstrap")
    def bootstrap_schedules():
        from acquisition.schedules import bootstrap_schedules

        return {"schedules": bootstrap_schedules()}

    @api.post("/sample-email")
    def sample_email(tenant_id: str = tenant):
        profile = ensure_ready_profile(state.repo, tenant_id)
        lead = {"first_name": "Asha", "reason": "your checkout asks for account creation before shipping rates", "company": "Example Co"}
        body = first_touch(lead, profile)
        corpus = " ".join(profile["proof_points"] + profile["services"] + [profile["business_name"]])
        verdict = critique(body, corpus, first_touch=True)
        if not verdict["passed"]:
            raise HTTPException(409, "; ".join(verdict["reasons"]))
        fit = score_lead(0.8, 0.7, 1)
        return {"body": body, "critic": verdict, "score": fit, "guard": state.guard.sender_calls}

    return api
