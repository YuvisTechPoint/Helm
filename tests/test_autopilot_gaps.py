from fastapi.testclient import TestClient

from api.main import create_app
from youtube.metadata import push_metadata_change
from youtube.orchestrator import start_workflow
from youtube.modules.analytics import funnel_from_metrics, metrics_from_analytics_api
from youtube.providers import FakeYouTube


def test_push_metadata_change_updates_fake_youtube_title():
    client = FakeYouTube()
    uploaded = client.insert({"snippet": {"title": "Old"}}, b"video")
    video_id = uploaded["id"]
    result = push_metadata_change(client, video_id, "title", "New title", {"title": "Old"})
    assert result["api"]["pushed"] is True
    assert client.metadata[video_id]["snippet"]["title"] == "New title"


def test_metrics_from_analytics_api_parses_rows():
    response = {
        "columnHeaders": [{"name": "views"}, {"name": "videoThumbnailImpressionsClickRate"}],
        "rows": [[120, 0.06]],
    }
    metrics = metrics_from_analytics_api(response)
    assert metrics["views"] == 120
    assert metrics["videoThumbnailImpressionsClickRate"] == 0.06


def test_funnel_from_metrics_builds_diagnostician_inputs():
    funnel = funnel_from_metrics(
        {"views": 200, "videoThumbnailImpressions": 4000, "videoThumbnailImpressionsClickRate": 0.05, "averageViewDuration": 24, "subscribersGained": 2},
        age_hours=72,
        channel_median_views=150,
    )
    assert funnel["views"] == 200
    assert funnel["ctr"] == 0.05


def test_sync_lead_sequence_runs_follow_ups(monkeypatch):
    from acquisition.sequence_sync import run_lead_sequence_sync

    calls = {"follow": 0}

    def fake_first_touch(payload):
        return {"status": "contacted"}

    def fake_plan(payload):
        return {"offsets": [0, 3, 7, 14], "send_time": "morning", "timezone": "UTC"}

    def fake_continue(payload):
        return {"continue": True}

    def fake_follow_up(payload):
        calls["follow"] += 1
        return {"status": "sent", "touch": payload["index"]}

    monkeypatch.setattr("acquisition.activities.acq_first_touch", fake_first_touch)
    monkeypatch.setattr("acquisition.activities.acq_sequence_plan", fake_plan)
    monkeypatch.setattr("acquisition.activities.sequence_should_continue", fake_continue)
    monkeypatch.setattr("acquisition.activities.acq_follow_up", fake_follow_up)

    result = run_lead_sequence_sync({"tenant_id": "local", "email": "ada@example.com"})
    assert result["sent"] is True
    assert result["touches"] == 4
    assert calls["follow"] == 3


def test_start_workflow_in_process_has_no_tcp_error():
    started = start_workflow("WeeklyPlanWorkflow", {})
    assert started["started"] is True
    assert "error" not in started
    if started.get("mode") == "in_process":
        assert started["result"]["niche"]["slug"] == "applied-psychology"


def test_bootstrap_tenant_seeds_profile_icp_and_volume():
    from core.bootstrap_tenant import bootstrap_tenant
    from core.container import AppContainer

    container = AppContainer.build()
    info = bootstrap_tenant(container)
    assert info["profile_approved"] is True
    assert info["icp_cells"] >= 3
    assert info["weekly_target"] >= 1
    assert info["daily_contacts_planned"] >= 1


def test_learning_volume_autopilot_endpoints():
    client = TestClient(create_app())
    learning = client.get("/acquisition/learning")
    assert learning.status_code == 200
    vol = client.post("/acquisition/volume", json={"weekly_qualified_target": 7})
    assert vol.status_code == 200
    assert vol.json()["daily_contacts_planned"] >= 1
    run = client.post("/acquisition/learning/run")
    assert run.status_code == 200
    assert "weights" in run.json()
    status = client.get("/autopilot/status")
    assert status.status_code == 200
    body = status.json()
    assert body["acquisition"]["profile_approved"] is True
    assert body["mode"] in {"in_process", "temporal"}
    daily = client.post("/autopilot/daily")
    assert daily.status_code == 200
    assert daily.json().get("finished_at")
    boot = client.post("/autopilot/bootstrap")
    assert boot.status_code == 200
    assert boot.json()["tenant"]["profile_approved"] is True


def test_dashboard_actions_run_without_profile_or_temporal():
    client = TestClient(create_app())
    health = client.get("/health").json()
    assert health["temporal"]["mode"] in {"in_process", "temporal"}
    demo = client.post("/acquisition/demo")
    assert demo.status_code == 200, demo.text
    assert demo.json()["status"] in {"converted", "proposal_sent", "booked", "qualified"}
    dry = client.post("/youtube/workflows/dry-run")
    assert dry.status_code == 200
    body = dry.json()
    assert body.get("started") is True
    assert "ConnectError" not in str(body)
    assert "ConnectionRefused" not in str(body)
    icp = client.post("/acquisition/icp/generate")
    assert icp.status_code == 200 and icp.json()["cells"]
    schedules = client.post("/autopilot/bootstrap")
    assert schedules.status_code == 200
    blob = schedules.json()
    assert all("ConnectionRefused" not in str(row) for row in blob["youtube_schedules"])
    assert all("ConnectionRefused" not in str(row) for row in blob["acquisition_schedules"])
    daily = client.post("/autopilot/daily")
    assert daily.status_code == 200
    assert daily.json()["acquisition"]["daily"]["started"] is True
