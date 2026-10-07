"""Unified business autopilot — runs both engines on a daily cadence."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request


def autopilot_status(youtube_state, acquisition, settings, autopilot=None) -> dict:
    from acquisition.defaults import ensure_ready_profile
    from core.temporal_gw import temporal_available

    tenant = settings.acquisition_tenant_id
    ensure_ready_profile(acquisition.repo, tenant)
    profile = acquisition.repo.get_profile_meta(tenant)
    uploads = youtube_state.store.list_all() if hasattr(youtube_state.store, "list_all") else []
    funnel = acquisition.repo.funnel_counts(tenant) if hasattr(acquisition.repo, "funnel_counts") else {}
    yt_kill = youtube_state.kill.active("youtube")
    acq_kill = acquisition.pipeline.kill.active("acquisition")
    profile_ok = bool(profile and profile.get("approved"))
    temporal_up = temporal_available()
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "mode": "temporal" if temporal_up else "in_process",
        "temporal_available": temporal_up,
        "youtube": {
            "kill_switch": yt_kill,
            "audit_approved": youtube_state.audit_approved,
            "quota_remaining": youtube_state.ledger.remaining,
            "uploads": len(uploads),
            "open_exceptions": len(youtube_state.exceptions.list_open("youtube")),
            "pivot": getattr(youtube_state.pipeline.optimizer, "pivot", None),
        },
        "acquisition": {
            "kill_switch": acq_kill,
            "profile_approved": profile_ok,
            "funnel": funnel,
            "open_escalations": len(acquisition.pipeline.exceptions.list_open("acquisition")),
            "icp_cells": len(acquisition.repo.list_icp_cells(tenant)),
        },
        "last_tick": getattr(autopilot, "last", None) if autopilot else None,
        "ready": not yt_kill and not acq_kill and profile_ok,
    }


def run_daily_autopilot(youtube_state, acquisition, settings) -> dict:
    from acquisition.defaults import ensure_ready_profile
    from youtube.orchestrator import start_workflow

    tenant = settings.acquisition_tenant_id
    ensure_ready_profile(acquisition.repo, tenant)
    results: dict = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": "in_process", "youtube": {}, "acquisition": {}}

    if not youtube_state.kill.active("youtube"):
        results["youtube"]["weekly_plan"] = start_workflow("WeeklyPlanWorkflow", {})
        for row in youtube_state.store.list_all() if hasattr(youtube_state.store, "list_all") else []:
            video_id = row.get("youtube_id")
            if not video_id:
                continue
            results["youtube"].setdefault("metrics", []).append(
                start_workflow(
                    "CollectMetricsWorkflow",
                    {"video_id": video_id, "published_at": datetime.now(timezone.utc).isoformat()},
                )
            )
        if settings.yt_audit_approved:
            results["youtube"]["cycle"] = youtube_state.pipeline.run_cycle()
    else:
        results["youtube"]["skipped"] = "kill switch active"

    if not acquisition.pipeline.kill.active("acquisition"):
        daily = start_workflow("AcquisitionDailyWorkflow", {"tenant_id": tenant})
        results["acquisition"]["daily"] = daily
        payload = daily.get("result") or {}
        results["acquisition"]["sequences"] = payload.get("sequences") or []
        results["acquisition"]["sweep"] = start_workflow("AcquisitionSweepWorkflow", {"tenant_id": tenant})
    else:
        results["acquisition"]["skipped"] = "kill switch active"

    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    return results


def router(youtube_state, acquisition, settings, container=None) -> APIRouter:
    api = APIRouter(prefix="/autopilot", tags=["autopilot"])

    @api.get("/status")
    def status(request: Request):
        auto = getattr(request.app.state, "autopilot", None)
        return autopilot_status(youtube_state, acquisition, settings, auto)

    @api.post("/daily")
    def daily():
        return run_daily_autopilot(youtube_state, acquisition, settings)

    @api.post("/tick")
    def tick(request: Request):
        auto = getattr(request.app.state, "autopilot", None)
        if auto is None:
            return run_daily_autopilot(youtube_state, acquisition, settings)
        return auto.tick(force_daily=True)

    @api.post("/bootstrap")
    def bootstrap():
        from acquisition.schedules import bootstrap_schedules as acq_schedules
        from core.bootstrap_tenant import bootstrap_tenant
        from youtube.schedules import bootstrap_schedules as yt_schedules

        tenant_info = bootstrap_tenant(container) if container is not None else {"tenant_id": settings.acquisition_tenant_id}
        return {
            "tenant": tenant_info,
            "youtube_schedules": yt_schedules(),
            "acquisition_schedules": acq_schedules(),
            "mode": "in_process",
        }

    return api
