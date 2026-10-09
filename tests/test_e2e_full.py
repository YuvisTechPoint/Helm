"""100% end-to-end: pipeline, HTTP /e2e/run, and every dashboard action."""

import subprocess
import sys
from pathlib import Path

from core.e2e_harness import DASHBOARD_ACTIONS, run_full_e2e, run_http_e2e, run_pipeline_e2e
from fastapi.testclient import TestClient

from api.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_e2e_produces_dry_run():
    step = run_pipeline_e2e()
    assert step.ok, step.detail


def test_http_e2e_run_endpoint():
    client = TestClient(create_app())
    response = client.post("/e2e/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["youtube"]["dry_run"]["passed"] >= 10


def test_all_dashboard_actions_return_success():
    client = TestClient(create_app())
    report = run_http_e2e(client)
    failed = [s for s in report.steps if not s.ok]
    assert not failed, failed


def test_full_e2e_harness():
    client = TestClient(create_app())
    report = run_full_e2e(client)
    assert report.ok, report.to_dict()


def test_e2e_cli_script():
    env = {**__import__("os").environ, "USE_SQLITE": "true"}
    result = subprocess.run([sys.executable, "run_e2e.py"], cwd=str(ROOT), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    assert '"ok": true' in result.stdout.lower() or '"ok": True' in result.stdout


def test_dashboard_action_count():
    assert len(DASHBOARD_ACTIONS) == 9
