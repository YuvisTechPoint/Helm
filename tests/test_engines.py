from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import youtube.models  # noqa: F401
from api.main import create_app
from core.db import Base, make_engine
from core.errors import OneChangeError, PublishingBlocked, QuotaExceeded, TermsViolation
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


def test_schema_has_core_tables(session):
    names = set(Base.metadata.tables)
    for required in ("secrets", "events", "jobs", "published_videos", "kill_switches"):
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
    transport = FakeTransport("uploaded1")
    uploaded = ResumableUploader(transport, "token").insert(client.inserts[0]["metadata"], b"mp4")
    assert uploaded["id"] == "uploaded1"


def test_niche_scout_prefers_psychology_until_live_data_overrides():
    choice = scout()
    assert choice.slug == "applied-psychology"
    saturated = {"applied-psychology": [{"channel_subscribers": 500_000} for _ in range(10)]}
    overridden = scout(saturated)
    assert overridden.slug != "applied-psychology"


def test_quality_gate_passes_ten_and_drops_after_two_rewrites():
    report = run_private_dry_run()
    assert report["passed"] == 10
    assert report["uploads"] == 10

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


def test_diagnostician_one_change_rollback_and_veto():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    optimizer = Optimizer()
    held = __import__("youtube.modules.diagnostician", fromlist=["diagnose"]).diagnose(_funnel(age_hours=24), [])
    assert held["action"] == "hold"
    change = apply_fix(optimizer, "v", _funnel(ctr=0.02, retention_first_30=0.5), now)
    assert change.lever == "title"
    with pytest.raises(OneChangeError):
        apply_fix(optimizer, "v", _funnel(ctr=0.02), now)


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


def test_ypp_never_auto_applies():
    progress = ypp_progress(1000, 4000)
    assert progress["eligible"] is True
    assert progress["auto_apply"] is False
    with pytest.raises(RuntimeError):
        apply_for_partner_program(progress)


def test_live_research_refuses_without_provider():
    with pytest.raises(ValueError):
        research_topic("projection", dry_run=False)


def test_activity_and_http_surface():
    choice = m2_niche_scout({})
    assert choice["slug"] == "applied-psychology"
    app = create_app()
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/youtube/oauth/start").status_code == 200
    blocked = client.post(
        "/youtube/publish",
        json={"idempotency_key": "pub-1", "title": "Public try", "privacy_status": "public", "dry_run": False, "provisional_research": False},
    )
    assert blocked.status_code == 409
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
    assert published["privacy_status"] == "private"


def test_workflow_endpoints():
    import os

    os.environ["USE_SQLITE"] = "true"
    client = TestClient(create_app())
    dry = client.post("/youtube/workflows/dry-run")
    assert dry.status_code == 200
    assert dry.json().get("result") or dry.json().get("started")
    e2e = client.post("/e2e/run")
    assert e2e.status_code == 200
    assert e2e.json()["youtube"]["dry_run"]["passed"] >= 10


def test_redis_quota():
    from core.redis_store import MemoryRedis
    from youtube.quota import QuotaLedger

    ledger = QuotaLedger(daily_limit=5000, redis=MemoryRedis())
    ledger.reserve_for_scheduled_uploads(2)
    assert ledger.reserved == 3200


def test_run_e2e_script():
    import os
    import subprocess
    import sys

    env = {**os.environ, "USE_SQLITE": "true"}
    result = subprocess.run(
        [sys.executable, "run_e2e.py"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
