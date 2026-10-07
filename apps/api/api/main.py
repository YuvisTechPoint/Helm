import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from acquisition.http import router as acquisition_router
from core.config import get_settings
from core.container import bootstrap
from core.http_platform import RequestContextMiddleware, install_error_handlers
from youtube.http import router as youtube_router


def create_app() -> FastAPI:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        os.environ.setdefault("USE_SQLITE", "false")
    container = bootstrap(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = container
        from core.autopilot import Autopilot

        if not os.environ.get("PYTEST_CURRENT_TEST"):
            from core.bootstrap_tenant import bootstrap_tenant

            app.state.bootstrap = bootstrap_tenant(container)
        auto = Autopilot(container)
        app.state.autopilot = auto
        if not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("DISABLE_AUTOPILOT") != "1":
            auto.start()
        try:
            yield
        finally:
            auto.stop()

    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app = FastAPI(
        title="Dual Engine API",
        version=settings.engine_version,
        description="Autonomous YouTube and lead-to-client engines. API is stateless; Temporal workers scale independently.",
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
        default_tenant=settings.acquisition_tenant_id,
    )
    install_error_handlers(app)
    app.state.settings = settings
    app.state.container = container
    app.state.session = container.session
    app.state.youtube = container.youtube
    app.state.acquisition = container.acquisition
    app.include_router(youtube_router(app.state.youtube))
    app.include_router(acquisition_router(app.state.acquisition))
    from api.webhooks import router as webhooks_router

    app.include_router(webhooks_router(app))
    from api.autopilot import router as autopilot_router

    app.include_router(autopilot_router(app.state.youtube, app.state.acquisition, settings, container=container))

    def _health_payload():
        youtube = app.state.youtube
        acquisition = app.state.acquisition
        tenant = settings.acquisition_tenant_id
        profile = acquisition.repo.get_profile_meta(tenant)
        yt_kill = youtube.kill.active("youtube")
        acq_kill = acquisition.pipeline.kill.active("acquisition")
        ready = not yt_kill and not acq_kill
        plane = container.health()
        from core.temporal_gw import temporal_available

        temporal_up = temporal_available()
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "version": settings.engine_version,
            "audit_approved": youtube.audit_approved,
            "youtube_kill_switch": yt_kill,
            "acquisition_kill_switch": acq_kill,
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
                "youtube": {"kill": yt_kill, "audit_approved": youtube.audit_approved, "quota_remaining": youtube.ledger.remaining},
                "acquisition": {
                    "kill": acq_kill,
                    "profile_approved": bool(profile and profile.get("approved")),
                    "tenant_id": tenant,
                },
            },
        }

    @app.get("/health")
    def health():
        return _health_payload()

    @app.get("/ready")
    def ready():
        return _health_payload()

    @app.get("/features")
    def features():
        """Machine-readable map of every live capability both engines expose."""
        paths = []
        for path, ops in app.openapi()["paths"].items():
            methods = sorted(method.upper() for method in ops if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"})
            if methods:
                paths.append({"path": path, "methods": methods})
        return {
            "version": settings.engine_version,
            "planes": {
                "api": "stateless FastAPI replicas",
                "workers": "Temporal task queue dual-engine",
                "postgres": "tenant-scoped system of record",
                "redis": "rate limits and counters",
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
            "acquisition": {
                "icp_bandit": True,
                "fit_intent_reach_score": True,
                "lookalike": True,
                "sequences": True,
                "policy_guard": True,
                "consent_channels": True,
                "esign_payments": True,
                "learning_wilson": True,
                "data_rights": True,
                "kill_switch": True,
            },
            "routes": paths,
        }

    @app.post("/e2e/run")
    def run_e2e():
        youtube_result = app.state.youtube.pipeline.run_cycle()
        acquisition = app.state.acquisition
        tenant_id = settings.acquisition_tenant_id
        from acquisition.defaults import ensure_ready_profile

        profile = ensure_ready_profile(acquisition.repo, tenant_id)
        acquisition_result = acquisition.pipeline.run_demo(
            tenant_id,
            profile,
            {
                "email": f"lead-{uuid.uuid4().hex[:8]}@buyer.example",
                "first_name": "Ada",
                "company": "Example Co",
                "reason": "checkout hides shipping rates until account creation",
                "fit": 0.8,
                "intent": 0.7,
            },
            "Interested — let's talk next week.",
            "2026-10-15T10:00:00+05:30",
        )
        return {"youtube": youtube_result, "acquisition": acquisition_result}

    return app
