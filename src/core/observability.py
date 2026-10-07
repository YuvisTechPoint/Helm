"""In-process metrics and structured counters — export via /metrics until Prometheus is wired."""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)
        self.latency_ms: dict[str, list[float]] = defaultdict(list)
        self.started_at = time.time()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self.counters[name] += value

    def observe_ms(self, name: str, ms: float) -> None:
        with self._lock:
            bucket = self.latency_ms[name]
            bucket.append(ms)
            if len(bucket) > 500:
                del bucket[:250]

    def snapshot(self) -> dict:
        with self._lock:
            latency = {}
            for key, samples in self.latency_ms.items():
                if not samples:
                    continue
                sorted_s = sorted(samples)
                latency[key] = {
                    "count": len(sorted_s),
                    "p50_ms": sorted_s[len(sorted_s) // 2],
                    "p95_ms": sorted_s[int(len(sorted_s) * 0.95)],
                    "max_ms": sorted_s[-1],
                }
            return {
                "uptime_s": round(time.time() - self.started_at, 1),
                "counters": dict(self.counters),
                "latency": latency,
            }


_METRICS = Metrics()


def metrics() -> Metrics:
    return _METRICS
