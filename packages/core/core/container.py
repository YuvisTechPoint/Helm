"""Composition root.

One process, one container: settings, DB session, shared kill/vault/jobs, both engine
states. API, worker, and Temporal activities resolve dependencies from here instead of
constructing parallel runtimes.

Scale plane:
  API replicas  → stateless HTTP, shared Postgres + Redis
  Worker replicas → Temporal task queue `dual-engine`
  Postgres      → tenant-scoped rows
  Redis         → rate limits and mailbox counters
  Object store  → video/audio artifacts
  Temporal      → durable workflows (sequences, sweeps, publish)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.bootstrap import db_session, vault_for
from core.circuit import CircuitBreaker
from core.config import Settings, get_settings
from core.exception_store import ExceptionStore
from core.jobs import JobBook
from core.kill_switch import KillSwitchBoard
from core.notify import NotifierHub
from core.redis_store import get_redis
from core.runtime import EngineRuntime, set_runtime


@dataclass
class AppContainer:
    settings: Settings
    session: object | None
    runtime: EngineRuntime
    redis: object
    circuits: dict[str, CircuitBreaker] = field(default_factory=dict)
    youtube: object | None = None
    acquisition: object | None = None

    @classmethod
    def build(cls, settings: Settings | None = None, session=None) -> "AppContainer":
        settings = settings or get_settings()
        if session is None:
            try:
                session = db_session()
            except Exception:
                session = None
        runtime = EngineRuntime(settings=settings, session=session)
        set_runtime(runtime)
        circuits = {
            "email": CircuitBreaker("email"),
            "llm": CircuitBreaker("llm"),
            "youtube": CircuitBreaker("youtube"),
            "payments": CircuitBreaker("payments"),
        }
        container = cls(settings=settings, session=session, runtime=runtime, redis=get_redis(), circuits=circuits)
        from acquisition.http import AcquisitionState
        from acquisition.runtime_ctx import bind_acquisition_runtime
        from youtube.http import YoutubeState
        from youtube.runtime_ctx import bind_youtube_runtime

        container.youtube = YoutubeState(settings=settings, session=session)
        container.acquisition = AcquisitionState(settings=settings, session=session)
        bind_acquisition_runtime(runtime)
        bind_youtube_runtime(runtime)
        return container

    def health(self) -> dict:
        yt_kill = self.runtime.kill.active("youtube")
        acq_kill = self.runtime.kill.active("acquisition")
        return {
            "ready": not yt_kill and not acq_kill,
            "database": self.session is not None,
            "circuits": {name: breaker.status for name, breaker in self.circuits.items()},
            "cache": type(self.redis).__name__,
        }


_CONTAINER: AppContainer | None = None


def bootstrap(settings: Settings | None = None, session=None) -> AppContainer:
    """Idempotent process bootstrap. API and worker call this once at start."""
    global _CONTAINER
    if settings is None and session is None and os.environ.get("USE_SQLITE", "").lower() == "true":
        # Tests and local sqlite each create_app() need a fresh bind to the process engine.
        pass
    _CONTAINER = AppContainer.build(settings=settings, session=session)
    return _CONTAINER


def get_container() -> AppContainer:
    global _CONTAINER
    if _CONTAINER is None:
        _CONTAINER = AppContainer.build()
    return _CONTAINER
