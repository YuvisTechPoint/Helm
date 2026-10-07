"""In-process autopilot so both engines keep cycling when Temporal is not installed."""

from __future__ import annotations

import threading
from datetime import datetime, timezone


class Autopilot:
    def __init__(self, container, interval_s: int = 900):
        self.container = container
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_daily_date = None
        self.last: dict = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="dual-engine-autopilot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self, *, force_daily: bool = False) -> dict:
        from acquisition.defaults import ensure_ready_profile
        from youtube.orchestrator import run_sync_workflow

        acquisition = self.container.acquisition
        settings = self.container.settings
        tenant = settings.acquisition_tenant_id
        now = datetime.now(timezone.utc)
        done = {"at": now.isoformat(), "sweep": None, "daily": None, "mode": "in_process"}
        try:
            ensure_ready_profile(acquisition.repo, tenant)
        except Exception as exc:
            done["profile"] = {"error": str(exc)}
        try:
            done["sweep"] = acquisition.pipeline.sweep(tenant)
        except Exception as exc:
            done["sweep"] = {"error": str(exc)}
        today = now.date()
        if force_daily or self._last_daily_date != today:
            try:
                done["daily"] = run_sync_workflow("AcquisitionDailyWorkflow", {"tenant_id": tenant})
                self._last_daily_date = today
            except Exception as exc:
                done["daily"] = {"error": str(exc)}
        self.last = done
        return done

    def _loop(self) -> None:
        self.tick()
        while not self._stop.wait(self.interval_s):
            self.tick()
