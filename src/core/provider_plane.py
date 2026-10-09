"""Provider mode inspection — no silent fakes in production."""

from __future__ import annotations

from core.config import Settings, get_settings
from core.errors import ConfigurationError, MissingCredentials


def is_production(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.mode_is_production()


def is_dev(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.mode_is_dev()


def youtube_client_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.youtube_refresh_token and settings.yt_client_id and settings.yt_client_secret:
        return "live"
    if is_dev(settings):
        return "simulated"
    raise MissingCredentials("YouTube OAuth: set YT_CLIENT_ID, YT_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN")


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


def temporal_mode() -> str:
    from core.temporal_gw import temporal_available

    return "temporal" if temporal_available() else "in_process"


def manifest(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    modes: dict[str, str] = {}
    blockers: list[str] = []
    for name, probe in (
        ("youtube", lambda: youtube_client_mode(settings)),
        ("llm", lambda: llm_mode(settings)),
        ("tts", lambda: tts_mode(settings)),
    ):
        try:
            modes[name] = probe()
        except MissingCredentials as exc:
            modes[name] = "blocked"
            blockers.append(f"{name}: {exc}")
    modes["temporal"] = temporal_mode()
    modes["database"] = "sqlite" if settings.database_url.startswith("sqlite") or __import__("os").environ.get("USE_SQLITE") == "true" else "postgres"
    mode = settings.engine_mode.value if hasattr(settings.engine_mode, "value") else settings.engine_mode
    return {
        "engine_mode": mode,
        "providers": modes,
        "simulated": [k for k, v in modes.items() if v in {"simulated", "dry_run", "deterministic", "in_process"}],
        "live": [k for k, v in modes.items() if v == "live"],
        "blockers": blockers,
        "production_ready": is_production(settings) and not blockers,
    }


def with_circuit(inner, breaker, method: str):
    if breaker is None or not hasattr(inner, method):
        return inner
    original = getattr(inner, method)

    def wrapped(*args, **kwargs):
        return breaker.call(original, *args, **kwargs)

    setattr(inner, method, wrapped)
    return inner


def validate_startup(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    blockers = manifest(settings)["blockers"]
    if is_production(settings) and not settings.api_key:
        blockers.append("security: API_KEY is required in production")
    if is_production(settings) and blockers:
        raise ConfigurationError("; ".join(blockers))
    return blockers
