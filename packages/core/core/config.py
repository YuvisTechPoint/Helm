from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://engine:engine@localhost:5432/engine"
    redis_url: str = "redis://localhost:6379/0"
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "dual-engine"

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

    email_provider: str = "direct"
    instantly_api_key: str = ""
    apollo_api_key: str = ""
    zerobounce_api_key: str = ""
    calendar_provider: str = "calcom"
    calcom_api_key: str = ""
    crm_webhook_url: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payment_provider: str = "auto"
    payment_currency: str = "inr"
    payment_success_url: str = "https://example.com/thanks"

    esign_provider: str = "memory"
    documenso_api_key: str = ""
    documenso_base_url: str = "https://app.documenso.com/api/v1"
    documenso_template_id: str = ""
    esign_webhook_secret: str = ""

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""

    acquisition_weekly_qualified_target: int = 5
    acquisition_escalation_sla_hours: int = 24

    alert_email_to: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    slack_webhook_url: str = ""
    owner_notify_channels: str = "log,slack,email"

    acquisition_tenant_id: str = "local"
    acquisition_region: str = "india"

    api_key: str = ""
    engine_mode: str = "dev"  # dev | staging | production
    webhook_shared_secret: str = ""
    inbound_email_webhook_secret: str = ""
    email_events_webhook_secret: str = ""
    calcom_webhook_secret: str = ""
    vapi_webhook_secret: str = ""
    youtube_policy_webhook_secret: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    engine_version: str = "2027.1"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    worker_threads: int = 16


def get_settings() -> Settings:
    return Settings()
