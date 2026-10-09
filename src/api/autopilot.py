"""YouTube channel autopilot — daily plan, metrics, and schedules."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from core.automation import run_daily


def autopilot_status(youtube_state, settings, autopilot=None) -> dict:
    from core.temporal_gw import temporal_available

    uploads = youtube_state.store.list_all() if hasattr(youtube_state.store, "list_all") else []
    yt_kill = youtube_state.kill.active("youtube")
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
        "last_tick": getattr(autopilot, "last", None) if autopilot else None,
        "ready": not yt_kill,
    }


def router(youtube_state, settings, container=None) -> APIRouter:
    api = APIRouter(prefix="/autopilot", tags=["autopilot"])

    @api.get("/status")
    def status(request: Request):
        auto = getattr(request.app.state, "autopilot", None)
        return autopilot_status(youtube_state, settings, auto)

    @api.get("/workflows")
    def workflows():
        from core.workflow_registry import manifest

        return manifest()

    @api.post("/daily")
    def daily():
        if container is None:
            raise RuntimeError("container required")
        return run_daily(container)

    @api.post("/tick")
    def tick(request: Request):
        auto = getattr(request.app.state, "autopilot", None)
        if auto is None:
            if container is None:
                raise RuntimeError("container required")
            return run_daily(container)
        return auto.tick(force_daily=True)

    @api.post("/bootstrap")
    def bootstrap():
        from core.bootstrap_tenant import bootstrap_channel
        from core.temporal_gw import temporal_available
        from youtube.schedules import bootstrap_schedules as yt_schedules

        channel_info = bootstrap_channel(container) if container is not None else {}
        temporal_up = temporal_available()
        return {
            "channel": channel_info,
            "youtube_schedules": yt_schedules(),
            "mode": "temporal" if temporal_up else "in_process",
            "temporal_available": temporal_up,
        }

    return api
