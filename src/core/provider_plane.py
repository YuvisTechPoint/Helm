"""Provider mode inspection — no silent fakes in production."""

from __future__ import annotations

from core.config import Settings, get_settings
from core.errors import ConfigurationError, MissingCredentials, ProviderUnavailable


def is_production(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.engine_mode.lower() == "production"


def is_dev(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.engine_mode.lower() in {"dev", "development", "local"}


def youtube_client_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.youtube_refresh_token and settings.yt_client_id and settings.yt_client_secret:
        return "live"
    if is_dev(settings):
        return "simulated"
    raise MissingCredentials("YouTube OAuth: set YT_CLIENT_ID, YT_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN")


def email_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.email_provider == "instantly" and settings.instantly_api_key:
        return "live"
    if is_dev(settings):
        return "simulated"
    raise MissingCredentials("Email: set EMAIL_PROVIDER=instantly and INSTANTLY_API_KEY")


def sourcing_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.apollo_api_key:
        return "live"
    if is_dev(settings):
        return "fixture"
    raise ProviderUnavailable("Lead sourcing: set APOLLO_API_KEY or run in dev mode")


def llm_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.anthropic_api_key or settings.openai_api_key:
        return "live"
    if is_dev(settings):
        return "deterministic"
    raise MissingCredentials("LLM: set ANTHROPIC_API_KEY or OPENAI_API_KEY")


def tts_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.elevenlabs_api_key or settings.tts_backup_api_key:
        return "live"
    if is_dev(settings):
        return "dry_run"
    raise MissingCredentials("TTS: set ELEVENLABS_API_KEY")


def payments_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.stripe_secret_key or settings.razorpay_key_secret:
        return "live"
    if is_dev(settings):
        return "memory"
    raise MissingCredentials("Payments: set STRIPE_SECRET_KEY or RAZORPAY_KEY_SECRET")


def esign_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.esign_provider == "documenso" and settings.documenso_api_key:
        return "live"
    if is_dev(settings):
        return "memory"
    raise MissingCredentials("E-sign: set ESIGN_PROVIDER=documenso and DOCUMENSO_API_KEY")


def temporal_mode() -> str:
    from core.temporal_gw import temporal_available

    return "temporal" if temporal_available() else "in_process"


def manifest(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    modes: dict[str, str] = {}
    blockers: list[str] = []
    for name, probe in (
        ("youtube", lambda: youtube_client_mode(settings)),
        ("email", lambda: email_mode(settings)),
        ("sourcing", lambda: sourcing_mode(settings)),
        ("llm", lambda: llm_mode(settings)),
        ("tts", lambda: tts_mode(settings)),
        ("payments", lambda: payments_mode(settings)),
        ("esign", lambda: esign_mode(settings)),
    ):
        try:
            modes[name] = probe()
        except (MissingCredentials, ProviderUnavailable) as exc:
            modes[name] = "blocked"
            blockers.append(f"{name}: {exc}")
    modes["temporal"] = temporal_mode()
    modes["database"] = "sqlite" if settings.database_url.startswith("sqlite") or __import__("os").environ.get("USE_SQLITE") == "true" else "postgres"
    return {
        "engine_mode": settings.engine_mode,
        "providers": modes,
        "simulated": [k for k, v in modes.items() if v in {"simulated", "fixture", "memory", "dry_run", "deterministic", "in_process"}],
        "live": [k for k, v in modes.items() if v == "live"],
        "blockers": blockers,
        "production_ready": is_production(settings) and not blockers,
    }


def with_circuit(inner, breaker, method: str):
    """Wrap a single provider method with a circuit breaker."""
    if breaker is None or not hasattr(inner, method):
        return inner
    original = getattr(inner, method)

    def wrapped(*args, **kwargs):
        return breaker.call(original, *args, **kwargs)

    setattr(inner, method, wrapped)
    return inner


def validate_startup(settings: Settings | None = None) -> list[str]:
    """Return blockers; raise in production if any remain."""
    settings = settings or get_settings()
    blockers = manifest(settings)["blockers"]
    if is_production(settings) and not settings.api_key:
        blockers.append("security: API_KEY is required in production")
    if is_production(settings) and blockers:
        raise ConfigurationError("; ".join(blockers))
    return blockers
