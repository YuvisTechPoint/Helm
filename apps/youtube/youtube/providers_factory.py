from core.config import Settings
from youtube.providers import (
    AnthropicLlm,
    ElevenLabsTts,
    FailoverLlm,
    FailoverTts,
    FakeYouTube,
    GoogleYouTubeData,
    OpenAiLlm,
    ResumableUploader,
    YouTubeAnalyticsClient,
)


def youtube_client(settings: Settings, vault=None, transport=None):
    if settings.youtube_refresh_token and settings.yt_client_id and settings.yt_client_secret:
        from youtube.oauth_flow import refresh_access_token

        tokens = refresh_access_token(settings.yt_client_id, settings.yt_client_secret, settings.youtube_refresh_token)
        access = tokens["access_token"]
        if vault is not None:
            vault.put("youtube_access_token", access)
        if transport is not None:
            return ResumableUploader(transport, access)
        return GoogleYouTubeData(access)
    return FakeYouTube()


def llm(settings: Settings):
    primary = AnthropicLlm(settings.anthropic_api_key, settings.anthropic_model) if settings.anthropic_api_key else None
    secondary = OpenAiLlm(settings.openai_api_key, settings.openai_model) if settings.openai_api_key else None
    if primary and secondary:
        return FailoverLlm(primary, secondary)
    return primary or secondary


def tts(settings: Settings):
    primary = ElevenLabsTts(settings.elevenlabs_api_key, settings.elevenlabs_voice_id) if settings.elevenlabs_api_key else None
    backup = ElevenLabsTts(settings.tts_backup_api_key, settings.elevenlabs_voice_id) if settings.tts_backup_api_key else None
    if primary and backup:
        return FailoverTts(primary, backup)
    return primary


def analytics_client(settings: Settings, vault=None):
    token = _access_token(settings, vault)
    if token:
        return YouTubeAnalyticsClient(token)
    return None


def data_client(settings: Settings, vault=None):
    """Read/write YouTube Data API client for metadata updates and competitor research."""
    token = _access_token(settings, vault)
    if token:
        return GoogleYouTubeData(token)
    return None


def _access_token(settings: Settings, vault=None) -> str:
    token = settings.youtube_refresh_token
    if vault is not None:
        try:
            token = vault.get("youtube_access_token") or token
        except Exception:
            pass
    if token and settings.yt_client_id and settings.yt_client_secret:
        try:
            from youtube.oauth_flow import refresh_access_token

            refreshed = refresh_access_token(settings.yt_client_id, settings.yt_client_secret, token)
            token = refreshed.get("access_token") or token
            if vault is not None:
                vault.put("youtube_access_token", token)
        except Exception:
            pass
    return token if settings.yt_client_id else ""
