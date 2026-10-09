"""Ensure every maintained workflow has sync coverage and autopilot stays unified."""

from core.automation import run_tick
from core.container import AppContainer
from core.workflow_registry import WORKFLOWS, assert_sync_coverage, manifest, workflow_names
from fastapi.testclient import TestClient
from youtube.orchestrator import run_sync_workflow

from api.main import create_app


def test_workflow_registry_lists_all_maintained_workflows():
    names = workflow_names()
    assert "ProduceOneWorkflow" in names
    assert "WeeklyPlanWorkflow" in names
    assert len(WORKFLOWS) == len(names) == 5


def test_every_workflow_has_sync_handler():
    missing = assert_sync_coverage(run_sync_workflow)
    assert missing == [], f"missing sync handlers: {missing}"


def test_autopilot_tick_includes_daily_on_force():
    container = AppContainer.build()
    done, _ = run_tick(container, force_daily=True)
    assert "outbox" in done
    assert "daily" in done
    assert done["daily"] is not None
    assert "youtube" in done["daily"]


def test_autopilot_api_workflows_endpoint():
    client = TestClient(create_app())
    response = client.get("/autopilot/workflows")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(WORKFLOWS)
    assert manifest()["count"] == body["count"]


def test_autopilot_daily_matches_unified_runner():
    client = TestClient(create_app())
    daily = client.post("/autopilot/daily")
    assert daily.status_code == 200
    body = daily.json()
    assert "youtube" in body
    assert "finished_at" in body
