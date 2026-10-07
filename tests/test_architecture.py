from core.circuit import CircuitBreaker
from core.container import AppContainer, bootstrap
from core.context import bind_context, tenant_id
from core.db import make_engine
from fastapi.testclient import TestClient

from api.main import create_app


def test_circuit_opens_and_falls_back():
    breaker = CircuitBreaker("llm", failure_threshold=2, reset_after=60)
    def boom():
        raise RuntimeError("down")
    assert breaker.call(boom, fallback=lambda: "memory") == "memory"
    assert breaker.call(boom, fallback=lambda: "memory") == "memory"
    assert breaker.status == "open"
    assert breaker.call(lambda: "live", fallback=lambda: "memory") == "memory"


def test_tenant_context_is_isolated():
    assert tenant_id() == "local"
    with bind_context(tenant="acme"):
        assert tenant_id() == "acme"
    assert tenant_id() == "local"


def test_postgres_engine_uses_pool_pre_ping():
    engine = make_engine("postgresql+psycopg://engine:engine@localhost:5432/engine")
    assert engine.pool._pre_ping is True
    engine.dispose()


def test_container_and_health_scale_plane():
    client = TestClient(create_app())
    health = client.get("/health").json()
    assert "scale" in health
    assert health["scale"]["task_queue"]
    assert "circuits" in health["scale"]
    container = AppContainer.build()
    assert container.youtube is not None and container.acquisition is not None
    assert container.youtube.pipeline.store is container.youtube.store
    assert bootstrap().runtime is not None
