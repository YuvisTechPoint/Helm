"""YouTube automation cycle — background autopilot and API daily run."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.container import AppContainer


def run_daily(container: AppContainer) -> dict:
    """Full daily YouTube automation: weekly plan, metrics, optional production cycle."""
    from youtube.orchestrator import start_workflow

    youtube_state = container.youtube
    settings = container.settings
    results: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "in_process",
        "youtube": {},
    }

    if not youtube_state.kill.active("youtube"):
        weekly = start_workflow("WeeklyPlanWorkflow", {})
        results["youtube"]["weekly_plan"] = weekly
        results["mode"] = weekly.get("mode", "in_process")
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

    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    return results


def run_tick(container: AppContainer, *, force_daily: bool = False, last_daily_date: date | None = None) -> tuple[dict, date | None]:
    """Background tick: outbox drain every cycle; full daily once per UTC day."""
    now = datetime.now(timezone.utc)
    today = now.date()
    done: dict = {"at": now.isoformat(), "daily": None, "outbox": None, "mode": "in_process"}

    run_full_daily = force_daily or last_daily_date != today
    if run_full_daily:
        try:
            done["daily"] = run_daily(container)
            done["mode"] = done["daily"].get("mode", "in_process")
            last_daily_date = today
        except Exception as exc:
            done["daily"] = {"error": str(exc)}

    try:
        from core.outbox import Outbox

        done["outbox"] = Outbox(container.session).drain()
    except Exception as exc:
        done["outbox"] = {"error": str(exc)}

    return done, last_daily_date
