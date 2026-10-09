"""End-to-end validation for the YouTube channel engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

DASHBOARD_ACTIONS: tuple[str, ...] = (
    "/autopilot/daily",
    "/e2e/run",
    "/autopilot/bootstrap",
    "/youtube/cycle",
    "/youtube/workflows/dry-run",
    "/youtube/discover",
    "/youtube/workflows/weekly-plan",
    "/youtube/dry-run",
    "/youtube/schedules/bootstrap",
)


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    payload: dict | None = None


@dataclass
class E2EReport:
    ok: bool
    steps: list[StepResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "passed": sum(1 for s in self.steps if s.ok),
            "failed": sum(1 for s in self.steps if not s.ok),
            "steps": [{"name": s.name, "ok": s.ok, "detail": s.detail} for s in self.steps],
        }


def run_pipeline_e2e() -> StepResult:
    from youtube.pipeline_e2e import YouTubePipeline

    youtube = YouTubePipeline().run_cycle()
    ok = youtube["dry_run"]["passed"] >= 10
    return StepResult("pipeline", ok, f"dry_run={youtube['dry_run']['passed']}", {"youtube": youtube})


def run_http_e2e(client) -> E2EReport:
    report = E2EReport(ok=True)

    for path in ("/health", "/ready", "/live", "/platform", "/autopilot/status", "/autopilot/workflows"):
        response = client.get(path)
        ok = response.status_code in {200, 503} if path == "/ready" else response.status_code == 200
        report.steps.append(StepResult(path, ok, f"status={response.status_code}"))
        if not ok:
            report.ok = False

    for path in DASHBOARD_ACTIONS:
        response = client.post(path)
        ok = response.status_code in {200, 201, 202}
        detail = f"status={response.status_code}"
        if not ok:
            detail = f"{detail} body={response.text[:200]}"
            report.ok = False
        report.steps.append(StepResult(path, ok, detail))

    return report


def run_full_e2e(client=None) -> E2EReport:
    report = E2EReport(ok=True)
    pipeline = run_pipeline_e2e()
    report.steps.append(pipeline)
    if not pipeline.ok:
        report.ok = False
    if client is not None:
        http = run_http_e2e(client)
        report.steps.extend(http.steps)
        if not http.ok:
            report.ok = False
    return report


def main_json(client=None) -> str:
    return json.dumps(run_full_e2e(client).to_dict(), indent=2)
