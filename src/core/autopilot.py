"""In-process autopilot — keeps the channel engine cycling when Temporal is not installed."""

from __future__ import annotations

import threading

from core.automation import run_tick


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
        self._thread = threading.Thread(target=self._loop, name="youtube-engine-autopilot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self, *, force_daily: bool = False) -> dict:
        done, self._last_daily_date = run_tick(
            self.container,
            force_daily=force_daily,
            last_daily_date=self._last_daily_date,
        )
        self.last = done
        return done

    def _loop(self) -> None:
        self.tick()
        while not self._stop.wait(self.interval_s):
            self.tick()
