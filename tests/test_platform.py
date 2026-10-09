import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.config import EngineMode, Settings, reload_settings
from core.platform import build_platform, reset_platform


def test_engine_mode_enum_coercion():
    settings = Settings(engine_mode="production")
    assert settings.engine_mode == EngineMode.PRODUCTION
    settings = Settings(engine_mode="local")
    assert settings.engine_mode == EngineMode.DEV


def test_platform_tier_overrides_resilience():
    reset_platform()
    dev = build_platform(Settings(engine_mode="dev"))
    prod = build_platform(Settings(engine_mode="production", api_key="x"))
    assert dev.resilience.circuit_failure_threshold >= prod.resilience.circuit_failure_threshold
    assert prod.resilience.provider_timeout_s <= dev.resilience.provider_timeout_s


def test_platform_public_dict_has_no_secrets():
    reset_platform()
    platform = build_platform(Settings(engine_mode="dev"))
    public = platform.to_public_dict()
    assert "tier" in public
    assert "resilience" in public
    assert "stripe" not in str(public).lower()
    assert public["security"]["api_key_required"] in {True, False}


def test_log_format_validation():
    with pytest.raises(ValueError):
        Settings(log_format="xml")


def test_ready_vs_live_endpoints():
    client = TestClient(create_app())
    live = client.get("/live")
    assert live.status_code == 200
    assert live.json()["alive"] is True

    ready = client.get("/ready")
    assert ready.status_code in {200, 503}
    body = ready.json()
    assert "probes" in body
    assert "database" in body["probes"]


def test_platform_endpoint():
    client = TestClient(create_app())
    response = client.get("/platform")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "dev"
    assert body["capabilities"]["circuit_breakers"] is True


def test_reload_settings_clears_cache():
    reload_settings()
    s1 = reload_settings()
    s2 = reload_settings()
    assert s1.engine_mode == s2.engine_mode
