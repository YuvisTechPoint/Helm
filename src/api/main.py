import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings, reload_settings
from core.container import bootstrap
from core.http_platform import RequestContextMiddleware, install_error_handlers
from core.logging_config import configure_logging
from core.platform import build_platform, get_platform
from core.readiness import run_readiness_checks
from youtube.http import router as youtube_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = reload_settings() if os.environ.get("PYTEST_CURRENT_TEST") else get_settings()
    configure_logging(settings.log_level, settings.log_format)
    build_platform(settings)
    if not settings.database_url.startswith("sqlite"):
        os.environ.setdefault("USE_SQLITE", "false")
    container = bootstrap(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container
        from core.autopilot import Autopilot
        from core.provider_plane import validate_startup

        app.state.provider_blockers = validate_startup(settings)
        app.state.platform = get_platform()
        logger.info(
            "youtube-engine starting tier=%s version=%s",
            app.state.platform.tier.value,
            settings.engine_version,
        )

        if not os.environ.get("PYTEST_CURRENT_TEST"):
            from core.bootstrap_tenant import bootstrap_channel

            app.state.bootstrap = bootstrap_channel(container)
        auto = Autopilot(container)
        app.state.autopilot = auto
        if not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("DISABLE_AUTOPILOT") != "1":
            auto.start()
        try:
            yield
        finally:
            logger.info("youtube-engine shutting down")
            auto.stop()
            session = getattr(container, "session", None)
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
            await asyncio.sleep(0)

    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app = FastAPI(
        title="YouTube Channel Engine API",
        version=settings.engine_version,
        description="Autonomous faceless YouTube channel engine. API is stateless; Temporal workers scale independently.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Engine-Version"],
    )
    app.add_middleware(
        RequestContextMiddleware,
        api_key=settings.api_key,
        engine_version=settings.engine_version,
        default_tenant=settings.channel_id,
    )
    install_error_handlers(app)
    app.state.settings = settings
    app.state.container = container
    app.state.session = container.session
    app.state.youtube = container.youtube
    app.include_router(youtube_router(app.state.youtube))
    from api.autopilot import router as autopilot_router

    app.include_router(autopilot_router(app.state.youtube, settings, container=container))

    def _health_payload():
        youtube = app.state.youtube
        yt_kill = youtube.kill.active("youtube")
        ready = not yt_kill
        plane = container.health()
        from core.temporal_gw import temporal_available

        temporal_up = temporal_available()
        providers = plane.get("providers", {})
        platform = get_platform()
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "engine_mode": platform.tier.value,
            "version": settings.engine_version,
            "providers": providers,
            "audit_approved": youtube.audit_approved,
            "youtube_kill_switch": yt_kill,
            "database": "sqlite" if os.environ.get("USE_SQLITE", "").lower() == "true" else settings.database_url.split("://", 1)[0],
            "temporal": {
                "address": settings.temporal_address,
                "available": temporal_up,
                "mode": "temporal" if temporal_up else "in_process",
            },
            "scale": {
                "cache": plane["cache"],
                "circuits": plane["circuits"],
                "task_queue": settings.temporal_task_queue,
                "db_pool": {"size": settings.db_pool_size, "overflow": settings.db_max_overflow},
            },
            "components": {
                "youtube": {
                    "kill": yt_kill,
                    "audit_approved": youtube.audit_approved,
                    "quota_remaining": youtube.ledger.remaining,
                },
            },
        }

    @app.get("/")
    def root():
        return {
            "name": "YouTube Channel Engine API",
            "version": settings.engine_version,
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
            "features": "/features",
            "dashboard": "http://localhost:3000",
        }

    @app.get("/json/version")
    def json_version():
        return {"version": settings.engine_version, "engine": "youtube-channel"}

    @app.get("/health")
    def health():
        return _health_payload()

    @app.get("/ready")
    def ready():
        payload = run_readiness_checks(container, timeout_s=get_platform().observability.readiness_timeout_s)
        payload["version"] = settings.engine_version
        payload["engine_mode"] = get_platform().tier.value
        if not payload["ready"]:
            return JSONResponse(payload, status_code=503)
        return payload

    @app.get("/live")
    def live():
        return {"alive": True, "version": settings.engine_version}

    @app.get("/platform")
    def platform_manifest():
        return get_platform().to_public_dict()

    @app.get("/metrics")
    def metrics_endpoint():
        from core.observability import metrics

        return metrics().snapshot()

    @app.get("/features")
    def features():
        paths = []
        for path, ops in app.openapi()["paths"].items():
            methods = sorted(method.upper() for method in ops if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"})
            if methods:
                paths.append({"path": path, "methods": methods})
        return {
            "version": settings.engine_version,
            "planes": {
                "api": "stateless FastAPI replicas",
                "workers": f"Temporal task queue {settings.temporal_task_queue}",
                "postgres": "channel state and metrics",
                "redis": "quota and rate limits",
                "object_store": "rendered video and audio",
            },
            "youtube": {
                "niche_scout": True,
                "competitor_discover": True,
                "weekly_plan": True,
                "quality_gate": True,
                "private_publish": True,
                "metrics_loop": True,
                "one_change_optimize": True,
                "ypp_progress": True,
                "kill_switch": True,
                "synthetic_media_flag": True,
            },
            "routes": paths,
        }

    @app.post("/e2e/run")
    def run_e2e():
        return {"youtube": app.state.youtube.pipeline.run_cycle()}

    return app
