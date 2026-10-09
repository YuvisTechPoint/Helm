"""Deep readiness probes — separate from liveness (/live)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.container import AppContainer

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0


def _probe_database(session, timeout_s: float) -> ProbeResult:
    import time

    if session is None:
        return ProbeResult("database", False, "no session")
    started = time.perf_counter()
    try:
        from sqlalchemy import text

        session.execute(text("SELECT 1"))
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("database", True, "connected", ms)
    except Exception as exc:
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("database", False, str(exc), ms)


def _probe_redis(redis_store, timeout_s: float) -> ProbeResult:
    import time

    started = time.perf_counter()
    try:
        if hasattr(redis_store, "client"):
            redis_store.client.ping()
            detail = "redis"
        else:
            redis_store.get("__probe__")
            detail = "memory-fallback"
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("cache", True, detail, ms)
    except Exception as exc:
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("cache", False, str(exc), ms)


def _probe_temporal() -> ProbeResult:
    import time

    started = time.perf_counter()
    try:
        from core.temporal_gw import temporal_available

        up = temporal_available()
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("temporal", up, "available" if up else "in_process_fallback", ms)
    except Exception as exc:
        ms = (time.perf_counter() - started) * 1000
        return ProbeResult("temporal", False, str(exc), ms)


def _probe_providers(container: AppContainer) -> ProbeResult:
    from core.platform import get_platform

    platform = get_platform()
    blockers = platform.security.production_blockers
    if platform.is_production and blockers:
        return ProbeResult("providers", False, "; ".join(blockers))
    return ProbeResult("providers", True, f"tier={platform.tier.value}")


def run_readiness_checks(container: AppContainer, *, timeout_s: float = 2.0) -> dict:
    from core.platform import get_platform
    from core.config import EngineMode

    platform = get_platform()
    probes: list[ProbeResult] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_probe_database, container.session, timeout_s): "database",
            pool.submit(_probe_redis, container.redis, timeout_s): "cache",
            pool.submit(_probe_temporal): "temporal",
            pool.submit(_probe_providers, container): "providers",
        }
        for future in as_completed(futures, timeout=timeout_s + 1):
            try:
                probes.append(future.result())
            except Exception as exc:
                probes.append(ProbeResult(futures[future], False, str(exc)))

    yt_kill = container.runtime.kill.active("youtube")
    kill_ok = not yt_kill

    critical = {"database"}
    if platform.is_production:
        critical.add("providers")
        if platform.tier == EngineMode.PRODUCTION:
            critical.add("temporal")

    probe_map = {p.name: p for p in probes}
    failed = [name for name in critical if not probe_map.get(name, ProbeResult(name, False)).ok]
    ready = kill_ok and not failed

    return {
        "ready": ready,
        "kill_switches": {"youtube": yt_kill},
        "probes": {p.name: {"ok": p.ok, "detail": p.detail, "latency_ms": round(p.latency_ms, 2)} for p in probes},
        "failed": failed,
    }
