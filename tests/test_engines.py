from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import acquisition.models  # noqa: F401
import youtube.models  # noqa: F401
from acquisition.close import build_proposal, place_outbound_call, promote_experiment, quote_price, send_whatsapp
from acquisition.funnel import (
    Sequence,
    activate_prompt,
    apply_unsubscribe,
    assess_qualification,
    classify_reply,
    complete_handoff,
    draft_reply,
    enters_outreach,
    first_touch,
    in_business_hours,
    mailbox_can_send,
    observe_mailbox,
    recontact_on,
    referral_lead,
    score_lead,
    thompson_shares,
    verify_email,
)
from acquisition.policy import PolicyDenied, PolicyGuard, critique, scrape_linkedin
from acquisition.tenancy import TenantDirectory
from api.main import create_app
from core.budget import BudgetGuard
from core.db import Base, make_engine
from core.errors import BudgetExceeded, IsolationError, OneChangeError, PublishingBlocked, QuotaExceeded, TermsViolation
from core.events import EventLog
from core.jobs import JobBook, backoff_seconds
from core.kill_switch import KillSwitchBoard
from core.timeutil import utcnow
from core.vault import MemoryVault, SqlVault, alert_expiring_credentials
from youtube.modules.analytics import blank_metrics, learn_publish_hour, record_snapshot, snapshot_plan
from youtube.modules.competitors import add_channel, download_competitor_video, is_outlier, outlier_ratio, pattern_report
from youtube.modules.diagnostician import Funnel, Optimizer, apply_fix, assert_allowed_lever, execute_pivot, propose_pivot, record_cycle, review_change, veto_pivot
from youtube.modules.gate import QualityGate
from youtube.modules.launch import schedule_publication
from youtube.modules.niche import scout
from youtube.modules.planner import add_topic, assert_cadence, build_calendar
from youtube.modules.publisher import InMemoryVideoStore, PublishRequest, publish
from youtube.modules.research import ScriptWriter, research_topic
from youtube.modules.visuals import Asset, build_timeline
from youtube.modules.voice import VoiceStage
from youtube.modules.ypp import apply_for_partner_program, ypp_progress
from youtube.pipeline import DRY_RUN_TOPICS, produce_topic, run_private_dry_run
from youtube.providers import FakeTransport, FakeYouTube, ResumableUploader
from youtube.quota import QuotaLedger
from acquisition.activities import authorize_email, draft_email
from youtube.activities import m11_publish, m5_research, m6_script, m7_quality_gate
from youtube.runtime import m2_niche_scout


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def test_schema_has_both_engines(session):
    names = set(Base.metadata.tables)
    for required in ("secrets", "events", "jobs", "published_videos", "tenants", "leads", "suppressions", "deals", "consents"):
        assert required in names


def test_vault_round_trip_and_expiry_alert():
    key = Fernet.generate_key().decode()
    vault = MemoryVault(key)
    soon = (utcnow() + timedelta(days=3)).isoformat()
    vault.put("youtube-refresh", "refresh-token", soon)
    assert vault.get("youtube-refresh") == "refresh-token"
    alerts = []

    class Queue:
        def add(self, kind, message):
            alerts.append((kind, message))

    assert alert_expiring_credentials(vault, Queue())
    assert alerts[0][0] == "token_expiry"


def test_sql_vault_round_trip(session):
    key = Fernet.generate_key().decode()
    vault = SqlVault(session, key)
    vault.put("llm", "secret-value")
    assert vault.get("llm") == "secret-value"


def test_events_are_append_only():
    log = EventLog()
    log.append("publish", "m11", {"id": "v"})
    with pytest.raises(RuntimeError):
        log.update("publish")


def test_job_idempotency_and_dead_letter():
    jobs = JobBook()
    first, created = jobs.begin("upload-1", "youtube.upload")
    second, again = jobs.begin("upload-1", "youtube.upload")
    assert created and not again
    assert first["run_id"] == second["run_id"]
    row = jobs.fail("upload-1", "network")
    assert row["status"] == "retry"
    assert row["retry_in"] == backoff_seconds(1)
    jobs.fail("upload-1", "network")
    dead = jobs.fail("upload-1", "network")
    assert dead["status"] == "dead_letter"


def test_quota_reserves_uploads_before_research():
    ledger = QuotaLedger()
    ledger.reserve_for_scheduled_uploads(6)
    ledger.allow_research(100)
    with pytest.raises(QuotaExceeded):
        ledger.allow_research(500)
    with pytest.raises(QuotaExceeded):
        ledger.reserve_for_scheduled_uploads(1)


def test_kill_switch_and_private_only_publish():
    store = InMemoryVideoStore()
    client = FakeYouTube()
    jobs = JobBook()
    ledger = QuotaLedger()
    board = KillSwitchBoard()
    request = PublishRequest(
        idempotency_key="v1",
        title="The psychology of loss aversion",
        description="Sources: https://example.org/dry-run/loss-aversion/1",
        tags=["psychology"],
        category_id="27",
        language="en",
        made_for_kids=False,
        contains_synthetic_media=True,
        uses_ai_voice=True,
        uses_realistic_ai_imagery=False,
        privacy_status="public",
        dry_run=False,
        provisional_research=False,
        chapters=[],
        content=b"mp4",
    )
    with pytest.raises(PublishingBlocked):
        publish(request, store=store, client=client, jobs=jobs, ledger=ledger, kill_active=False, audit_approved=False)
    assert client.inserts == []
    board.set("youtube", True, "strike")
    private = PublishRequest(**{**request.__dict__, "idempotency_key": "v2", "privacy_status": "private", "dry_run": True, "provisional_research": True})
    with pytest.raises(PublishingBlocked):
        publish(private, store=store, client=client, jobs=jobs, ledger=ledger, kill_active=board.active("youtube"), audit_approved=False)


def test_publish_is_idempotent_and_resumable():
    store = InMemoryVideoStore()
    client = FakeYouTube()
    jobs = JobBook()
    ledger = QuotaLedger()
    request = PublishRequest(
        idempotency_key="dry-1",
        title="Why loss aversion changes how you decide",
        description="provisional",
        tags=["psychology"],
        category_id="27",
        language="en",
        made_for_kids=False,
        contains_synthetic_media=True,
        uses_ai_voice=True,
        uses_realistic_ai_imagery=False,
        privacy_status="private",
        dry_run=True,
        provisional_research=True,
        chapters=[{"start": 0, "title": "Hook"}],
        content=b"mp4",
    )
    first = publish(request, store=store, client=client, jobs=jobs, ledger=ledger, kill_active=False, audit_approved=False)
    second = publish(request, store=store, client=client, jobs=jobs, ledger=ledger, kill_active=False, audit_approved=False)
    assert first["youtube_id"] == second["youtube_id"]
    assert len(client.inserts) == 1
    assert client.inserts[0]["metadata"]["status"]["privacyStatus"] == "private"
    assert client.inserts[0]["metadata"]["status"]["containsSyntheticMedia"] is True
    transport = FakeTransport("uploaded1")
    uploaded = ResumableUploader(transport, "token").insert(client.inserts[0]["metadata"], b"mp4")
    assert uploaded["id"] == "uploaded1"
    assert [call[0] for call in transport.calls] == ["POST", "PUT"]


def test_missing_disclosure_blocks_before_insert():
    request = PublishRequest(
        idempotency_key="bare",
        title="Title",
        description="d",
        tags=[],
        category_id="27",
        language="en",
        made_for_kids=None,
        contains_synthetic_media=False,
        uses_ai_voice=True,
        uses_realistic_ai_imagery=False,
        privacy_status="private",
        dry_run=True,
        provisional_research=True,
        chapters=[],
    )
    with pytest.raises(PublishingBlocked):
        publish(request, store=InMemoryVideoStore(), client=FakeYouTube(), jobs=JobBook(), ledger=QuotaLedger(), kill_active=False, audit_approved=False)


def test_niche_scout_prefers_psychology_until_live_data_overrides():
    choice = scout()
    assert choice.slug == "applied-psychology"
    saturated = {"applied-psychology": [{"channel_subscribers": 500_000} for _ in range(10)]}
    overridden = scout(saturated)
    assert overridden.slug != "applied-psychology"


def test_competitor_metadata_only_and_outliers():
    with pytest.raises(TermsViolation):
        download_competitor_video("abc")
    tracked = []
    for index in range(100):
        add_channel(tracked, {"channel_id": f"c{index}"})
    with pytest.raises(ValueError):
        add_channel(tracked, {"channel_id": "overflow"})
    ratio = outlier_ratio(300, [40, 50, 60, 55])
    assert is_outlier(ratio)
    report = pattern_report(
        [{"video_id": "v", "title": "Why habits stick", "views": 300, "same_age_views": [40, 50, 60], "thumbnail_url": "https://i.ytimg.com/vi/v/hq.jpg"}]
    )
    assert report["tracked_media"] == "metadata_only"
    assert report["outliers"][0]["title_structure"] == "why_question"
    with pytest.raises(TermsViolation):
        pattern_report([{"title": "x", "views": 1, "same_age_views": [1], "file_path": "stolen.mp4"}])


def test_calendar_respects_cadence_and_repeats():
    topics = []
    for index in range(8):
        topics.append({"slug": f"long-{index}", "title": f"Long {index}", "cluster": "mind", "kind": "long", "demand": 3, "gap": 3, "fit": 3})
        topics.append({"slug": f"short-{index}", "title": f"Short {index}", "cluster": "mind", "kind": "short", "demand": 2, "gap": 2, "fit": 2})
    calendar = build_calendar(date(2026, 10, 5), topics)
    weeks: dict[tuple, dict] = {}
    slugs = []
    for item in calendar:
        day = date.fromisoformat(item["planned_on"])
        key = day.isocalendar()[:2]
        weeks.setdefault(key, {"long": 0, "short": 0})
        weeks[key][item["kind"]] += 1
        slugs.append(item["slug"])
    assert len(slugs) == len(set(slugs))
    for counts in weeks.values():
        assert counts["long"] <= 3
        assert counts["short"] <= 5
    with pytest.raises(Exception):
        add_topic([{"slug": "same"}], {"slug": "same"}, set())
    with pytest.raises(Exception):
        assert_cadence({"long": 3, "short": 0}, "long")


def test_quality_gate_passes_ten_and_drops_after_two_rewrites():
    report = run_private_dry_run()
    assert report["passed"] == 10
    assert report["uploads"] == 10
    again = produce_topic(
        DRY_RUN_TOPICS[0],
        writer=ScriptWriter(),
        gate=QualityGate(),
        store=InMemoryVideoStore(),
        client=FakeYouTube(),
        jobs=JobBook(),
        ledger=QuotaLedger(),
        queue=__import__("core.jobs", fromlist=["ExceptionQueue"]).ExceptionQueue(),
        past_scripts=[],
        previous_format=None,
    )
    # A second independent store still uploads once; the shared dry-run keys are per store.
    assert again["status"] == "published_private"

    class StuckWriter(ScriptWriter):
        def write(self, topic, brief, previous_format=None, rewrite_notes=None):
            script = super().write(topic, brief, previous_format, rewrite_notes)
            script.title = "scary stories compilation volume twelve"
            return script

    dropped = produce_topic(
        DRY_RUN_TOPICS[0],
        writer=StuckWriter(),
        gate=QualityGate(),
        store=InMemoryVideoStore(),
        client=FakeYouTube(),
        jobs=JobBook(),
        ledger=QuotaLedger(),
        queue=__import__("core.jobs", fromlist=["ExceptionQueue"]).ExceptionQueue(),
        past_scripts=[],
        previous_format=None,
    )
    assert dropped["status"] == "dropped"
    assert dropped["rewrites"] == 2


def test_voice_visuals_refuse_unlicensed_and_unlicensed_assets():
    with pytest.raises(Exception):
        VoiceStage(voice_id="clone-of-a-real-person")
    track = VoiceStage().render("narration", "out.wav")
    assert "loudnorm=I=-14" in " ".join(track.ffmpeg_argv)
    with pytest.raises(PublishingBlocked):
        build_timeline("projection", 30, [Asset(key="song", kind="music", licence="")])
    timeline = build_timeline("projection", 90, [Asset(key="diagram", kind="diagram", licence="original")])
    assert timeline.width == 1920
    assert timeline.scenes[0]["duration"] <= 30


def test_analytics_plan_and_launch_gate():
    published = datetime(2026, 1, 1, tzinfo=timezone.utc)
    labels = [row["label"] for row in snapshot_plan(published)]
    assert labels == ["2h", "24h", "48h", "7d", "28d"]
    store = {}
    metrics = blank_metrics()
    metrics["audienceGeography"] = [{"country": "US", "views": 10}]
    first = record_snapshot(store, "v", "48h", metrics, published.isoformat())
    second = record_snapshot(store, "v", "48h", {"views": 99}, published.isoformat())
    assert first is second
    assert learn_publish_hour([{"hour": 15, "views": 10}, {"hour": 18, "views": 40}]) == 18
    with pytest.raises(PublishingBlocked):
        schedule_publication(audit_approved=False, week_counts={"long": 0}, kind="long", when=published)
    scheduled = schedule_publication(audit_approved=True, week_counts={"long": 2, "short": 1}, kind="long", when=published)
    assert scheduled["privacy_status"] == "public"


def _funnel(**overrides) -> Funnel:
    base = dict(
        age_hours=72,
        views=100,
        channel_median_views=80,
        impressions_ratio=1,
        ctr=0.06,
        retention_first_30=0.5,
        retention_mid=0.5,
        subscribers_per_1000=5,
        low_rpm_traffic_share=0.1,
    )
    base.update(overrides)
    return Funnel(**base)


def test_diagnostician_one_change_rollback_and_veto():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    optimizer = Optimizer()
    held = __import__("youtube.modules.diagnostician", fromlist=["diagnose"]).diagnose(_funnel(age_hours=24), [])
    assert held["action"] == "hold"
    change = apply_fix(optimizer, "v", _funnel(ctr=0.02, retention_first_30=0.5), now)
    assert change.lever == "title"
    with pytest.raises(OneChangeError):
        apply_fix(optimizer, "v", _funnel(ctr=0.02), now)
    assert review_change(change, now + timedelta(hours=1), 0.01) == "waiting"
    assert review_change(change, now + timedelta(hours=73), 0.01) == "rolled_back"
    with pytest.raises(PublishingBlocked):
        assert_allowed_lever("fake_engagement")
    hook = Optimizer()
    content = apply_fix(hook, "v2", _funnel(ctr=0.08, retention_first_30=0.1), now)
    assert content.lever == "hook_threshold"
    assert review_change(content, now, 0.2, uploads_since=2) == "waiting"
    assert review_change(content, now, 0.05, uploads_since=3) == "rolled_back"
    pivot_state = Optimizer()
    for _ in range(3):
        record_cycle(pivot_state, False)
    proposal = propose_pivot(pivot_state, now, "applied-psychology", "personal-finance")
    assert proposal is not None
    assert execute_pivot(pivot_state, now + timedelta(hours=71)) is False
    veto_pivot(pivot_state)
    assert execute_pivot(pivot_state, now + timedelta(hours=80)) is False
    fresh = Optimizer()
    for _ in range(3):
        record_cycle(fresh, False)
    propose_pivot(fresh, now, "applied-psychology", "personal-finance")
    assert execute_pivot(fresh, now + timedelta(hours=73)) is True


def test_ypp_never_auto_applies():
    progress = ypp_progress(1000, 4000)
    assert progress["eligible"] is True
    assert progress["auto_apply"] is False
    assert progress["human_application_required"] is True
    with pytest.raises(RuntimeError):
        apply_for_partner_program(progress)


def test_budget_pause_and_hard_stop():
    guard = BudgetGuard()
    guard.configure("channel", "llm", 100)
    guard.charge("channel", "llm", 90, pause_at=0.9)
    assert guard.production_allowed("channel", "llm") is False
    tenants = TenantDirectory()
    tenants.create("local", "india")
    tenants.set_budget("local", 50)
    tenants.spend("local", 50)
    with pytest.raises(BudgetExceeded):
        tenants.spend("local", 1)


def test_policy_guard_blocks_bad_sends():
    guard = PolicyGuard()
    calls = []

    def sender(request):
        calls.append(request)
        return {"ok": True}

    base = {
        "tenant_id": "local",
        "lead_id": "lead-1",
        "channel": "email",
        "email": "ada@buyer.example",
        "body": "Hello Ada, your checkout hides shipping until account creation. Northwind audits that. Worth a reply?",
        "critic_passed": True,
        "verification": "valid",
        "lawful_basis": "legitimate_interest",
        "sequence_touch": True,
    }
    guard.send(base, sender)
    assert len(calls) == 1
    failed = {**base, "critic_passed": False, "lead_id": "lead-2"}
    with pytest.raises(PolicyDenied):
        guard.send(failed, sender)
    assert len(calls) == 1
    guard.suppression.add("blocked@buyer.example", tenant_id=None)
    with pytest.raises(PolicyDenied):
        guard.send({**base, "lead_id": "lead-3", "email": "blocked@buyer.example"}, sender)
    with pytest.raises(PolicyDenied):
        guard.send({**base, "channel": "whatsapp", "consent": None}, sender)
    with pytest.raises(PolicyDenied):
        guard.send({**base, "channel": "linkedin"}, sender)
    with pytest.raises(TermsViolation):
        scrape_linkedin()
    verdict = critique("See https://example.com now", "profile", first_touch=True)
    assert verdict["passed"] is False


def _profile():
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
        "conversion_definition": "qualified_meeting",
        "human_name": "Mina",
        "version": 1,
        "guarantees": [],
    }


def test_sequence_stops_on_reply_and_books_qualified_meeting():
    now = datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc)
    assert in_business_hours(now, "Asia/Kolkata")
    sequence = Sequence("lead-1", now)
    assert sequence.next_touch(now)["index"] == 0
    sequence.mark_sent()
    sequence.mark_replied()
    assert sequence.next_touch(now + timedelta(days=4)) is None
    assert classify_reply("Please unsubscribe me") == "unsubscribe"
    assert classify_reply("Are you an AI?") == "identity"
    reply = draft_reply("identity", "Are you an AI?", _profile(), "")
    assert reply["text"].startswith("Yes.")
    guard = PolicyGuard()
    apply_unsubscribe(guard, "lead-1", "ada@buyer.example")
    with pytest.raises(PolicyDenied):
        guard.authorize(
            {
                "tenant_id": "other",
                "lead_id": "lead-9",
                "channel": "email",
                "email": "ada@buyer.example",
                "critic_passed": True,
                "verification": "valid",
                "lawful_basis": "legitimate_interest",
                "sequence_touch": True,
            }
        )
    lead = {
        "email": "ada@buyer.example",
        "first_name": "Ada",
        "stage": "qualified",
        "need": "checkout",
        "authority": "yes",
        "budget": "80000",
        "budget_amount": 80000,
        "timeline": "this month",
    }
    assert assess_qualification({"budget_amount": 1000}, 50000) == "disqualified"

    class Calendar:
        def book(self, email, slot):
            return {"id": "evt", "email": email, "slot": slot}

    from acquisition.funnel import book_meeting

    event = book_meeting(lead, _profile(), Calendar(), "2026-10-08T10:00:00+05:30")
    assert event["id"] == "evt"
    package = complete_handoff(guard, lead, _profile(), ["interested"])
    assert "Mina" in package["message"]
    with pytest.raises(PolicyDenied):
        guard.authorize(
            {
                "tenant_id": "local",
                "lead_id": lead["email"],
                "channel": "email",
                "email": lead["email"],
                "critic_passed": True,
                "verification": "valid",
                "lawful_basis": "legitimate_interest",
            }
        )
    body = first_touch(
        {"first_name": "Ada", "reason": "your checkout asks for an account before shipping rates", "company": "Example Co"},
        _profile(),
    )
    assert "http" not in body
    assert len(body.split()) <= 120
    assert verify_email("invalid") is False
    assert verify_email("valid") is True
    assert enters_outreach(score_lead(0.5, 0.4, 0.5)) is False
    assert referral_lead("Please talk to Priya", "ada@buyer.example")["first_name"] == "Priya"
    assert recontact_on("not now, try 2026-11-01", now).date().isoformat() == "2026-11-01"
    shares = thompson_shares([{"successes": 40, "failures": 1}, {"successes": 1, "failures": 40}], __import__("random").Random(1))
    assert abs(sum(shares) - 1) < 1e-9
    assert shares[0] > shares[1]
    version = {"name": "v1", "active": False}
    activate_prompt(version)
    assert version["active"] is True
    mailbox = {"paused": False, "daily_cap": 2}
    assert mailbox_can_send(mailbox, 2) is False
    assert observe_mailbox(mailbox, 0.01, 0.002, 0.99) == "paused"


def test_price_floor_consent_channels_and_tenants():
    profile = _profile()
    with pytest.raises(PolicyDenied):
        quote_price(profile["list_price"], 0.5, profile["price_floor"], profile["discount_limit"])
    proposal = build_proposal(profile, 0.05)
    assert proposal["price"] >= profile["price_floor"]
    guard = PolicyGuard()
    calls = []
    with pytest.raises(PolicyDenied):
        send_whatsapp(guard, {"tenant_id": "local", "lead_id": "l", "email": "a@b.co", "body": "Reply STOP to opt out", "critic_passed": True, "consent": None}, lambda request: calls.append(request))
    assert calls == []
    with pytest.raises(PolicyDenied):
        place_outbound_call(
            guard,
            {"tenant_id": "local", "lead_id": "l", "email": "a@b.co", "body": "Hello", "critic_passed": True, "business_name": "Northwind", "consent": {"basis": "legitimate_interest"}},
            lambda request: calls.append(request),
        )
    sent = place_outbound_call(
        guard,
        {
            "tenant_id": "local",
            "lead_id": "l2",
            "email": "b@b.co",
            "body": "Following up on tomorrow at 4.",
            "critic_passed": True,
            "business_name": "Northwind",
            "consent": {"basis": "express", "withdrawn": False},
        },
        lambda request: {"called": True, "body": request["body"]},
    )
    assert sent["body"].startswith("This is an AI assistant")
    winner = promote_experiment(
        [{"name": "a", "sends": 30, "positive": 6, "active": True}, {"name": "b", "sends": 30, "positive": 1, "active": True}],
        min_sends=20,
    )
    assert winner["name"] == "a"
    directory = TenantDirectory()
    directory.create("a", "india")
    directory.create("b", "eu")
    directory.tenants["a"]["leads"].append({"email": "secret@a.example"})
    with pytest.raises(IsolationError):
        directory.leads_for("b", "a")
    directory.assign_domain("a", "go-a.example")
    with pytest.raises(IsolationError):
        directory.assign_domain("b", "go-a.example")
    assert directory.leads_for("a", "a")[0]["email"] == "secret@a.example"
    invoice = directory.record_invoice("a", 2500, "platform fee")
    assert invoice["tenant_id"] == "a"
    with pytest.raises(IsolationError):
        directory.record_invoice("missing", 1, "nope")


def test_live_research_refuses_without_provider():
    with pytest.raises(ValueError):
        research_topic("projection", dry_run=False)


def test_activity_and_http_surface():
    choice = m2_niche_scout({})
    assert choice["slug"] == "applied-psychology"
    app = create_app()
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["audit_approved"] is False
    oauth = client.get("/youtube/oauth/start")
    assert oauth.status_code == 200
    assert "client_id=" in oauth.json()["url"]
    stored = client.post("/youtube/vault/secrets", json={"name": "openai", "value": "sk-test"})
    assert stored.status_code == 200
    fetched = client.get("/youtube/vault/secrets/openai")
    assert fetched.json()["stored"] is True and "value" not in fetched.json()
    blocked = client.post(
        "/youtube/publish",
        json={"idempotency_key": "pub-1", "title": "Public try", "privacy_status": "public", "dry_run": False, "provisional_research": False},
    )
    assert blocked.status_code == 409
    ypp = client.get("/youtube/ypp", params={"subscribers": 10, "watch_hours": 12})
    assert ypp.json()["auto_apply"] is False
    profile = client.post(
        "/acquisition/profile",
        json={
            "business_name": "Northwind",
            "services": ["checkout audit"],
            "proof_points": ["A shop fixed shipping rates before account creation."],
            "price_floor": 50000,
            "list_price": 80000,
            "discount_limit": 0.1,
            "human_name": "Mina",
            "faq": ["Audits cover cart to paid."],
        },
    )
    assert profile.status_code == 200
    sample = client.post("/acquisition/sample-email")
    assert sample.status_code == 200
    assert "http" not in sample.json()["body"]
    created = client.post("/acquisition/tenants", json={"tenant_id": "second", "region": "eu"})
    assert created.status_code == 200
    client.post("/acquisition/domains", json={"tenant_id": "local", "domain": "go.example"})
    clash = client.post("/acquisition/domains", json={"tenant_id": "second", "domain": "go.example"})
    assert clash.status_code == 409
    client.post("/acquisition/spend", json={"tenant_id": "local", "amount": 10000})
    over = client.post("/acquisition/spend", json={"tenant_id": "local", "amount": 1})
    assert over.status_code == 409
    funnel = client.get("/acquisition/funnel")
    assert funnel.status_code == 200 and "sourced" in funnel.json()["counts"]
    mailboxes = client.get("/acquisition/mailboxes")
    assert mailboxes.json()["mailboxes"]
    assert client.get("/acquisition/escalations").json()["escalations"] == []
    activated = client.post("/acquisition/prompts/activate")
    assert activated.json()["active"] is True
    status = client.get("/youtube/status")
    assert status.status_code == 200
    assert status.json()["last_dry_run"] is None
    ran = client.post("/youtube/dry-run")
    assert ran.json()["passed"] == 10
    assert client.get("/youtube/status").json()["last_dry_run"]["uploads"] == 10


def test_module_activities_publish_one_private_video():
    topic = DRY_RUN_TOPICS[0]
    brief = m5_research({"slug": topic["slug"]})
    script = m6_script({"topic": topic, "brief": brief, "previous_format": None, "rewrite_notes": None})
    gate = m7_quality_gate(
        {
            "script": script,
            "brief": brief,
            "competitor_titles": ["scary stories compilation volume twelve"],
            "past_scripts": [],
            "previous_format": None,
        }
    )
    assert gate["decision"] == "pass"
    published = m11_publish(
        {
            "idempotency_key": "activity-projection",
            "title": "The psychology of psychological projection",
            "description": script["ending"],
            "uses_ai_voice": True,
            "provisional_research": True,
        }
    )
    again = m11_publish(
        {
            "idempotency_key": "activity-projection",
            "title": "The psychology of psychological projection",
            "description": script["ending"],
            "uses_ai_voice": True,
            "provisional_research": True,
        }
    )
    assert published["privacy_status"] == "private"
    assert published["youtube_id"] == again["youtube_id"]
    profile = {
        "business_name": "Northwind",
        "services": ["checkout audit"],
        "proof_points": ["A shop fixed shipping rates before account creation."],
    }
    lead = {"first_name": "Ada", "reason": "checkout hides shipping rates", "company": "Example Co", "email": "ada@buyer.example"}
    draft = draft_email({"lead": lead, "profile": profile})
    assert draft["critic_passed"] is True
    blocked = authorize_email({"critic_passed": False, "request": {}})
    assert blocked["sent"] is False


def test_acquisition_demo_and_e2e_endpoint():
    import os

    os.environ["USE_SQLITE"] = "true"
    app = create_app()
    client = TestClient(app)
    client.post(
        "/acquisition/profile",
        json={
            "business_name": "Northwind",
            "services": ["checkout audit"],
            "proof_points": ["A shop fixed shipping rates before account creation."],
            "price_floor": 50000,
            "list_price": 80000,
            "discount_limit": 0.1,
            "human_name": "Mina",
            "faq": ["Audits cover cart to paid."],
            "faq_terms": ["audit", "checkout"],
            "objections": {"price": "The floor for this audit is published in the profile."},
        },
    )
    demo = client.post("/acquisition/demo")
    assert demo.status_code == 200
    assert demo.json()["status"] == "converted"
    funnel = client.get("/acquisition/funnel")
    assert funnel.json()["counts"]["converted"] >= 1
    threads = client.get("/acquisition/conversations")
    assert threads.json()["conversations"]
    e2e = client.post("/e2e/run")
    assert e2e.status_code == 200
    assert e2e.json()["acquisition"]["status"] == "converted"
    assert e2e.json()["youtube"]["dry_run"]["passed"] >= 10


def test_workflow_endpoints_and_sourcing():
    import os

    os.environ["USE_SQLITE"] = "true"
    app = create_app()
    client = TestClient(app)
    client.post(
        "/acquisition/profile",
        json={
            "business_name": "Northwind",
            "services": ["checkout audit"],
            "proof_points": ["A shop fixed shipping rates before account creation."],
            "price_floor": 50000,
            "list_price": 80000,
            "discount_limit": 0.1,
            "human_name": "Mina",
            "faq": ["Audits cover cart to paid."],
        },
    )
    batch = client.post("/acquisition/leads/source-batch")
    assert batch.status_code == 200
    assert batch.json()["sourced"] >= 2
    dry = client.post("/youtube/workflows/dry-run")
    assert dry.status_code == 200
    assert dry.json().get("result") or dry.json().get("started")
    produce = client.post("/youtube/workflows/produce/projection")
    assert produce.status_code == 200
    from youtube.activities import m13_apply_fix

    fix = m13_apply_fix(
        {
            "video_id": "vid1",
            "funnel": {
                "age_hours": 72,
                "views": 80,
                "channel_median_views": 120,
                "impressions_ratio": 1,
                "ctr": 0.02,
                "retention_first_30": 0.5,
                "retention_mid": 0.5,
                "subscribers_per_1000": 4,
                "low_rpm_traffic_share": 0.1,
            },
            "new_value": "Why projection changes decisions",
            "current_metadata": {"title": "old title"},
        }
    )
    assert fix["change"] == "title"
    assert fix["updated"]["title"] == "Why projection changes decisions"


def test_render_thumbnails_and_discover():
    from youtube.modules.discover import discover_channels
    from youtube.modules.render import ProductionRenderer
    from youtube.modules.thumbnails import render_thumbnail
    from youtube.providers import FakeYouTube

    thumb = render_thumbnail("Why habits stick")
    assert len(thumb) > 20
    renderer = ProductionRenderer(workdir="artifacts/test-render")
    result = renderer.render_short("habit-short", "A short on habit loops.", 30)
    assert result["bytes"] > 0
    channels = discover_channels(FakeYouTube(), ["psychology"])
    assert len(channels) >= 3


def test_redis_quota_and_mailbox_limit():
    from acquisition.mailbox_limit import MailboxLimiter
    from core.redis_store import MemoryRedis, RateLimiter
    from youtube.quota import QuotaLedger

    ledger = QuotaLedger(daily_limit=5000, redis=MemoryRedis())
    ledger.reserve_for_scheduled_uploads(2)
    assert ledger.reserved == 3200
    limiter = MailboxLimiter(RateLimiter(MemoryRedis()))
    assert limiter.allow("ava@outreach.example", 2) is True
    assert limiter.allow("ava@outreach.example", 2) is True
    assert limiter.allow("ava@outreach.example", 2) is False


def test_webhooks_and_signed_conversion(session):
    import os

    os.environ["USE_SQLITE"] = "true"
    app = create_app()
    client = TestClient(app)
    client.post(
        "/acquisition/profile",
        json={
            "business_name": "Northwind",
            "services": ["checkout audit"],
            "proof_points": ["A shop fixed shipping rates before account creation."],
            "price_floor": 50000,
            "list_price": 80000,
            "discount_limit": 0.1,
            "conversion_definition": "signed_proposal",
            "human_name": "Mina",
            "faq": ["Audits cover cart to paid."],
        },
    )
    demo = client.post("/acquisition/demo")
    assert demo.status_code == 200
    assert demo.json()["deal"]["status"] == "signed"
    inbound = client.post("/webhooks/inbound/email", json={"from": "buyer@example.com", "text": "Still interested"})
    assert inbound.status_code in {200, 409}
    discover = client.post("/youtube/discover")
    assert discover.status_code == 200
    assert discover.json()["channels"] >= 1


def test_enrichment_icp_and_profile_approval(session):
    from acquisition.modules.icp import generate_icp, generate_icp_hypotheses, pick_cell
    from acquisition.modules.research_brief import build_research_brief
    from acquisition.modules.scoring import compute_scores
    from acquisition.modules.triggers import detect_triggers
    from acquisition.providers.enrichment import enrich_lead
    from acquisition.repository import AcquisitionRepository

    enriched = enrich_lead({"email": "ada@example.com", "company": "Example Co"})
    assert enriched.get("domain")
    icp = generate_icp({"services": ["checkout audit"], "business_name": "Northwind"})
    assert icp["roles"]
    cells = generate_icp_hypotheses({"services": ["checkout audit"], "business_name": "Northwind"})
    assert len(cells) >= 3
    assert pick_cell(cells)["name"]
    profile = _profile()
    lead = {"email": "ada@buyer.example", "company": "Shopify Brand Co", "reason": "checkout friction"}
    brief = build_research_brief(lead, profile)
    assert brief.facts
    triggers = detect_triggers(lead["reason"], profile)
    scores = compute_scores(lead, cells[0], profile, "valid", triggers)
    assert scores["score"] > 0
    repo = AcquisitionRepository(session)
    repo.save_profile("local", {"business_name": "Northwind", "services": ["audit"]}, approved=False)
    assert repo.is_profile_approved("local") is False
    repo.approve_profile("local")
    assert repo.is_profile_approved("local") is True


def test_acquisition_inbound_and_qualification(session):
    import os

    os.environ["USE_SQLITE"] = "true"
    app = create_app()
    client = TestClient(app)
    client.post(
        "/acquisition/profile",
        json={
            "business_name": "Northwind",
            "services": ["checkout audit"],
            "proof_points": ["A shop fixed shipping rates before account creation."],
            "price_floor": 50000,
            "list_price": 80000,
            "discount_limit": 0.1,
            "human_name": "Mina",
            "faq": ["Audits cover cart to paid."],
            "faq_terms": ["audit", "checkout"],
            "objections": {"price": "The floor for this audit is published in the profile."},
        },
    )
    inbound = client.post(
        "/acquisition/inbound/form",
        json={
            "email": "inbound@buyer.example",
            "first_name": "Ravi",
            "company": "Inbound Co",
            "message": "Interested in a checkout audit this month.",
        },
    )
    assert inbound.status_code == 200
    assert inbound.json()["status"] in {"replied", "positive", "qualifying"}
    qualify = client.post("/acquisition/qualify", json={"email": "inbound@buyer.example", "answer": "checkout friction"})
    assert qualify.status_code == 200
    icp = client.get("/acquisition/icp")
    assert icp.status_code == 200


def test_optimizer_store_persists(session):
    from youtube.store import DbOptimizerStore

    store = DbOptimizerStore(session)
    row = store.record_change("vid1", "title", "open", "0.04", {"value": "new title"})
    assert row["lever"] == "title"


def test_run_e2e_script():
    import os
    import subprocess
    import sys

    env = {**os.environ, "USE_SQLITE": "true"}
    result = subprocess.run([sys.executable, "run_e2e.py"], cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
