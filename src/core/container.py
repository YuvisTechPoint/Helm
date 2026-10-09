"""Composition root for the YouTube channel engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.bootstrap import db_session, vault_for
from core.circuit import CircuitBreaker
from core.config import Settings, get_settings
from core.runtime import EngineRuntime, set_runtime
from core.redis_store import get_redis


@dataclass
class AppContainer:
    settings: Settings
    session: object | None
    runtime: EngineRuntime
    redis: object
    circuits: dict[str, CircuitBreaker] = field(default_factory=dict)
    youtube: object | None = None

    @classmethod
    def build(cls, settings: Settings | None = None, session=None) -> "AppContainer":
        from core.platform import build_platform, reset_platform
        from youtube.http import YoutubeState
        from youtube.runtime_ctx import bind_youtube_runtime

        settings = settings or get_settings()
        reset_platform()
        platform = build_platform(settings)
        if session is None:
            try:
                session = db_session()
            except Exception:
                session = None
        runtime = EngineRuntime(settings=settings, session=session)
        set_runtime(runtime)
        resilience = platform.resilience
        circuits = {
            "llm": CircuitBreaker(
                "llm",
                failure_threshold=resilience.circuit_failure_threshold,
                reset_after=resilience.circuit_reset_after_s,
            ),
            "youtube": CircuitBreaker(
                "youtube",
                failure_threshold=resilience.circuit_failure_threshold,
                reset_after=resilience.circuit_reset_after_s,
            ),
        }
        container = cls(settings=settings, session=session, runtime=runtime, redis=get_redis(), circuits=circuits)
        container.youtube = YoutubeState(settings=settings, session=session, circuits=circuits)
        bind_youtube_runtime(runtime, circuits=circuits)
        return container

    def health(self) -> dict:
        from core.platform import get_platform
        from core.provider_plane import manifest
        from core.readiness import run_readiness_checks

        providers = manifest(self.settings)
        readiness = run_readiness_checks(self, timeout_s=get_platform().observability.readiness_timeout_s)
        return {
            "ready": readiness["ready"],
            "database": self.session is not None,
            "circuits": {name: breaker.status for name, breaker in self.circuits.items()},
            "cache": type(self.redis).__name__,
            "providers": providers,
            "readiness": readiness,
            "platform": get_platform().to_public_dict(),
        }


_CONTAINER: AppContainer | None = None


def bootstrap(settings: Settings | None = None, session=None) -> AppContainer:
    global _CONTAINER
    if settings is None and session is None and os.environ.get("USE_SQLITE", "").lower() == "true":
        pass
    _CONTAINER = AppContainer.build(settings=settings, session=session)
    return _CONTAINER


def get_container() -> AppContainer:
    global _CONTAINER
    if _CONTAINER is None:
        _CONTAINER = AppContainer.build()
    return _CONTAINER
