from fastapi.testclient import TestClient

from api.main import create_app
from youtube.orchestrator import run_sync_workflow
from youtube.pipeline import DRY_RUN_TOPICS


def _client():
    return TestClient(create_app())


def test_all_parameterless_gets_succeed():
    client = _client()
    catalog = client.get("/features")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["youtube"]["quality_gate"]
    assert any("/youtube/ops" in row["path"] or row["path"].endswith("/ops") for row in body["routes"])
    spec = client.get("/openapi.json").json()
    failed = []
    for path, item in spec["paths"].items():
        if "get" not in item or "{" in path:
            continue
        if path in {"/docs", "/redoc", "/openapi.json"}:
            continue
        response = client.get(path)
        if response.status_code >= 500:
            failed.append((path, response.status_code, response.text[:200]))
        if path in {"/health", "/ready", "/features", "/youtube/ops", "/youtube/plan"}:
            assert response.status_code == 200, path
    assert not failed, failed


def test_core_mutations_and_youtube_metrics_optimize_fallback():
    client = _client()
    dry = client.post("/youtube/dry-run")
    assert dry.status_code == 200 and dry.json()["passed"] == 10
    plan = client.get("/youtube/plan")
    assert plan.status_code == 200 and plan.json()["niche"]
    metrics = run_sync_workflow("CollectMetricsWorkflow", {"video_id": "vid-surface", "published_at": "2026-10-01T00:00:00+00:00"})
    assert metrics["snapshots"]
    optimize = run_sync_workflow("OptimizeVideoWorkflow", {"video_id": "vid-surface"})
    assert "diagnosis" in optimize
    slug = DRY_RUN_TOPICS[0]["slug"]
    produced = run_sync_workflow("ProduceOneWorkflow", {**DRY_RUN_TOPICS[0], "slug": slug})
    assert produced["status"] in {"published_private", "dropped"}
