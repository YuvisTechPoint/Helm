"""Request-scoped tenant and correlation IDs. Safe across threads via ContextVar."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="local")
_engine: ContextVar[str] = ContextVar("engine", default="")


def request_id() -> str:
    return _request_id.get()


def tenant_id() -> str:
    return _tenant_id.get()


def current_engine() -> str:
    return _engine.get()


@contextmanager
def bind_context(*, tenant: str | None = None, request: str | None = None, engine: str | None = None):
    tokens = []
    if tenant is not None:
        tokens.append((_tenant_id, _tenant_id.set(tenant)))
    if request is not None:
        tokens.append((_request_id, _request_id.set(request)))
    if engine is not None:
        tokens.append((_engine, _engine.set(engine)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
