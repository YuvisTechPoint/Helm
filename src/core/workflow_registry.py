"""Canonical registry of YouTube automation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

Engine = Literal["youtube"]
Trigger = Literal["schedule", "api", "autopilot"]


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    engine: Engine
    description: str
    sync_supported: bool
    triggers: tuple[Trigger, ...]
    schedule_id: str | None = None


WORKFLOWS: tuple[WorkflowSpec, ...] = (
    WorkflowSpec("ProduceOneWorkflow", "youtube", "Research → script → gate → voice → render → publish", True, ("api",)),
    WorkflowSpec("ProducePrivateWorkflow", "youtube", "Private dry-run publish path", True, ("schedule",), "private-dry-run"),
    WorkflowSpec("WeeklyPlanWorkflow", "youtube", "Niche scout + competitor report", True, ("schedule", "autopilot"), "weekly-plan"),
    WorkflowSpec("CollectMetricsWorkflow", "youtube", "Post-publish metrics snapshots", True, ("schedule", "autopilot")),
    WorkflowSpec("OptimizeVideoWorkflow", "youtube", "Diagnose funnel + apply one change", True, ("api",)),
)


def workflow_names() -> set[str]:
    return {spec.name for spec in WORKFLOWS}


def manifest() -> dict:
    return {
        "count": len(WORKFLOWS),
        "workflows": [
            {
                "name": spec.name,
                "engine": spec.engine,
                "description": spec.description,
                "sync_supported": spec.sync_supported,
                "triggers": list(spec.triggers),
                "schedule_id": spec.schedule_id,
            }
            for spec in WORKFLOWS
        ],
    }


def assert_sync_coverage(runner: Callable[[str, dict], object]) -> list[str]:
    missing = []
    for spec in WORKFLOWS:
        if not spec.sync_supported:
            continue
        try:
            runner(spec.name, _probe_payload(spec.name))
        except ValueError as exc:
            if "unknown workflow" in str(exc):
                missing.append(spec.name)
        except Exception:
            pass
    return missing


def _probe_payload(name: str) -> dict:
    probes = {
        "ProduceOneWorkflow": {"slug": "probe-topic", "competitor_titles": [], "target_seconds": 60},
        "ProducePrivateWorkflow": {"slug": "probe"},
        "WeeklyPlanWorkflow": {},
        "CollectMetricsWorkflow": {"video_id": "probe", "published_at": "2026-01-01T00:00:00+00:00"},
        "OptimizeVideoWorkflow": {"video_id": "probe"},
    }
    return probes.get(name, {})
