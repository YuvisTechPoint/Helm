"""Platform configuration — single source of truth for runtime posture.

Industry pattern: separate *what runs* (Settings/secrets) from *how it runs*
(resilience, security, observability). API, workers, and CI all resolve the same
PlatformConfig so dev/staging/production behave predictably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config import EngineMode

if TYPE_CHECKING:
    from core.config import Settings


@dataclass(frozen=True)
class ResilienceConfig:
    """Circuit breakers, pools, and backoff — tuned per tier."""

    circuit_failure_threshold: int
    circuit_reset_after_s: float
    db_pool_size: int
    db_max_overflow: int
    db_pool_pre_ping: bool
    db_pool_recycle_s: int
    redis_connect_timeout_s: float
    provider_timeout_s: float
    shutdown_timeout_s: float


@dataclass(frozen=True)
class SecurityConfig:
    """Auth, CORS, and webhook posture."""

    api_key_required: bool
    cors_origins: tuple[str, ...]
    webhook_secrets_configured: bool
    vault_key_configured: bool
    production_blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservabilityConfig:
    """Logging, metrics, and tracing hooks."""

    log_level: str
    log_format: str  # text | json
    engine_version: str
    otel_enabled: bool
    otel_endpoint: str
    metrics_enabled: bool
    readiness_timeout_s: float


@dataclass(frozen=True)
class ScalePlane:
    """Horizontal scale contract — what operators replicate."""

    api_replicas: str
    worker_replicas: str
    task_queue: str
    cache_backend: str
    database_backend: str
    object_store_backend: str


@dataclass(frozen=True)
class PlatformConfig:
    """Immutable platform manifest resolved once per process."""

    tier: EngineMode
    tenant_id: str
    resilience: ResilienceConfig
    security: SecurityConfig
    observability: ObservabilityConfig
    scale: ScalePlane
    capabilities: dict[str, bool] = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.tier == EngineMode.PRODUCTION

    def to_public_dict(self) -> dict:
        """Safe for /platform and dashboards — no secrets."""
        return {
            "tier": self.tier.value,
            "tenant_id": self.tenant_id,
            "resilience": {
                "circuit_failure_threshold": self.resilience.circuit_failure_threshold,
                "circuit_reset_after_s": self.resilience.circuit_reset_after_s,
                "db_pool": {
                    "size": self.resilience.db_pool_size,
                    "max_overflow": self.resilience.db_max_overflow,
                    "pre_ping": self.resilience.db_pool_pre_ping,
                    "recycle_s": self.resilience.db_pool_recycle_s,
                },
                "shutdown_timeout_s": self.resilience.shutdown_timeout_s,
            },
            "security": {
                "api_key_required": self.security.api_key_required,
                "cors_origins": list(self.security.cors_origins),
                "vault_key_configured": self.security.vault_key_configured,
                "webhook_secrets_configured": self.security.webhook_secrets_configured,
                "production_blockers": list(self.security.production_blockers),
            },
            "observability": {
                "log_level": self.observability.log_level,
                "log_format": self.observability.log_format,
                "engine_version": self.observability.engine_version,
                "otel_enabled": self.observability.otel_enabled,
                "metrics_enabled": self.observability.metrics_enabled,
            },
            "scale": {
                "api": self.scale.api_replicas,
                "workers": self.scale.worker_replicas,
                "task_queue": self.scale.task_queue,
                "cache": self.scale.cache_backend,
                "database": self.scale.database_backend,
                "object_store": self.scale.object_store_backend,
            },
            "capabilities": self.capabilities,
        }


_TIER_OVERRIDES: dict[EngineMode, dict] = {
    EngineMode.DEV: {
        "circuit_failure_threshold": 5,
        "circuit_reset_after_s": 30.0,
        "provider_timeout_s": 60.0,
    },
    EngineMode.STAGING: {
        "circuit_failure_threshold": 4,
        "circuit_reset_after_s": 45.0,
        "provider_timeout_s": 45.0,
    },
    EngineMode.PRODUCTION: {
        "circuit_failure_threshold": 3,
        "circuit_reset_after_s": 60.0,
        "provider_timeout_s": 30.0,
    },
}


def _tier(settings: Settings) -> EngineMode:
    raw = settings.engine_mode
    if isinstance(raw, EngineMode):
        return raw
    return EngineMode(str(raw).lower())


def _tier_requires_api_key(tier: EngineMode) -> bool:
    return tier in {EngineMode.STAGING, EngineMode.PRODUCTION}


def _tier_requires_temporal(tier: EngineMode) -> bool:
    return tier == EngineMode.PRODUCTION


def _webhook_secrets_ok(settings: Settings) -> bool:
    if not _tier_requires_api_key(_tier(settings)):
        return True
    return bool(settings.youtube_policy_webhook_secret)


def build_platform(settings: Settings) -> PlatformConfig:
    """Resolve platform posture from settings — call once at bootstrap."""
    tier = _tier(settings)
    overrides = _TIER_OVERRIDES[tier]
    origins = tuple(origin.strip() for origin in settings.cors_origins.split(",") if origin.strip())

    from core.provider_plane import manifest

    provider_manifest = manifest(settings)
    blockers = tuple(provider_manifest.get("blockers", []))
    if _tier_requires_api_key(tier) and not settings.api_key:
        blockers = (*blockers, "security: API_KEY is required")

    use_sqlite = settings.database_url.startswith("sqlite") or __import__("os").environ.get("USE_SQLITE", "").lower() == "true"

    global _PLATFORM
    _PLATFORM = PlatformConfig(
        tier=tier,
        tenant_id=settings.channel_id,
        resilience=ResilienceConfig(
            circuit_failure_threshold=int(overrides["circuit_failure_threshold"]),
            circuit_reset_after_s=float(overrides["circuit_reset_after_s"]),
            db_pool_size=settings.db_pool_size,
            db_max_overflow=settings.db_max_overflow,
            db_pool_pre_ping=True,
            db_pool_recycle_s=1800,
            redis_connect_timeout_s=settings.redis_connect_timeout_s,
            provider_timeout_s=float(overrides["provider_timeout_s"]),
            shutdown_timeout_s=settings.shutdown_timeout_s,
        ),
        security=SecurityConfig(
            api_key_required=_tier_requires_api_key(tier) and bool(settings.api_key),
            cors_origins=origins or ("http://localhost:3000",),
            webhook_secrets_configured=_webhook_secrets_ok(settings),
            vault_key_configured=bool(settings.vault_fernet_key),
            production_blockers=blockers,
        ),
        observability=ObservabilityConfig(
            log_level=settings.log_level.upper(),
            log_format=settings.log_format.lower(),
            engine_version=settings.engine_version,
            otel_enabled=settings.otel_enabled,
            otel_endpoint=settings.otel_endpoint,
            metrics_enabled=True,
            readiness_timeout_s=settings.readiness_timeout_s,
        ),
        scale=ScalePlane(
            api_replicas="stateless horizontal",
            worker_replicas=f"Temporal queue `{settings.temporal_task_queue}`",
            task_queue=settings.temporal_task_queue,
            cache_backend="redis",
            database_backend="sqlite" if use_sqlite else "postgresql",
            object_store_backend="s3-compatible",
        ),
        capabilities={
            "youtube_engine": True,
            "transactional_outbox": True,
            "circuit_breakers": True,
            "kill_switches": True,
            "autopilot": True,
            "temporal_workflows": True,
        },
    )
    return _PLATFORM


_PLATFORM: PlatformConfig | None = None


def get_platform(settings: Settings | None = None) -> PlatformConfig:
    if settings is not None:
        return build_platform(settings)
    if _PLATFORM is None:
        from core.config import get_settings

        build_platform(get_settings())
    return _PLATFORM


def reset_platform() -> None:
    """Test helper — clear cached platform."""
    global _PLATFORM
    _PLATFORM = None
