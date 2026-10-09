from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineMode(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://engine:engine@localhost:5432/engine"
    redis_url: str = "redis://localhost:6379/0"
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "youtube-engine"

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "engine"
    s3_access_key: str = "engine"
    s3_secret_key: str = "engine-secret"

    vault_fernet_key: str = ""

    yt_audit_approved: bool = False
    yt_client_id: str = ""
    yt_client_secret: str = ""
    yt_redirect_uri: str = "http://localhost:8000/youtube/oauth/callback"
    youtube_api_key: str = ""
    youtube_refresh_token: str = ""

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openai_model: str = "gpt-4o-mini"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "stock-calm-en-us"
    tts_backup_api_key: str = ""

    alert_email_to: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    slack_webhook_url: str = ""
    owner_notify_channels: str = "log,slack,email"

    channel_id: str = "local"
    youtube_policy_webhook_secret: str = ""

    api_key: str = ""
    engine_mode: EngineMode = EngineMode.DEV
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    engine_version: str = "2027.1"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    worker_threads: int = Field(default=16, ge=1, le=128)

    log_level: str = "INFO"
    log_format: str = "text"
    otel_enabled: bool = False
    otel_endpoint: str = ""
    otel_service_name: str = "youtube-channel-api"
    shutdown_timeout_s: float = Field(default=30.0, ge=5.0, le=300.0)
    readiness_timeout_s: float = Field(default=2.0, ge=0.5, le=30.0)
    redis_connect_timeout_s: float = Field(default=1.0, ge=0.1, le=10.0)
    circuit_failure_threshold: int = Field(default=5, ge=1, le=50)
    circuit_reset_after_s: float = Field(default=30.0, ge=5.0, le=600.0)
    run_migrations: bool = False

    @field_validator("engine_mode", mode="before")
    @classmethod
    def _normalize_engine_mode(cls, value):
        if isinstance(value, EngineMode):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {"development": EngineMode.DEV, "local": EngineMode.DEV, "prod": EngineMode.PRODUCTION}
            if normalized in aliases:
                return aliases[normalized]
            return EngineMode(normalized)
        return value

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, value: str) -> str:
        fmt = value.strip().lower()
        if fmt not in {"text", "json"}:
            raise ValueError("log_format must be 'text' or 'json'")
        return fmt

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.strip().upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return upper

    def mode_is_production(self) -> bool:
        return self.engine_mode == EngineMode.PRODUCTION

    def mode_is_dev(self) -> bool:
        return self.engine_mode == EngineMode.DEV


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    from core.platform import reset_platform

    reset_platform()
    return get_settings()
