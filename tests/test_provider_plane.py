import pytest

from core.config import Settings
from core.errors import ConfigurationError, MissingCredentials
from core.provider_plane import manifest, validate_startup, with_circuit
from core.circuit import CircuitBreaker


def test_manifest_dev_marks_simulated_providers():
    settings = Settings(engine_mode="dev")
    m = manifest(settings)
    assert m["engine_mode"] == "dev"
    assert "youtube" in m["simulated"]
    assert m["production_ready"] is False


def test_manifest_production_lists_blockers():
    settings = Settings(engine_mode="production", api_key="secret")
    m = manifest(settings)
    assert m["blockers"]
    assert m["providers"]["youtube"] == "blocked"


def test_validate_startup_raises_in_production():
    settings = Settings(engine_mode="production", api_key="")
    with pytest.raises(ConfigurationError):
        validate_startup(settings)


def test_with_circuit_opens_after_failures():
    breaker = CircuitBreaker("test", failure_threshold=2)
    calls = {"n": 0}

    class Sender:
        def send(self):
            calls["n"] += 1
            raise RuntimeError("down")

    sender = Sender()
    with_circuit(sender, breaker, "send")
    with pytest.raises(RuntimeError):
        sender.send()
    with pytest.raises(RuntimeError):
        sender.send()
    from core.errors import ProviderUnavailable

    with pytest.raises(ProviderUnavailable):
        sender.send()
