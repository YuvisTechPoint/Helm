import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import acquisition.models  # noqa: F401
import youtube.models  # noqa: F401
from acquisition.funnel import (
    REPLY_EVAL_SET,
    activate_prompt,
    classify_reply,
    evaluate_classifier,
    first_touch,
    requested_channel,
    resolve_call_time,
)
from acquisition.modules.experiments import ExperimentStore
from acquisition.modules.learning import (
    lookalike_similarity,
    plan_volume,
    retrain_score_weights,
    seed_from_client_list,
    weighted_score,
)
from acquisition.policy import AI_DISCLOSURE, PolicyDenied, PolicyGuard
from acquisition.repository import AcquisitionRepository
from core.db import Base, make_engine
from core.kill_switch import KillSwitchBoard


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()


def _profile(conversion: str = "qualified_meeting") -> dict:
    return {
        "business_name": "Northwind",
        "services": ["checkout audit"],
        "proof_points": ["A home goods shop cut checkout drop-off after a shipping-rate fix."],
        "faq": ["The audit covers the path from cart to paid order."],
        "faq_terms": ["audit", "checkout"],
        "objections": {"price": "The floor for this audit is published in the profile."},
        "price_floor": 50000,
        "list_price": 80000,
        "discount_limit": 0.1,
        "conversion_definition": conversion,
        "human_name": "Mina",
        "version": 1,
        "guarantees": [],
        "timezone": "Asia/Kolkata",
        "deposit_percent": 50,
    }


def _pipeline(session, kill=None):
    from acquisition.pipeline_e2e import LeadPipeline

    pipe = LeadPipeline(AcquisitionRepository(session), PolicyGuard(kill_switches=kill or KillSwitchBoard()))
    return pipe


def _tenant() -> str:
    return f"t-{uuid.uuid4().hex[:6]}"


def _to_positive(pipe, tenant: str, profile: dict, email: str | None = None) -> str:
    email = email or f"lead-{uuid.uuid4().hex[:8]}@buyer.example"
    pipe.repo.save_profile(tenant, profile, approved=True)
    sourced = pipe.source_lead(
        tenant,
        {"email": email, "first_name": "Ada", "company": "Example Co", "reason": "checkout hides shipping rates until account creation", "fit": 0.8, "intent": 0.7},
    )
    assert sourced["status"] == "sourced"
    assert pipe.outreach(tenant, email, force=True)["status"] == "contacted"
    assert pipe.handle_reply(tenant, email, "Interested — let's talk next week.")["status"] == "positive"
    return email


def _qualify(pipe, tenant: str, email: str) -> None:
    pipe.repo.upsert_lead(tenant, email, {"need": "checkout", "authority": "yes", "budget": "60000", "budget_amount": 60000, "timeline": "this month"})


def test_positive_reply_is_not_suppressed_and_reply_is_sent(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    assert pipe.repo.is_suppressed(email) is False
    thread = next(row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == email)
    outbound = [message for message in thread["messages"] if message["direction"] == "outbound"]
    assert len(outbound) == 2
    assert "blocked" not in outbound[-1]
    assert "What problem" in outbound[-1]["body"]


def test_signed_proposal_converts_only_on_signature(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile("signed_proposal"))
    _qualify(pipe, tenant, email)
    sent = pipe.qualify_and_convert(tenant, email)
    assert sent["status"] == "proposal_sent"
    assert sent["sign_url"]
    assert pipe._lead(tenant, email)["stage"] == "proposal_sent"
    assert pipe.repo.get_deal(tenant, email)["price_cents"] == 8_000_000
    assert pipe.money(tenant)["pipeline_value_cents"] == 8_000_000
    signed = pipe.handle_esign_event(tenant, "completed", envelope_id=sent["deal"]["envelope_id"])
    money = pipe.money(tenant)
    assert money["pipeline_value_cents"] == 0 and money["revenue_cents"] == 8_000_000
    assert signed["status"] == "converted"
    assert signed["deal"]["status"] == "signed"
    lead = pipe._lead(tenant, email)
    assert lead["stage"] == "converted" and lead["automation_frozen"] is True
    thread = next(row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == email)
    handover = [message for message in thread["messages"] if message.get("handover")]
    assert handover and "blocked" not in handover[-1] and "Mina" in handover[-1]["body"]
    assert thread["state"] == "handed_off"
    assert pipe.handle_esign_event(tenant, "completed", email=email)["status"] == "already_signed"


def test_declined_proposal_goes_to_nurture(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile("signed_proposal"))
    _qualify(pipe, tenant, email)
    pipe.qualify_and_convert(tenant, email)
    declined = pipe.handle_esign_event(tenant, "declined", email=email)
    assert declined["status"] == "declined"
    assert pipe._lead(tenant, email)["stage"] == "nurture"


def test_paid_conversion_waits_for_full_deposit(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile("paid"))
    _qualify(pipe, tenant, email)
    proposal = pipe.qualify_and_convert(tenant, email)
    pending = pipe.handle_esign_event(tenant, "completed", envelope_id=proposal["deal"]["envelope_id"])
    assert pending["status"] == "payment_pending"
    assert pending["payment_link"]
    deposit = pending["deal"]["deposit_cents"]
    assert deposit == 4_000_000
    partial = pipe.mark_paid(tenant, email, deposit - 1)
    assert partial["status"] == "partial"
    assert pipe._lead(tenant, email)["stage"] == "payment_pending"
    paid = pipe.mark_paid(tenant, email, deposit, reference="pay_1")
    assert paid["status"] == "paid"
    assert paid["deal"]["status"] == "paid"
    assert pipe._lead(tenant, email)["stage"] == "converted"
    assert pipe.mark_paid(tenant, email, deposit)["status"] == "already_paid"
    money = pipe.money(tenant)
    assert money["revenue_cents"] == deposit
    assert money["spend_by_category"]["sending"] > 0


def test_meeting_confirmation_reminders_and_pre_call_brief(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    _qualify(pipe, tenant, email)
    slot = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
    result = pipe.qualify_and_convert(tenant, email, slot)
    assert result["status"] == "converted"
    assert "Need: checkout" in result["handoff"]["briefing"]["one_page"]
    deal = pipe.repo.get_deal(tenant, email)
    assert deal["status"] == "booked" and len(deal["reminders_due"]) == 2
    thread = next(row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == email)
    confirmation = [message for message in thread["messages"] if message.get("handover")][-1]
    assert "Agenda" in confirmation["body"] and "blocked" not in confirmation
    start = datetime.fromisoformat(slot)
    first = pipe.sweep(tenant, now=start - timedelta(hours=23))
    assert first["reminders"] == 1
    assert pipe.sweep(tenant, now=start - timedelta(hours=23))["reminders"] == 0
    assert pipe.sweep(tenant, now=start - timedelta(minutes=30))["reminders"] == 1
    with pytest.raises(PolicyDenied):
        pipe.guard.authorize(
            {"tenant_id": tenant, "lead_id": email, "channel": "email", "email": email, "critic_passed": True, "verification": "valid", "lawful_basis": "legitimate_interest"}
        )


def test_whatsapp_switch_requires_request_and_stop_withdraws_everywhere(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    switched = pipe.handle_reply(tenant, email, "WhatsApp me on +91 98765 43210 instead.")
    assert switched["status"] == "channel_switched" and switched["sent"] is True
    consent = pipe.repo.get_consent(tenant, email, "whatsapp")
    assert consent and consent["basis"] == "consent" and consent["source"] == "email_reply"
    lead = pipe._lead(tenant, email)
    assert lead["active_channel"] == "whatsapp" and lead["phone"] == "+919876543210"
    stopped = pipe.handle_channel_message(tenant, "whatsapp", "+91 98765 43210", "STOP")
    assert stopped["status"] == "unsubscribed"
    assert pipe.repo.get_consent(tenant, email, "whatsapp") is None
    assert pipe.repo.is_suppressed(email) and pipe.repo.is_suppressed("+919876543210")
    blocked = pipe._deliver(tenant, pipe._lead(tenant, email), "Reply STOP to opt out", channel="whatsapp")
    assert blocked["sent"] is False


def test_channel_switch_without_number_asks_then_completes(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    pending = pipe.handle_reply(tenant, email, "Can you text me instead?")
    assert pending["status"] == "channel_pending"
    done = pipe.handle_reply(tenant, email, "+44 7700 900123")
    assert done["status"] == "channel_switched" and done["channel"] == "sms"


def test_requested_call_uses_express_consent_and_disclosure(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    scheduled = pipe.handle_reply(tenant, email, "Call me tomorrow at 4 on +1 415 555 0100.")
    assert scheduled["status"] == "call_scheduled"
    assert pipe.repo.get_consent(tenant, email, "voice")["basis"] == "express"
    call_at = datetime.fromisoformat(scheduled["call_at"])
    assert call_at.hour == 16
    assert pipe.sweep(tenant, now=call_at - timedelta(minutes=5))["calls"] == 0
    assert pipe.sweep(tenant, now=call_at + timedelta(minutes=1))["calls"] == 1
    thread = next(row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == email)
    call = [message for message in thread["messages"] if message.get("channel") == "voice"][-1]
    assert call["body"].startswith(AI_DISCLOSURE)
    assert pipe.sweep(tenant, now=call_at + timedelta(minutes=2))["calls"] == 0


def test_no_cold_whatsapp_or_voice_without_consent(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    pipe.repo.upsert_lead(tenant, email, {"phone": "+15550001111"})
    assert pipe._deliver(tenant, pipe._lead(tenant, email), "Hi. Reply STOP to opt out.", channel="whatsapp")["sent"] is False
    assert pipe.place_call(tenant, email)["status"] == "blocked"


def test_inbound_whatsapp_from_unknown_number_creates_consented_lead(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    pipe.repo.save_profile(tenant, _profile(), approved=True)
    result = pipe.handle_channel_message(tenant, "whatsapp", "+919000000001", "Interested in a checkout audit", "Ravi")
    assert result["status"] == "positive"
    lead = pipe._lead_by_phone(tenant, "+919000000001")
    assert lead["first_name"] == "Ravi"
    assert pipe.repo.get_consent(tenant, lead["email"], "whatsapp")
    thread = next(row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == lead["email"])
    assert thread["messages"][-1]["channel"] == "whatsapp" and "blocked" not in thread["messages"][-1]


def test_kill_switches_block_tenant_channel_and_global(session):
    kill = KillSwitchBoard()
    pipe = _pipeline(session, kill)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    lead = pipe._lead(tenant, email)
    for scope in (f"acquisition:tenant:{tenant}", "acquisition:channel:email", "acquisition", "global"):
        kill.set(scope, True, "test")
        assert pipe._deliver(tenant, lead, "Checking in.")["sent"] is False
        kill.set(scope, False)
    assert pipe._deliver(tenant, lead, "Checking in.")["sent"] is True
    kill.set("acquisition", True, "paused by owner")
    assert pipe.run_daily(tenant)["status"] == "paused"
    kill.set("acquisition", False)


def test_out_of_office_does_not_stop_sequence(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    pipe.repo.save_profile(tenant, _profile(), approved=True)
    email = f"ooo-{uuid.uuid4().hex[:6]}@buyer.example"
    pipe.source_lead(tenant, {"email": email, "first_name": "Ada", "company": "Example Co", "reason": "checkout hides shipping rates", "fit": 0.8, "intent": 0.7})
    pipe.outreach(tenant, email, force=True)
    assert pipe.handle_reply(tenant, email, "Automatic reply: out of office")["status"] == "out_of_office"
    assert pipe.sequence_should_continue(tenant, email)["continue"] is True
    assert pipe.follow_up(tenant, email, 1)["status"] == "sent"
    pipe.handle_reply(tenant, email, "What does the audit include?")
    assert pipe.sequence_should_continue(tenant, email)["continue"] is False
    assert pipe.follow_up(tenant, email, 2)["status"] == "stopped"


def test_escalations_get_holding_reply_and_sla_alert(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    escalated = pipe.handle_reply(tenant, email, "Can you do custom pricing for 12 stores?")
    assert escalated["status"] == "escalated"
    assert escalated["holding"].startswith("I'll confirm")
    assert pipe.check_escalation_sla(tenant) == 0
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    assert pipe.check_escalation_sla(tenant, later) >= 1
    assert pipe.check_escalation_sla(tenant, later) == 0


def test_data_export_and_erasure(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    pipe.repo.record_consent(tenant, email, "whatsapp", "consent", source="form", evidence="ticked box")
    exported = pipe.export_lead(tenant, email)
    assert exported["lead"]["email"] == email
    assert exported["conversation"]["messages"]
    assert exported["consents"][0]["evidence"] == "ticked box"
    erased = pipe.erase_lead(tenant, email)
    assert erased["suppressed"] is True
    assert pipe._lead(tenant, email) is None
    assert not [row for row in pipe.repo.list_conversations(tenant) if row["lead_email"] == email]
    assert pipe.source_lead(tenant, {"email": email, "first_name": "Ada", "company": "X"})["status"] == "suppressed"


def test_bounces_pause_mailbox_and_rotate(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    pipe.repo.save_profile(tenant, _profile(), approved=True)
    default = pipe.mailboxes.ensure_default(tenant)
    warming = pipe.mailboxes.add_mailbox(tenant, f"mia@{tenant}-go.example", f"{tenant}-go.example", 30)
    assert warming["warmed"] is False and warming["ready"] is False
    spare = pipe.mailboxes.add_mailbox(tenant, f"leo@{tenant}-try.example", f"{tenant}-try.example", 30, warmed=True)
    assert spare["ready"] is True
    for _ in range(20):
        pipe.mailboxes.record_send(tenant, default["address"])
    for index in range(2):
        pipe.record_email_event(tenant, "bounce", f"bad{index}@buyer.example", default["address"])
    boxes = {box["address"]: box for box in pipe.mailboxes.list_mailboxes(tenant)}
    assert boxes[default["address"]]["paused"] is True
    assert pipe.mailboxes.pick(tenant)["address"] == spare["address"]
    assert pipe.repo.is_suppressed("bad0@buyer.example")


def test_complaint_unsubscribes_lead(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    email = _to_positive(pipe, tenant, _profile())
    pipe.record_email_event(tenant, "complaint", email)
    assert pipe._lead(tenant, email)["stage"] == "unsubscribed"


def test_learning_loop_retrains_seeds_and_plans(session):
    leads = []
    for index in range(40):
        intent = 0.9 if index % 2 else 0.3
        leads.append({"fit": 0.6 + (index % 3) * 0.1, "intent": intent, "stage": "positive" if intent > 0.5 and index % 4 != 1 else "contacted"})
    weights = retrain_score_weights(leads)
    assert weights["status"] == "trained"
    assert weights["intent"] > weights["fit"]
    assert retrain_score_weights(leads[:5])["status"] == "skipped"
    assert weighted_score(0.8, 0.7, 1.0, {"fit": 1, "intent": 1, "reach": 1}) == pytest.approx(0.56)
    converted = [{"industry": "ecommerce", "geo": "india", "title": "Head of Growth", "tech_stack": ["shopify"]}] * 3
    close = lookalike_similarity({"industry": "ecommerce", "geo": "india", "title": "Growth Lead", "tech_stack": ["shopify"]}, converted)
    far = lookalike_similarity({"industry": "banking", "geo": "us", "title": "CFO"}, converted)
    assert close > far
    seeded = seed_from_client_list(_profile(), [
        {"company": "Shop A", "industry": "ecommerce", "geo": "india", "role": "Founder", "outcome": "won"},
        {"company": "Shop B", "industry": "ecommerce", "geo": "india", "role": "CMO", "outcome": "lost"},
    ])
    assert seeded["cells"][0]["successes"] == 1 and seeded["cells"][0]["failures"] == 1
    assert seeded["existing_clients"] == ["Shop A"]
    plan = plan_volume([], 5, 30)
    assert plan["weekly_contacts_needed"] == 167 and plan["daily_contacts_planned"] == 30 and plan["capacity_limited"]


def test_pipeline_learning_reports_and_seeding(session):
    pipe = _pipeline(session)
    tenant = _tenant()
    pipe.repo.save_profile(tenant, _profile(), approved=True)
    seeded = pipe.seed_clients(tenant, [{"company": "Shop A", "industry": "ecommerce", "geo": "india", "outcome": "won"}])
    assert seeded["existing_clients"] == 1
    assert pipe.source_lead(tenant, {"email": f"x-{uuid.uuid4().hex[:5]}@shop-a.example", "first_name": "A", "company": "Shop A Ltd"})["reason"] == "existing client"
    store = pipe.experiments
    for _ in range(25):
        store.record_send("pain-first", dimension="angle", tenant_id=tenant)
        store.record_send("proof-first", dimension="angle", tenant_id=tenant)
    for _ in range(6):
        store.record_send("pain-first", positive=True, dimension="angle", tenant_id=tenant)
    summary = pipe.run_weekly_learning(tenant)
    angle = [change for change in summary["changes"] if change["dimension"] == "angle"]
    assert angle and angle[0]["winner"] == "pain-first" and "positive reply rate" in angle[0]["why"]
    variants = {variant["name"]: variant for variant in store.by_dimension(tenant)["angle"]}
    assert variants["proof-first"]["retired"] is True
    assert len(variants) == 3
    report = pipe.run_monthly_report(tenant)
    assert "angle now uses 'pain-first'" in report["text"]
    assert pipe.repo.get_state(tenant, "reports")["months"] == [report["month"]]


def test_experiment_assignment_is_stable_and_copy_varies():
    store = ExperimentStore()
    first = store.assign("ada@buyer.example")
    assert first == store.assign("ADA@buyer.example")
    assert set(first) == {"angle", "subject", "sequence_length", "send_time"}
    lead = {"first_name": "Ada", "reason": "your checkout hides shipping", "company": "Example Co"}
    profile = _profile()
    assert first_touch(lead, profile, "pain-first") != first_touch(lead, profile, "proof-first")
    localised = first_touch({**lead, "language": "de"}, {**profile, "languages": ["en", "de"]}, language="de")
    assert localised.startswith("Hallo Ada") and "Viele Grüße" in localised


def test_classifier_eval_gate():
    result = evaluate_classifier()
    assert result["cases"] == len(REPLY_EVAL_SET) >= 35
    assert result["accuracy"] >= 0.95
    version = {"name": "v2", "active": False}
    activate_prompt(version, baseline_accuracy=result["accuracy"])
    assert version["active"] and version["eval"]["accuracy"] == result["accuracy"]
    with pytest.raises(PolicyDenied):
        activate_prompt({"name": "v3"}, classifier=lambda text: "question")
    assert classify_reply("Could we discuss a partnership?") == "press"
    assert requested_channel("Please call me")["channel"] == "voice"
    when = resolve_call_time({"day": "tomorrow", "hour": 4, "minute": 0, "meridiem": None}, datetime(2026, 10, 8, 5, tzinfo=timezone.utc))
    assert when.hour == 16 and when.day == 9


def test_send_window_delay_lands_in_weekday_window():
    from zoneinfo import ZoneInfo

    from acquisition.activities import send_window_delay

    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    delay = send_window_delay(now, "Asia/Kolkata", "morning", __import__("random").Random(1))
    target = (now + timedelta(seconds=delay)).astimezone(ZoneInfo("Asia/Kolkata"))
    assert target.weekday() < 5 and 9 <= target.hour < 11


def _app(monkeypatch):
    monkeypatch.setenv("USE_SQLITE", "true")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "rzp_test")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("ESIGN_WEBHOOK_SECRET", "esign-secret")
    monkeypatch.setenv("ACQUISITION_TENANT_ID", _tenant())
    from api.main import create_app

    client = TestClient(create_app())
    profile = {key: value for key, value in _profile("paid").items() if key not in {"version"}}
    assert client.post("/acquisition/profile", json=profile).status_code == 200
    return client


def test_webhooks_verify_signatures_and_drive_conversion(monkeypatch):
    client = _app(monkeypatch)
    app_pipe = client.app.state.acquisition.pipeline
    tenant = client.app.state.settings.acquisition_tenant_id
    email = _to_positive(app_pipe, tenant, _profile("paid"))
    _qualify(app_pipe, tenant, email)
    proposal = client.post("/acquisition/convert", json={"email": email})
    assert proposal.json()["status"] == "proposal_sent"
    bad_esign = client.post("/webhooks/esign", json={"event": "DOCUMENT_COMPLETED", "payload": {"id": proposal.json()["deal"]["envelope_id"]}})
    assert bad_esign.status_code == 401
    signed = client.post(
        "/webhooks/esign",
        headers={"x-documenso-secret": "esign-secret"},
        json={"event": "DOCUMENT_COMPLETED", "payload": {"id": proposal.json()["deal"]["envelope_id"]}},
    )
    assert signed.json()["status"] == "payment_pending"
    deposit = signed.json()["deal"]["deposit_cents"]
    event = json.dumps(
        {"type": "checkout.session.completed", "data": {"object": {"id": "cs_1", "payment_status": "paid", "amount_total": deposit, "metadata": {"email": email, "tenant_id": tenant}}}}
    ).encode()
    assert client.post("/webhooks/stripe", content=event, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
    stamp = str(int(time.time()))
    signature = hmac.new(b"whsec_test", f"{stamp}.".encode() + event, hashlib.sha256).hexdigest()
    paid = client.post("/webhooks/stripe", content=event, headers={"stripe-signature": f"t={stamp},v1={signature}"})
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    razor = json.dumps({"event": "payment_link.paid", "payload": {"payment_link": {"entity": {"id": "plink_1", "amount_paid": deposit, "notes": {"email": email}}}}}).encode()
    assert client.post("/webhooks/razorpay", content=razor, headers={"x-razorpay-signature": "nope"}).status_code == 400
    good = hmac.new(b"rzp_test", razor, hashlib.sha256).hexdigest()
    assert client.post("/webhooks/razorpay", content=razor, headers={"x-razorpay-signature": good}).json()["status"] == "already_paid"


def test_channel_webhooks_and_controls(monkeypatch):
    client = _app(monkeypatch)
    assert client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"}).text == "42"
    assert client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"}).status_code == 403
    number = f"9198{uuid.uuid4().int % 10**8:08d}"
    inbound = client.post(
        "/webhooks/whatsapp",
        json={"entry": [{"changes": [{"value": {"contacts": [{"wa_id": number, "profile": {"name": "Ravi"}}], "messages": [{"from": number, "text": {"body": "Interested in an audit"}}]}}]}]},
    )
    assert inbound.json()["handled"] == 1
    sms = client.post("/webhooks/twilio/sms", content=f"From=%2B{number}&Body=STOP", headers={"content-type": "application/x-www-form-urlencoded"})
    assert sms.status_code == 200 and "<Response>" in sms.text
    vapi = client.post("/webhooks/vapi", json={"message": {"type": "assistant-request"}})
    assert vapi.json()["assistantOverrides"]["firstMessage"].startswith(AI_DISCLOSURE)
    report = client.post(
        "/webhooks/vapi",
        json={"message": {"type": "end-of-call-report", "call": {"customer": {"number": "+15550009999"}}, "transcript": "AI: hello. Caller: interested", "summary": "Caller is interested in an audit"}},
    )
    assert report.json()["status"] == "positive"
    events = client.post("/webhooks/email-events", json=[{"type": "bounce", "email": "gone@buyer.example"}])
    assert events.json()["processed"] == 1
    assert client.get("/acquisition/channels").json()["channels"]["whatsapp"]["live"] is False
    killed = client.post("/acquisition/controls/kill", json={"scope": "channel", "channel": "sms", "active": True, "reason": "carrier review"})
    assert killed.json()["scope"] == "acquisition:channel:sms"
    assert client.get("/acquisition/controls").json()["channels"]["sms"] is True
    client.post("/acquisition/controls/kill", json={"scope": "channel", "channel": "sms", "active": False})
    assert client.get("/acquisition/controls").json()["channels"]["sms"] is False
    assert client.get("/acquisition/eval").json()["accuracy"] >= 0.95
    assert client.post("/acquisition/prompts/activate").status_code == 200
    assert client.get("/acquisition/volume").json()["target_qualified_per_week"] >= 1
    assert client.post("/acquisition/volume", json={"weekly_qualified_target": 8}).json()["target_qualified_per_week"] == 8
    assert "reports" in client.get("/acquisition/reports").json()
    assert client.post("/acquisition/mailboxes", json={"address": "x@northwind.example", "domain": "northwind.example"}).status_code in {200, 400}
    assert client.post("/acquisition/sweep").status_code == 200


def test_sync_fallback_runs_new_workflows(session):
    from youtube.orchestrator import run_sync_workflow

    from acquisition.runtime_ctx import acquisition_runtime

    tenant = _tenant()
    acquisition_runtime().repo.save_profile(tenant, _profile(), approved=True)
    assert "calls" in run_sync_workflow("AcquisitionSweepWorkflow", {"tenant_id": tenant})
    assert "weights" in run_sync_workflow("WeeklyLearningWorkflow", {"tenant_id": tenant})
    assert "text" in run_sync_workflow("MonthlyReportWorkflow", {"tenant_id": tenant})
    daily = run_sync_workflow("AcquisitionDailyWorkflow", {"tenant_id": tenant})
    assert daily["status"] in {"ok", "paused", "blocked"}
