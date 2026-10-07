import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from temporalio import activity

from acquisition.funnel import classify_reply, draft_reply, follow_up
from acquisition.modules.icp import generate_icp
from acquisition.modules.llm_copy import LlmCopywriter, LlmCritic
from acquisition.providers.enrichment import enrich_lead
from acquisition.providers.sourcing import source_leads
from acquisition.runtime_ctx import acquisition_runtime

SEND_WINDOWS = {"morning": (9, 11), "midday": (11, 13), "afternoon": (14, 16)}
_PIPELINE = None


def _pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        from acquisition.pipeline_e2e import LeadPipeline

        ctx = acquisition_runtime()
        _PIPELINE = LeadPipeline(ctx.repo, ctx.guard)
    return _PIPELINE


def send_window_delay(now: datetime, tz_name: str, window: str, rng: random.Random | None = None) -> int:
    """Seconds until a randomised minute inside the next weekday send window in the prospect's time zone."""
    rng = rng or random.Random()
    start_hour, end_hour = SEND_WINDOWS.get(window, SEND_WINDOWS["morning"])
    local = now.astimezone(ZoneInfo(tz_name))
    for day in range(0, 8):
        candidate_day = local + timedelta(days=day)
        if candidate_day.weekday() >= 5:
            continue
        window_start = candidate_day.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        window_end = candidate_day.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        if window_end <= local:
            continue
        earliest = max(window_start, local)
        span = int((window_end - earliest).total_seconds())
        target = earliest + timedelta(seconds=rng.randint(0, max(span - 60, 0)))
        return max(0, int((target - local).total_seconds()))
    return 3600


@activity.defn
def draft_email(payload: dict) -> dict:
    ctx = acquisition_runtime()
    profile = payload["profile"]
    lead = payload["lead"]
    touch = payload.get("touch")
    copywriter = LlmCopywriter(ctx.llm)
    critic = LlmCritic(ctx.llm)
    if touch:
        body = follow_up(lead, profile, 1)
    else:
        body = copywriter.first_touch(lead, profile)
    corpus = " ".join(profile.get("proof_points", []) + profile.get("services", []) + [profile["business_name"]])
    verdict = critic.critique(body, corpus, first_touch=touch is None)
    return {"body": body, "critic_passed": verdict["passed"], "reasons": verdict["reasons"]}


@activity.defn
def authorize_email(payload: dict) -> dict:
    if not payload.get("critic_passed"):
        return {"sent": False, "reason": "critic failed"}
    ctx = acquisition_runtime()
    try:
        ctx.guard.send(payload["request"], ctx.sender.send, mailbox_limiter=ctx.mailbox_limiter)
        if ctx.budget:
            ctx.budget.charge(payload["request"].get("tenant_id", "local"), "email", 5, pause_at=0.9)
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}
    return {"sent": True}


@activity.defn
def classify_inbound(payload: dict) -> dict:
    if payload.get("email") and payload.get("tenant_id"):
        return _pipeline().handle_reply(payload["tenant_id"], payload["email"], payload["text"], channel=payload.get("channel", "email"))
    label = classify_reply(payload["text"])
    draft = draft_reply(label, payload["text"], payload["profile"], payload.get("brief", ""))
    return {"label": label, "text": draft["text"], "escalate": draft["escalate"]}


@activity.defn
def source_icp_leads(payload: dict) -> dict:
    ctx = acquisition_runtime()
    icp = payload.get("icp") or generate_icp(payload.get("profile", {}), ctx.llm)
    leads = [enrich_lead(lead) for lead in source_leads(icp)]
    return {"leads": leads, "count": len(leads), "icp": icp}


@activity.defn
def enrich_lead_activity(payload: dict) -> dict:
    return enrich_lead(payload["lead"])


@activity.defn
def sequence_should_continue(payload: dict) -> dict:
    email = (payload.get("email") or payload["lead"]["email"]).lower()
    tenant_id = payload.get("tenant_id", acquisition_runtime().settings.acquisition_tenant_id)
    return _pipeline().sequence_should_continue(tenant_id, email)


@activity.defn
def acq_sequence_plan(payload: dict) -> dict:
    pipeline = _pipeline()
    plan = pipeline.sequence_plan(payload["tenant_id"], payload["email"])
    profile = pipeline.repo.get_profile(payload["tenant_id"]) or {}
    plan["timezone"] = profile.get("timezone", "Asia/Kolkata")
    return plan


@activity.defn
def acq_send_window_delay(payload: dict) -> int:
    return send_window_delay(datetime.now(timezone.utc), payload.get("timezone", "Asia/Kolkata"), payload.get("send_time", "morning"))


@activity.defn
def acq_first_touch(payload: dict) -> dict:
    try:
        return _pipeline().outreach(payload["tenant_id"], payload["email"], force=payload.get("force", False))
    except Exception as exc:
        return {"status": "blocked", "reason": str(exc)}


@activity.defn
def acq_follow_up(payload: dict) -> dict:
    return _pipeline().follow_up(payload["tenant_id"], payload["email"], payload["index"])


@activity.defn
def acq_run_daily(payload: dict) -> dict:
    return _pipeline().run_daily(payload["tenant_id"])


@activity.defn
def acq_weekly_learning(payload: dict) -> dict:
    return _pipeline().run_weekly_learning(payload["tenant_id"], payload.get("min_sends", 20))


@activity.defn
def acq_monthly_report(payload: dict) -> dict:
    return _pipeline().run_monthly_report(payload["tenant_id"], payload.get("month"))


@activity.defn
def acq_sweep(payload: dict) -> dict:
    return _pipeline().sweep(payload["tenant_id"])


ACQUISITION_ACTIVITIES = [
    draft_email,
    authorize_email,
    classify_inbound,
    source_icp_leads,
    enrich_lead_activity,
    sequence_should_continue,
    acq_sequence_plan,
    acq_send_window_delay,
    acq_first_touch,
    acq_follow_up,
    acq_run_daily,
    acq_weekly_learning,
    acq_monthly_report,
    acq_sweep,
]
